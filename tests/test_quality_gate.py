import pytest

from config.project_config import ReviewConfig
from feedback.quality_gate import QualityGate


def test_quality_gate_blocks_on_critical():
    findings = [
        {"file": "a.py", "line": 1, "severity": "critical", "description": "SQLi"},
    ]
    gate = QualityGate(findings, ReviewConfig(block_on_critical=True))
    result = gate.assess()
    assert result["risk_level"] == "critical"
    assert result["status"] == "failure"
    assert "blocked" in result["description"].lower()


def test_quality_gate_allows_critical_when_config_override():
    findings = [
        {"file": "a.py", "line": 1, "severity": "critical", "description": "SQLi"},
    ]
    gate = QualityGate(findings, ReviewConfig(block_on_critical=False))
    result = gate.assess()
    assert result["risk_level"] == "critical"
    assert result["status"] == "success"
    assert "not blocked" in result["description"].lower()


def test_quality_gate_warns_on_warning():
    findings = [
        {"file": "a.py", "line": 1, "severity": "warning", "description": "Style"},
    ]
    gate = QualityGate(findings)
    result = gate.assess()
    assert result["risk_level"] == "medium"
    assert result["status"] == "success"
    assert "Warning" in result["description"]


def test_quality_gate_passes_on_low():
    findings = [
        {"file": "a.py", "line": 1, "severity": "info", "description": "Minor"},
    ]
    gate = QualityGate(findings)
    result = gate.assess()
    assert result["risk_level"] == "low"
    assert result["status"] == "success"
    assert "No blocking" in result["description"]


def test_quality_gate_empty_findings():
    gate = QualityGate([])
    result = gate.assess()
    assert result["risk_level"] == "low"
    assert result["status"] == "success"
