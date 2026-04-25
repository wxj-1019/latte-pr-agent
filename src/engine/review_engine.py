import logging
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from context.builder import PRDiff, ProjectContextBuilder
from config.project_config import ReviewConfig
from llm import ReviewRouter
from prompts.registry import PromptRegistry
from rag import RAGRetriever
from repositories import ReviewRepository, FindingRepository
from static import SemgrepAnalyzer, FindingMerger
from engine.deduplicator import CommentDeduplicator
from engine.cache import ReviewCache
from engine.rule_engine import RuleEngine
from engine.chunker import PRChunker

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
        repo_id: str = "",
        project_config: Optional[ReviewConfig] = None,
    ):
        self.session = session
        self.router = router
        self.cache = cache
        self.prompt_version = prompt_version
        self.enable_static_analysis = enable_static_analysis
        self.repo_id = repo_id
        self.project_config = project_config
        self.review_repo = ReviewRepository(session)
        self.finding_repo = FindingRepository(session)
        self.deduplicator = CommentDeduplicator(session)
        rag_retriever = RAGRetriever() if repo_id else None
        self.context_builder = ProjectContextBuilder(
            db_session=session, repo_id=repo_id, rag_retriever=rag_retriever, project_config=project_config
        )
        self.semgrep = SemgrepAnalyzer()
        self.merger = FindingMerger()
        self.rule_engine = RuleEngine(project_config) if project_config else None

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
        # Preload existing findings to avoid N+1 queries during deduplication
        await self.deduplicator.preload_existing(review_id)

        primary_model = getattr(self.router, "config", {}).get("primary_model", "deepseek-chat")
        if not primary_model:
            primary_model = "deepseek-chat"

        # Load prompt registry and get system prompt for this version
        prompt_registry = PromptRegistry(self.session)
        await prompt_registry.load_from_db()
        system_prompt = prompt_registry.get_text(self.prompt_version)

        # 1. Check cache
        if self.cache:
            cached = await self.cache.get(pr_diff, self.prompt_version, primary_model)
            if cached is not None:
                await self._persist_findings(review_id, cached, primary_model)
                await self.review_repo.update_status(review_id, "completed")
                return {**cached, "cached": True}

        # 2. Build context (ProjectContextBuilder)
        pr_diff_obj = PRDiff(content=pr_diff, repo_id=self.repo_id)
        built_context = await self.context_builder.build_context(pr_diff_obj)
        if context:
            built_context.update(context)

        # 2.5 GraphRAG: retrieve related code context for changed files
        if self.repo_id and changed_files:
            try:
                from graph.graph_rag import GraphRAGRetriever
                graph_rag = GraphRAGRetriever(self.session)
                rag_results = await graph_rag.retrieve(
                    repo_id=self.repo_id,
                    query="分析 PR 代码变更的影响范围",
                    changed_files=changed_files,
                    depth=2,
                    top_k=8,
                )
                if rag_results:
                    built_context["graph_rag"] = rag_results
                    logger.info("Review %s: GraphRAG retrieved %s related entities", review_id, len(rag_results))
            except Exception as exc:
                logger.warning("Review %s: GraphRAG retrieval skipped: %s", review_id, exc)

        # 3. Determine effective model from project config if available
        effective_router = self._get_effective_router()

        # 4. Build prompt and call LLM (with chunking for large PRs)
        ai_result = await self._run_llm_review(
            review_id=review_id,
            pr_diff=pr_diff,
            built_context=built_context,
            pr_size_tokens=pr_size_tokens,
            router=effective_router,
            system_prompt=system_prompt,
        )

        degraded = ai_result.get("degraded", False)

        # 5. Static analysis (optional)
        static_findings: List[dict] = []
        if self.enable_static_analysis and repo_path and changed_files:
            try:
                static_findings = await self.semgrep.analyze(repo_path, changed_files)
                logger.info("Review %s: semgrep found %s issues", review_id, len(static_findings))
            except Exception as exc:
                logger.warning("Review %s: static analysis failed: %s", review_id, exc, exc_info=True)

        # 5.5 Rule engine analysis
        rule_findings: List[dict] = []
        if self.rule_engine and changed_files:
            try:
                rule_findings = self.rule_engine.analyze(changed_files, pr_diff)
                logger.info("Review %s: rule engine found %s issues", review_id, len(rule_findings))
            except Exception as exc:
                logger.warning("Review %s: rule engine failed: %s", review_id, exc, exc_info=True)

        all_static = static_findings + rule_findings

        # 6. Merge results
        merged_result = self.merger.merge_with_degraded(
            ai_result.get("issues", []),
            all_static,
            degraded=degraded,
        )
        # Preserve extra fields from AI result
        for key in ("summary", "reasoner_reviewed"):
            if key in ai_result:
                merged_result[key] = ai_result[key]

        # 7. Persist findings and record prompt version
        await self._persist_findings(review_id, merged_result, primary_model)
        review = await self.review_repo.get_by_id(review_id)
        if review:
            review.prompt_version = self.prompt_version
        await self.review_repo.update_status(review_id, "completed")

        # 8. Update cache
        if self.cache:
            await self.cache.set(pr_diff, self.prompt_version, primary_model, merged_result)

        return merged_result

    def _get_effective_router(self):
        """如果 project_config 中指定了 ai_model，则返回一个覆盖 primary 配置的 router。"""
        if not self.project_config:
            return self.router
        primary = self.project_config.ai_model.primary
        if not primary:
            return self.router
        # Create a shallow copy of router config with overridden primary
        import copy
        new_config = copy.deepcopy(self.router.config)
        new_config["primary_model"] = primary
        # Instantiate same class with new config
        return self.router.__class__(config=new_config, providers=self.router.providers)

    async def _run_llm_review(
        self,
        review_id: int,
        pr_diff: str,
        built_context: Dict,
        pr_size_tokens: int,
        router,
        system_prompt: str | None = None,
    ) -> Dict:
        """对 PR diff 执行 LLM 审查。超大 PR 自动分块审查后合并结果。"""
        max_chunk_tokens = 6000
        if pr_size_tokens <= max_chunk_tokens:
            prompt = self._build_prompt(pr_diff, built_context)
            try:
                return await router.review(prompt, pr_size_tokens, system_prompt)
            except (OSError, ConnectionError, TimeoutError) as exc:
                logger.exception("Review %s: LLM call failed: %s", review_id, exc)
                return {"issues": [], "summary": "LLM error", "risk_level": "low", "degraded": True}

        # Large PR: chunk and review each part
        logger.info("Review %s: PR exceeds %s tokens, using chunking", review_id, max_chunk_tokens)
        chunker = PRChunker(max_chunk_tokens=max_chunk_tokens)
        chunks = chunker.chunk(pr_diff)
        all_issues = []
        summaries = []
        reasoner_reviewed = False

        for idx, chunk in enumerate(chunks):
            prompt = self._build_prompt(chunk["content"], built_context)
            try:
                part_result = await router.review(prompt, chunk["tokens"], system_prompt)
            except (OSError, ConnectionError, TimeoutError) as exc:
                logger.exception("Review %s: LLM chunk %s failed: %s", review_id, idx, exc)
                continue
            all_issues.extend(part_result.get("issues", []))
            if part_result.get("summary"):
                summaries.append(part_result["summary"])
            if part_result.get("reasoner_reviewed"):
                reasoner_reviewed = True

        if not all_issues and not summaries:
            return {"issues": [], "summary": "LLM error", "risk_level": "low", "degraded": True}

        return {
            "issues": all_issues,
            "summary": " | ".join(summaries) if summaries else "Review completed",
            "risk_level": "high" if any(i.get("severity") == "critical" for i in all_issues)
            else "medium" if any(i.get("severity") == "warning" for i in all_issues)
            else "low",
            "degraded": False,
            "reasoner_reviewed": reasoner_reviewed,
        }

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
        if context.get("graph_rag"):
            rag = context["graph_rag"]
            rag_lines = ["相关代码上下文（GraphRAG 检索）:"]
            for r in rag[:8]:
                sig = r.get("signature") or ""
                rag_lines.append(f"- [{r.get('entity_type', '')}] {r.get('name', '')} ({r.get('file_path', '')}:{r.get('start_line', '')}) {sig}")
            ctx_lines.append("\n".join(rag_lines))

        ctx_str = "\n\n".join(ctx_lines)
        return f"""请审查以下 Pull Request 的代码变更。

项目上下文：
{ctx_str}

--- DIFF 开始 ---
{pr_diff}
--- DIFF 结束 ---

请以 JSON 对象格式返回审查发现。"""

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
