from typing import Dict, List, Optional

from config.project_config import ReviewConfig


class QualityGate:
    """基于 findings 和项目配置判定质量门禁状态。"""

    def __init__(self, findings: List[Dict], config: Optional[ReviewConfig] = None):
        self.findings = findings
        self.config = config or ReviewConfig()

    def assess(self) -> Dict[str, str]:
        """返回包含 risk_level、status、description 的字典。"""
        severities = [f.get("severity", "").lower() for f in self.findings]

        if "critical" in severities:
            risk_level = "high"
            if self.config.block_on_critical:
                return {
                    "risk_level": risk_level,
                    "status": "failure",
                    "description": "Critical issues found. Merge blocked by policy.",
                }
            return {
                "risk_level": risk_level,
                "status": "success",
                "description": "Critical issues found, but merge not blocked (config override).",
            }

        if "warning" in severities:
            return {
                "risk_level": "medium",
                "status": "success",
                "description": "Warning issues found. Review recommended before merge.",
            }

        return {
            "risk_level": "low",
            "status": "success",
            "description": "Review completed. No blocking issues found.",
        }
