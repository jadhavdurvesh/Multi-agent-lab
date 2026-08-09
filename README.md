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

Two workflows in `.github/workflows/` let you trigger a run from the browser
instead of a terminal — useful from a phone, or for kicking off a run without
having your provider keys sitting on a local machine.

### How a run actually works, step by step

1. You go to the **Actions** tab → pick a workflow → **Run workflow** → fill
   in the form (task, branch prefix, test command) → **Run workflow** button.
2. GitHub spins up a fresh Ubuntu runner and checks out the code (both this
   repo and, for the external variant, the target repo too).
3. It installs `requirements.txt`, then runs
   `python main.py --task "<what you typed>" --autonomous` against whichever
   repo is in play. `--autonomous` is hardcoded in both workflows — a
   workflow run can't stop and wait for an `input()` prompt the way a
   terminal run can, so there's no safe-mode pause here. Read that as: only
   dispatch a run with a task you're comfortable with the agents attempting
   unsupervised.
4. The agents do their normal thing — Architect reads the repo, Planner
   breaks the task into subtasks, Developer/Tester/Reviewer iterate per
   subtask — each step logged to `.agent/history/*.jsonl` and `usage.json`
   as it goes, same as a local run.
5. On success, a branch named `<branch input>-<run number>` (e.g.
   `agent/task-7`) gets pushed, and a PR opens automatically via `gh pr
   create` if a token with `pull-requests: write` is available in that job.
6. Either way — pass or fail — the **"Upload run logs"** step attaches
   `usage.json` and `.agent/history/*.jsonl` as a downloadable artifact on
   the run page, so you can see exactly what each agent did and which
   provider/model handled which call, even on a failed run.

### `agent-run.yml` — points the agents at this repo

Self-contained: checks out this repo, agents work on it, PR opens here.
Needs `contents: write` + `pull-requests: write`, which the built-in
`GITHUB_TOKEN` already has for its own repo — no extra secret to set up.

It now supports both:

- **Manual runs** (`workflow_dispatch`) with task/branch/test-command inputs.
- **Hourly runs** (`schedule` at `0 * * * *`) that pull work from an issue queue.

For scheduled runs, task selection is:

1. Query open issues labeled `agent-task` (oldest first).
2. Skip cleanly if no eligible issue exists.
3. Skip cleanly if an open PR already exists on an `agent/task-*` branch (to
   avoid overlapping autonomous streams).
4. Pick one issue, remove `agent-task`, add `agent-task-running`, and use the
   **issue title** as `--task`.

When the run finishes, the workflow marks task status on that issue:

- **Success**: remove `agent-task-running`, add `agent-task-done`, comment with
  the run number.
- **Failure**: remove `agent-task-running`, re-add `agent-task`, comment that it
  was re-queued.

To queue work for automation, open an issue and add the `agent-task` label.
To pause automation, disable the workflow or remove the `schedule` trigger from
`.github/workflows/agent-run.yml`.

### `agent-run-external.yml` — points the agents at a *different* repo

This repo stays the "controller" (supplies the code that runs) while a
separate repo — the one named in the `target_repo` input, `owner/repo` — is
what actually gets read, edited, committed, and PR'd. That needs a
`TARGET_REPO_PAT` secret: the default `GITHUB_TOKEN` can only act on the repo
the workflow lives in, so reaching a different repo requires a real token
scoped to it. Setup is a fine-grained PAT (Contents + Pull requests: Read and
write, repository access limited to the target repo) saved as a repository
secret named `TARGET_REPO_PAT` — full steps are in the workflow file's header
comment.

This workflow now has:

- **Manual mode** (`workflow_dispatch`) with `target_repo` defaulting to
  `jadhavdurvesh/psychic-dollop`.
- **Hourly mode** (`schedule` at `15 * * * *`) that also targets
  `jadhavdurvesh/psychic-dollop` by default.

For scheduled runs in the target repo:

1. The workflow checks for open issues labeled `agent-task` (oldest first).
2. It skips cleanly if none exist.
3. It skips cleanly if an open PR already exists on an `agent/task-*` branch.
4. It moves the selected issue to `agent-task-running` and uses the issue title
   as the task.
5. On success it adds `agent-task-done`; on failure it re-adds `agent-task`.

So to drive automatic hourly work, create issues in
`jadhavdurvesh/psychic-dollop` with the `agent-task` label.

### Secrets either workflow needs

Add whichever of these you actually have keys for under **Settings → Secrets
and variables → Actions**: `OPENROUTER_API_KEY`, `GROQ_API_KEY`,
`GEMINI_API_KEY`, `CEREBRAS_API_KEY`. A missing one isn't an error — that
provider just gets skipped in the fallback chain (see `config/agents.yaml`).
Never commit real keys; `.env` is gitignored for local runs, and these
workflows only ever read keys from Actions secrets, never from a file in the
repo.

## Safety note

The Developer and Tester agents run real shell commands and rewrite real
files inside whatever `--repo` you point at. Safe mode is on by default for
that reason. If you do run `--autonomous`, do it against a disposable clone
or inside a container/VM rather than a repo you care about — the tools scope
file writes to the repo root, but that is not a sandbox for the shell
commands the Tester (and any command the Developer's edits trigger) can run.
