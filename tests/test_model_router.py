from unittest.mock import MagicMock

from core.model_router import ModelRouter


def test_router_falls_through_to_groq_after_provider_failures():
    router = ModelRouter.__new__(ModelRouter)

    openrouter = MagicMock()
    openrouter.name = "openrouter"
    openrouter.model = "test-openrouter"

    cerebras = MagicMock()
    cerebras.name = "cerebras"
    cerebras.model = "test-cerebras"

    gemini = MagicMock()
    gemini.name = "gemini"
    gemini.model = "test-gemini"

    groq = MagicMock()
    groq.name = "groq"
    groq.model = "test-groq"

    openrouter.complete.side_effect = RuntimeError("404 Not Found")
    cerebras.complete.side_effect = RuntimeError("402 Payment Required")
    gemini.complete.side_effect = RuntimeError("429 Too Many Requests")

    groq.complete.return_value = {
        "text": "Groq succeeded",
        "provider": "groq",
        "model": "test-groq",
        "latency_s": 0.1,
        "prompt_tokens": 10,
        "completion_tokens": 5,
    }

    router.providers = {
        "developer": [
            openrouter,
            cerebras,
            gemini,
            groq,
        ]
    }

    router.usage = {}
    router._record = MagicMock()

    result = router.call(
        "developer",
        "system prompt",
        "user prompt",
    )

    assert result["provider"] == "groq"
    assert result["text"] == "Groq succeeded"

    openrouter.complete.assert_called_once()
    cerebras.complete.assert_called_once()
    gemini.complete.assert_called_once()
    groq.complete.assert_called_once()


def test_router_raises_when_all_providers_fail():
    router = ModelRouter.__new__(ModelRouter)

    providers = []

    for name in [
        "openrouter",
        "cerebras",
        "gemini",
        "groq",
    ]:
        provider = MagicMock()
        provider.name = name
        provider.model = f"test-{name}"
        provider.complete.side_effect = RuntimeError(
            f"{name} failed"
        )
        providers.append(provider)

    router.providers = {
        "developer": providers
    }

    router.usage = {}
    router._record = MagicMock()

    try:
        router.call(
            "developer",
            "system prompt",
            "user prompt",
        )
        assert False, "Expected RuntimeError"
    except RuntimeError as error:
        assert "All providers exhausted" in str(error)

    for provider in providers:
        provider.complete.assert_called_once()
