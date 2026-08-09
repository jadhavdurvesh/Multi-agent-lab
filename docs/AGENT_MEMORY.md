# The `.agent/` directory

Every run creates or reuses a `.agent/` folder **inside the target repo**
(the one you pass to `--repo`, not this controller repo). It's how agents
share context within a run and across repeated runs — `TaskManager`
(`core/task_manager.py`) owns all of it.

```
<target-repo>/.agent/
├── architecture.md   written by the Architect agent each run
├── decisions.md       appended to over time, never overwritten
├── tasks.json          the current plan, written by the Planner
└── history/
    └── YYYY-MM-DD.jsonl   one line per model call or test run, that day
```

## `architecture.md`

Overwritten every run. Whatever the Architect agent's most recent analysis
was — relevant files, what needs to change, what could break. If you want
that context to survive being overwritten, copy anything worth keeping into
`decisions.md` instead.

## `decisions.md`

Append-only. Nothing in this codebase writes to it automatically today —
`TaskManager.append_decision()` exists as a hook for future use (e.g. a
Reviewer or human recording *why* a particular approach was chosen), but no
agent calls it yet. Safe to edit by hand; whatever's in here gets folded
into agent prompts via `TaskManager.read_context()`, though no agent
currently calls `read_context()` either — right now it's a hook for adding
richer prompts later, not something actively wired into a run.

## `tasks.json`

The Planner's output for the current run — a JSON array of subtask objects
(`id`, `title`, `description`, optionally `files`). Overwritten each time
`PlannerAgent.run()` executes, so it reflects the most recent plan, not a
history of every plan ever made.

## `history/*.jsonl`

One file per calendar day (UTC), one JSON line appended per event — every
model call from every agent, plus every test run. This is the actual
record of what happened, and it's the only piece of `.agent/` that
accumulates rather than getting overwritten. Each line looks like:

```json
{"timestamp": "...", "agent": "developer", "event": "model_call",
 "detail": {"text": "...", "provider": "openrouter", "model": "...",
            "latency_s": 0.8, "prompt_tokens": 412, "completion_tokens": 96}}
```

This is what `usage.json` is aggregated from, and it's the first place to
look when a run did something unexpected — find the relevant agent's
`model_call` entry and read the raw `text` the model actually returned.

## Should `.agent/` be committed to the target repo?

Up to you. `architecture.md` and `tasks.json` are cheap to regenerate and
change every run, so treating them as disposable (gitignored) is
reasonable. `history/*.jsonl` is the one part with lasting value — it's
your only record of what each provider/model actually did, which is the
whole point if you're comparing them. If you want that to persist across
runs and machines, commit `history/` and gitignore the rest.
