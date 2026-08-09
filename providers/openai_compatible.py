"""Generic OpenAI-compatible chat-completion provider. Works with OpenRouter,
Groq, Together, Cerebras, a local Ollama/vLLM server in OpenAI-compat mode —
anything exposing POST {base_url}/chat/completions.
"""
from __future__ import annotations

import os
import time

import requests


class OpenAICompatibleProvider:
    def __init__(self, name: str, base_url: str, api_key_env: str, model: str):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.api_key = os.environ.get(api_key_env, "")
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "max_tokens": max_tokens,
        }
        retryable_status_codes = {429, 500, 502, 503, 504}
        max_attempts = 3
        backoff_seconds = 1.0
        last_error = None

        for attempt in range(max_attempts):
            start = time.time()
            try:
                resp = requests.post(f"{self.base_url}/chat/completions", json=payload, headers=headers, timeout=120)
                latency = time.time() - start

                if resp.status_code in retryable_status_codes and attempt < max_attempts - 1:
                    retry_after = resp.headers.get("Retry-After")
                    wait_s = float(retry_after) if retry_after and retry_after.isdigit() else backoff_seconds
                    time.sleep(wait_s)
                    backoff_seconds *= 2
                    continue

                resp.raise_for_status()
                data = resp.json()
                text = data["choices"][0]["message"]["content"]
                usage = data.get("usage", {})
                return {
                    "text": text,
                    "provider": self.name,
                    "model": self.model,
                    "latency_s": round(latency, 2),
                    "prompt_tokens": usage.get("prompt_tokens", 0),
                    "completion_tokens": usage.get("completion_tokens", 0),
                }
            except requests.RequestException as e:
                last_error = e
                status_code = getattr(getattr(e, "response", None), "status_code", None)
                should_retry = status_code is None or status_code in retryable_status_codes
                if should_retry and attempt < max_attempts - 1:
                    time.sleep(backoff_seconds)
                    backoff_seconds *= 2
                    continue
                raise

        if last_error:
            raise last_error
        raise RuntimeError(f"{self.name} failed to produce a completion")


class MockProvider:
    """Returns a canned response so orchestration control-flow can be tested
    for free, without spending real API quota. It does NOT return realistic
    agent output (valid JSON plans/edits/reviews) — every agent is written to
    degrade gracefully when it can't parse a response, so --dry-run proves
    the plumbing works, not that any given model's output will be good.
    """

    def __init__(self, name: str = "mock", model: str = "mock-model"):
        self.name = name
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        return {
            "text": f"[MOCK RESPONSE from {self.name}] system={system[:60]!r} user={user[:60]!r}",
            "provider": self.name,
            "model": self.model,
            "latency_s": 0.01,
            "prompt_tokens": len(system.split()) + len(user.split()),
            "completion_tokens": 20,
        }
