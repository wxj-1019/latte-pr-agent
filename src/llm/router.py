import asyncio
import logging
from typing import Dict, Optional

from openai import RateLimitError, APITimeoutError

from llm.base import LLMProvider
from llm.deepseek import DeepSeekProvider
from llm.anthropic import AnthropicProvider
from llm.qwen import QwenProvider

logger = logging.getLogger(__name__)


class ReviewRouter:
    """审查路由：根据配置和 PR 规模选择模型"""

    def __init__(self, config: Dict, providers: Optional[Dict[str, LLMProvider]] = None):
        self.providers: Dict[str, LLMProvider] = providers or {
            "deepseek": DeepSeekProvider(),
            "anthropic": AnthropicProvider(),
            "qwen": QwenProvider(),
        }
        self.config = config

    async def review(self, prompt: str, pr_size_tokens: int, system_prompt: str | None = None) -> Dict:
        primary = self.config.get("primary_model", "deepseek-chat")

        # Enterprise user specified high-end model
        if "claude" in primary:
            return await self.providers["anthropic"].review(prompt, primary, system_prompt)

        # Qwen strategy
        if "qwen" in primary:
            return await self.providers["qwen"].review(prompt, primary, system_prompt)

        # Default strategy: DeepSeek fast review
        result = await self.providers["deepseek"].review(prompt, primary, system_prompt)

        # Dual-model verification
        if self.config.get("enable_reasoner_review", False):
            issues = result.get("issues", []) if isinstance(result, dict) else []
            has_risk = any(
                isinstance(i, dict) and i.get("severity") in ["critical", "warning"]
                for i in issues
            ) if issues else False
            if has_risk and pr_size_tokens < 15000:
                reasoner_prompt = self._build_reasoner_prompt(result, prompt)
                reasoner_result = await self.providers["deepseek"].review(
                    reasoner_prompt, "deepseek-reasoner", system_prompt
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
        """Merge reasoner review into primary result.

        For overlapping issues, reasoner's description/severity takes precedence
        so its detailed reasoning is preserved. Reasoner-only issues are appended
        with a flag for downstream tracking.
        """
        merged_issues = []
        primary_issues = primary.get("issues", [])
        reasoner_issues = reasoner.get("issues", [])

        # Build lookup for reasoner issues by (file, line, category)
        reasoner_map: Dict[tuple, Dict] = {}
        for ri in reasoner_issues:
            key = (ri.get("file"), ri.get("line"), ri.get("category"))
            reasoner_map[key] = ri

        for pi in primary_issues:
            key = (pi.get("file"), pi.get("line"), pi.get("category"))
            ri = reasoner_map.pop(key, None)
            if ri:
                # Smart merge: prefer reasoner's refined assessment
                merged = dict(pi)
                if ri.get("description"):
                    merged["description"] = ri["description"]
                if ri.get("severity"):
                    merged["severity"] = ri["severity"]
                merged["reasoner_reviewed"] = True
                merged_issues.append(merged)
            else:
                merged_issues.append(pi)

        # Append reasoner-only issues
        for ri in reasoner_map.values():
            ri_copy = dict(ri)
            ri_copy["reasoner_only"] = True
            merged_issues.append(ri_copy)

        result = dict(primary)
        result["issues"] = merged_issues
        result["reasoner_reviewed"] = True
        return result


class ResilientReviewRouter(ReviewRouter):
    """具备降级能力的审查路由器"""

    async def review(self, prompt: str, pr_size_tokens: int, system_prompt: str | None = None) -> Dict:
        return await self.review_with_fallback(prompt, pr_size_tokens, system_prompt)

    async def review_with_fallback(self, prompt: str, pr_size_tokens: int, system_prompt: str | None = None) -> Dict:
        models = [self.config.get("primary_model") or self.config.get("primary", "deepseek-chat")]
        models += self.config.get("fallback_chain", [])

        last_error = None
        for model in models:
            provider = self._get_provider(model)
            for attempt in range(2):
                try:
                    logger.info("Trying model %s, attempt %s", model, attempt + 1)
                    return await provider.review(prompt, model, system_prompt)
                except RateLimitError:
                    await asyncio.sleep(2 ** attempt)
                except APITimeoutError:
                    if attempt == 1:
                        break  # 切换下一个模型
                except Exception as e:
                    logger.warning("Model %s failed: %s", model, e, exc_info=True)
                    last_error = e
                    if attempt == 1:
                        break

        # 所有模型均不可用：返回降级结果
        logger.error("All models down. Last error: %s", last_error)
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
        if "qwen" in model:
            return self.providers["qwen"]
        return self.providers["deepseek"]
