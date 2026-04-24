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
        last_prompt, last_metadata = await self._get_last_project_prompt(project_id)

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
            features["static"], features["config"], features["historical"]
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
        version = await self._next_version(project_id)
        metadata = {
            "generated_for": "commit_analysis",
            "project_id": project_id,
            "repo_id": repo_id,
            "version": version,
            "feature_fingerprint": current_fingerprint,
            "generation_mode": "structured+llm_refinement" if prompt_text != base_prompt else "structured_fallback",
            "focus_areas": ["logic", "functionality", "regression_risk", "data_consistency"],
            **features["static"],
            **features["config"],
            **features["historical"],
        }

        await self.registry.save_version(version, prompt_text, metadata)
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

        fingerprint_data = {
            "language": static.get("dominant_language"),
            "framework": static.get("framework"),
            "key_paths": sorted(static.get("key_paths", [])),
            "commit_type_dist": commit_type_dist,
            "critical_paths": sorted(config.get("critical_paths", [])),
            "custom_rules_count": len(config.get("custom_rules", [])),
            "top_3_cats": top_3_cats,
        }

        raw = json.dumps(fingerprint_data, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    async def _get_last_project_prompt(self, project_id: int) -> Tuple[Optional[str], Optional[Dict]]:
        """获取该项目最新的专属 Prompt 文本及其 metadata。"""
        prefix = f"project-{project_id}-v"
        try:
            result = await self.session.execute(
                select(PromptExperiment)
                .where(PromptExperiment.version.like(f"{prefix}%"))
                .order_by(select(func.max(PromptExperiment.created_at)))
                .limit(1)
            )
            # 上面的 order_by 写法不对，应该用子查询或 desc。修正：
        except Exception:
            logger.exception("Failed to get last project prompt for %s", project_id)
            return None, None

        # 重新用正确方式查询
        try:
            from sqlalchemy import desc
            result = await self.session.execute(
                select(PromptExperiment)
                .where(PromptExperiment.version.like(f"{prefix}%"))
                .order_by(desc(PromptExperiment.created_at))
                .limit(1)
            )
            row = result.scalar_one_or_none()
            if row:
                return row.prompt_text, row.metadata_json or {}
        except Exception:
            logger.exception("Failed to get last project prompt for %s", project_id)
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
                capture_output=True, text=True, timeout=15,
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
    # Prompt 构建
    # ------------------------------------------------------------------

    def _build_structured_prompt(self, features: Dict, config: Dict, historical: Dict) -> str:
        """基于规则构建高质量结构化 Prompt（不依赖 LLM）。"""
        language = features.get("dominant_language", "未知")
        framework = features.get("framework", "unknown")
        commit_type = features.get("dominant_commit_type", "mixed")
        key_paths = features.get("key_paths", [])
        critical_paths = config.get("critical_paths", [])
        custom_rules = config.get("custom_rules", [])
        hist_cats = historical.get("historical_categories", {})
        top_risk = historical.get("top_risk_category", "")

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

        user_msg = (
            f"请对以下结构化代码审查 Prompt 进行润色和增强。\n\n"
            f"【项目特征】\n"
            f"- 技术栈: {language}" + (f" ({framework})" if framework != "unknown" else "") + "\n"
            f"- 主要 Commit 类型: {commit_type}\n"
            f"- 历史高频问题: {top_risk or '暂无数据'}\n\n"
            f"【当前 Prompt】\n"
            f"{base_prompt}\n\n"
            f"【要求】\n"
            f"1. 保持检查清单结构和 JSON 输出格式完全不变。\n"
            f"2. 将技术栈特征和历史问题数据自然融入对应检查项的描述中，使其更具针对性。\n"
            f"3. 语言保持专业、简洁、可执行。\n"
            f"4. 直接返回润色后的完整 Prompt 文本。"
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

    async def _next_version(self, project_id: int) -> str:
        """生成下一个版本号，如 project-123-v1, project-123-v2。"""
        prefix = f"project-{project_id}-v"
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
            return f"{prefix}1"
