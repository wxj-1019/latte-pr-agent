import fnmatch
import logging
import re
from typing import Dict, List, Optional

from config.project_config import ReviewConfig, CustomRule

logger = logging.getLogger(__name__)


class RuleEngine:
    """基于 .review-config.yml 的自定义规则引擎。"""

    def __init__(self, config: ReviewConfig):
        self.config = config

    def analyze(self, changed_files: List[str], diff_content: str) -> List[Dict]:
        """对变更文件和 diff 内容执行规则检查。"""
        findings: List[Dict] = []

        # 1. Ignore patterns: filter out matched files from further rule checks
        filtered_files = [
            f for f in changed_files
            if not self._is_ignored(f)
        ]

        # 2. Critical path rules
        for file_path in filtered_files:
            for pattern in self.config.critical_paths:
                if self._match_path(file_path, pattern):
                    findings.append({
                        "file": file_path,
                        "line": 1,
                        "category": "compliance",
                        "severity": "warning",
                        "description": f"文件命中关键路径规则: {pattern}",
                        "confidence": 0.95,
                        "source": "rule_engine",
                        "rule_id": "critical_path",
                    })
                    break  # one finding per file is enough

        # 3. Custom rules
        for rule in self.config.custom_rules:
            for file_path in filtered_files:
                if not self._match_path(file_path, rule.pattern):
                    continue

                # forbidden regex on diff content scoped to this file
                if rule.forbidden:
                    file_diff = self._extract_file_diff(diff_content, file_path)
                    for line_num, line_text in file_diff:
                        if re.search(rule.forbidden, line_text):
                            findings.append({
                                "file": file_path,
                                "line": line_num,
                                "category": "compliance",
                                "severity": rule.severity,
                                "description": rule.message or f"命中规则: {rule.name}",
                                "confidence": 0.90,
                                "source": "rule_engine",
                                "rule_id": rule.name,
                            })

        return findings

    def filter_ignored_files(self, files: List[str]) -> List[str]:
        """返回未被 ignore_patterns 过滤的文件列表。"""
        return [f for f in files if not self._is_ignored(f)]

    def _is_ignored(self, file_path: str) -> bool:
        for pattern in self.config.ignore_patterns:
            if self._match_path(file_path, pattern):
                return True
        return False

    @staticmethod
    def _match_path(file_path: str, pattern: str) -> bool:
        """支持 glob 风格的路径匹配，包括 ** 递归通配符。"""
        # 也支持目录前缀匹配，如 "src/core/" 匹配 "src/core/utils.py"
        if pattern.endswith("/") and file_path.startswith(pattern):
            return True
        # 处理 ** 递归通配符的常见模式
        if "**" in pattern:
            if pattern.endswith("/**/*"):
                prefix = pattern[:-5]  # e.g. "tests/"
                if file_path.startswith(prefix):
                    return True
            if pattern == "**/*" or pattern == "**":
                return True
            if pattern.startswith("**/"):
                suffix = pattern[3:]
                if fnmatch.fnmatch(file_path, suffix):
                    return True
                # 也检查任意前缀
                parts = file_path.split("/")
                for i in range(len(parts)):
                    subpath = "/".join(parts[i:])
                    if fnmatch.fnmatch(subpath, suffix):
                        return True
            regex = (
                pattern
                .replace(".", r"\.")
                .replace("**", "<<<DOUBLESTAR>>>")
                .replace("*", r"[^/]*")
                .replace("?", r".")
                .replace("<<<DOUBLESTAR>>>", ".*")
            )
            if re.fullmatch(regex, file_path):
                return True
        if fnmatch.fnmatch(file_path, pattern):
            return True
        return False

    @staticmethod
    def _extract_file_diff(diff_content: str, target_file: str) -> List[tuple]:
        """从 diff 内容中提取指定文件的变更行（+/- 行）及其行号。

        返回 [(line_number, line_text), ...]
        """
        lines = []
        in_target = False
        current_line = 0

        for line in diff_content.splitlines():
            if line.startswith("diff --git "):
                in_target = target_file in line
                current_line = 0
                continue

            if not in_target:
                continue

            hunk_match = re.match(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,\d+)? @@", line)
            if hunk_match:
                current_line = int(hunk_match.group(1))
                continue

            if line.startswith("+") and not line.startswith("+++"):
                lines.append((current_line, line[1:]))
                current_line += 1
            elif line.startswith("-") and not line.startswith("---"):
                # For forbidden checks, also inspect removed lines
                lines.append((current_line, line[1:]))
            elif not line.startswith("\\"):
                # context line
                if current_line > 0:
                    current_line += 1

        return lines
