from typing import List, Dict, Optional


class FindingMerger:
    """合并 AI 审查结果与静态分析结果"""

    def merge(self, ai_findings: List[Dict], static_findings: List[Dict]) -> List[Dict]:
        merged = [self._normalize(af) for af in ai_findings]

        for sf in static_findings:
            sf_norm = self._normalize(sf)
            # 去重：同一位置、同类问题已存在 AI 发现时，以 AI 结果为主，提升 confidence
            duplicate = next(
                (
                    af
                    for af in merged
                    if af.get("file") == sf_norm.get("file")
                    and af.get("line") == sf_norm.get("line")
                    and af.get("category") == sf_norm.get("category")
                ),
                None,
            )
            if duplicate:
                duplicate["confidence"] = min(duplicate.get("confidence", 0.0) + 0.05, 1.0)
                duplicate["sources"] = duplicate.get("sources", []) + [sf_norm.get("source", "semgrep")]
            else:
                merged.append(sf_norm)

        return merged

    def _normalize(self, finding: Dict) -> Dict:
        """确保 finding 包含统一字段"""
        return {
            "file": finding.get("file", ""),
            "line": finding.get("line"),
            "category": finding.get("category", "general"),
            "severity": finding.get("severity", "warning"),
            "description": finding.get("description", ""),
            "suggestion": finding.get("suggestion", ""),
            "confidence": finding.get("confidence", 0.8),
            "sources": finding.get("sources", [finding.get("source", "ai")]),
            "rule_id": finding.get("rule_id", ""),
            **finding,
        }

    def merge_with_degraded(
        self, ai_findings: List[Dict], static_findings: List[Dict], degraded: bool = False
    ) -> Dict:
        """返回包含 merged findings 和 degraded 标记的完整结果"""
        merged = self.merge(ai_findings, static_findings)
        return {
            "issues": merged,
            "degraded": degraded,
            "summary": "审查完成" if not degraded else "AI 模型不可用，仅展示静态分析结果",
            "risk_level": self._assess_risk_level(merged),
        }

    def _assess_risk_level(self, findings: List[Dict]) -> str:
        severities = [f.get("severity", "") for f in findings]
        if "critical" in severities:
            return "high"
        if "warning" in severities:
            return "medium"
        return "low"
