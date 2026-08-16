"""Tests that config/agents.yaml has the right provider ordering and models.

Groq is primary because it responds in 1-3 seconds vs Gemini's 5-30 seconds.
With 13-16 model calls per run, slow primary providers cause 20-minute timeouts.
"""
from pathlib import Path
import yaml


def _config():
    path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    return yaml.safe_load(path.read_text())


def test_all_agents_have_groq_as_primary():
    """Groq must be first in every agent chain — it is the fastest provider."""
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        first = agent_cfg["providers"][0]["provider"]
        assert first == "groq", (
            f"Agent '{agent_name}' has '{first}' as primary — should be 'groq' "
            f"(Groq responds in 1-3s; slow primaries cause 20-minute timeouts)"
        )


def test_all_agents_have_gemini_fallback():
    """Gemini should appear as a fallback in every agent chain."""
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        providers = [p["provider"] for p in agent_cfg["providers"]]
        assert "gemini" in providers, (
            f"Agent '{agent_name}' has no Gemini fallback: {providers}"
        )


def test_groq_before_gemini_in_all_chains():
    """Groq must come before Gemini in every chain (Groq is primary)."""
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        providers = [p["provider"] for p in agent_cfg["providers"]]
        if "gemini" in providers:
            assert providers.index("groq") < providers.index("gemini"), (
                f"Agent '{agent_name}': groq must come before gemini"
            )


def test_cerebras_model_is_valid():
    """Cerebras model must be one of their supported model IDs."""
    cfg = _config()
    valid = {"llama-3.3-70b", "llama3.1-8b", "llama-3.1-8b"}
    for agent_name, agent_cfg in cfg["agents"].items():
        for p in agent_cfg["providers"]:
            if p["provider"] == "cerebras":
                assert p["model"] in valid, (
                    f"Agent '{agent_name}' cerebras model '{p['model']}' not in {valid}"
                )
