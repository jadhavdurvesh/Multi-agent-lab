from unittest.mock import Mock, patch

import requests

from providers.openai_compatible import OpenAICompatibleProvider


def test_complete_retries_on_rate_limit_then_succeeds():
    provider = OpenAICompatibleProvider("test", "https://example.com", "MISSING_KEY", "model-a")

    rate_limited = Mock(status_code=429, headers={})
    success = Mock(status_code=200, headers={})
    success.raise_for_status.return_value = None
    success.json.return_value = {
        "choices": [{"message": {"content": "ok"}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }

    with patch("providers.openai_compatible.requests.post", side_effect=[rate_limited, success]) as post, patch(
        "providers.openai_compatible.time.sleep"
    ) as sleep:
        result = provider.complete("sys", "usr")

    assert result["text"] == "ok"
    assert post.call_count == 2
    sleep.assert_called_once_with(1.0)


def test_complete_does_not_retry_on_404():
    provider = OpenAICompatibleProvider("test", "https://example.com", "MISSING_KEY", "model-a")

    not_found = Mock(status_code=404, headers={})
    err = requests.HTTPError("not found")
    err.response = not_found
    not_found.raise_for_status.side_effect = err

    with patch("providers.openai_compatible.requests.post", return_value=not_found) as post, patch(
        "providers.openai_compatible.time.sleep"
    ) as sleep:
        try:
            provider.complete("sys", "usr")
            assert False, "should have raised HTTPError"
        except requests.HTTPError:
            pass

    assert post.call_count == 1
    sleep.assert_not_called()
