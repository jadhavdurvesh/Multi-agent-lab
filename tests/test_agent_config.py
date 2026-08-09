from pathlib import Path

import yaml


def test_developer_cerebras_fallback_uses_supported_model():
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    config = yaml.safe_load(config_path.read_text())

    providers = config["agents"]["developer"]["providers"]
    cerebras = next(p for p in providers if p["provider"] == "cerebras")
    assert cerebras["model"] == "gemma-4-31b"


def test_planner_and_tester_prefer_gemini_to_reduce_groq_bursts():
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    config = yaml.safe_load(config_path.read_text())

    assert config["agents"]["planner"]["providers"][0]["provider"] == "gemini"
    assert config["agents"]["tester"]["providers"][0]["provider"] == "gemini"


def test_developer_tries_gemini_before_groq():
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    config = yaml.safe_load(config_path.read_text())

    providers = [p["provider"] for p in config["agents"]["developer"]["providers"]]
    assert providers.index("gemini") < providers.index("groq")
