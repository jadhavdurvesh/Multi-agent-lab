"""Tests that config/agents.yaml has correct structure and valid providers."""
from pathlib import Path
import yaml


def _config():
    return yaml.safe_load(
        (Path(__file__).resolve().parent.parent / "config" / "agents.yaml").read_text()
    )


def test_all_agents_defined():
    cfg = _config()
    for name in ("architect", "planner", "developer", "tester", "reviewer"):
        assert name in cfg["agents"], f"Missing agent: {name}"


def test_all_agents_have_groq_as_primary():
    cfg = _config()
    for name, acfg in cfg["agents"].items():
        first = acfg["providers"][0]["provider"]
        assert first == "groq", f"Agent '{name}' primary is '{first}', should be 'groq'"


def test_no_discontinued_models():
    """Catch known-discontinued model names before they cause 404 failures."""
    discontinued = [
        "llama-3.1-8b-instant",
        "llama-3.3-70b-versatile",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ]
    cfg = _config()
    for agent_name, acfg in cfg["agents"].items():
        for p in acfg["providers"]:
            model = p.get("model", "")
            for bad in discontinued:
                assert bad not in model, (
                    f"Agent '{agent_name}' provider '{p['provider']}' uses "
                    f"discontinued model '{model}' — update to current model"
                )


def test_all_providers_have_required_keys():
    cfg = _config()
    for agent_name, acfg in cfg["agents"].items():
        for p in acfg["providers"]:
            assert "provider" in p, f"Missing 'provider' in {agent_name}"
            assert "base_url" in p, f"Missing 'base_url' in {agent_name}"
            assert "api_key_env" in p, f"Missing 'api_key_env' in {agent_name}"
            assert "model" in p, f"Missing 'model' in {agent_name}"
