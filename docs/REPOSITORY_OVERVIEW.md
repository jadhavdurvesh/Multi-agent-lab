# Multi-agent-lab Repository Overview

This repository is a Python-based controller for a multi-agent coding workflow.  
It runs a sequence of AI-assisted agents against a target Git repository to analyze tasks, plan work, implement changes, run tests, review output, and prepare code for pull requests.

## What this project does

The workflow is:

1. **Architect** analyzes repository structure and task impact.
2. **Planner** turns the task into JSON subtasks.
3. **Developer** proposes file edits for each subtask.
4. **Tester** runs a configured test command.
5. **Reviewer** evaluates the diff and requests fixes if needed.

This loop continues until tests pass and review criteria are met (or retry limits are reached).

## Key technologies

- **Python 3** for orchestration and tooling
- **requests** for model API calls
- **PyYAML** for agent/provider configuration
- **python-dotenv** for loading environment variables
- **pytest** for unit tests
- **GitHub Actions** for browser-triggered autonomous runs

## Repository structure

```text
main.py                      CLI entrypoint
agents/                      Role-specific agent logic
core/                        Orchestration, routing, task memory
tools/                       Filesystem, git, terminal adapters
providers/                   OpenAI-compatible provider + mock provider
config/agents.yaml           Provider/model fallback config per agent
tests/                       Unit tests
docs/                        Supporting documentation
```

## Core components

### `main.py`
- Parses CLI arguments (`--repo`, `--task`, `--branch`, `--autonomous`, `--dry-run`, `--test-command`)
- Initializes tool adapters, task manager, model router, and orchestrator
- Executes the run and prints final status

### `core/orchestrator.py`
- Coordinates the full agent pipeline
- Supports **safe mode** (approval prompts) and autonomous mode
- Handles iterative test/review fix cycles
- Commits, pushes, and attempts PR creation (via `gh`) at the end

### `core/model_router.py`
- Loads provider chains from `config/agents.yaml`
- Routes each agent to the first working provider
- Falls back automatically on failures
- Tracks request/token usage in `usage.json`

### `core/task_manager.py`
- Manages run memory under `.agent/` in the target repo
- Stores architecture notes, task plan, and event logs
- Persists model/test events for debugging and auditability

## Agent layer (`agents/`)

- `architect.py`: repository/task analysis
- `planner.py`: structured subtask generation (JSON)
- `developer.py`: edit generation and application
- `tester.py`: deterministic test command execution
- `reviewer.py`: diff review with approval/comments output
- `base.py`: shared model call + event logging helper

## Tool adapters (`tools/`)

- `filesystem.py`: repo-scoped file read/write/list/search with path-escape protection
- `git.py`: branch checkout, diff, commit, push helpers
- `terminal.py`: executes shell commands in repo root with timeout and captured output

## Provider abstraction (`providers/`)

- `openai_compatible.py` implements a generic `/chat/completions` client
- Includes retry logic for transient failures and rate limits
- `MockProvider` supports `--dry-run` to test orchestration flow without real model calls

## Configuration (`config/agents.yaml`)

- Defines provider/model fallback chains per role (`architect`, `planner`, `developer`, `tester`, `reviewer`)
- Uses environment variables for API keys (for example: `OPENROUTER_API_KEY`, `GROQ_API_KEY`, `GEMINI_API_KEY`, `CEREBRAS_API_KEY`)

## Runtime memory in target repo (`.agent/`)

Each run writes to `.agent/` inside the **target repository**:

- `architecture.md` (latest architecture analysis)
- `tasks.json` (latest plan)
- `decisions.md` (append-only decision log hook)
- `history/YYYY-MM-DD.jsonl` (event log for model calls/tests)

## Testing

Run tests from repository root:

```bash
pytest -q
```

Tests validate:
- filesystem/task-memory behaviors
- provider retry logic
- config assumptions

## GitHub Actions workflows

- `agent-run.yml`: runs agents against this repository
- `agent-run-external.yml`: uses this repository as controller and runs agents against a separate target repository

Both workflows:
- install dependencies
- configure git identity
- run `main.py` in autonomous mode
- upload usage/history artifacts

## Typical local usage

```bash
pip install -r requirements.txt
cp .env.example .env
python main.py --repo /path/to/repo --task "Your task"
```

Use `--dry-run --autonomous` to validate control flow without real model costs.
