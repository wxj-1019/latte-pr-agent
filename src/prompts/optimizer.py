import json
import logging
from typing import Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from prompts.registry import PromptRegistry
from llm import DeepSeekProvider

logger = logging.getLogger(__name__)


OPTIMIZER_SYSTEM_PROMPT = """You are a prompt engineering expert.
Given a code review system prompt and feedback statistics showing which categories have high false-positive rates, generate an improved system prompt.
The improved prompt should:
1. Keep the same JSON output format requirement.
2. Add explicit cautions or extra instructions for the high-FP categories.
3. Remain concise and focused on code review.

Return only the new prompt text (plain string, no markdown wrappers)."""


class AutoPromptOptimizer:
    """基于开发者反馈数据自动优化 Prompt。"""

    HIGH_FP_THRESHOLD = 0.3

    def __init__(self, session: AsyncSession, provider: Optional[DeepSeekProvider] = None):
        self.session = session
        self.provider = provider or DeepSeekProvider()
        self.registry = PromptRegistry(session)

    async def analyze_and_optimize(
        self,
        base_version: str = "v1",
        new_version: str = "v2",
        min_samples: int = 10,
    ) -> Dict:
        """分析 feedback 数据，若发现高 FP 类别则生成优化版 Prompt 并注册为新版本。"""
        await self.registry.load_from_db()
        base_text = self.registry.get_text(base_version)

        stats = await self._fetch_category_fp_rates(min_samples)
        if not stats["high_fp_categories"]:
            return {
                "optimized": False,
                "reason": "未发现高误报率类别",
                "stats": stats,
            }

        optimized_text = await self._generate_prompt(
            base_text, stats["high_fp_categories"], stats["details"]
        )
        await self.registry.save_version(
            version=new_version,
            text=optimized_text,
            metadata={
                "base_version": base_version,
                "triggered_by": stats["high_fp_categories"],
                "fp_details": stats["details"],
            },
        )
        return {
            "optimized": True,
            "new_version": new_version,
            "triggered_by": stats["high_fp_categories"],
            "stats": stats,
            "prompt_preview": optimized_text[:500],
        }

    async def _fetch_category_fp_rates(self, min_samples: int) -> Dict:
        from sqlalchemy import func, select
        from models import DeveloperFeedback, ReviewFinding, Review

        stmt = (
            select(
                ReviewFinding.category,
                func.count(ReviewFinding.id).label("total"),
                func.count(DeveloperFeedback.id).filter(
                    DeveloperFeedback.is_false_positive.is_(True)
                ).label("fp"),
            )
            .join(Review, ReviewFinding.review_id == Review.id)
            .outerjoin(DeveloperFeedback, ReviewFinding.id == DeveloperFeedback.finding_id)
            .where(ReviewFinding.category.isnot(None))
            .group_by(ReviewFinding.category)
        )
        result = await self.session.execute(stmt)
        rows = result.all()

        high_fp = []
        details = []
        for category, total, fp in rows:
            if total < min_samples:
                continue
            fp_rate = fp / total if total else 0.0
            details.append({
                "category": category,
                "total_findings": total,
                "false_positives": fp,
                "fp_rate": round(fp_rate, 4),
            })
            if fp_rate >= self.HIGH_FP_THRESHOLD:
                high_fp.append(category)

        return {"high_fp_categories": high_fp, "details": details}

    async def _generate_prompt(
        self,
        base_prompt: str,
        high_fp_categories: List[str],
        details: List[Dict],
    ) -> str:
        fp_summary = "\n".join(
            f"- {d['category']}: FP rate {d['fp_rate']}% ({d['false_positives']}/{d['total_findings']})"
            for d in details
            if d["category"] in high_fp_categories
        )
        user_msg = (
            f"Current system prompt:\n\n{base_prompt}\n\n"
            f"High false-positive categories:\n{fp_summary}\n\n"
            f"Please generate an improved system prompt that reduces false positives for these categories."
        )
        try:
            text = await self.provider.generate_text(
                messages=[
                    {"role": "system", "content": OPTIMIZER_SYSTEM_PROMPT},
                    {"role": "user", "content": user_msg},
                ],
                model="deepseek-chat",
                temperature=0.3,
                max_tokens=2000,
            ) or base_prompt
            # Strip markdown code blocks if present
            text = text.strip()
            if text.startswith("```"):
                lines = text.splitlines()
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].startswith("```"):
                    lines = lines[:-1]
                text = "\n".join(lines).strip()
            return text
        except Exception as exc:
            logger.exception("Failed to generate optimized prompt: %s", exc)
            return base_prompt
