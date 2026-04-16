import json
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from llm import DeepSeekProvider, AnthropicProvider, QwenProvider, ReviewRouter, ResilientReviewRouter
from openai import RateLimitError, APITimeoutError


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
    broken_response.choices[0].message.content = '{"issues": [{"file": "a.py", "line": 1, "severity": "warning", "description": "bad"}]}'

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
    assert result["error"] == "api_call_failed"


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
    mock_deepseek.review.assert_called_once_with("code", "deepseek-chat", None)


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
    assert len(result["issues"]) == 1


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


# ==================== Router Defensive Programming Tests ====================

@pytest.mark.asyncio
async def test_router_defensive_against_invalid_result():
    from llm.base import LLMProvider
    mock_deepseek = MagicMock(spec=LLMProvider)
    mock_deepseek.review = AsyncMock(return_value="not a dict")
    router = ReviewRouter(config={"enable_reasoner_review": True}, providers={"deepseek": mock_deepseek, "anthropic": MagicMock()})
    result = await router.review("prompt", pr_size_tokens=100)
    assert result == "not a dict"


# ==================== Resilient Review Router Tests ====================

@pytest.mark.asyncio
async def test_resilient_router_fallback_chain():
    from unittest.mock import MagicMock
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(side_effect=[
        RateLimitError("rate limited", response=MagicMock(), body=None),
        {"issues": [{"severity": "warning"}]}
    ])
    router = ResilientReviewRouter(
        config={"primary": "deepseek-chat", "fallback_chain": []},
        providers={"deepseek": mock_deepseek, "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=100)
    assert result["issues"][0]["severity"] == "warning"
    assert mock_deepseek.review.call_count == 2


@pytest.mark.asyncio
async def test_resilient_router_all_models_down():
    from unittest.mock import MagicMock
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(side_effect=Exception("API down"))
    router = ResilientReviewRouter(
        config={"primary": "deepseek-chat", "fallback_chain": []},
        providers={"deepseek": mock_deepseek, "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=100)
    assert result.get("degraded") is True
    assert "AI 模型服务暂时不可用" in result["summary"]


@pytest.mark.asyncio
async def test_resilient_router_anthropic_fallback():
    from unittest.mock import MagicMock
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(side_effect=APITimeoutError("timeout"))
    mock_anthropic = MagicMock()
    mock_anthropic.review = AsyncMock(return_value={"issues": [{"severity": "info"}]})
    router = ResilientReviewRouter(
        config={"primary": "deepseek-chat", "fallback_chain": ["claude-3-5-sonnet"]},
        providers={"deepseek": mock_deepseek, "anthropic": mock_anthropic},
    )
    result = await router.review("code", pr_size_tokens=100)
    assert result["issues"][0]["severity"] == "info"
    mock_anthropic.review.assert_called_once()


# ==================== Qwen Provider Tests ====================

@pytest.mark.asyncio
async def test_qwen_review_success(mock_openai_response):
    provider = QwenProvider(api_key="fake")
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, return_value=mock_openai_response):
        result = await provider.review("Review this code", "qwen-coder-plus-latest")

    assert result["issues"][0]["severity"] == "critical"
    assert result["risk_level"] == "high"


@pytest.mark.asyncio
async def test_qwen_review_json_repair():
    provider = QwenProvider(api_key="fake")
    broken_response = MagicMock()
    broken_response.choices = [MagicMock()]
    broken_response.choices[0].message.content = '{"issues": [{"file": "a.py", "line": 1, "severity": "warning", "description": "bad"}]}'

    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, return_value=broken_response):
        result = await provider.review("Review this code", "qwen-coder-plus-latest")

    assert len(result["issues"]) == 1
    assert result["issues"][0]["severity"] == "warning"


@pytest.mark.asyncio
async def test_qwen_review_retry_then_fail():
    provider = QwenProvider(api_key="fake")
    with patch.object(provider.client.chat.completions, "create", new_callable=AsyncMock, side_effect=Exception("API error")):
        result = await provider.review("Review this code", "qwen-coder-plus-latest")

    assert "error" in result
    assert result["error"] == "api_call_failed"


@pytest.mark.asyncio
async def test_router_uses_qwen():
    mock_qwen = MagicMock()
    mock_qwen.review = AsyncMock(return_value={"issues": []})
    router = ReviewRouter(
        config={"primary_model": "qwen-coder-plus-latest"},
        providers={"qwen": mock_qwen, "deepseek": MagicMock(), "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=1000)
    mock_qwen.review.assert_called_once_with("code", "qwen-coder-plus-latest", None)


@pytest.mark.asyncio
async def test_resilient_router_qwen_fallback():
    mock_deepseek = MagicMock()
    mock_deepseek.review = AsyncMock(side_effect=APITimeoutError("timeout"))
    mock_qwen = MagicMock()
    mock_qwen.review = AsyncMock(return_value={"issues": [{"severity": "info"}]})
    router = ResilientReviewRouter(
        config={"primary": "deepseek-chat", "fallback_chain": ["qwen-coder-plus-latest"]},
        providers={"deepseek": mock_deepseek, "qwen": mock_qwen, "anthropic": MagicMock()},
    )
    result = await router.review("code", pr_size_tokens=100)
    assert result["issues"][0]["severity"] == "info"
    mock_qwen.review.assert_called_once()
