# AGENTS.md

This repository is a controller for a multi-agent coding workflow.

## Purpose

- Coordinate five agents: Architect → Planner → Developer → Tester → Reviewer.
- Execute tasks against a target Git repository.
- Iterate until tests pass and review gates are satisfied.

## Repository map

- `main.py` — CLI entrypoint for task runs.
- `core/` — orchestration, provider routing, and task memory management.
- `agents/` — role-specific agent logic.
- `tools/` — filesystem, terminal, and git tool adapters.
- `providers/` — model provider integrations (OpenAI-compatible + mock).
- `config/agents.yaml` — provider/model assignments per agent.
- `tests/` — unit tests.

## Local development

1. Install dependencies:
   - `pip install -r requirements.txt`
2. Configure environment:
   - `cp .env.example .env`
   - Add API keys only for providers you use.
3. Adjust agent model/provider config in `config/agents.yaml`.

## Common commands

- Dry run:
  - `python main.py --repo /path/to/repo --task "Your task" --dry-run --autonomous`
- Real run (safe mode prompts enabled by default):
  - `python main.py --repo /path/to/repo --task "Your task"`
- Run tests:
  - `pytest -q`

## Guardrails

- Never commit real credentials; `.env` must stay local.
- Prefer safe mode unless working in a disposable environment.
- Keep changes scoped and minimal when modifying agent behavior.
