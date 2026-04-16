from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from llm import ReviewRouter
from repositories import ReviewRepository, FindingRepository
from engine.deduplicator import CommentDeduplicator
from engine.cache import ReviewCache


class ReviewEngine:
    """AI 审查引擎核心：组装 Prompt、调用 LLM、解析结果、持久化"""

    def __init__(
        self,
        session: AsyncSession,
        router: ReviewRouter,
        cache: Optional[ReviewCache] = None,
        prompt_version: str = "v1",
    ):
        self.session = session
        self.router = router
        self.cache = cache
        self.prompt_version = prompt_version
        self.review_repo = ReviewRepository(session)
        self.finding_repo = FindingRepository(session)
        self.deduplicator = CommentDeduplicator(session)

    async def run(
        self,
        review_id: int,
        pr_diff: str,
        context: Optional[Dict] = None,
        pr_size_tokens: int = 0,
    ) -> Dict:
        """执行单次审查流程"""
        # 1. Check cache
        primary_model = self.router.config.get("primary_model", "deepseek-chat")
        if self.cache:
            cached = await self.cache.get(pr_diff, self.prompt_version, primary_model)
            if cached:
                await self._persist_findings(review_id, cached, primary_model)
                await self.review_repo.update_status(review_id, "completed")
                return {**cached, "cached": True}

        # 2. Build prompt
        prompt = self._build_prompt(pr_diff, context or {})

        # 3. Call LLM
        result = await self.router.review(prompt, pr_size_tokens)

        # 4. Persist findings
        await self._persist_findings(review_id, result, primary_model)
        await self.review_repo.update_status(review_id, "completed")

        # 5. Update cache
        if self.cache:
            await self.cache.set(pr_diff, self.prompt_version, primary_model, result)

        return result

    def _build_prompt(self, pr_diff: str, context: Dict) -> str:
        ctx_lines = []
        if context.get("dependency_graph"):
            ctx_lines.append("Dependency Graph:\n" + str(context["dependency_graph"]))
        if context.get("similar_bugs"):
            ctx_lines.append("Similar Historical Bugs:\n" + str(context["similar_bugs"]))
        if context.get("api_contracts"):
            ctx_lines.append("API Contract Changes:\n" + str(context["api_contracts"]))

        ctx_str = "\n\n".join(ctx_lines)
        return f"""Please review the following Pull Request diff.

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
                ai_model=model,
                raw_response=issue,
            )
