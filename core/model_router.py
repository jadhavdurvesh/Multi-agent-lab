from __future__ import annotations

import json
from pathlib import Path

import yaml

from providers.openai_compatible import MockProvider, OpenAICompatibleProvider


class ModelRouter:
    def __init__(self, config_path: str = "config/agents.yaml", usage_path: str = "usage.json", dry_run: bool = False):
        self.dry_run = dry_run
        self.usage_path = Path(usage_path)
        with open(config_path) as f:
            self.config = yaml.safe_load(f)
        self.providers = self._build_providers()
        self.usage = self._load_usage()

    def _build_providers(self) -> dict:
        chains = {}
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
        self.usage_path.write_text(json.dumps(self.usage, indent=2))

    def _record(self, result: dict) -> None:
        entry = self.usage.setdefault(result["provider"], {"requests": 0, "prompt_tokens": 0, "completion_tokens": 0})
        entry["requests"] += 1
        entry["prompt_tokens"] += result.get("prompt_tokens", 0)
        entry["completion_tokens"] += result.get("completion_tokens", 0)
        self._save_usage()

    _TRANSIENT = ("429", "500", "502", "503", "504")
    _MAX_RETRIES = 3

    def call(self, agent_name: str, system: str, user: str, max_tokens: int = 2000) -> dict:
        import time
        chain = self.providers.get(agent_name)
        if not chain:
            raise ValueError(f"No provider configured for agent '{agent_name}' in config/agents.yaml")
        last_error = None
        for provider in chain:
            name = getattr(provider, "name", "?")
            is_transient_capable = type(provider).__name__ != "MockProvider"
            attempts = self._MAX_RETRIES if is_transient_capable else 1
            for attempt in range(attempts):
                try:
                    result = provider.complete(system, user, max_tokens=max_tokens)
                    self._record(result)
                    return result
                except Exception as e:
                    last_error = e
                    if any(code in str(e) for code in self._TRANSIENT) and attempt < attempts - 1:
                        wait = 2 ** attempt
                        print(f"[ROUTER] {name} transient error (attempt {attempt+1}/{attempts}): {e}. Retrying in {wait}s...")
                        time.sleep(wait)
                        continue
                    print(f"[ROUTER] {name} failed: {e}. Trying next provider.")
                    break
        raise RuntimeError(f"All providers exhausted for agent '{agent_name}': {last_error}")
