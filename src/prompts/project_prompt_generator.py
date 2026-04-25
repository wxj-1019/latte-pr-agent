import hashlib
import json
import logging
import os
import re
from typing import Dict, List, Optional, Tuple

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from prompts.registry import PromptRegistry
from llm import DeepSeekProvider
from models.commit_finding import CommitFinding
from models.commit_analysis import CommitAnalysis
from models.prompt_experiment import PromptExperiment
from models.code_entity import CodeEntity
from models.code_relationship import CodeRelationship

logger = logging.getLogger(__name__)

# 更优质的默认 Prompt，包含结构化检查清单
DEFAULT_COMMIT_ANALYSIS_PROMPT = (
    "你是一位资深的代码审查专家。请分析提供的代码变更（diff），并以 JSON 对象格式返回发现的问题列表。\n\n"
    "【审查检查清单】\n"
    "1. 功能完整性：变更是否完整实现了预期功能，是否遗漏场景、分支或边界条件。\n"
    "2. 逻辑正确性：条件分支、循环终止、状态流转、异常处理路径是否正确。\n"
    "3. 回归风险：修改是否可能破坏现有功能，是否存在对外部接口/数据结构的破坏性变更。\n"
    "4. 数据一致性：事务、并发、持久化操作中的数据完整性是否得到保障。\n"
    "5. 代码质量：是否存在重复代码、命名不清晰、过度复杂等问题。\n\n"
    "要求的 JSON 格式：\n"
    '{"issues": [{"file": "path/to/file", "line": 42, "severity": "critical|warning|info", '
    '"category": "security|logic|performance|architecture|style", "description": "问题描述", '
    '"suggestion": "修复建议", "confidence": 0.95, "evidence": "代码片段", "reasoning": "原因"}], '
    '"summary": "总结", "risk_level": "low|medium|high"}\n\n'
    "请保持简洁和准确。如果没有发现问题，返回空的 issues 数组。"
)

REFINER_SYSTEM_PROMPT = """你是一位 Prompt Engineering 专家。你的任务是基于给定的结构化 Prompt 模板和项目特征，对其进行润色和增强。

要求：
1. 保持原有的 JSON 输出格式要求和检查清单结构不变。
2. 将项目特征自然地融入检查清单的每一项中（如技术栈特定风险、关键路径提示）。
3. 保持中文输出，语言简洁、专业、可执行。
4. 不要删减原有的核心检查项，只能补充或细化。
5. 直接返回润色后的 Prompt 文本，不要加 Markdown 代码块包装。"""


