import logging
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from context.builder import PRDiff, ProjectContextBuilder
from llm import ReviewRouter
from repositories import ReviewRepository, FindingRepository
from static import SemgrepAnalyzer, FindingMerger
from engine.deduplicator import CommentDeduplicator
from engine.cache import ReviewCache

logger = logging.getLogger(__name__)


class ReviewEngine:
    """AI 审查引擎核心：组装 Prompt、调用 LLM、解析结果、持久化、静态分析融合"""

    def __init__(
        self,
        session: AsyncSession,
        router: ReviewRouter,
        cache: Optional[ReviewCache] = None,
        prompt_version: str = "v1",
        enable_static_analysis: bool = True,
    ):
        self.session = session
        self.router = router
        self.cache = cache
        self.prompt_version = prompt_version
        self.enable_static_analysis = enable_static_analysis
        self.review_repo = ReviewRepository(session)
        self.finding_repo = FindingRepository(session)
        self.deduplicator = CommentDeduplicator(session)
        self.context_builder = ProjectContextBuilder()
        self.semgrep = SemgrepAnalyzer()
        self.merger = FindingMerger()

    async def run(
        self,
        review_id: int,
        pr_diff: str,
        context: Optional[Dict] = None,
        pr_size_tokens: int = 0,
        repo_path: Optional[str] = None,
        changed_files: Optional[List[str]] = None,
    ) -> Dict:
        """执行单次审查流程"""
        primary_model = getattr(self.router, "config", {}).get("primary_model", "deepseek-chat")
        if not primary_model:
            primary_model = "deepseek-chat"

        # 1. Check cache
        if self.cache:
            cached = await self.cache.get(pr_diff, self.prompt_version, primary_model)
            if cached:
                await self._persist_findings(review_id, cached, primary_model)
                await self.review_repo.update_status(review_id, "completed")
                return {**cached, "cached": True}

        # 2. Build context (ProjectContextBuilder)
        pr_diff_obj = PRDiff(content=pr_diff)
        built_context = self.context_builder.build_context(pr_diff_obj)
        if context:
            built_context.update(context)

        # 3. Build prompt
        prompt = self._build_prompt(pr_diff, built_context)

        # 4. Call LLM
        try:
            ai_result = await self.router.review(prompt, pr_size_tokens)
        except Exception as exc:
            logger.exception(f"Review {review_id}: LLM call failed: {exc}")
            ai_result = {"issues": [], "summary": "LLM error", "risk_level": "low", "degraded": True}

        degraded = ai_result.get("degraded", False)

        # 5. Static analysis (optional)
        static_findings: List[dict] = []
        if self.enable_static_analysis and repo_path and changed_files:
            try:
                static_findings = self.semgrep.analyze(repo_path, changed_files)
                logger.info(f"Review {review_id}: semgrep found {len(static_findings)} issues")
            except Exception as exc:
                logger.warning(f"Review {review_id}: static analysis failed: {exc}")

        # 6. Merge results
        merged_result = self.merger.merge_with_degraded(
            ai_result.get("issues", []),
            static_findings,
            degraded=degraded,
        )
        # Preserve extra fields from AI result
        for key in ("summary", "reasoner_reviewed"):
            if key in ai_result:
                merged_result[key] = ai_result[key]

        # 7. Persist findings
        await self._persist_findings(review_id, merged_result, primary_model)
        await self.review_repo.update_status(review_id, "completed")

        # 8. Update cache
        if self.cache:
            await self.cache.set(pr_diff, self.prompt_version, primary_model, merged_result)

        return merged_result

    def _build_prompt(self, pr_diff: str, context: Dict) -> str:
        ctx_lines = []
        if context.get("dependency_graph"):
            graph = context["dependency_graph"]
            ctx_lines.append(f"Dependency Risk Score: {graph.get('risk_score', 0)}")
            if graph.get("upstream"):
                ctx_lines.append("Upstream Imports:\n" + str(graph["upstream"]))
        if context.get("api_contracts"):
            api = context["api_contracts"]
            if api.get("breaking_count", 0) > 0:
                ctx_lines.append(f"API Breaking Changes: {api['breaking_count']}")
        if context.get("similar_bugs"):
            ctx_lines.append("Similar Historical Bugs:\n" + str(context["similar_bugs"]))

        ctx_str = "\n\n".join(ctx_lines)
        return f"""Please review the following Pull Request diff.

Project Context:
{ctx_str}

--- DIFF START ---
{pr_diff}
--- DIFF END ---

Respond with a JSON object containing the review findings."""

    async def _persist_findings(
        self, review_id: int, result: Dict, model: str
    ) -> None:
        for issue in result.get("issues", []):
            file_path = issue.get("file", "")
            line_number = issue.get("line")

            if not await self.deduplicator.should_comment(review_id, file_path, line_number):
                continue

            await self.finding_repo.create(
                review_id=review_id,
                file_path=file_path,
                line_number=line_number,
                category=issue.get("category"),
                severity=issue.get("severity"),
                description=issue.get("description", ""),
                suggestion=issue.get("suggestion"),
                confidence=issue.get("confidence"),
                ai_model=model if issue.get("source") != "semgrep" else "semgrep",
                raw_response=issue,
            )
