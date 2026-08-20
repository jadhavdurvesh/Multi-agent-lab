"""Tests that config/agents.yaml has correct provider ordering and valid models."""
from pathlib import Path
import yaml


def _config():
    path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    return yaml.safe_load(path.read_text())


def test_all_agents_have_groq_as_primary():
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        first = agent_cfg["providers"][0]["provider"]
        assert first == "groq", (
            f"Agent '{agent_name}' primary is '{first}' — should be 'groq' (fastest free tier)"
        )


def test_all_agents_have_nvidia_as_second():
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        second = agent_cfg["providers"][1]["provider"]
        assert second == "nvidia", (
            f"Agent '{agent_name}' second provider is '{second}' — should be 'nvidia' "
            f"(100+ models, OpenAI-compatible, free at build.nvidia.com)"
        )


def test_nvidia_base_url_correct():
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        for p in agent_cfg["providers"]:
            if p["provider"] == "nvidia":
                assert "integrate.api.nvidia.com/v1" in p["base_url"], (
                    f"Agent '{agent_name}' NVIDIA base_url wrong: {p['base_url']}"
                )
                assert p["api_key_env"] == "NVIDIA_API_KEY", (
                    f"Agent '{agent_name}' NVIDIA key env wrong: {p['api_key_env']}"
                )


def test_groq_before_gemini_in_all_chains():
    cfg = _config()
    for agent_name, agent_cfg in cfg["agents"].items():
        providers = [p["provider"] for p in agent_cfg["providers"]]
        if "gemini" in providers and "groq" in providers:
            assert providers.index("groq") < providers.index("gemini"), (
                f"Agent '{agent_name}': groq must come before gemini"
            )


def test_cerebras_model_is_valid():
    cfg = _config()
    valid = {"llama-3.3-70b", "llama3.1-8b", "llama-3.1-8b"}
    for agent_name, agent_cfg in cfg["agents"].items():
        for p in agent_cfg["providers"]:
            if p["provider"] == "cerebras":
                assert p["model"] in valid, (
                    f"Agent '{agent_name}' cerebras model '{p['model']}' not in {valid}"
                )
