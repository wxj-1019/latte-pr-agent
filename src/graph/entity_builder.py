import hashlib
import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from code_ast import TreeSitterParser
from code_ast.extractors import (
    CallExtractor,
    DecoratorExtractor,
    FunctionExtractor,
    InheritanceExtractor,
)
from models import CodeEntity, CodeRelationship, CodeEntityEmbedding

logger = logging.getLogger(__name__)


EXTENSION_TO_LANG = {
    ".py": "python",
    ".java": "java",
    ".go": "go",
    ".ts": "typescript",
    ".tsx": "typescript",
}

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".next", ".pytest_cache", "target"}


class EntityGraphBuilder:
    """扫描仓库，基于 AST 提取函数/类/接口等实体及调用、继承、装饰器关系。"""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def build(
        self,
        repo_path: str,
        repo_id: str,
        org_id: str = "default",
        force: bool = False,
    ) -> Dict[str, int]:
        """构建实体级知识图，返回统计信息 {"entities": N, "relationships": M}。"""
        if not force:
            existing = await self.session.execute(
                select(CodeEntity).where(
                    CodeEntity.repo_id == repo_id,
                    CodeEntity.org_id == org_id,
                ).limit(1)
            )
            if existing.scalar_one_or_none():
                return {"entities": 0, "relationships": 0, "skipped": True}

        repo_root = Path(repo_path).resolve()

        # Clear old data
        await self.session.execute(
            delete(CodeRelationship).where(
                CodeRelationship.repo_id == repo_id,
                CodeRelationship.org_id == org_id,
            )
        )
        await self.session.execute(
            delete(CodeEntity).where(
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
            )
        )

        # Phase 1: collect entities
        entity_records: List[CodeEntity] = []
        entity_key_map: Dict[Tuple[str, str, str], CodeEntity] = {}  # (file, type, name) -> entity

        for file_path in repo_root.rglob("*"):
            if any(part in SKIP_DIRS for part in file_path.parts):
                continue
            if not file_path.is_file():
                continue
            lang = EXTENSION_TO_LANG.get(file_path.suffix)
            if not lang:
                continue

            try:
                source = file_path.read_bytes()
            except Exception:
                continue

            parser = TreeSitterParser(lang)
            tree = parser.parse(source)
            if not tree:
                continue

            rel_file = str(file_path.relative_to(repo_root)).replace("\\", "/")
            root = tree.root_node

            func_ext = FunctionExtractor(lang)
            functions = func_ext.extract_functions(root)
            classes = func_ext.extract_classes(root)

            for fn in functions:
                key = (rel_file, "function", fn.name)
                if key in entity_key_map:
                    continue
                ent = CodeEntity(
                    org_id=org_id,
                    repo_id=repo_id,
                    file_path=rel_file,
                    entity_type="function",
                    name=fn.name,
                    signature=fn.signature,
                    start_line=fn.start_line,
                    end_line=fn.end_line,
                    meta_json={"return_type": fn.return_type},
                )
                entity_records.append(ent)
                entity_key_map[key] = ent

            for cls in classes:
                key = (rel_file, "class", cls.name)
                if key in entity_key_map:
                    continue
                ent = CodeEntity(
                    org_id=org_id,
                    repo_id=repo_id,
                    file_path=rel_file,
                    entity_type="class",
                    name=cls.name,
                    signature="",
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    meta_json={"bases": cls.bases},
                )
                entity_records.append(ent)
                entity_key_map[key] = ent

        if entity_records:
            self.session.add_all(entity_records)
            await self.session.flush()

        # Build lookup by ID after flush
        entity_id_map: Dict[Tuple[str, str, str], int] = {}
        for key, ent in entity_key_map.items():
            entity_id_map[key] = ent.id

        # Phase 2: collect relationships
        rel_records: List[CodeRelationship] = []

        for file_path in repo_root.rglob("*"):
            if any(part in SKIP_DIRS for part in file_path.parts):
                continue
            if not file_path.is_file():
                continue
            lang = EXTENSION_TO_LANG.get(file_path.suffix)
            if not lang:
                continue

            try:
                source = file_path.read_bytes()
            except Exception:
                continue

            parser = TreeSitterParser(lang)
            tree = parser.parse(source)
            if not tree:
                continue

            rel_file = str(file_path.relative_to(repo_root)).replace("\\", "/")
            root = tree.root_node

            local_funcs = [fn.name for fn in FunctionExtractor(lang).extract_functions(root)]
            local_classes = [cls.name for cls in FunctionExtractor(lang).extract_classes(root)]

            # Calls
            call_ext = CallExtractor(lang)
            for call in call_ext.extract(root, local_functions=local_funcs, local_classes=local_classes):
                src_key = self._resolve_caller_key(rel_file, call.caller_name, entity_id_map)
                if src_key is None:
                    continue
                src_id = entity_id_map[src_key]
                tgt_key = self._resolve_target_key(call.callee_name, entity_id_map, repo_root, rel_file, lang)
                tgt_id = entity_id_map.get(tgt_key) if tgt_key else None
                rel_records.append(CodeRelationship(
                    org_id=org_id,
                    repo_id=repo_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type="calls",
                    source_file=rel_file,
                    target_file=tgt_key[0] if tgt_key else None,
                    meta_json={"callee_name": call.callee_name, "line": call.start_line},
                ))

            # Inheritance
            inh_ext = InheritanceExtractor(lang)
            for inh in inh_ext.extract(root):
                src_key = (rel_file, "class", inh.class_name)
                if src_key not in entity_id_map:
                    continue
                src_id = entity_id_map[src_key]
                tgt_key = self._resolve_target_key(inh.base_name, entity_id_map, repo_root, rel_file, lang)
                tgt_id = entity_id_map.get(tgt_key) if tgt_key else None
                rel_records.append(CodeRelationship(
                    org_id=org_id,
                    repo_id=repo_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type="inherits",
                    source_file=rel_file,
                    target_file=tgt_key[0] if tgt_key else None,
                    meta_json={"base_name": inh.base_name, "line": inh.start_line},
                ))

            # Decorators
            dec_ext = DecoratorExtractor(lang)
            for dec in dec_ext.extract(root):
                target_type = "function" if dec.target_type == "function" else "class"
                src_key = (rel_file, target_type, dec.target_name)
                if src_key not in entity_id_map:
                    continue
                src_id = entity_id_map[src_key]
                tgt_key = self._resolve_target_key(dec.decorator_name, entity_id_map, repo_root, rel_file, lang)
                tgt_id = entity_id_map.get(tgt_key) if tgt_key else None
                rel_records.append(CodeRelationship(
                    org_id=org_id,
                    repo_id=repo_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type="decorates",
                    source_file=rel_file,
                    target_file=tgt_key[0] if tgt_key else None,
                    meta_json={"decorator_name": dec.decorator_name, "line": dec.start_line},
                ))

        if rel_records:
            self.session.add_all(rel_records)
            await self.session.flush()

        # Phase 3: generate embeddings for semantic search
        emb_count = await self._generate_embeddings(entity_records, repo_id, org_id)

        return {
            "entities": len(entity_records),
            "relationships": len(rel_records),
            "embeddings": emb_count,
            "skipped": False,
        }

    async def incremental_update(
        self,
        repo_path: str,
        repo_id: str,
        changed_files: List[str],
        org_id: str = "default",
    ) -> Dict[str, int]:
        """仅更新变更文件相关的实体和关系。"""
        if not changed_files:
            return {"entities": 0, "relationships": 0, "embeddings": 0}

        repo_root = Path(repo_path).resolve()

        # Step 1: Delete old entities, relationships, and embeddings for changed files
        old_entities_result = await self.session.execute(
            select(CodeEntity).where(
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
                CodeEntity.file_path.in_(changed_files),
            )
        )
        old_entities = old_entities_result.scalars().all()
        old_entity_ids = [e.id for e in old_entities]

        if old_entity_ids:
            await self.session.execute(
                delete(CodeRelationship).where(
                    CodeRelationship.repo_id == repo_id,
                    CodeRelationship.org_id == org_id,
                    (CodeRelationship.source_entity_id.in_(old_entity_ids))
                    | (CodeRelationship.target_entity_id.in_(old_entity_ids)),
                )
            )
            await self.session.execute(
                delete(CodeEntityEmbedding).where(
                    CodeEntityEmbedding.repo_id == repo_id,
                    CodeEntityEmbedding.org_id == org_id,
                    CodeEntityEmbedding.entity_id.in_(old_entity_ids),
                )
            )
            await self.session.execute(
                delete(CodeEntity).where(
                    CodeEntity.repo_id == repo_id,
                    CodeEntity.org_id == org_id,
                    CodeEntity.id.in_(old_entity_ids),
                )
            )
            await self.session.flush()

        # Step 2: Parse changed files and extract entities
        entity_records: List[CodeEntity] = []
        entity_key_map: Dict[Tuple[str, str, str], CodeEntity] = {}

        for rel_file in changed_files:
            file_path = repo_root / rel_file
            if not file_path.exists() or not file_path.is_file():
                continue
            if any(part in SKIP_DIRS for part in file_path.parts):
                continue
            lang = EXTENSION_TO_LANG.get(file_path.suffix)
            if not lang:
                continue

            try:
                source = file_path.read_bytes()
            except Exception:
                continue

            parser = TreeSitterParser(lang)
            tree = parser.parse(source)
            if not tree:
                continue

            root = tree.root_node
            func_ext = FunctionExtractor(lang)
            functions = func_ext.extract_functions(root)
            classes = func_ext.extract_classes(root)

            for fn in functions:
                key = (rel_file, "function", fn.name)
                if key in entity_key_map:
                    continue
                ent = CodeEntity(
                    org_id=org_id,
                    repo_id=repo_id,
                    file_path=rel_file,
                    entity_type="function",
                    name=fn.name,
                    signature=fn.signature,
                    start_line=fn.start_line,
                    end_line=fn.end_line,
                    meta_json={"return_type": fn.return_type},
                )
                entity_records.append(ent)
                entity_key_map[key] = ent

            for cls in classes:
                key = (rel_file, "class", cls.name)
                if key in entity_key_map:
                    continue
                ent = CodeEntity(
                    org_id=org_id,
                    repo_id=repo_id,
                    file_path=rel_file,
                    entity_type="class",
                    name=cls.name,
                    signature="",
                    start_line=cls.start_line,
                    end_line=cls.end_line,
                    meta_json={"bases": cls.bases},
                )
                entity_records.append(ent)
                entity_key_map[key] = ent

        if entity_records:
            self.session.add_all(entity_records)
            await self.session.flush()

        # Step 3: Load global entity_id_map from DB (existing + newly inserted)
        all_entities_result = await self.session.execute(
            select(CodeEntity).where(
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
            )
        )
        all_entities = all_entities_result.scalars().all()
        entity_id_map: Dict[Tuple[str, str, str], int] = {}
        for e in all_entities:
            entity_id_map[(e.file_path, e.entity_type, e.name)] = e.id

        # Step 4: Re-parse relationships for changed files only
        rel_records: List[CodeRelationship] = []

        for rel_file in changed_files:
            file_path = repo_root / rel_file
            if not file_path.exists() or not file_path.is_file():
                continue
            lang = EXTENSION_TO_LANG.get(file_path.suffix)
            if not lang:
                continue

            try:
                source = file_path.read_bytes()
            except Exception:
                continue

            parser = TreeSitterParser(lang)
            tree = parser.parse(source)
            if not tree:
                continue

            root = tree.root_node
            local_funcs = [fn.name for fn in FunctionExtractor(lang).extract_functions(root)]
            local_classes = [cls.name for cls in FunctionExtractor(lang).extract_classes(root)]

            # Calls
            for call in CallExtractor(lang).extract(root, local_functions=local_funcs, local_classes=local_classes):
                src_key = self._resolve_caller_key(rel_file, call.caller_name, entity_id_map)
                if src_key is None:
                    continue
                src_id = entity_id_map[src_key]
                tgt_key = self._resolve_target_key(call.callee_name, entity_id_map, repo_root, rel_file, lang)
                tgt_id = entity_id_map.get(tgt_key) if tgt_key else None
                rel_records.append(CodeRelationship(
                    org_id=org_id,
                    repo_id=repo_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type="calls",
                    source_file=rel_file,
                    target_file=tgt_key[0] if tgt_key else None,
                    meta_json={"callee_name": call.callee_name, "line": call.start_line},
                ))

            # Inheritance
            for inh in InheritanceExtractor(lang).extract(root):
                src_key = (rel_file, "class", inh.class_name)
                if src_key not in entity_id_map:
                    continue
                src_id = entity_id_map[src_key]
                tgt_key = self._resolve_target_key(inh.base_name, entity_id_map, repo_root, rel_file, lang)
                tgt_id = entity_id_map.get(tgt_key) if tgt_key else None
                rel_records.append(CodeRelationship(
                    org_id=org_id,
                    repo_id=repo_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type="inherits",
                    source_file=rel_file,
                    target_file=tgt_key[0] if tgt_key else None,
                    meta_json={"base_name": inh.base_name, "line": inh.start_line},
                ))

            # Decorators
            for dec in DecoratorExtractor(lang).extract(root):
                target_type = "function" if dec.target_type == "function" else "class"
                src_key = (rel_file, target_type, dec.target_name)
                if src_key not in entity_id_map:
                    continue
                src_id = entity_id_map[src_key]
                tgt_key = self._resolve_target_key(dec.decorator_name, entity_id_map, repo_root, rel_file, lang)
                tgt_id = entity_id_map.get(tgt_key) if tgt_key else None
                rel_records.append(CodeRelationship(
                    org_id=org_id,
                    repo_id=repo_id,
                    source_entity_id=src_id,
                    target_entity_id=tgt_id,
                    relation_type="decorates",
                    source_file=rel_file,
                    target_file=tgt_key[0] if tgt_key else None,
                    meta_json={"decorator_name": dec.decorator_name, "line": dec.start_line},
                ))

        if rel_records:
            self.session.add_all(rel_records)
            await self.session.flush()

        # Step 5: Generate embeddings for new/changed entities
        emb_count = await self._generate_embeddings(entity_records, repo_id, org_id)

        return {
            "entities": len(entity_records),
            "relationships": len(rel_records),
            "embeddings": emb_count,
            "deleted": len(old_entity_ids),
        }

    async def _generate_embeddings(
        self,
        entity_records: List[CodeEntity],
        repo_id: str,
        org_id: str,
    ) -> int:
        """为实体生成语义嵌入并写入 code_entity_embeddings。"""
        if not entity_records:
            return 0

        try:
            from rag.embedder import EmbeddingClient

            embedder = EmbeddingClient()
            texts = []
            for ent in entity_records:
                text = f"{ent.name} {ent.signature or ''} in {ent.file_path}"
                texts.append(text)

            embeddings = await embedder.embed_batch(texts)

            emb_records = []
            for ent, emb in zip(entity_records, embeddings):
                text = f"{ent.name} {ent.signature or ''} in {ent.file_path}"
                text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
                emb_records.append(CodeEntityEmbedding(
                    org_id=org_id,
                    repo_id=repo_id,
                    entity_id=ent.id,
                    embedding=emb,
                    text_hash=text_hash,
                ))

            if emb_records:
                self.session.add_all(emb_records)
                await self.session.flush()
            return len(emb_records)
        except Exception as exc:
            logger.warning("Entity embedding generation skipped: %s", exc)
            return 0

    @staticmethod
    def _resolve_caller_key(
        file_path: str,
        caller_name: str,
        entity_id_map: Dict[Tuple[str, str, str], int],
    ) -> Optional[Tuple[str, str, str]]:
        """将 caller_name 解析为实体键。"""
        if caller_name == "<module>":
            return None
        # Try function first, then class
        key = (file_path, "function", caller_name)
        if key in entity_id_map:
            return key
        key = (file_path, "class", caller_name)
        if key in entity_id_map:
            return key
        return None

    @staticmethod
    def _resolve_target_key(
        target_name: str,
        entity_id_map: Dict[Tuple[str, str, str], int],
        repo_root: Path,
        current_file: str,
        lang: str,
    ) -> Optional[Tuple[str, str, str]]:
        """尝试在全局实体映射中解析 target_name。"""
        if not target_name:
            return None
        # Simple name matching across all files (same type guessed as function)
        candidates = []
        for (file, etype, name), eid in entity_id_map.items():
            if name == target_name:
                candidates.append((file, etype, name))
        if len(candidates) == 1:
            return candidates[0]
        if len(candidates) > 1:
            # Prefer same file, then shortest path
            same_file = [c for c in candidates if c[0] == current_file]
            if same_file:
                return same_file[0]
            return min(candidates, key=lambda c: len(c[0]))
        # Try attribute-style: module.Class or module.function
        if "." in target_name:
            parts = target_name.split(".")
            # Last part as name
            last = parts[-1]
            for (file, etype, name), eid in entity_id_map.items():
                if name == last:
                    candidates.append((file, etype, name))
            if candidates:
                same_file = [c for c in candidates if c[0] == current_file]
                if same_file:
                    return same_file[0]
                return min(candidates, key=lambda c: len(c[0]))
        return None
