from typing import Dict


class FeedbackFormatter:
    """将 review_finding 格式化为三段式评论（What/Where/Why/How）"""

    @staticmethod
    def format(finding: Dict) -> str:
        severity = finding.get("severity", "info").upper()
        description = finding.get("description", "")
        evidence = finding.get("evidence", "")
        reasoning = finding.get("reasoning", "")
        suggestion = finding.get("suggestion", "")

        lines = [
            f"**[{severity}]** {description}",
            "",
        ]

        if evidence:
            lines.extend([
                "**证据:**",
                f"```\n{evidence}\n```",
                "",
            ])

        if reasoning:
            lines.extend([
                "**推理:**",
                reasoning,
                "",
            ])

        if suggestion:
            lines.extend([
                "**建议:**",
                suggestion,
            ])

        return "\n".join(lines)

    @staticmethod
    def format_suggestion(finding: Dict) -> str:
        """生成可直接采纳的代码建议块"""
        suggestion = finding.get("suggestion", "")
        return f"```suggestion\n{suggestion}\n```"
