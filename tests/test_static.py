import json
import pytest
from unittest.mock import patch, MagicMock

from static import SemgrepAnalyzer, FindingMerger


class TestSemgrepAnalyzer:
    def test_analyze_when_semgrep_not_installed(self):
        analyzer = SemgrepAnalyzer()
        with patch("static.semgrep.shutil.which", return_value=None):
            result = analyzer.analyze("/repo", ["src/main.py"])
        assert result == []

    def test_analyze_success(self):
        analyzer = SemgrepAnalyzer()
        mock_output = {
            "results": [
                {
                    "path": "/repo/src/main.py",
                    "start": {"line": 10},
                    "extra": {
                        "metadata": {"categories": ["security"], "severity": "HIGH"},
                        "message": "Possible SQL injection",
                    },
                    "check_id": "python.sql.security",
                }
            ]
        }
        with patch("static.semgrep.shutil.which", return_value="semgrep"):
            with patch("static.semgrep.subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=1, stdout=json.dumps(mock_output))
                result = analyzer.analyze("/repo", ["src/main.py"])

        assert len(result) == 1
        assert result[0]["file"] == "src/main.py"
        assert result[0]["category"] == "security"
        assert result[0]["severity"] == "high"
        assert result[0]["source"] == "semgrep"

    def test_analyze_subprocess_failure(self):
        analyzer = SemgrepAnalyzer()
        with patch("static.semgrep.shutil.which", return_value="semgrep"):
            with patch("static.semgrep.subprocess.run", side_effect=Exception("boom")):
                result = analyzer.analyze("/repo", ["src/main.py"])
        assert result == []


class TestFindingMerger:
    def test_merge_distinct_findings(self):
        merger = FindingMerger()
        ai = [
            {"file": "a.py", "line": 1, "category": "logic", "description": "bug", "confidence": 0.9}
        ]
        static = [
            {"file": "b.py", "line": 2, "category": "security", "description": "injection", "confidence": 0.8}
        ]
        result = merger.merge(ai, static)
        assert len(result) == 2

    def test_merge_duplicate_boosts_confidence(self):
        merger = FindingMerger()
        ai = [
            {"file": "a.py", "line": 1, "category": "security", "description": "bug", "confidence": 0.85}
        ]
        static = [
            {"file": "a.py", "line": 1, "category": "security", "description": "injection", "confidence": 0.90}
        ]
        result = merger.merge(ai, static)
        assert len(result) == 1
        assert result[0]["confidence"] == 0.90
        assert "semgrep" in result[0]["sources"]

    def test_merge_with_degraded(self):
        merger = FindingMerger()
        result = merger.merge_with_degraded(
            [],
            [{"file": "a.py", "line": 1, "category": "security", "severity": "critical"}],
            degraded=True,
        )
        assert result["degraded"] is True
        assert result["risk_level"] == "high"
        assert "degraded" in result["summary"].lower()
