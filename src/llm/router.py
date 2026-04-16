from typing import Dict, Optional

from llm.base import LLMProvider
from llm.deepseek import DeepSeekProvider
from llm.anthropic import AnthropicProvider


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
