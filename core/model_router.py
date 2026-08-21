"""Routes each agent to its provider chain with fallback, retry, and usage tracking.

Error classification:
  AUTH (401/403)  → bad/expired key — fall through immediately, no retry
  TRANSIENT (429/5xx/529) → rate-limit/overload — retry with backoff, then fall through
  OTHER           → fall through immediately

Usage is tracked in usage.json so you can compare providers after a run.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import yaml

from providers.openai_compatible import MockProvider, OpenAICompatibleProvider

_AUTH      = ("401", "403")
_TRANSIENT = ("429", "500", "502", "503", "504", "529")
_MAX_RETRY = 2   # retry transient errors up to N times per provider


class ModelRouter:
    def __init__(self, config_path: str = "config/agents.yaml",
                 usage_path: str = "usage.json", dry_run: bool = False):
        self.dry_run = dry_run
        self.usage_path = Path(usage_path)
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.providers = self._build_providers()
        self.usage = self._load_usage()

    def _build_providers(self) -> dict:
        chains: dict[str, list] = {}
        for agent_name, cfg in self.config.get("agents", {}).items():
            chain = []
            for option in cfg["providers"]:
                if self.dry_run:
                    chain.append(MockProvider(name=option["provider"]))
                else:
                    chain.append(OpenAICompatibleProvider(
                        name=option["provider"],
                        base_url=option["base_url"],
                        api_key_env=option["api_key_env"],
                        model=option["model"],
                    ))
            chains[agent_name] = chain
        return chains

    def _load_usage(self) -> dict:
        if self.usage_path.exists():
            return json.loads(self.usage_path.read_text())
        return {}

    def _save_usage(self) -> None:
        try:
            self.usage_path.write_text(json.dumps(self.usage, indent=2))
        except OSError:
            pass  # non-fatal — usage tracking shouldn't crash a run

    def _record(self, result: dict) -> None:
        entry = self.usage.setdefault(result["provider"], {
            "requests": 0, "prompt_tokens": 0, "completion_tokens": 0,
            "total_latency_s": 0.0,
        })
        entry["requests"] += 1
        entry["prompt_tokens"] += result.get("prompt_tokens", 0)
        entry["completion_tokens"] += result.get("completion_tokens", 0)
        entry["total_latency_s"] = round(
            entry.get("total_latency_s", 0.0) + result.get("latency_s", 0.0), 2
        )
        self._save_usage()

    def call(self, agent_name: str, system: str, user: str,
             max_tokens: int = 2000) -> dict:
        chain = self.providers.get(agent_name)
        if not chain:
            raise ValueError(
                f"No provider configured for agent '{agent_name}' in config/agents.yaml"
            )

        last_error: Exception | None = None

        for provider in chain:
            name = getattr(provider, "name", "?")
            is_mock = type(provider).__name__ == "MockProvider"

            for attempt in range(1 if is_mock else _MAX_RETRY + 1):
                try:
                    result = provider.complete(system, user, max_tokens=max_tokens)
                    self._record(result)
                    return result

                except Exception as e:
                    last_error = e
                    err_str = str(e)

                    if any(code in err_str for code in _AUTH):
                        # Bad/expired key — no point retrying this provider
                        print(f"[ROUTER] {name}: auth error (key invalid/expired) → next provider")
                        break

                    if any(code in err_str for code in _TRANSIENT):
                        if attempt < _MAX_RETRY:
                            wait = min(2 ** attempt, 8)
                            print(f"[ROUTER] {name}: rate-limited (attempt {attempt+1}/{_MAX_RETRY+1}) → retry in {wait}s")
                            time.sleep(wait)
                            continue
                        print(f"[ROUTER] {name}: rate-limited, retries exhausted → next provider")
                        break

                    # Other error — fall through immediately
                    print(f"[ROUTER] {name}: {e} → next provider")
                    break

        raise RuntimeError(
            f"All providers exhausted for agent '{agent_name}': {last_error}"
        )
