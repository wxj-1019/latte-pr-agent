import json
import shutil
import subprocess
from typing import List


class SemgrepAnalyzer:
    """轻量级静态分析器，MVP 阶段零外部服务依赖"""

    def analyze(self, repo_path: str, changed_files: List[str]) -> List[dict]:
        if not shutil.which("semgrep"):
            return []

        cmd = [
            "semgrep", "--config=auto",
            "--json", "--quiet",
        ] + [f"{repo_path}/{f}" for f in changed_files]

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        except Exception:
            return []

        if result.returncode not in [0, 1]:  # semgrep 发现 issue 时返回 1
            return []

        try:
            findings = json.loads(result.stdout)
        except json.JSONDecodeError:
            return []

        return [
            {
                "file": r["path"].replace(f"{repo_path}/", ""),
                "line": r["start"]["line"],
                "category": "security" if "security" in r["extra"]["metadata"].get("categories", []) else "architecture",
                "severity": r["extra"]["metadata"].get("severity", "warning").lower(),
                "description": r["extra"]["message"],
                "confidence": 0.90,
                "source": "semgrep",
                "rule_id": r["check_id"],
            }
            for r in findings.get("results", [])
        ]
