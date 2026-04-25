import asyncio
import logging
import time
from typing import Awaitable, Callable, Dict, List, Optional

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from commits.schemas import CommitInfo
from engine.cache import get_redis_client
from models.commit_analysis import CommitAnalysis
from models.commit_finding import CommitFinding
from models.project_repo import ProjectRepo

logger = logging.getLogger(__name__)

ProgressCallback = Optional[Callable[[str, int, int], Awaitable[None]]]


class CommitService:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_project(self, project_id: int) -> Optional[ProjectRepo]:
        result = await self.session.execute(select(ProjectRepo).where(ProjectRepo.id == project_id))
        return result.scalar_one_or_none()

    async def save_commits(
        self,
        project_id: int,
        commits: List[CommitInfo],
        progress_callback: ProgressCallback = None,
    ) -> int:
        t0 = time.monotonic()
        saved = 0
        skipped = 0
        total = len(commits)
        report_interval = max(1, total // 10) if total > 0 else 1

        for idx, ci in enumerate(commits):
            result = await self.session.execute(
                select(CommitAnalysis).where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.commit_hash == ci.hash,
                )
            )
            if result.scalar_one_or_none():
                skipped += 1
                continue

            ca = CommitAnalysis(
                project_id=project_id,
                commit_hash=ci.hash,
                parent_hash=ci.parent_hash or None,
                author_name=ci.author_name,
                author_email=ci.author_email,
                message=ci.message,
                commit_ts=ci.timestamp,
                additions=ci.additions,
                deletions=ci.deletions,
                changed_files=ci.changed_files,
                status="pending",
            )
            self.session.add(ca)
            saved += 1

            if progress_callback and (idx + 1) % report_interval == 0:
                await progress_callback("saving_commits", idx + 1, total)

        await self.session.commit()
        elapsed = time.monotonic() - t0
        logger.info(
            "Saved %d new commits for project %s (skipped %d duplicates, total %d, %.2fs)",
            saved, project_id, skipped, total, elapsed,
        )
        return saved

    async def list_commits(
        self, project_id: int, page: int = 1, page_size: int = 20, risk_level: Optional[str] = None
    ) -> dict:
        query = select(CommitAnalysis).where(CommitAnalysis.project_id == project_id)
        if risk_level:
            query = query.where(CommitAnalysis.risk_level == risk_level)
        query = query.order_by(CommitAnalysis.commit_ts.desc())

        count_q = select(func.count()).select_from(CommitAnalysis).where(CommitAnalysis.project_id == project_id)
        if risk_level:
            count_q = count_q.where(CommitAnalysis.risk_level == risk_level)
        total = (await self.session.execute(count_q)).scalar() or 0

        query = query.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        commits = list(result.scalars().all())
        return {"commits": commits, "total": total, "page": page, "page_size": page_size}

    async def get_commit(self, project_id: int, commit_hash: str) -> Optional[CommitAnalysis]:
        result = await self.session.execute(
            select(CommitAnalysis).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.commit_hash == commit_hash,
            )
        )
        return result.scalar_one_or_none()

    async def get_commit_findings(self, commit_analysis_id: int) -> List[CommitFinding]:
        result = await self.session.execute(
            select(CommitFinding).where(CommitFinding.commit_analysis_id == commit_analysis_id)
        )
        return list(result.scalars().all())

    async def get_project_findings(
        self, project_id: int, severity: Optional[str] = None, page: int = 1, page_size: int = 20
    ) -> dict:
        query = (
            select(CommitFinding, CommitAnalysis.commit_hash, CommitAnalysis.message.label("commit_message"))
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )
        if severity:
            query = query.where(CommitFinding.severity == severity)

        total = (await self.session.execute(
            select(func.count()).select_from(CommitFinding)
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )).scalar() or 0

        query = query.order_by(CommitFinding.created_at.desc()).offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(query)
        rows = result.all()
        findings = []
        for row in rows:
            finding = row[0]
            findings.append({
                "id": finding.id,
                "commit_hash": row[1],
                "commit_message": row[2],
                "file_path": finding.file_path,
                "line_number": finding.line_number,
                "severity": finding.severity,
                "category": finding.category,
                "description": finding.description,
                "suggestion": finding.suggestion,
                "confidence": finding.confidence,
            })
        return {"findings": findings, "total": total, "page": page}

    async def get_project_stats(self, project_id: int) -> dict:
        commits_total = (await self.session.execute(
            select(func.count()).where(CommitAnalysis.project_id == project_id)
        )).scalar() or 0

        analyzed = (await self.session.execute(
            select(func.count()).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.status == "completed",
            )
        )).scalar() or 0

        findings_total = (await self.session.execute(
            select(func.count())
            .select_from(CommitFinding)
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
        )).scalar() or 0

        sev_result = await self.session.execute(
            select(CommitFinding.severity, func.count())
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.severity)
        )
        severity_dist = {row[0]: row[1] for row in sev_result.all()}

        cat_result = await self.session.execute(
            select(CommitFinding.category, func.count())
            .join(CommitFinding.analysis)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.category)
        )
        category_dist = {row[0]: row[1] for row in cat_result.all()}

        # Risk level distribution from commits
        risk_result = await self.session.execute(
            select(CommitAnalysis.risk_level, func.count())
            .where(CommitAnalysis.project_id == project_id, CommitAnalysis.risk_level.isnot(None))
            .group_by(CommitAnalysis.risk_level)
        )
        risk_dist = {row[0]: row[1] for row in risk_result.all()}

        # Code changes stats
        changes_result = await self.session.execute(
            select(
                func.coalesce(func.sum(CommitAnalysis.additions), 0),
                func.coalesce(func.sum(CommitAnalysis.deletions), 0),
                func.coalesce(func.sum(CommitAnalysis.changed_files), 0),
            )
            .where(CommitAnalysis.project_id == project_id)
        )
        changes_row = changes_result.one_or_none()
        additions = int(changes_row[0]) if changes_row else 0
        deletions = int(changes_row[1]) if changes_row else 0
        files_changed = int(changes_row[2]) if changes_row else 0

        return {
            "total_commits": commits_total,
            "analyzed_commits": analyzed,
            "total_findings": findings_total,
            "severity_distribution": severity_dist,
            "category_distribution": category_dist,
            "risk_distribution": risk_dist,
            "code_changes": {
                "additions": additions,
                "deletions": deletions,
                "files": files_changed,
            },
        }

    async def get_contributor_analysis(self, project_id: int) -> dict:
        # Group by email only; use the most frequent name for display
        commit_rows = (await self.session.execute(
            select(
                CommitAnalysis.author_email,
                func.count(CommitAnalysis.id).label("commit_count"),
                func.sum(CommitAnalysis.additions).label("total_additions"),
                func.sum(CommitAnalysis.deletions).label("total_deletions"),
                func.sum(CommitAnalysis.changed_files).label("total_files"),
                func.max(CommitAnalysis.commit_ts).label("latest_commit"),
            )
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitAnalysis.author_email)
            .order_by(func.count(CommitAnalysis.id).desc())
        )).all()

        contributors = []
        for row in commit_rows:
            email, commits, adds, dels, files, latest = row
            # Pick the most frequent name for this email
            name_result = await self.session.execute(
                select(CommitAnalysis.author_name)
                .where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.author_email == email,
                )
                .group_by(CommitAnalysis.author_name)
                .order_by(func.count(CommitAnalysis.id).desc())
                .limit(1)
            )
            name = name_result.scalar_one_or_none() or "Unknown"

            sev_rows = (await self.session.execute(
                select(CommitFinding.severity, func.count())
                .join(CommitFinding.analysis)
                .where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.author_email == email,
                )
                .group_by(CommitFinding.severity)
            )).all()
            sev_map = {r[0]: r[1] for r in sev_rows}

            critical_count = sev_map.get("critical", 0)
            warning_count = sev_map.get("warning", 0)
            info_count = sev_map.get("info", 0)
            total_findings = critical_count + warning_count + info_count

            analyzed_commits = (await self.session.execute(
                select(func.count()).where(
                    CommitAnalysis.project_id == project_id,
                    CommitAnalysis.author_email == email,
                    CommitAnalysis.status == "completed",
                )
            )).scalar() or 0

            if analyzed_commits == 0:
                quality_score = None
                grade = None
                finding_density = None
            else:
                penalty = critical_count * 15 + warning_count * 5 + info_count * 1
                quality_score = max(0, 100 - penalty)
                grade = self._score_to_grade(quality_score)
                finding_density = round(total_findings / analyzed_commits, 2)

            contributors.append({
                "author_name": name,
                "author_email": email or "",
                "commit_count": commits,
                "analyzed_commits": analyzed_commits,
                "total_additions": int(adds or 0),
                "total_deletions": int(dels or 0),
                "total_files_changed": int(files or 0),
                "latest_commit": latest.isoformat() if latest else None,
                "findings": {
                    "critical": critical_count,
                    "warning": warning_count,
                    "info": info_count,
                    "total": total_findings,
                },
                "finding_density": finding_density,
                "quality_score": quality_score,
                "grade": grade,
            })

        return {"contributors": contributors, "total": len(contributors)}

    async def get_contributor_detail(self, project_id: int, author_email: str) -> dict:
        base_q = select(CommitAnalysis).where(
            CommitAnalysis.project_id == project_id,
            CommitAnalysis.author_email == author_email,
        ).order_by(CommitAnalysis.commit_ts.desc())

        total = (await self.session.execute(
            select(func.count()).select_from(CommitAnalysis).where(
                CommitAnalysis.project_id == project_id,
                CommitAnalysis.author_email == author_email,
            )
        )).scalar() or 0

        commits_result = await self.session.execute(base_q.limit(50))
        commits = list(commits_result.scalars().all())

        # Batch load findings to avoid N+1 queries
        commit_ids = [c.id for c in commits]
        findings_map: dict = {}
        if commit_ids:
            findings_result = await self.session.execute(
                select(CommitFinding).where(CommitFinding.commit_analysis_id.in_(commit_ids))
            )
            for f in findings_result.scalars().all():
                findings_map.setdefault(f.commit_analysis_id, []).append(f)

        commit_list = []
        for c in commits:
            findings = findings_map.get(c.id, [])
            commit_list.append({
                "commit_hash": c.commit_hash,
                "message": c.message,
                "commit_ts": c.commit_ts.isoformat() if c.commit_ts else None,
                "additions": c.additions,
                "deletions": c.deletions,
                "changed_files": c.changed_files,
                "risk_level": c.risk_level,
                "status": c.status,
                "findings_count": len(findings),
                "findings": [
                    {
                        "id": f.id,
                        "file_path": f.file_path,
                        "line_number": f.line_number,
                        "severity": f.severity,
                        "category": f.category,
                        "description": f.description,
                        "suggestion": f.suggestion,
                    }
                    for f in findings
                ],
            })

        return {"commits": commit_list, "total": total}

    async def get_knowledge_graph(self, project_id: int) -> dict:
        """返回项目文件依赖图的节点和边数据（支持文件级和模块级聚合）。"""
        from models import FileDependency

        # 获取所有文件依赖
        result = await self.session.execute(
            select(FileDependency)
            .where(FileDependency.repo_id == (
                select(ProjectRepo.repo_id).where(ProjectRepo.id == project_id).scalar_subquery()
            ))
        )
        deps = result.scalars().all()

        # 构建文件级节点和边
        file_nodes = set()
        file_edges = []
        module_edges_map = {}

        for d in deps:
            src = d.downstream_file
            tgt = d.upstream_file
            file_nodes.add(src)
            file_nodes.add(tgt)
            file_edges.append({"source": src, "target": tgt, "type": "imports"})

            # 模块级聚合（取第一级目录作为模块名）
            src_module = src.split("/")[0] if "/" in src else "root"
            tgt_module = tgt.split("/")[0] if "/" in tgt else "root"
            if src_module != tgt_module:
                key = (src_module, tgt_module)
                module_edges_map[key] = module_edges_map.get(key, 0) + 1

        module_nodes = sorted(set(m for pair in module_edges_map for m in pair))
        module_edges = [
            {"source": src, "target": tgt, "count": cnt}
            for (src, tgt), cnt in module_edges_map.items()
        ]

        return {
            "file_graph": {
                "nodes": [{"id": f, "group": f.split("/")[0] if "/" in f else "root"} for f in sorted(file_nodes)],
                "edges": file_edges,
            },
            "module_graph": {
                "nodes": [{"id": m, "group": m} for m in module_nodes],
                "edges": module_edges,
            },
        }

    async def build_entity_graph(self, project_id: int, force: bool = False) -> dict:
        """触发实体级知识图谱构建。"""
        from graph.entity_builder import EntityGraphBuilder

        project = await self.get_project(project_id)
        if not project or not project.local_path:
            raise ValueError("Project not found or not cloned")

        builder = EntityGraphBuilder(self.session)
        stats = await builder.build(
            repo_path=project.local_path,
            repo_id=project.repo_id,
            org_id=project.org_id or "default",
            force=force,
        )
        await self.session.commit()
        return stats

    async def get_entity_graph(self, project_id: int) -> dict:
        """获取实体级知识图谱数据（函数/类节点 + 调用/继承/装饰器边）。"""
        from models import CodeEntity, CodeRelationship

        project = await self.get_project(project_id)
        if not project:
            return {"nodes": [], "edges": []}

        repo_id = project.repo_id
        org_id = project.org_id or "default"

        entities_result = await self.session.execute(
            select(CodeEntity).where(
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
            )
        )
        entities = entities_result.scalars().all()

        rels_result = await self.session.execute(
            select(CodeRelationship).where(
                CodeRelationship.repo_id == repo_id,
                CodeRelationship.org_id == org_id,
            )
        )
        rels = rels_result.scalars().all()

        nodes = [
            {
                "id": str(e.id),
                "name": e.name,
                "type": e.entity_type,
                "file": e.file_path,
                "group": e.file_path.split("/")[0] if "/" in e.file_path else "root",
                "start_line": e.start_line,
                "end_line": e.end_line,
            }
            for e in entities
        ]

        edges = [
            {
                "source": str(r.source_entity_id),
                "target": str(r.target_entity_id) if r.target_entity_id else None,
                "type": r.relation_type,
                "source_file": r.source_file,
                "target_file": r.target_file,
            }
            for r in rels
        ]

        return {"nodes": nodes, "edges": edges}

    async def get_entity_neighbors(self, project_id: int, entity_id: int) -> dict:
        """获取指定实体的邻居（入边 + 出边）。"""
        from models import CodeEntity, CodeRelationship

        project = await self.get_project(project_id)
        if not project:
            return {"entity": None, "incoming": [], "outgoing": []}

        repo_id = project.repo_id
        org_id = project.org_id or "default"

        entity_result = await self.session.execute(
            select(CodeEntity).where(
                CodeEntity.id == entity_id,
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
            )
        )
        entity = entity_result.scalar_one_or_none()

        incoming_result = await self.session.execute(
            select(CodeRelationship, CodeEntity).join(
                CodeEntity, CodeEntity.id == CodeRelationship.source_entity_id
            ).where(
                CodeRelationship.target_entity_id == entity_id,
                CodeRelationship.repo_id == repo_id,
                CodeRelationship.org_id == org_id,
            )
        )
        incoming = []
        for rel, src_ent in incoming_result.all():
            incoming.append({
                "relation_id": rel.id,
                "relation_type": rel.relation_type,
                "source_entity": {
                    "id": src_ent.id,
                    "name": src_ent.name,
                    "type": src_ent.entity_type,
                    "file": src_ent.file_path,
                },
                "meta": rel.meta_json,
            })

        outgoing_result = await self.session.execute(
            select(CodeRelationship, CodeEntity).join(
                CodeEntity, CodeEntity.id == CodeRelationship.target_entity_id
            ).where(
                CodeRelationship.source_entity_id == entity_id,
                CodeRelationship.repo_id == repo_id,
                CodeRelationship.org_id == org_id,
            )
        )
        outgoing = []
        for rel, tgt_ent in outgoing_result.all():
            outgoing.append({
                "relation_id": rel.id,
                "relation_type": rel.relation_type,
                "target_entity": {
                    "id": tgt_ent.id,
                    "name": tgt_ent.name,
                    "type": tgt_ent.entity_type,
                    "file": tgt_ent.file_path,
                },
                "meta": rel.meta_json,
            })

        return {
            "entity": {
                "id": entity.id,
                "name": entity.name,
                "type": entity.entity_type,
                "file": entity.file_path,
                "signature": entity.signature,
                "start_line": entity.start_line,
                "end_line": entity.end_line,
                "meta": entity.meta_json,
            } if entity else None,
            "incoming": incoming,
            "outgoing": outgoing,
        }

    async def semantic_code_search(
        self,
        project_id: int,
        query: str,
        entity_type: Optional[str] = None,
        top_k: int = 10,
    ) -> List[Dict]:
        """语义搜索代码实体。"""
        from graph.semantic_search import SemanticCodeSearch

        project = await self.get_project(project_id)
        if not project:
            return []

        searcher = SemanticCodeSearch(self.session)
        return await searcher.search(
            repo_id=project.repo_id,
            query=query,
            entity_type=entity_type,
            top_k=top_k,
            org_id=project.org_id or "default",
        )

    async def graph_rag_retrieve(
        self,
        project_id: int,
        query: str,
        changed_files: Optional[List[str]] = None,
        depth: int = 2,
        top_k: int = 10,
    ) -> List[Dict]:
        """GraphRAG 检索：结合向量搜索 + 图遍历获取相关代码上下文。"""
        from graph.graph_rag import GraphRAGRetriever

        project = await self.get_project(project_id)
        if not project:
            return []

        retriever = GraphRAGRetriever(self.session)
        return await retriever.retrieve(
            repo_id=project.repo_id,
            query=query,
            changed_files=changed_files,
            depth=depth,
            top_k=top_k,
            org_id=project.org_id or "default",
        )

    async def get_code_complexity(self, project_id: int) -> Dict:
        """基于知识图谱计算代码复杂度指标。"""
        from models import CodeEntity, CodeRelationship
        from sqlalchemy import func

        project = await self.get_project(project_id)
        if not project:
            return {}

        repo_id = project.repo_id
        org_id = project.org_id or "default"

        # Total entities by type
        type_counts_result = await self.session.execute(
            select(CodeEntity.entity_type, func.count(CodeEntity.id))
            .where(CodeEntity.repo_id == repo_id, CodeEntity.org_id == org_id)
            .group_by(CodeEntity.entity_type)
        )
        type_counts = {row[0]: row[1] for row in type_counts_result.all()}
        total_entities = sum(type_counts.values())
        total_functions = type_counts.get("function", 0)
        total_classes = type_counts.get("class", 0)

        # God classes: classes with most incoming relationships
        god_class_result = await self.session.execute(
            select(CodeEntity.name, func.count(CodeRelationship.id))
            .join(CodeRelationship, CodeRelationship.target_entity_id == CodeEntity.id)
            .where(
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
                CodeEntity.entity_type == "class",
            )
            .group_by(CodeEntity.id)
            .order_by(func.count(CodeRelationship.id).desc())
            .limit(10)
        )
        god_classes = [{"name": row[0], "incoming": row[1]} for row in god_class_result.all()]
        god_class_count = sum(1 for g in god_classes if g["incoming"] >= 5)

        # Circular dependencies: A->B->A (simple 2-hop cycles)
        cycle_sql = """
            SELECT COUNT(*) FROM code_relationships a
            JOIN code_relationships b ON a.target_entity_id = b.source_entity_id
                AND b.target_entity_id = a.source_entity_id
            WHERE a.repo_id = :repo_id AND a.org_id = :org_id
              AND a.relation_type = 'calls' AND b.relation_type = 'calls'
              AND a.source_entity_id < b.source_entity_id
        """
        cycle_result = await self.session.execute(
            select(func.count()).select_from(CodeRelationship),
            {"repo_id": repo_id, "org_id": org_id},
        )
        # Actually use raw text for the join
        from sqlalchemy import text
        cycle_result = await self.session.execute(
            text(cycle_sql),
            {"repo_id": repo_id, "org_id": org_id},
        )
        cycle_count = cycle_result.scalar() or 0

        # Isolated functions: no incoming or outgoing calls
        isolated_result = await self.session.execute(
            select(func.count(CodeEntity.id))
            .where(
                CodeEntity.repo_id == repo_id,
                CodeEntity.org_id == org_id,
                CodeEntity.entity_type == "function",
            )
            .where(
                ~CodeEntity.id.in_(
                    select(CodeRelationship.source_entity_id)
                    .where(CodeRelationship.repo_id == repo_id, CodeRelationship.org_id == org_id)
                    .union(
                        select(CodeRelationship.target_entity_id)
                        .where(CodeRelationship.repo_id == repo_id, CodeRelationship.org_id == org_id)
                    )
                )
            )
        )
        isolated_count = isolated_result.scalar() or 0
        isolated_ratio = round(isolated_count / total_functions, 2) if total_functions > 0 else 0

        return {
            "total_entities": total_entities,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "god_class_count": god_class_count,
            "god_classes": god_classes[:5],
            "cycle_dependencies": cycle_count,
            "isolated_functions": isolated_count,
            "isolated_ratio": isolated_ratio,
        }

    async def get_architecture_mermaid(self, project_id: int, repo_path: str | None = None) -> str:
        """基于项目结构和代码上下文生成 Mermaid 架构图（使用 LLM）。

        返回 Mermaid 语法字符串，前端直接渲染。结果会缓存 1 天。
        """
        cache_key = f"architecture_mermaid:{project_id}"
        try:
            redis = await get_redis_client()
            cached = await redis.get(cache_key)
            if cached:
                return cached.decode("utf-8")
        except Exception as exc:
            logger.warning("Redis cache read failed for architecture mermaid: %s", exc)

        from llm import DeepSeekProvider
        from prompts.project_prompt_generator import ProjectPromptGenerator

        project = await self.get_project(project_id)
        if not project:
            return ""

        # 收集项目结构快照作为 LLM 输入
        generator = ProjectPromptGenerator(self.session)
        try:
            code_ctx = generator._scan_code_context(repo_path) if repo_path else {}
        except Exception:
            code_ctx = {}

        tree = code_ctx.get("directory_tree", [])
        api_patterns = code_ctx.get("api_patterns", [])
        config_summary = code_ctx.get("config_summary", {})

        context_parts = []
        if tree:
            context_parts.append("【项目目录结构】\n" + "\n".join(tree[:30]))
        if api_patterns:
            context_parts.append("【API / 模型模式】\n" + "\n".join(api_patterns[:10]))
        if config_summary:
            for fname, content in list(config_summary.items())[:2]:
                context_parts.append(f"【{fname}】\n{content}")

        context_text = "\n\n".join(context_parts) if context_parts else "项目暂无代码上下文数据。"

        system_prompt = (
            "你是一位软件架构专家。基于提供的项目结构信息，生成一个 Mermaid 语法的架构图。\n"
            "要求：\n"
            "1. 使用 graph TD（从上到下）或 graph LR（从左到右）布局\n"
            "2. 节点使用方框 [模块名] 或圆角框 (服务名)\n"
            "3. 区分层级：前端层 / API 网关 / 服务层 / 数据层 / 基础设施\n"
            "4. 标注关键技术（如 FastAPI、PostgreSQL、Redis、Next.js 等）\n"
            "5. 如果识别到微服务边界，用 subgraph 分组\n"
            "6. 只输出纯 Mermaid 语法，不要加 ``` 代码块标记\n"
            "7. 保持简洁，节点不超过 20 个"
        )
        user_prompt = f"请分析以下项目并生成架构图：\n\n{context_text}"

        mermaid = ""
        try:
            provider = DeepSeekProvider()
            mermaid = await provider.generate_text(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=2000,
            )
            if mermaid:
                mermaid = mermaid.strip()
                if mermaid.startswith("```"):
                    lines = mermaid.splitlines()
                    if lines[0].startswith("```"):
                        lines = lines[1:]
                    if lines and lines[-1].startswith("```"):
                        lines = lines[:-1]
                    mermaid = "\n".join(lines).strip()
        except Exception as exc:
            logger.warning("LLM architecture generation failed for project %s: %s", project_id, exc)

        if mermaid:
            try:
                redis = await get_redis_client()
                await redis.setex(cache_key, 86400, mermaid)
            except Exception as exc:
                logger.warning("Redis cache write failed for architecture mermaid: %s", exc)
            return mermaid

        # 回退：基于目录结构生成简单架构图
        fallback = self._fallback_architecture(tree, api_patterns)
        try:
            redis = await get_redis_client()
            await redis.setex(cache_key, 86400, fallback)
        except Exception as exc:
            logger.warning("Redis cache write failed for architecture mermaid fallback: %s", exc)
        return fallback

    @staticmethod
    def _fallback_architecture(tree: list, api_patterns: list) -> str:
        """当 LLM 不可用时，基于目录结构生成简单的 Mermaid 架构图。"""
        modules = set()
        for line in tree:
            clean = line.strip().rstrip("/")
            if clean and not clean.startswith(".") and "/" not in clean and clean not in {"node_modules", "__pycache__", ".venv", "dist", "build", ".next", "target"}:
                modules.add(clean)

        nodes = sorted(modules)[:12]
        if not nodes:
            return "graph TD\n    A[暂无架构数据]\n"

        lines = ["graph TD"]
        for i, mod in enumerate(nodes):
            lines.append(f"    {i}[{mod}]")
        # 简单连线：按顺序连接
        for i in range(len(nodes) - 1):
            lines.append(f"    {i} --> {i+1}")
        return "\n".join(lines)

    @staticmethod
    def _score_to_grade(score: int) -> str:
        if score >= 90:
            return "A"
        if score >= 75:
            return "B"
        if score >= 60:
            return "C"
        if score >= 40:
            return "D"
        return "F"
