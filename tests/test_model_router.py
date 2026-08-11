"""Tests for ModelRouter fallback and exhaustion behaviour.

The router retries transient errors (429, 5xx) up to 3 times per provider
before moving to the next one. Non-transient errors (404, 402) move straight
to the next provider without retrying. These tests verify both behaviours.
"""
from unittest.mock import MagicMock, patch

from core.model_router import ModelRouter


def _make_router(provider_mocks: dict) -> ModelRouter:
    router = ModelRouter.__new__(ModelRouter)
    router.providers = provider_mocks
    router.usage = {}
    router._record = MagicMock()
    return router


def test_router_falls_through_after_non_transient_failures():
    """404/402 errors move immediately to the next provider (no retries)."""
    openrouter = MagicMock(name="openrouter", model="test-openrouter")
    cerebras = MagicMock(name="cerebras", model="test-cerebras")
    groq = MagicMock(name="groq", model="test-groq")

    openrouter.complete.side_effect = RuntimeError("404 Not Found")
    cerebras.complete.side_effect = RuntimeError("402 Payment Required")
    groq.complete.return_value = {
        "text": "Groq succeeded", "provider": "groq", "model": "test-groq",
        "latency_s": 0.1, "prompt_tokens": 10, "completion_tokens": 5,
    }

    router = _make_router({"developer": [openrouter, cerebras, groq]})

    with patch("time.sleep"):  # don't actually sleep in tests
        result = router.call("developer", "system", "user")

    assert result["provider"] == "groq"
    assert result["text"] == "Groq succeeded"
    openrouter.complete.assert_called_once()
    cerebras.complete.assert_called_once()
    groq.complete.assert_called_once()


def test_router_retries_transient_errors_before_falling_through():
    """429 is transient — the router retries that provider 3 times before
    moving to the next one, so complete() is called 3 times, not 1.
    """
    gemini = MagicMock(name="gemini", model="test-gemini")
    groq = MagicMock(name="groq", model="test-groq")

    gemini.complete.side_effect = RuntimeError("429 Too Many Requests")
    groq.complete.return_value = {
        "text": "Groq succeeded", "provider": "groq", "model": "test-groq",
        "latency_s": 0.1, "prompt_tokens": 10, "completion_tokens": 5,
    }

    router = _make_router({"developer": [gemini, groq]})

    with patch("time.sleep"):
        result = router.call("developer", "system", "user")

    assert result["provider"] == "groq"
    # gemini retried 3 times before the router gave up on it
    assert gemini.complete.call_count == 3
    groq.complete.assert_called_once()


def test_router_raises_when_all_providers_exhausted():
    """RuntimeError with 'All providers exhausted' when every provider fails."""
    providers = []
    for name in ["openrouter", "cerebras", "gemini", "groq"]:
        p = MagicMock(name=name, model=f"test-{name}")
        p.complete.side_effect = RuntimeError(f"{name} failed")
        providers.append(p)

    router = _make_router({"developer": providers})

    with patch("time.sleep"):
        try:
            router.call("developer", "system", "user")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "All providers exhausted" in str(e)
