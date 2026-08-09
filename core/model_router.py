"""Routes each agent to its configured provider(s), with automatic fallback
and usage tracking (usage.json) so you can compare providers/models at the
end of a run.
"""
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

    def call(self, agent_name: str, system: str, user: str) -> dict:
        chain = self.providers.get(agent_name)
        if not chain:
            raise ValueError(f"No provider configured for agent '{agent_name}' in config/agents.yaml")
        last_error = None
        for provider in chain:
            print(
                  f"[ROUTER] Trying {agent_name} via "
                f"{provider.name} ({provider.model})"
                 )
            try:
                result = provider.complete(system, user)
                self._record(result)
                return result
            except Exception as e:  # noqa: BLE001 - quota/rate-limit/network errors all fall through to the next provider
                print(f"[ROUTER] {agent_name} via {provider.name} ({provider.model}) failed: {e}")
                last_error = e
                continue
        raise RuntimeError(f"All providers exhausted for agent '{agent_name}': {last_error}")
