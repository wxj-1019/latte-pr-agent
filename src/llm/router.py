import asyncio
import logging
from typing import Dict, Optional

from openai import RateLimitError, APITimeoutError

from llm.base import LLMProvider
from llm.deepseek import DeepSeekProvider
from llm.anthropic import AnthropicProvider

logger = logging.getLogger(__name__)


class ReviewRouter:
    """审查路由：根据配置和 PR 规模选择模型"""

    def __init__(self, config: Dict, providers: Optional[Dict[str, LLMProvider]] = None):
        self.providers: Dict[str, LLMProvider] = providers or {
            "deepseek": DeepSeekProvider(),
            "anthropic": AnthropicProvider(),
        }
        self.config = config

    async def review(self, prompt: str, pr_size_tokens: int) -> Dict:
        primary = self.config.get("primary_model", "deepseek-chat")

        # Enterprise user specified high-end model
        if "claude" in primary:
            return await self.providers["anthropic"].review(prompt, primary)

        # Default strategy: DeepSeek fast review
        result = await self.providers["deepseek"].review(prompt, primary)

        # Dual-model verification
        if self.config.get("enable_reasoner_review", False):
            has_risk = any(
                i.get("severity") in ["critical", "warning"]
                for i in result.get("issues", [])
            )
            if has_risk and pr_size_tokens < 15000:
                reasoner_prompt = self._build_reasoner_prompt(result, prompt)
                reasoner_result = await self.providers["deepseek"].review(
                    reasoner_prompt, "deepseek-reasoner"
                )
                result = self._merge_results(result, reasoner_result)

        return result

    def _build_reasoner_prompt(self, initial_result: Dict, original_prompt: str) -> str:
        issues_text = "\n".join(
            f"- [{i.get('severity')}] {i.get('description')}"
            for i in initial_result.get("issues", [])
            if i.get("severity") in ["critical", "warning"]
        )
        return (
            f"The following code was initially reviewed and potential issues were found:\n\n"
            f"{issues_text}\n\n"
            f"Please carefully re-evaluate these issues against the original code diff. "
            f"Confirm, refute, or refine each issue with detailed reasoning. "
            f"Return your response in the same JSON format.\n\n"
            f"Original prompt:\n{original_prompt}"
        )

    def _merge_results(self, primary: Dict, reasoner: Dict) -> Dict:
        """Merge reasoner review into primary result."""
        merged_issues = []
        primary_issues = primary.get("issues", [])
        reasoner_issues = reasoner.get("issues", [])

        # Simple merge: keep all primary issues, add reasoner issues that don't duplicate
        merged_issues.extend(primary_issues)
        for ri in reasoner_issues:
            dup = any(
                pi.get("file") == ri.get("file") and pi.get("line") == ri.get("line")
                and pi.get("category") == ri.get("category")
                for pi in primary_issues
            )
            if not dup:
                merged_issues.append(ri)

        primary["issues"] = merged_issues
        primary["reasoner_reviewed"] = True
        return primary


class ResilientReviewRouter(ReviewRouter):
    """具备降级能力的审查路由器"""

    async def review(self, prompt: str, pr_size_tokens: int) -> Dict:
        return await self.review_with_fallback(prompt, pr_size_tokens)

    async def review_with_fallback(self, prompt: str, pr_size_tokens: int) -> Dict:
        models = [self.config.get("primary", "deepseek-chat")]
        models += self.config.get("fallback_chain", [])

        last_error = None
        for model in models:
            provider = self._get_provider(model)
            for attempt in range(2):
                try:
                    logger.info(f"Trying model {model}, attempt {attempt + 1}")
                    return await provider.review(prompt, model)
                except RateLimitError:
                    await asyncio.sleep(2 ** attempt)
                except APITimeoutError:
                    if attempt == 1:
                        break  # 切换下一个模型
                except Exception as e:
                    logger.warning(f"Model {model} failed: {e}")
                    last_error = e
                    if attempt == 1:
                        break

        # 所有模型均不可用：返回降级结果
        logger.error(f"All models down. Last error: {last_error}")
        return {
            "summary": "AI 模型服务暂时不可用，本次仅展示静态分析结果",
            "risk_level": "low",
            "issues": [],
            "degraded": True,
            "error": str(last_error) if last_error else "unknown",
        }

    def _get_provider(self, model: str) -> LLMProvider:
        if "claude" in model:
            return self.providers["anthropic"]
        return self.providers["deepseek"]
