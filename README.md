# multi-agent-lab

A small multi-agent coding system. Point it at any local git repo and a task
description; five agents (Architect → Planner → Developer → Tester →
Reviewer) work the task on its own branch, iterating until tests pass and the
diff is approved, then push the branch (and open a PR automatically if the
GitHub CLI `gh` is installed and authenticated).

## Layout

```
agents/       Architect, Planner, Developer, Tester, Reviewer
core/         model_router (provider fallback + usage tracking),
              task_manager (.agent/ project memory in the TARGET repo),
              orchestrator (the run loop + approval gates)
tools/        filesystem, terminal, git — what agents actually act through
providers/    generic OpenAI-compatible provider + a MockProvider for --dry-run
config/       agents.yaml — which provider(s) each agent uses, in fallback order
tests/        unit tests for the tool layer (pytest -q)
```

## Setup

1. `pip install -r requirements.txt`
2. `cp .env.example .env` and fill in keys for whichever providers you use.
3. Edit `config/agents.yaml`. Each agent lists one or more providers tried in
   order, so a second free tier can pick up when the first is rate-limited.
   **The model IDs shipped here are a starting point, not a guarantee** —
   OpenRouter's free-model roster in particular rotates weekly. Check
   openrouter.ai/models (filter: Free), console.groq.com/docs/models, and
   ai.google.dev/gemini-api/docs/models before a real run.

   Any provider with an OpenAI-compatible `/chat/completions` endpoint works
   here without touching `providers/openai_compatible.py` — just add another
   `provider:`/`base_url:`/`api_key_env:`/`model:` block. Gemini (Google AI
   Studio) is wired in as an example, and Cerebras, Together, Mistral, and
   NVIDIA NIM all have genuine no-card free tiers if you want more fallback
   depth — see github.com/cheahjs/free-llm-api-resources for current limits,
   since they change often and some of the "free API" roundups floating
   around are just marketing pages for paid gateways.

## Run

See the control flow for free, no keys needed:

```bash
python main.py --repo /path/to/some/repo --task "Add a health check endpoint" --dry-run --autonomous
```

A real run (safe mode is the default — it asks before implementing and again
before pushing):

```bash
python main.py --repo /path/to/your/repo --task "Add a health check endpoint"
```

Add `--autonomous` to skip both prompts once you trust it. Add
`--test-command "npm test"` (or whatever fits) if the target repo isn't
Python — the Tester agent just runs whatever string you give it.

## What's real vs. what depends on your models

- **Fully working, verified**: filesystem/git/terminal tools, the provider
  router with fallback + usage tracking (`usage.json`), per-event logging
  (`.agent/history/*.jsonl` in the target repo — timestamp, agent, tokens,
  latency, provider, for comparing models afterward), the retry/approval-gate
  loop, and PR creation via `gh` if available.
- **Depends entirely on which models you wire in**: architecture analysis
  quality, plan quality, code edit quality, review judgment. Every agent
  degrades gracefully (skips the edit, requests changes, retries) if a model
  returns something that doesn't parse — it won't crash the run, but it also
  won't write good code for you if the underlying model can't.

## GitHub Actions

Two workflows ship in `.github/workflows/`:

- **`agent-run.yml`** — runs the agents against this repo itself (self-improvement). Trigger from the Actions tab, type a task, it commits/pushes/PRs here.
- **`agent-run-external.yml`** — keeps this repo as the "controller" and points the agents at a *different* repo (your actual product). That repo gets the branch, commits, and PR. Requires a `TARGET_REPO_PAT` secret (a token scoped to the target repo, since the default `GITHUB_TOKEN` can only act on the repo the workflow lives in) — setup instructions are in the workflow file's header comment.

Either way, add `OPENROUTER_API_KEY` / `GROQ_API_KEY` / `GEMINI_API_KEY` as repository secrets first (Settings → Secrets and variables → Actions). Never commit real keys — `.env` is gitignored for local runs.

## Safety note

The Developer and Tester agents run real shell commands and rewrite real
files inside whatever `--repo` you point at. Safe mode is on by default for
that reason. If you do run `--autonomous`, do it against a disposable clone
or inside a container/VM rather than a repo you care about — the tools scope
file writes to the repo root, but that is not a sandbox for the shell
commands the Tester (and any command the Developer's edits trigger) can run.