class ProjectPromptGenerator:
    """基于项目特征自动生成并持续进化专属 Commit 分析 Prompt。

    核心机制：
    1. 特征指纹（Feature Fingerprint）：每次生成时计算项目特征的哈希指纹并持久化。
    2. 自适应进化：当项目技术栈、配置、历史问题分布、Commit 类型发生显著变化时，
       自动触发重新生成新版本 Prompt，而不是一成不变。
    3. 阈值控制：支持多级变化检测（技术栈变化强制重生、历史问题变化条件重生等）。
    """

    # 进化阈值常量
    EVOLVE_MIN_NEW_FINDINGS = 10          # 新增 findings 超过此值才考虑进化
    EVOLVE_COMMIT_TYPE_SHIFT_PCT = 0.3    # commit 类型占比变化超过 30% 视为显著偏移
    EVOLVE_TOP_RISK_CHANGE = True         # Top 风险类别发生变化时触发进化

    def __init__(self, session: AsyncSession, provider: Optional[DeepSeekProvider] = None):
        self.session = session
        self.provider = provider or DeepSeekProvider()
        self.registry = PromptRegistry(session)

    async def generate(self, project, force: bool = False) -> Optional[str]:
        """为指定项目生成并保存专属 Prompt，支持自适应进化。

        Args:
            project: ProjectRepo 实例
            force: 是否强制重新生成，忽略指纹比对

        Returns:
            version 字符串，或 None（跳过生成时返回现有版本）
        """
        repo_path = project.local_path
        repo_id = project.repo_id
        project_id = project.id

        if not repo_path or not os.path.isdir(repo_path):
            logger.warning("Project %s has no valid local path, skipping prompt generation", project_id)
            return None

        # 1. 采集当前项目全貌特征
        features = await self._collect_all_features(project)

        # 2. 计算当前特征指纹
        current_fingerprint = self._compute_fingerprint(features)

        # 3. 获取上一次生成的项目 Prompt 及其指纹
        last_prompt, last_metadata = await self._get_last_project_prompt(repo_id)

        # 4. 自适应进化判断
        if not force and last_prompt is not None:
            should_evolve, evolve_reason = self._should_evolve(
                current_fingerprint, last_metadata, features
            )
            if not should_evolve:
                logger.info(
                    "Project %s prompt fingerprint unchanged (%s), skipping generation",
                    project_id, current_fingerprint[:8]
                )
                # 返回现有最新版本号
                return last_metadata.get("version") if last_metadata else None
            logger.info(
                "Project %s prompt evolved: %s", project_id, evolve_reason
            )

        # 5. 构建结构化基础 Prompt
        base_prompt = self._build_structured_prompt(
            features["static"], features["config"], features["historical"], features.get("graph", {})
        )

        # 6. 可选：用 LLM 润色增强
        try:
            prompt_text = await self._refine_prompt_with_llm(
                base_prompt, features["static"], features["config"], features["historical"]
            )
        except Exception as exc:
            logger.warning("LLM prompt refinement failed for %s: %s, using structured base prompt", project_id, exc)
            prompt_text = base_prompt

        # 7. 保存新版本
        version = await self._next_version(project_id, repo_id)
        metadata = {
            "generated_for": "commit_analysis",
            "project_id": project_id,
            "repo_id": repo_id,
            "version": version,
            "feature_fingerprint": current_fingerprint,
            "generation_mode": "structured+llm_refinement" if prompt_text != base_prompt else "structured_fallback",
            "focus_areas": ["logic", "functionality", "regression_risk", "data_consistency"],
            "graph": features.get("graph", {}),
            **features["static"],
            **features["config"],
            **features["historical"],
        }

        await self.registry.save_version(version, prompt_text, metadata, repo_id=repo_id)
        logger.info(
            "Generated project prompt for %s: version=%s fingerprint=%s length=%d",
            project_id, version, current_fingerprint[:8], len(prompt_text)
        )
        return version

    # ------------------------------------------------------------------
    # 特征采集与指纹
    # ------------------------------------------------------------------

    async def _collect_all_features(self, project) -> Dict:
        """采集项目的完整特征（静态 + 配置 + 历史）。"""
        repo_path = project.local_path
        features = {
            "static": {},
            "config": {},
            "historical": {},
        }

        try:
            features["static"] = self._collect_project_features(repo_path)
        except Exception as exc:
            logger.warning("Failed to collect static features: %s", exc)

        try:
            features["config"] = self._collect_project_config(project)
        except Exception as exc:
            logger.warning("Failed to collect project config: %s", exc)

        try:
            features["historical"] = await self._collect_historical_findings(project.id)
        except Exception as exc:
            logger.warning("Failed to collect historical findings: %s", exc)

        try:
            features["graph"] = await self._collect_graph_features(
                project.repo_id, getattr(project, "org_id", "default")
            )
        except Exception as exc:
            logger.warning("Failed to collect graph features: %s", exc)
            features["graph"] = {}

        return features

    def _compute_fingerprint(self, features: Dict) -> str:
        """计算项目特征指纹，用于判断是否需要进化。"""
        static = features.get("static", {})
        config = features.get("config", {})
        historical = features.get("historical", {})

        # 提取对 Prompt 内容有实质影响的关键特征
        commit_patterns = static.get("commit_patterns", {})
        total_commits = sum(commit_patterns.values()) or 1
        commit_type_dist = {
            k: round(v / total_commits, 2)
            for k, v in commit_patterns.items()
        }

        hist_cats = historical.get("historical_categories", {})
        top_3_cats = [
            {"cat": k, "cnt": v}
            for k, v in sorted(hist_cats.items(), key=lambda x: -x[1])[:3]
        ]

        # code_context 关键特征（使用顶层目录结构，避免单个文件变化导致指纹抖动）
        code_ctx = static.get("code_context", {}) or {}
        api_patterns_sig = sorted(set(code_ctx.get("api_patterns", [])))[:8]
        sample_files_sig = sorted(s["file"] for s in code_ctx.get("code_samples", []))[:6]
        style_sig = f"{code_ctx.get('import_style') or ''}|{code_ctx.get('naming_convention') or ''}"
        # tree 只取顶层目录名（不含文件），稳定且能反映架构变化
        tree_lines = code_ctx.get("directory_tree", [])
        tree_sig = sorted(
            line.strip().rstrip("/")
            for line in tree_lines[:20]
            if line.strip() and not line.strip().startswith(".") and line.strip().endswith("/")
        )[:10]

        graph = features.get("graph", {})
        graph_sig = {
            "entity_types": sorted(graph.get("entity_type_counts", {}).keys()),
            "relation_types": sorted(graph.get("relation_type_counts", {}).keys()),
            "top_entity": graph.get("top_entities", [{}])[0].get("name", "") if graph.get("top_entities") else "",
            "layer_count": len(graph.get("architecture_layers", {})),
        }

        fingerprint_data = {
            "language": static.get("dominant_language"),
            "framework": static.get("framework"),
            "key_paths": sorted(static.get("key_paths", [])),
            "commit_type_dist": commit_type_dist,
            "critical_paths": sorted(config.get("critical_paths", [])),
            "custom_rules_count": len(config.get("custom_rules", [])),
            "top_3_cats": top_3_cats,
            "api_patterns": api_patterns_sig,
            "sample_files": sample_files_sig,
            "style": style_sig,
            "tree_head": tree_sig,
            "graph": graph_sig,
        }

        raw = json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    async def _get_last_project_prompt(self, repo_id: str) -> Tuple[Optional[str], Optional[Dict]]:
        """获取该项目最新的专属 Prompt 文本及其 metadata。"""
        try:
            from sqlalchemy import desc
            result = await self.session.execute(
                select(PromptExperiment)
                .where(PromptExperiment.repo_id == repo_id)
                .order_by(desc(PromptExperiment.created_at))
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                return row.prompt_text, row.metadata_json or {}
        except Exception:
            logger.exception("Failed to get last project prompt for %s", repo_id)
            await self.session.rollback()
        return None, None

    def _should_evolve(
        self,
        current_fingerprint: str,
        last_metadata: Optional[Dict],
        current_features: Dict,
    ) -> Tuple[bool, str]:
        """判断是否需要进化 Prompt。返回 (should_evolve, reason)。"""
        if last_metadata is None:
            return True, "首次生成"

        last_fingerprint = last_metadata.get("feature_fingerprint", "")
        if current_fingerprint == last_fingerprint:
            return False, "指纹未变化"

        # 指纹不同，进一步分析变化类型和幅度
        reasons: List[str] = []

        # 1. 技术栈变化（强制进化）
        last_lang = last_metadata.get("dominant_language")
        last_fw = last_metadata.get("framework")
        curr_lang = current_features["static"].get("dominant_language")
        curr_fw = current_features["static"].get("framework")
        if last_lang != curr_lang or last_fw != curr_fw:
            reasons.append(f"技术栈变化: {last_lang}/{last_fw} -> {curr_lang}/{curr_fw}")

        # 2. 项目配置变化
        last_critical = set(last_metadata.get("critical_paths", []))
        curr_critical = set(current_features["config"].get("critical_paths", []))
        if last_critical != curr_critical:
            reasons.append("关键路径配置变化")

        last_rules_count = len(last_metadata.get("custom_rules", []))
        curr_rules_count = len(current_features["config"].get("custom_rules", []))
        if last_rules_count != curr_rules_count:
            reasons.append(f"自定义规则数量变化: {last_rules_count} -> {curr_rules_count}")

        # 3. Commit 类型显著偏移
        last_patterns = last_metadata.get("commit_patterns", {})
        curr_patterns = current_features["static"].get("commit_patterns", {})
        last_total = sum(last_patterns.values()) or 1
        curr_total = sum(curr_patterns.values()) or 1
        for ctype in ("feat", "fix", "refactor", "test"):
            last_pct = last_patterns.get(ctype, 0) / last_total
            curr_pct = curr_patterns.get(ctype, 0) / curr_total
            if abs(last_pct - curr_pct) >= self.EVOLVE_COMMIT_TYPE_SHIFT_PCT:
                reasons.append(f"Commit 类型 '{ctype}' 占比显著偏移: {last_pct:.0%} -> {curr_pct:.0%}")

        # 4. 历史问题 Top 风险类别变化
        if self.EVOLVE_TOP_RISK_CHANGE:
            last_top = last_metadata.get("top_risk_category", "")
            curr_top = current_features["historical"].get("top_risk_category", "")
            if last_top != curr_top:
                reasons.append(f"Top 风险类别变化: {last_top or '无'} -> {curr_top or '无'}")

        # 5. 新增 findings 数量达到阈值
        last_total_findings = last_metadata.get("total_findings", 0)
        curr_total_findings = current_features["historical"].get("total_findings", 0)
        new_findings = curr_total_findings - last_total_findings
        if new_findings >= self.EVOLVE_MIN_NEW_FINDINGS:
            reasons.append(f"新增 findings 达到阈值: +{new_findings}")

        # 6. 知识图谱架构变化
        last_graph = last_metadata.get("graph", {})
        curr_graph = current_features.get("graph", {})
        last_entity_types = set(last_graph.get("entity_type_counts", {}).keys())
        curr_entity_types = set(curr_graph.get("entity_type_counts", {}).keys())
        if last_entity_types != curr_entity_types:
            reasons.append("实体类型分布变化")
        last_layers = set(last_graph.get("architecture_layers", {}).keys())
        curr_layers = set(curr_graph.get("architecture_layers", {}).keys())
        if last_layers != curr_layers:
            reasons.append("架构分层变化")
        last_god = len(last_graph.get("god_class_candidates", []))
        curr_god = len(curr_graph.get("god_class_candidates", []))
        if last_god != curr_god:
            reasons.append(f"God Class 数量变化: {last_god} -> {curr_god}")

        if reasons:
            return True, "; ".join(reasons)

        # 指纹不同但以上阈值均未触发——可能是无关特征抖动（如 docs/chore 比例微变），跳过
        return False, "指纹不同但关键特征未达进化阈值"

    # ------------------------------------------------------------------
    # 静态特征采集
    # ------------------------------------------------------------------

    def _collect_project_features(self, repo_path: str) -> Dict:
        """采集项目静态特征：commit 模式、语言、框架、目录结构。"""
        features: Dict = {"commit_patterns": {}, "tech_stack": {}, "key_paths": []}

        # 1. Commit 模式统计
        try:
            import subprocess

            result = subprocess.run(
                ["git", "-C", repo_path, "log", "-30", "--format=%s"],
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
            )
            messages = [line.strip() for line in result.stdout.splitlines() if line.strip()]
            patterns = {"feat": 0, "fix": 0, "bugfix": 0, "refactor": 0, "test": 0, "docs": 0, "chore": 0, "other": 0}
            for msg in messages:
                lower = msg.lower()
                matched = False
                for key in patterns:
                    if key != "other" and (lower.startswith(key) or f"{key}:" in lower or f"{key}(" in lower):
                        patterns[key] += 1
                        matched = True
                        break
                if not matched:
                    patterns["other"] += 1
            features["commit_patterns"] = patterns
            features["recent_commit_count"] = len(messages)
            dominant_type = max(patterns, key=patterns.get)
            features["dominant_commit_type"] = dominant_type if patterns[dominant_type] > 0 else "mixed"
        except Exception as exc:
            logger.warning("Failed to analyze git log for %s: %s", repo_path, exc)

        # 2. 技术栈识别（语言 + 框架）
        try:
            stack = self._detect_tech_stack(repo_path)
            features["tech_stack"] = stack
            features["dominant_language"] = stack.get("language", "unknown")
            features["framework"] = stack.get("framework", "unknown")
            features["key_paths"] = stack.get("key_paths", [])
        except Exception as exc:
            logger.warning("Failed to detect tech stack for %s: %s", repo_path, exc)
            features["dominant_language"] = "unknown"
            features["framework"] = "unknown"
            features["key_paths"] = []

        # 3. 代码内容上下文扫描
        try:
            features["code_context"] = self._scan_code_context(repo_path)
        except Exception as exc:
            logger.warning("Failed to scan code context for %s: %s", repo_path, exc)
            features["code_context"] = {}

        return features

    def _detect_tech_stack(self, repo_path: str) -> Dict:
        """识别项目技术栈：语言、框架、构建工具、关键目录。"""
        stack = {"language": "unknown", "framework": "unknown", "build_tool": "unknown", "key_paths": []}
        lang_hints: Dict[str, int] = {}
        framework_hints: Dict[str, int] = {}
        key_paths: List[str] = []

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "__pycache__", ".venv", "venv", "target", "build", "dist", ".idea", ".vscode"}]
            rel_root = os.path.relpath(root, repo_path)
            if rel_root == ".":
                rel_root = ""

            for name in dirs:
                if name in ("src", "lib", "app", "api", "tests", "test", "scripts", "cmd", "pkg", "internal", "core", "handlers", "controllers", "services", "models", "db", "middleware"):
                    key_paths.append(name)

            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in (".py", ".js", ".jsx", ".ts", ".tsx", ".java", ".go", ".rs", ".cpp", ".c", ".h", ".rb", ".php", ".swift", ".kt"):
                    lang_hints[ext] = lang_hints.get(ext, 0) + 1

                if f == "requirements.txt" or f == "pyproject.toml" or f == "setup.py":
                    stack["build_tool"] = "pip/setuptools"
                    framework_hints.update(self._scan_python_framework(os.path.join(root, f)))
                elif f == "package.json":
                    stack["build_tool"] = "npm/yarn/pnpm"
                    framework_hints.update(self._scan_node_framework(os.path.join(root, f)))
                elif f == "pom.xml":
                    stack["build_tool"] = "Maven"
                    framework_hints["Spring"] = framework_hints.get("Spring", 0) + 1
                elif f == "build.gradle" or f == "build.gradle.kts":
                    stack["build_tool"] = "Gradle"
                    framework_hints["Spring"] = framework_hints.get("Spring", 0) + 1
                elif f == "go.mod":
                    stack["build_tool"] = "Go Modules"
                    framework_hints.update(self._scan_go_framework(os.path.join(root, f)))
                elif f == "Cargo.toml":
                    stack["build_tool"] = "Cargo"
                elif f == "Dockerfile" or f == "docker-compose.yml":
                    stack["has_docker"] = True

        if lang_hints:
            dominant_ext = max(lang_hints, key=lang_hints.get)
            lang_map = {
                ".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript",
                ".ts": "TypeScript", ".tsx": "TypeScript",
                ".java": "Java", ".go": "Go", ".rs": "Rust",
                ".cpp": "C++", ".c": "C", ".h": "C/C++",
                ".rb": "Ruby", ".php": "PHP", ".swift": "Swift", ".kt": "Kotlin",
            }
            stack["language"] = lang_map.get(dominant_ext, dominant_ext)

        if framework_hints:
            stack["framework"] = max(framework_hints, key=framework_hints.get)

        stack["key_paths"] = sorted(set(key_paths))[:12]
        return stack

    def _scan_python_framework(self, file_path: str) -> Dict[str, int]:
        hints: Dict[str, int] = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
            if "fastapi" in content:
                hints["FastAPI"] = 3
            if "django" in content:
                hints["Django"] = 3
            if "flask" in content:
                hints["Flask"] = 2
            if "sqlalchemy" in content or "alembic" in content:
                hints["SQLAlchemy"] = 2
            if "pytest" in content or "unittest" in content:
                hints["pytest"] = 1
        except Exception:
            pass
        return hints

    def _scan_node_framework(self, file_path: str) -> Dict[str, int]:
        hints: Dict[str, int] = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
            if "next" in content:
                hints["Next.js"] = 4
            if "react" in content:
                hints["React"] = 3
            if "vue" in content:
                hints["Vue"] = 3
            if "express" in content:
                hints["Express"] = 2
            if "nestjs" in content:
                hints["NestJS"] = 2
            if "typescript" in content:
                hints["TypeScript"] = 1
        except Exception:
            pass
        return hints

    def _scan_go_framework(self, file_path: str) -> Dict[str, int]:
        hints: Dict[str, int] = {}
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                content = f.read().lower()
            if "gin" in content:
                hints["Gin"] = 3
            if "echo" in content:
                hints["Echo"] = 2
            if "fiber" in content:
                hints["Fiber"] = 2
            if "gorm" in content:
                hints["GORM"] = 2
        except Exception:
            pass
        return hints

    # ------------------------------------------------------------------
    # 代码内容上下文扫描
    # ------------------------------------------------------------------

    def _scan_code_context(self, repo_path: str) -> Dict:
        """扫描项目实际代码内容，提取架构上下文、代码风格、API 模式等。"""
        context: Dict = {
            "directory_tree": [],
            "config_summary": {},
            "code_samples": [],
            "api_patterns": [],
            "import_style": None,
            "naming_convention": None,
        }

        EXCLUDE_DIRS = {
            ".git", "node_modules", "__pycache__", ".venv", "venv",
            "target", "build", "dist", ".next", ".idea", ".vscode",
            ".pytest_cache", ".ruff_cache", ".mypy_cache", "coverage",
            "out", ".turbo", ".nx", ".parcel-cache", ".gradle",
        }
        EXCLUDE_EXTS = {
            ".lock", ".log", ".ico", ".png", ".jpg", ".jpeg", ".gif",
            ".svg", ".woff", ".woff2", ".ttf", ".eot", ".mp3", ".mp4",
            ".zip", ".tar", ".gz", ".7z", ".exe", ".dll", ".so", ".dylib",
            ".pyc", ".pyo", ".class", ".o", ".obj", ".min.js", ".min.css",
        }

        # 1. 目录树快照（最大深度 4）
        tree_lines: List[str] = []
        for root, dirs, files in os.walk(repo_path):
            depth = root[len(repo_path):].count(os.sep)
            if depth >= 4:
                del dirs[:]
                continue
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            rel_root = os.path.relpath(root, repo_path)
            indent = "  " * depth
            dir_name = os.path.basename(root) or "."
            meaningful = [
                f for f in files
                if not f.startswith(".")
                and os.path.splitext(f)[1].lower() not in EXCLUDE_EXTS
            ]
            if depth == 0:
                tree_lines.append(f"{dir_name}/")
            else:
                tree_lines.append(f"{indent}{dir_name}/")
            for f in sorted(meaningful)[:5]:
                tree_lines.append(f"{indent}  {f}")
            if len(tree_lines) >= 100:
                del dirs[:]
                break
        context["directory_tree"] = tree_lines[:100]

        # 2. 关键配置文件内容摘要
        config_files = [
            ("pyproject.toml", 25),
            ("requirements.txt", 20),
            ("package.json", 25),
            ("tsconfig.json", 20),
            ("next.config.js", 15),
            ("next.config.ts", 15),
            ("tailwind.config.js", 15),
            ("tailwind.config.ts", 15),
            ("Dockerfile", 15),
            ("docker-compose.yml", 15),
            (".review-config.yml", 15),
            ("go.mod", 15),
            ("Cargo.toml", 15),
            ("pom.xml", 15),
            ("build.gradle", 15),
        ]
        for fname, max_lines in config_files:
            content = self._read_file_head(os.path.join(repo_path, fname), max_lines)
            if content:
                context["config_summary"][fname] = content

        # 3. 入口文件和代表性代码片段
        entry_patterns = {
            "main.py", "app.py", "manage.py", "wsgi.py", "asgi.py",
            "index.js", "index.ts", "index.tsx", "main.js", "main.ts",
            "server.ts", "server.js", "app.ts", "app.tsx",
            "App.tsx", "App.vue", "app.vue",
        }
        samples: List[Dict] = []
        found_entries: set[str] = set()

        for root, dirs, files in os.walk(repo_path):
            dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
            rel_root = os.path.relpath(root, repo_path)
            for f in files:
                ext = os.path.splitext(f)[1].lower()
                if ext in EXCLUDE_EXTS:
                    continue
                fpath = os.path.join(root, f)
                try:
                    size = os.path.getsize(fpath)
                    if size > 200 * 1024:
                        continue
                except OSError:
                    continue
                rel_file = os.path.join(rel_root, f) if rel_root != "." else f

                if f in entry_patterns:
                    content = self._read_file_head(fpath, 35)
                    if content:
                        samples.append({"file": rel_file, "role": "entry", "content": content})
                        found_entries.add(f)

                # API 模式扫描（轻量：只读前 30 行）
                if ext in (".py", ".js", ".ts", ".tsx", ".java", ".go", ".rs"):
                    self._scan_api_patterns(fpath, rel_file, ext, context)

        # 补充代表性样本（关键目录）
        if len(samples) < 4:
            sample_dirs = {"src", "app", "lib", "api", "routes", "controllers", "services", "models", "handlers", "pages", "internal", "pkg", "cmd"}
            for root, dirs, files in os.walk(repo_path):
                dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS and not d.startswith(".")]
                rel_root = os.path.relpath(root, repo_path)
                parts = rel_root.split(os.sep)
                if not any(p in sample_dirs for p in parts):
                    continue
                for f in sorted(files):
                    ext = os.path.splitext(f)[1].lower()
                    if ext not in (".py", ".js", ".ts", ".tsx", ".go", ".java", ".rs"):
                        continue
                    rel_file = os.path.join(rel_root, f) if rel_root != "." else f
                    if any(s["file"] == rel_file for s in samples):
                        continue
                    fpath = os.path.join(root, f)
                    try:
                        if os.path.getsize(fpath) > 100 * 1024:
                            continue
                    except OSError:
                        continue
                    content = self._read_file_head(fpath, 25)
                    if content:
                        samples.append({"file": rel_file, "role": "sample", "content": content})
                        break
                if len(samples) >= 8:
                    break

        context["code_samples"] = samples[:8]
        context["api_patterns"] = list(dict.fromkeys(context["api_patterns"]))[:10]
        self._detect_code_style(context)
        return context

    def _read_file_head(self, file_path: str, max_lines: int = 30) -> Optional[str]:
        """安全读取文件头部若干行。"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = []
                for _ in range(max_lines):
                    line = f.readline()
                    if not line:
                        break
                    # 过滤掉过长的行（如 minified）
                    if len(line) > 500:
                        line = line[:500] + "...\n"
                    lines.append(line)
                return "".join(lines).rstrip()
        except Exception:
            return None

    def _scan_api_patterns(self, file_path: str, rel_file: str, ext: str, context: Dict) -> None:
        """轻量扫描代码文件，识别 API/路由/模型模式。"""
        try:
            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                head = f.read(8000)  # 只读前 8KB
        except Exception:
            return

        patterns = context.setdefault("api_patterns", [])

        if ext == ".py":
            # FastAPI / Flask / Django 路由
            route_matches = re.findall(r"@(app|router|blueprint)\.\s*(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", head, re.I)
            for m in route_matches:
                patterns.append(f"{rel_file}: {m[1].upper()} {m[2]}")
            # Pydantic / Django ORM 模型
            if re.search(r"class\s+\w+\s*\(\s*BaseModel\s*\)", head):
                patterns.append(f"{rel_file}: Pydantic BaseModel")
            if re.search(r"class\s+\w+\s*\(\s*models\.Model\s*\)", head):
                patterns.append(f"{rel_file}: Django ORM Model")
            # SQLAlchemy
            if re.search(r"class\s+\w+\s*\([^)]*DeclarativeBase|Base\s*\)", head):
                patterns.append(f"{rel_file}: SQLAlchemy Model")
            # Alembic migration
            if "alembic" in rel_file.lower() and re.search(r"def\s+upgrade\s*\(", head):
                patterns.append(f"{rel_file}: Alembic Migration")

        elif ext in (".js", ".ts", ".tsx"):
            # Next.js / Express 路由
            if re.search(r"export\s+(default\s+)?(async\s+)?function\s+(GET|POST|PUT|DELETE|PATCH)\s*\(", head, re.I):
                patterns.append(f"{rel_file}: Next.js API Route")
            route_matches = re.findall(r"(app\.|router\.)\s*(get|post|put|delete|patch)\s*\(\s*['\"]([^'\"]+)['\"]", head, re.I)
            for m in route_matches:
                patterns.append(f"{rel_file}: {m[1].upper()} {m[2]}")
            # React Component
            if re.search(r"export\s+(default\s+)?(function|const)\s+\w+.*Component|React\.FC|JSX\.Element", head, re.I):
                patterns.append(f"{rel_file}: React Component")
            # Hook
            if re.search(r"export\s+(function|const)\s+use[A-Z]\w+", head):
                patterns.append(f"{rel_file}: React Hook")

        elif ext == ".go":
            if re.search(r"func\s+\w+\s*\([^)]*\*?gin\.Context\)", head):
                patterns.append(f"{rel_file}: Gin Handler")
            if re.search(r"http\.Handle(Func)?\s*\(", head):
                patterns.append(f"{rel_file}: stdlib HTTP Handler")

        elif ext == ".java":
            if re.search(r"@RestController|@Controller", head):
                patterns.append(f"{rel_file}: Spring Controller")
            if re.search(r"@Entity|@Table\s*\(", head):
                patterns.append(f"{rel_file}: JPA Entity")

    def _detect_code_style(self, context: Dict) -> None:
        """基于代码样本识别项目的命名规范和导入风格。"""
        all_content = "\n".join(
            s.get("content", "") for s in context.get("code_samples", [])
        )
        if not all_content:
            return

        # Import 风格
        import_lines = re.findall(r"^(?:from\s+\S+\s+import|import\s+\S+)", all_content, re.M)
        if import_lines:
            if len([l for l in import_lines if l.startswith("from ")]) > len(import_lines) * 0.5:
                context["import_style"] = "absolute (from X import Y)"
            else:
                context["import_style"] = "direct import"

        # JS/TS import 风格
        js_imports = re.findall(r"^(import\s+.*from\s+['\"])", all_content, re.M)
        if js_imports:
            rel_count = sum(1 for i in js_imports if i.startswith("import ") and "from '" in i or 'from "' in i)
            if rel_count:
                context["import_style"] = "ES Module (import X from 'Y')"

        # 命名规范
        snake_case = len(re.findall(r"\b[a-z_][a-z0-9_]*\b", all_content))
        camel_case = len(re.findall(r"\b[a-z][a-zA-Z0-9]+[A-Z][a-zA-Z0-9]*\b", all_content))
        pascal_case = len(re.findall(r"\b[A-Z][a-zA-Z0-9]*\b", all_content))
        if snake_case > camel_case and snake_case > pascal_case:
            context["naming_convention"] = "snake_case"
        elif camel_case > pascal_case:
            context["naming_convention"] = "camelCase"
        else:
            context["naming_convention"] = "PascalCase / mixed"

    def _collect_project_config(self, project) -> Dict:
        """读取项目配置中的 critical_paths 和 custom_rules。"""
        result: Dict = {"critical_paths": [], "custom_rules": []}
        config = getattr(project, "config_json", None) or {}
        if not isinstance(config, dict):
            return result

        review_config = config.get("review_config", {})
        result["critical_paths"] = review_config.get("critical_paths", [])
        result["custom_rules"] = review_config.get("custom_rules", [])
        result["context_analysis_enabled"] = review_config.get("context_analysis", {}).get("enabled", False)
        return result

    async def _collect_historical_findings(self, project_id: int) -> Dict:
        """统计该项目历史 Commit 分析中的高频问题类别。"""
        result: Dict = {"historical_categories": {}, "historical_severity": {}, "total_findings": 0}

        cat_stmt = (
            select(CommitFinding.category, func.count(CommitFinding.id))
            .join(CommitAnalysis, CommitFinding.commit_analysis_id == CommitAnalysis.id)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.category)
        )
        cat_rows = (await self.session.execute(cat_stmt)).all()
        result["historical_categories"] = {row[0]: row[1] for row in cat_rows}

        sev_stmt = (
            select(CommitFinding.severity, func.count(CommitFinding.id))
            .join(CommitAnalysis, CommitFinding.commit_analysis_id == CommitAnalysis.id)
            .where(CommitAnalysis.project_id == project_id)
            .group_by(CommitFinding.severity)
        )
        sev_rows = (await self.session.execute(sev_stmt)).all()
        result["historical_severity"] = {row[0]: row[1] for row in sev_rows}

        result["total_findings"] = sum(result["historical_categories"].values())
        if result["historical_categories"]:
            result["top_risk_category"] = max(result["historical_categories"], key=result["historical_categories"].get)
        return result

    # ------------------------------------------------------------------
    # 知识图谱特征采集
    # ------------------------------------------------------------------

    async def _collect_graph_features(self, repo_id: str, org_id: str = "default") -> Dict:
        """从知识图谱采集项目架构特征：实体分布、关键实体、架构层、关系模式。"""
        result: Dict = {
            "entity_type_counts": {},
            "relation_type_counts": {},
            "top_entities": [],
            "architecture_layers": {},
            "has_circular_dependency": False,
            "god_class_candidates": [],
        }

        # 1. 实体类型分布
        try:
            stmt = (
                select(CodeEntity.entity_type, func.count(CodeEntity.id))
                .where(CodeEntity.repo_id == repo_id, CodeEntity.org_id == org_id)
                .group_by(CodeEntity.entity_type)
            )
            rows = (await self.session.execute(stmt)).all()
            result["entity_type_counts"] = {row[0]: row[1] for row in rows}
        except Exception as exc:
            logger.warning("Failed to query entity types: %s", exc)

        # 2. 关系类型分布
        try:
            stmt = (
                select(CodeRelationship.relation_type, func.count(CodeRelationship.id))
                .where(CodeRelationship.repo_id == repo_id, CodeRelationship.org_id == org_id)
                .group_by(CodeRelationship.relation_type)
            )
            rows = (await self.session.execute(stmt)).all()
            result["relation_type_counts"] = {row[0]: row[1] for row in rows}
        except Exception as exc:
            logger.warning("Failed to query relation types: %s", exc)

        # 3. 入度最高的实体（被引用最多的函数/类）
        try:
            in_degree_stmt = (
                select(
                    CodeEntity.id,
                    CodeEntity.name,
                    CodeEntity.entity_type,
                    CodeEntity.file_path,
                    func.count(CodeRelationship.id).label("in_degree"),
                )
                .join(
                    CodeRelationship,
                    CodeEntity.id == CodeRelationship.target_entity_id,
                )
                .where(
                    CodeEntity.repo_id == repo_id,
                    CodeEntity.org_id == org_id,
                    CodeRelationship.relation_type.in_(["calls", "inherits", "implements", "decorates"]),
                )
                .group_by(CodeEntity.id, CodeEntity.name, CodeEntity.entity_type, CodeEntity.file_path)
                .order_by(func.count(CodeRelationship.id).desc())
                .limit(10)
            )
            rows = (await self.session.execute(in_degree_stmt)).all()
            result["top_entities"] = [
                {
                    "name": row[1],
                    "type": row[2],
                    "file": row[3],
                    "in_degree": row[4],
                }
                for row in rows
            ]
        except Exception as exc:
            logger.warning("Failed to query top entities: %s", exc)

        # 4. 架构分层推断（基于文件路径）
        try:
            stmt = (
                select(CodeEntity.file_path, func.count(CodeEntity.id))
                .where(CodeEntity.repo_id == repo_id, CodeEntity.org_id == org_id)
                .group_by(CodeEntity.file_path)
            )
            rows = (await self.session.execute(stmt)).all()
            layers: Dict[str, Dict] = {}
            for file_path, count in rows:
                layer = self._infer_architecture_layer(file_path)
                if layer not in layers:
                    layers[layer] = {"entity_count": 0}
                layers[layer]["entity_count"] += count
            result["architecture_layers"] = layers
        except Exception as exc:
            logger.warning("Failed to infer architecture layers: %s", exc)

        # 5. 循环依赖检测（自环）
        try:
            stmt = (
                select(func.count(CodeRelationship.id))
                .where(
                    CodeRelationship.repo_id == repo_id,
                    CodeRelationship.org_id == org_id,
                    CodeRelationship.source_entity_id == CodeRelationship.target_entity_id,
                )
            )
            count = (await self.session.execute(stmt)).scalar() or 0
            result["has_circular_dependency"] = count > 0
        except Exception as exc:
            logger.warning("Failed to detect circular dependencies: %s", exc)

        # 6. God Class 候选（入度 > 20 的类）
        try:
            god_stmt = (
                select(
                    CodeEntity.name,
                    CodeEntity.file_path,
                    func.count(CodeRelationship.id).label("in_degree"),
                )
                .join(
                    CodeRelationship,
                    CodeEntity.id == CodeRelationship.target_entity_id,
                )
                .where(
                    CodeEntity.repo_id == repo_id,
                    CodeEntity.org_id == org_id,
                    CodeEntity.entity_type == "class",
                    CodeRelationship.relation_type.in_(["calls", "inherits", "implements", "contains"]),
                )
                .group_by(CodeEntity.id, CodeEntity.name, CodeEntity.file_path)
                .having(func.count(CodeRelationship.id) > 20)
                .order_by(func.count(CodeRelationship.id).desc())
                .limit(5)
            )
            rows = (await self.session.execute(god_stmt)).all()
            result["god_class_candidates"] = [
                {"name": row[0], "file": row[1], "in_degree": row[2]}
                for row in rows
            ]
        except Exception as exc:
            logger.warning("Failed to query god classes: %s", exc)

        return result

    @staticmethod
    def _infer_architecture_layer(file_path: str) -> str:
        """根据文件路径推断架构层。优先匹配目录名，其次匹配文件名。"""
        path_lower = file_path.lower().replace("\\", "/")
        parts = path_lower.split("/")
        dir_parts = parts[:-1] if len(parts) > 1 else []
        file_name = parts[-1] if parts else ""

        # 先按目录名匹配（更可靠）
        for part in dir_parts:
            if part in ("controller", "controllers", "handler", "handlers", "route", "routes", "view", "views", "endpoint", "endpoints", "api"):
                return "controller"
            elif part in ("service", "services", "business", "usecase", "usecases", "application"):
                return "service"
            elif part in ("model", "models", "entity", "entities", "repository", "repositories", "repo", "repos", "db", "dao", "daos", "schema", "schemas"):
                return "data"
            elif part in ("middleware", "middlewares", "filter", "filters", "interceptor", "interceptors", "guard", "guards", "auth"):
                return "middleware"
            elif part in ("util", "utils", "helper", "helpers", "common", "lib", "libs", "shared", "tool", "tools"):
                return "utility"
            elif part in ("test", "tests", "spec", "specs", "fixture", "fixtures", "mock", "mocks"):
                return "test"
            elif part in ("config", "configs", "setting", "settings", "env"):
                return "config"

        # 目录未匹配，再按文件名匹配
        if any(seg in file_name for seg in ["controller", "handler", "route", "view", "endpoint"]):
            return "controller"
        elif any(seg in file_name for seg in ["service", "business", "usecase"]):
            return "service"
        elif any(seg in file_name for seg in ["model", "repository", "dao", "schema"]):
            return "data"
        elif any(seg in file_name for seg in ["middleware", "filter", "interceptor", "guard"]):
            return "middleware"
        elif any(seg in file_name for seg in ["util", "helper", "common"]):
            return "utility"
        elif any(seg in file_name for seg in ["test", "spec", "mock"]):
            return "test"
        elif any(seg in file_name for seg in ["config", "setting"]):
            return "config"

        return "other"

    # ------------------------------------------------------------------
    # Prompt 构建
    # ------------------------------------------------------------------

    def _build_structured_prompt(self, features: Dict, config: Dict, historical: Dict, graph: Dict) -> str:
        """基于规则构建高质量结构化 Prompt（不依赖 LLM）。"""
        language = features.get("dominant_language", "未知")
        framework = features.get("framework", "unknown")
        commit_type = features.get("dominant_commit_type", "mixed")
        key_paths = features.get("key_paths", [])
        critical_paths = config.get("critical_paths", [])
        custom_rules = config.get("custom_rules", [])
        hist_cats = historical.get("historical_categories", {})
        top_risk = historical.get("top_risk_category", "")
        code_context = features.get("code_context", {}) or {}

        lines: List[str] = [
            "你是一位资深的代码审查专家。请分析提供的代码变更（diff），并以 JSON 对象格式返回发现的问题列表。",
            "",
            "【项目上下文】",
            f"- 主要技术栈: {language}" + (f" ({framework})" if framework and framework != "unknown" else ""),
        ]

        if key_paths:
            lines.append(f"- 项目结构关键目录: {', '.join(key_paths)}")
        if critical_paths:
            lines.append(f"- 配置的关键路径（高风险）: {', '.join(critical_paths)}")
        if top_risk:
            lines.append(f"- 历史高频问题类别（需重点复查）: {top_risk} ({hist_cats[top_risk]} 次)")
        if hist_cats and len(hist_cats) > 1:
            others = [f"{k}({v})" for k, v in sorted(hist_cats.items(), key=lambda x: -x[1])[:3] if k != top_risk]
            if others:
                lines.append(f"- 其他历史问题: {', '.join(others)}")

        # --- 代码内容上下文 ---
        tree = code_context.get("directory_tree", [])
        config_summary = code_context.get("config_summary", {})
        api_patterns = code_context.get("api_patterns", [])
        import_style = code_context.get("import_style")
        naming = code_context.get("naming_convention")
        code_samples = code_context.get("code_samples", [])

        if tree:
            lines.append("")
            lines.append("【项目目录结构快照】")
            lines.append("```")
            for line in tree[:40]:
                lines.append(line)
            if len(tree) > 40:
                lines.append(f"... ({len(tree) - 40} more items)")
            lines.append("```")

        if config_summary:
            lines.append("")
            lines.append("【关键配置摘要】")
            for fname, content in list(config_summary.items())[:3]:
                lines.append(f"--- {fname} ---")
                lines.append(content)
                lines.append("")

        if api_patterns:
            lines.append("【识别的 API / 模型模式】")
            for p in api_patterns[:8]:
                lines.append(f"  - {p}")
            lines.append("")

        # --- 知识图谱架构上下文 ---
        if graph:
            entity_counts = graph.get("entity_type_counts", {})
            relation_counts = graph.get("relation_type_counts", {})
            top_entities = graph.get("top_entities", [])
            layers = graph.get("architecture_layers", {})
            god_classes = graph.get("god_class_candidates", [])
            has_cycle = graph.get("has_circular_dependency", False)

            graph_lines: List[str] = []
            if entity_counts:
                graph_lines.append(f"- 实体分布: {', '.join(f'{k}({v})' for k, v in entity_counts.items())}")
            if relation_counts:
                graph_lines.append(f"- 关系分布: {', '.join(f'{k}({v})' for k, v in relation_counts.items())}")
            if layers:
                layer_summary = ', '.join(f"{k}({v.get('entity_count', 0)})" for k, v in layers.items())
                graph_lines.append(f"- 架构分层: {layer_summary}")
            if top_entities:
                graph_lines.append("- 核心实体（高被引用）:")
                for ent in top_entities[:5]:
                    graph_lines.append(f"  • [{ent['type']}] {ent['name']} (入度: {ent['in_degree']}, 文件: {ent['file']})")
            if god_classes:
                graph_lines.append("- God Class 候选（被引用过多的类）:")
                for gc in god_classes[:3]:
                    graph_lines.append(f"  • {gc['name']} (入度: {gc['in_degree']}, 文件: {gc['file']})")
            if has_cycle:
                graph_lines.append("- ⚠️ 检测到循环依赖")

            if graph_lines:
                lines.append("【知识图谱架构分析】")
                lines.extend(graph_lines)
                lines.append("")

        if import_style or naming:
            style_parts = []
            if import_style:
                style_parts.append(f"导入风格: {import_style}")
            if naming:
                style_parts.append(f"命名规范: {naming}")
            lines.append(f"【代码风格】{', '.join(style_parts)}")
            lines.append("")

        if code_samples:
            lines.append("【代表性代码片段（供理解项目风格）】")
            for sample in code_samples[:4]:
                lines.append(f"--- {sample['file']} ({sample.get('role', 'sample')}) ---")
                lines.append("```")
                lines.append(sample["content"])
                lines.append("```")
                lines.append("")

        lines.append("【审查检查清单】")

        # 1. 通用层
        lines.append("1. 功能完整性")
        lines.append("   - 代码变更是否完整实现了 commit message 描述的功能或修复？")
        lines.append("   - 是否遗漏了异常分支、边界条件、空值处理或权限校验？")
        lines.append("   - 新增功能是否配套了必要的错误提示或日志记录？")

        # 2. Commit 类型感知层
        lines.append("")
        lines.append("2. 逻辑正确性")
        if commit_type in ("feat", "fix"):
            lines.append("   - 条件分支是否覆盖了所有业务场景？特别关注新增逻辑的边界条件。")
            lines.append("   - 循环、递归、异步流程的终止条件是否正确，是否存在死循环或竞态条件？")
        else:
            lines.append("   - 条件分支、循环终止、状态流转是否正确？")
        lines.append("   - 异常处理路径是否完备？捕获的异常是否有合理的降级策略？")

        # 3. 回归风险
        lines.append("")
        lines.append("3. 回归风险评估")
        if critical_paths:
            lines.append(f"   - 修改是否影响了配置的关键路径 {critical_paths} 下的模块？")
        else:
            lines.append("   - 修改是否影响了核心业务模块或公共工具函数？")
        lines.append("   - 是否存在对外部接口、数据库表结构、API 契约的破坏性变更？")
        lines.append("   - 删除或重命名操作是否遗留了未清理的引用？")

        # 4. 数据一致性
        lines.append("")
        lines.append("4. 数据一致性与并发安全")
        lines.append("   - 事务边界是否正确？是否存在部分提交或长事务风险？")
        lines.append("   - 并发场景下（多线程/多协程/分布式）是否存在竞态条件或数据覆盖？")
        lines.append("   - 缓存与数据库的一致性是否得到保障？")

        # 5. Commit 类型特定
        lines.append("")
        lines.append("5. Commit 类型针对性检查")
        if commit_type == "feat":
            lines.append("   [本次为 feat 类型] 重点检查：")
            lines.append("   - 需求覆盖度：是否完整实现了需求描述的所有 acceptance criteria？")
            lines.append("   - 可测试性：新增功能是否便于编写单元测试或集成测试？")
            lines.append("   - 兼容性：新功能对旧数据、旧客户端是否向后兼容？")
        elif commit_type == "fix":
            lines.append("   [本次为 fix 类型] 重点检查：")
            lines.append("   - 根因修复：是否修复了真正的原因，而非仅消除了表面症状？")
            lines.append("   - 副作用：修复是否引入了新的行为变更或性能退化？")
            lines.append("   - 测试覆盖：是否为该 Bug 补充了回归测试，防止再次复现？")
        elif commit_type == "refactor":
            lines.append("   [本次为 refactor 类型] 重点检查：")
            lines.append("   - 行为一致性：重构前后对外暴露的行为是否完全一致？")
            lines.append("   - 性能变化：重构是否引入了额外的性能开销（如重复计算、额外 I/O）？")
            lines.append("   - 依赖影响：被重构的模块是否有大量上游调用方需要同步验证？")
        elif commit_type == "test":
            lines.append("   [本次为 test 类型] 重点检查：")
            lines.append("   - 测试有效性：测试是否真正验证了业务逻辑，而非仅覆盖了代码行？")
            lines.append("   - 断言完整性：断言条件是否足够严格，能否捕获真实的回归？")
            lines.append("   - Mock/Stub 合理性：外部依赖的模拟是否与真实行为一致？")
        else:
            lines.append("   - 请结合 commit message 判断本次变更的核心目的，并针对性检查。")

        # 6. 技术栈特定
        tech_checks = self._get_tech_specific_checks(language, framework)
        if tech_checks:
            lines.append("")
            lines.append(f"6. [{language}] 技术栈特定检查")
            for chk in tech_checks:
                lines.append(f"   - {chk}")

        # 7. 项目规则合规
        if custom_rules:
            lines.append("")
            lines.append("7. 项目自定义规则合规")
            for rule in custom_rules:
                name = rule.get("name", "未命名规则")
                msg = rule.get("message", "")
                sev = rule.get("severity", "warning")
                lines.append(f"   - [{sev}] {name}: {msg}")

        # JSON 格式要求
        lines.append("")
        lines.append("要求的 JSON 格式：")
        lines.append(
            '{"issues": [{"file": "path/to/file", "line": 42, "severity": "critical|warning|info", '
            '"category": "security|logic|performance|architecture|style", "description": "问题描述", '
            '"suggestion": "修复建议", "confidence": 0.95, "evidence": "代码片段", "reasoning": "原因"}], '
            '"summary": "总结", "risk_level": "low|medium|high"}'
        )
        lines.append("")
        lines.append("请保持简洁和准确。如果没有发现问题，返回空的 issues 数组。")

        return "\n".join(lines)

    def _get_tech_specific_checks(self, language: str, framework: str) -> List[str]:
        """根据技术栈返回特定的审查检查点。"""
        checks: List[str] = []

        if language == "Python":
            checks.append("异步函数（async def）内部是否正确使用了 await，是否存在阻塞调用混入事件循环？")
            checks.append("可变默认参数（如 def f(x=[])）或类属性共享可变对象是否正确？")
            checks.append("异常处理是否捕获了过于宽泛的 Exception，掩盖了真正的错误？")
            if framework == "FastAPI":
                checks.append("Pydantic 模型变更是否兼容旧数据，是否遗漏了字段校验规则（Field/validator）？")
                checks.append("依赖注入（Depends）是否存在循环依赖或资源泄漏？")
            elif framework == "Django":
                checks.append("ORM 查询是否引入了 N+1 问题，是否缺少 select_related/prefetch_related？")
                checks.append("Migration 文件是否包含数据迁移，是否对大数据表做了安全处理？")
            elif framework == "Flask":
                checks.append("应用上下文（app_context）和请求上下文是否正确管理？")

        elif language == "Go":
            checks.append("错误处理是否完备？是否对 error 进行了判断而非忽略？")
            checks.append("Goroutine 泄漏风险：是否正确使用了 sync.WaitGroup / context.Cancel？")
            checks.append("Slice/Map 的并发访问是否使用了互斥锁或 channel 同步？")
            if framework == "Gin":
                checks.append("路由处理器是否正确处理了请求绑定错误和响应格式？")

        elif language in ("JavaScript", "TypeScript"):
            checks.append("异步操作是否正确处理了 Promise rejection 或 await 异常？")
            checks.append("null/undefined 的防御性检查是否完备（可选链、默认值）？")
            if framework == "React":
                checks.append("Hook 规则是否被遵守（如 useEffect 依赖数组是否完整）？")
                checks.append("组件重渲染优化：是否避免了不必要的 state 更新或匿名函数传参？")
            elif framework in ("Next.js", "NestJS"):
                checks.append("API 路由的输入校验和错误边界处理是否完善？")

        elif language == "Java":
            checks.append("Stream/Optional 的使用是否合理，是否引入了性能陷阱（如多次遍历）？")
            checks.append("并发代码是否正确使用了 synchronized / Lock / Atomic 工具？")
            if framework == "Spring":
                checks.append("事务注解（@Transactional）的传播行为和回滚规则是否正确？")
                checks.append("依赖注入是否存在循环依赖，Bean 作用域是否合理？")

        elif language == "Rust":
            checks.append("所有权和生命周期标注是否正确，是否存在不必要的 clone() 导致性能损失？")
            checks.append("unsafe 块的使用是否最小化，是否有充分的注释说明安全不变式？")
            checks.append("错误处理：是否过度使用了 unwrap/expect，生产代码应优先使用 ? 传播错误。")

        return checks

    async def _refine_prompt_with_llm(self, base_prompt: str, features: Dict, config: Dict, historical: Dict) -> str:
        """使用 LLM 对结构化基础 Prompt 进行润色增强。"""
        language = features.get("dominant_language", "未知")
        framework = features.get("framework", "unknown")
        commit_type = features.get("dominant_commit_type", "mixed")
        top_risk = historical.get("top_risk_category", "")
        code_context = features.get("code_context", {}) or {}

        # 构建代码上下文摘要
        code_ctx_parts: List[str] = []
        api_patterns = code_context.get("api_patterns", [])
        if api_patterns:
            code_ctx_parts.append(f"API/模型模式: {', '.join(api_patterns[:5])}")
        import_style = code_context.get("import_style")
        naming = code_context.get("naming_convention")
        if import_style:
            code_ctx_parts.append(f"导入风格: {import_style}")
        if naming:
            code_ctx_parts.append(f"命名规范: {naming}")
        code_samples = code_context.get("code_samples", [])
        if code_samples:
            code_ctx_parts.append(f"代表性文件: {', '.join(s['file'] for s in code_samples[:3])}")
        code_ctx_str = "\n".join(f"- {p}" for p in code_ctx_parts) if code_ctx_parts else "暂无代码上下文"

        user_msg = (
            f"请对以下结构化代码审查 Prompt 进行润色和增强。\n\n"
            f"【项目特征】\n"
            f"- 技术栈: {language}" + (f" ({framework})" if framework != "unknown" else "") + "\n"
            f"- 主要 Commit 类型: {commit_type}\n"
            f"- 历史高频问题: {top_risk or '暂无数据'}\n\n"
            f"【代码上下文摘要】\n"
            f"{code_ctx_str}\n\n"
            f"【当前 Prompt】\n"
            f"{base_prompt}\n\n"
            f"【要求】\n"
            f"1. 保持检查清单结构和 JSON 输出格式完全不变。\n"
            f"2. 将技术栈特征、代码上下文和历史问题数据自然融入对应检查项的描述中，使其更具针对性。\n"
            f"3. 例如：如果项目使用 FastAPI + Pydantic，在数据校验项中强化 Pydantic 模型兼容性提示；如果项目有 Alembic migration，在数据一致性项中强化 migration 安全性提示。\n"
            f"4. 语言保持专业、简洁、可执行。\n"
            f"5. 直接返回润色后的完整 Prompt 文本。"
        )

        text = await self.provider.generate_text(
            messages=[
                {"role": "system", "content": REFINER_SYSTEM_PROMPT},
                {"role": "user", "content": user_msg},
            ],
            model="deepseek-chat",
            temperature=0.2,
            max_tokens=3000,
        )

        if not text:
            return base_prompt

        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()

        # 简单校验：润色后的 prompt 必须包含 "JSON" 和 "issues"，否则回退
        if "JSON" not in text or "issues" not in text:
            logger.warning("LLM refined prompt lost required structure, falling back to base prompt")
            return base_prompt

        return text

    @staticmethod
    def _sanitize_repo_id(repo_id: str) -> str:
        """清理 repo_id 中的特殊字符，只保留字母、数字、下划线和连字符。"""
        return re.sub(r"[^a-zA-Z0-9_-]", "-", repo_id)

    async def _next_version(self, project_id: int, repo_id: str) -> str:
        """生成下一个版本号，如 wxj-1019-latte-code-v1。"""
        safe_repo = self._sanitize_repo_id(repo_id)
        prefix = f"{safe_repo}-v"
        try:
            result = await self.session.execute(
                select(PromptExperiment.version)
                .where(PromptExperiment.version.like(f"{prefix}%"))
            )
            versions = [row[0] for row in result.all()]
            max_num = 0
            for v in versions:
                m = re.search(rf"{re.escape(prefix)}(\d+)", v)
                if m:
                    max_num = max(max_num, int(m.group(1)))
            return f"{prefix}{max_num + 1}"
        except Exception:
            logger.exception("Failed to compute next version for project %s", project_id)
            await self.session.rollback()
            return f"{prefix}1"
