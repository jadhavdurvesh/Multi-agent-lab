from unittest.mock import MagicMock, patch
from core.model_router import ModelRouter


def _make_router(provider_mocks: dict) -> ModelRouter:
    router = ModelRouter.__new__(ModelRouter)
    router.providers = provider_mocks
    router.usage = {}
    router._record = MagicMock()
    return router


def test_router_falls_through_after_non_transient_failures():
    """404/402 move immediately to the next provider — no retries."""
    openrouter = MagicMock(name="openrouter", model="test-openrouter")
    cerebras = MagicMock(name="cerebras", model="test-cerebras")
    groq = MagicMock(name="groq", model="test-groq")

    openrouter.complete.side_effect = RuntimeError("404 Not Found")
    cerebras.complete.side_effect = RuntimeError("402 Payment Required")
    groq.complete.return_value = {
        "text": "Groq succeeded", "provider": "groq", "model": "test-groq",
        "latency_s": 0.1, "prompt_tokens": 10, "completion_tokens": 5,
    }

    with patch("time.sleep"):
        result = _make_router({"developer": [openrouter, cerebras, groq]}).call(
            "developer", "system", "user"
        )

    assert result["provider"] == "groq"
    openrouter.complete.assert_called_once()
    cerebras.complete.assert_called_once()
    groq.complete.assert_called_once()


def test_router_retries_transient_errors_then_falls_through():
    """429 is transient — retried 3x per provider before moving on."""
    gemini = MagicMock(name="gemini", model="test-gemini")
    groq = MagicMock(name="groq", model="test-groq")

    gemini.complete.side_effect = RuntimeError("429 Too Many Requests")
    groq.complete.return_value = {
        "text": "Groq succeeded", "provider": "groq", "model": "test-groq",
        "latency_s": 0.1, "prompt_tokens": 10, "completion_tokens": 5,
    }

    with patch("time.sleep"):
        result = _make_router({"developer": [gemini, groq]}).call(
            "developer", "system", "user"
        )

    assert result["provider"] == "groq"
    assert gemini.complete.call_count == 3   # retried 3x before falling through
    groq.complete.assert_called_once()


def test_router_raises_when_all_providers_exhausted():
    providers = []
    for name in ["openrouter", "cerebras", "gemini", "groq"]:
        p = MagicMock(name=name, model=f"test-{name}")
        p.complete.side_effect = RuntimeError(f"{name} failed")
        providers.append(p)

    with patch("time.sleep"):
        try:
            _make_router({"developer": providers}).call("developer", "system", "user")
            assert False, "Expected RuntimeError"
        except RuntimeError as e:
            assert "All providers exhausted" in str(e)
