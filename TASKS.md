# Task Queue

This file is the source of truth for the agent task queue.

The `seed-tasks.yml` workflow runs on every push to `main` and on a daily
schedule. It reads this file and creates a GitHub Issue labeled `agent-task`
for each task that doesn't already have a matching open issue. The hourly
`agent-run.yml` workflow picks the oldest open `agent-task` issue, works on
it, and marks it done — so you manage work by editing this file, not by
manually creating issues.

**To add a task:** add a line starting with `- ` under the appropriate
section. Push to main. The seeder creates the issue within minutes.

**To remove a task:** delete or comment out the line. The seeder won't
re-create it if the issue was already closed; if the issue is still open,
close it manually.

---

## Multi-agent-lab (this repo)

- Add a `--max-tokens` CLI flag so callers can override the 2000 default per agent
- Add retry count to the usage.json output per provider so flaky providers are visible in the report
- Write a real test that mocks the OpenAI-compatible endpoint and verifies DeveloperAgent writes files correctly
- Add a `--verbose` flag that prints the full raw model response for each agent call, for debugging parse failures
- Document how to add a new provider in docs/ADDING_A_PROVIDER.md

## psychic-dollop (external target repo)

- Add a `/health` endpoint to app.py that returns `{"status": "ok"}` with a test for it
- Add a `farewell(name)` function alongside `greet()` and test it
- Add a `__version__` string to app.py and expose it in a `/version` endpoint
