from pathlib import Path

import yaml


def test_developer_cerebras_fallback_uses_supported_model():
    config_path = Path(__file__).resolve().parent.parent / "config" / "agents.yaml"
    config = yaml.safe_load(config_path.read_text())

    providers = config["agents"]["developer"]["providers"]
    cerebras = next(p for p in providers if p["provider"] == "cerebras")
    assert cerebras["model"] == "llama-3.3-70b"
