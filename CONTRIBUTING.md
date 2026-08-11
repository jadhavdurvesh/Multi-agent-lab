# 🤝 Contributing to Multi-agent-lab

Thank you for your interest in contributing! Whether it's a bug fix,
a new provider, better docs, or a new agent role, every contribution helps.

---

## 🌟 Ways to Contribute

- 🐛 Reporting bugs (open a GitHub Issue)
- 💡 Suggesting tasks for the agent queue (edit `TASKS.md` and open a PR)
- 🔧 Fixing bugs in the agent or tool layer
- ⚡ Adding a new model provider to `config/agents.yaml` or `providers/`
- 🧪 Writing tests (`tests/` — currently very sparse, help welcome)
- 📚 Improving documentation in `docs/`
- 🤖 Adding a new agent role to `agents/`

---

## 🚀 Getting Started

### 1. Fork and clone

```bash
git clone https://github.com/<your-username>/Multi-agent-lab.git
cd Multi-agent-lab
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Create a branch

Never work directly on `main`.

```bash
git checkout -b fix/your-fix-name
# or
git checkout -b feat/new-provider-name
# or
git checkout -b docs/what-you-are-documenting
```

### 4. Test locally before opening a PR

```bash
# Unit tests (fast, no API keys needed)
pytest tests/ -q

# Full dry run against a local repo (no API keys needed)
python main.py --repo /path/to/any/git/repo --task "describe something small" --dry-run --autonomous
```

---

## 💻 How the codebase is structured

```
agents/       One file per agent role. Each inherits BaseAgent.
              To add a role: add a file here, wire it into Orchestrator.
core/         model_router.py — provider fallback + usage tracking
              task_manager.py — .agent/ memory in the target repo
              orchestrator.py — the run loop
tools/        filesystem.py, terminal.py, git.py — what agents act through
providers/    openai_compatible.py — works with any /chat/completions endpoint
config/       agents.yaml — which model each agent uses, in fallback order
```

---

## 📝 Commit message convention

```
feat: add Cerebras provider fallback
fix: strip markdown fences before parsing developer edits
docs: document the .agent/ memory format
test: add unit test for DeveloperAgent._parse_edits
chore: update requirements.txt
```

---

## 🔀 Pull Request process

1. Make sure `pytest tests/ -q` passes.
2. Push your branch and open a PR against `main`.
3. Include in the PR description:
   - What the change does
   - How you tested it
   - Any provider keys or secrets required (don't include actual key values)

---

## ➕ Adding a new provider

1. Add a block under each relevant agent in `config/agents.yaml`:
   ```yaml
   - provider: your-provider
     base_url: https://api.your-provider.com/v1
     api_key_env: YOUR_PROVIDER_API_KEY
     model: model-name
   ```
2. If the provider isn't OpenAI-compatible, add a subclass in
   `providers/openai_compatible.py` that implements `.complete(system, user)`.
3. Add your key to `.env` locally and to GitHub Actions secrets for CI.
4. Test with `--dry-run` first, then a real run against a throwaway repo.

---

## 🐛 Reporting bugs

Include:
- What command you ran (redact any key values)
- The full output / traceback
- Which providers and models were configured
- Python version and OS

---

## 📜 License

By contributing, you agree your contribution is licensed under the
DMJ Community License (DCL) v1.0 — see `LICENSE.md`.
