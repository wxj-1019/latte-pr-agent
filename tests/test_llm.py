import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm import DeepSeekProvider, AnthropicProvider, ReviewRouter


# ==================== DeepSeek Provider Tests ====================

@pytest.fixture
def mock_openai_response():
    response = MagicMock()
    response.choices = [MagicMock()]
    response.choices[0].message.content = json.dumps({
        "issues": [
            {
                "file": "src/main.py",
                "line": 10,
                "severity": "critical",
                "description": "SQL injection",
                "confidence": 0.95,
            }
        ],
        "summary": "Found 1 issue",
        "risk_level": "high",
    })
    return response


@pytest.mark.asyncio
async def test_deepseek_review_success(mock_openai_response):
    provider = DeepSeekProvider(api_key="fake")
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_openai_response):
        result = await provider.review("Review this code", "deepseek-chat")

    assert result["issues"][0]["severity"] == "critical"
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_deepseek_review_json_repair():
    provider = DeepSeekProvider(api_key="fake")
    broken_response = MagicMock()
    broken_response.choices = [MagicMock()]
    broken_response.choices[0].message.content = '{"issues": [{"file": "a.py", "line": 1, "severity": "warning", "description": "bad"}]}'  # trailing comma would break strict json

    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, return_value=broken_response):
        result = await provider.review("Review this code", "deepseek-chat")

    assert len(result["issues"]) == 1
    assert result["issues"][0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_deepseek_review_retry_then_fail():
    provider = DeepSeekProvider(api_key="fake")
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await provider.review("Review this code", "deepseek-chat")

    assert "error" in result
    assert result["error"] == "json_parse_failed"


# ==================== Anthropic Provider Tests ====================

@pytest.fixture
def mock_anthropic_response():
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = json.dumps({
        "issues": [
            {
                "file": "src/app.py",
                "line": 5,
                "severity": "warning",
                "description": "Refactor needed",
            }
        ],
        "summary": "Minor issue",
        "risk_level": "medium",
    })
    return response


@pytest.mark.asyncio
async def test_anthropic_review_success(mock_anthropic_response):
    provider = AnthropicProvider(api_key="fake")
    with patch.object(provider.client.messages, "create", new_callable=AsyncMock, return_value=mock_anthropic_response):
        result = await provider.review("Review this code", "claude-3-5-sonnet")

    assert result["issues"][0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_anthropic_review_extract_json_block():
    provider = AnthropicProvider(api_key="fake")
    response = MagicMock()
    response.content = [MagicMock()]
    response.content[0].text = "```json\n{\"issues\": [], \"summary\": \"ok\"}\n```"

    with patch.object(provider.client.messages, "create", new_callable=AsyncMock, return_value=response):
        result = await provider.review("Review this code", "claude-3-5-sonnet")

    assert result["summary"] == "ok"
    assert result["issues"] == []


# ==================== Review Router Tests ====================

@pytest.mark.asyncio
async def test_router_uses_claude_for_enterprise():
    from unittest.mock import MagicMock
    mock_anthropic = MagicMock()
    mock_anthropic.review = AsyncMock(return_value={"issues": []})
    router = ReviewRouter(
        config={"primary_model": "claude-3-5-sonnet"},
        providers={"anthropic": mock_anthropic, "deepseek": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=1000)
    mock_anthropic.review.assert_called_once()


@pytest.mark.asyncio
async def test_router_deepseek_default():
    from unittest.mock import MagicMock
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(return_value={"issues": []})
    router = ReviewRouter(
        config={"primary_model": "deepseek-chat"},
        providers={"deepseek": mock_deepseek, "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=1000)
    mock_deepseek.review.assert_called_once_with("code", "deepseek-chat")


@pytest.mark.asyncio
async def test_router_triggers_reasoner_for_critical():
    from unittest.mock import MagicMock
    primary_result = {
        "issues": [
            {"file": "a.py", "line": 1, "severity": "critical", "description": "bug"}
        ]
    }
    reasoner_result = {
        "issues": [
            {"file": "a.py", "line": 1, "severity": "warning", "description": "confirmed"}
        ]
    }
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(side_effect=[primary_result, reasoner_result])
    router = ReviewRouter(
        config={
            "primary_model": "deepseek-chat",
            "enable_reasoner_review": True,
        },
        providers={"deepseek": mock_deepseek, "anthropic": MagicMock()},
    )

    result = await router.review("code", pr_size_tokens=5000)

    assert result.get("reasoner_reviewed") is True
    assert len(result["issues"]) == 1  # merged, duplicates removed


@pytest.mark.asyncio
async def test_router_skips_reasoner_when_disabled():
    from unittest.mock import MagicMock
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(return_value={"issues": [{"severity": "critical"}]})
    router = ReviewRouter(
        config={
            "primary_model": "deepseek-chat",
            "enable_reasoner_review": False,
        },
        providers={"deepseek": mock_deepseek, "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=5000)

    assert result.get("reasoner_reviewed") is None
    assert mock_deepseek.review.call_count == 1


@pytest.mark.asyncio
async def test_router_skips_reasoner_for_large_pr():
    from unittest.mock import MagicMock
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(return_value={"issues": [{"severity": "critical"}]})
    router = ReviewRouter(
        config={
            "primary_model": "deepseek-chat",
            "enable_reasoner_review": True,
        },
        providers={"deepseek": mock_deepseek, "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=20000)

    assert result.get("reasoner_reviewed") is None
    assert mock_deepseek.review.call_count == 1
