"""conftest.py — adds repo root to sys.path for all pytest runs.

Without this, pytest run from the repo root in CI can't find the
core/, agents/, tools/ packages when tests do 'from core.xxx import'.
tests/test_tools.py already has sys.path.insert manually, but
tests/test_model_router.py and tests/test_agent_config.py rely on
the path being set globally.
"""
import sys
from pathlib import Path

# Ensure repo root is always on sys.path regardless of where pytest is invoked
sys.path.insert(0, str(Path(__file__).resolve().parent))
