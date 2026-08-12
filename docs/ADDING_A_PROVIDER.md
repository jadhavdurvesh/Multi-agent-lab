# Adding a New Model Provider

Any service that exposes an OpenAI-compatible `/chat/completions` endpoint
works out of the box — no new Python code needed, just a YAML block and a key.
Providers that use a different API shape need a small subclass.

---

## Case 1: OpenAI-compatible endpoint (most providers)

Works for: OpenRouter, Groq, Together, Cerebras, Mistral, Fireworks,
Perplexity, a local Ollama server, a local vLLM server, etc.

### 1. Add the key to `.env`

```env
MYPROVIDER_API_KEY=sk-...
```

And to your GitHub Actions secrets (Settings → Secrets and variables →
Actions) under the same name.

### 2. Add a block to `config/agents.yaml`

Add it under whichever agent(s) you want it to serve, in fallback order
(first entry is tried first):

```yaml
agents:
  developer:
    providers:
      - provider: openrouter           # existing
        base_url: https://openrouter.ai/api/v1
        api_key_env: OPENROUTER_API_KEY
        model: meta-llama/llama-3.3-70b-instruct:free

      - provider: myprovider           # ← new entry
        base_url: https://api.myprovider.com/v1
        api_key_env: MYPROVIDER_API_KEY
        model: myprovider-model-name
```

`base_url` should point to the root before `/chat/completions` — the
provider class appends that path itself.

### 3. Test without spending quota

```bash
# --dry-run swaps every provider for a MockProvider — no API calls, no keys needed
python main.py --repo /path/to/any/repo --task "add a hello function" \
  --dry-run --autonomous
```

This proves the routing and orchestration work before you involve real
API calls. Then run without `--dry-run` against a throwaway repo to
verify the key and model name are correct.

---

## Case 2: Non-OpenAI-compatible endpoint

If the provider uses a different request/response shape, add a subclass
in `providers/openai_compatible.py`:

```python
class MyProviderClient:
    """Adapter for providers that don't use /chat/completions."""

    def __init__(self, name: str, api_key_env: str, model: str):
        self.name = name
        self.api_key = os.environ.get(api_key_env, "")
        self.model = model

    def complete(self, system: str, user: str, max_tokens: int = 2000) -> dict:
        import time
        start = time.time()
        # Call the provider's actual API here
        resp = requests.post(
            "https://api.myprovider.com/generate",
            headers={"X-API-Key": self.api_key},
            json={"prompt": f"{system}\n\n{user}", "max_tokens": max_tokens},
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()
        return {
            "text": data["output"],                     # adapt to real response shape
            "provider": self.name,
            "model": self.model,
            "latency_s": round(time.time() - start, 2),
            "prompt_tokens": data.get("usage", {}).get("input", 0),
            "completion_tokens": data.get("usage", {}).get("output", 0),
        }
```

Then wire it into `ModelRouter._build_providers()`:

```python
def _build_providers(self) -> dict:
    chains = {}
    for agent_name, cfg in self.config.get("agents", {}).items():
        chain = []
        for option in cfg["providers"]:
            if self.dry_run:
                chain.append(MockProvider(name=option["provider"]))
            elif option["provider"] == "myprovider":          # ← add this branch
                chain.append(MyProviderClient(
                    name=option["provider"],
                    api_key_env=option["api_key_env"],
                    model=option["model"],
                ))
            else:
                chain.append(OpenAICompatibleProvider(...))   # existing
        chains[agent_name] = chain
    return chains
```

---

## Finding free model IDs

Free-tier model lineups rotate — check these before a real run:

- **OpenRouter free models:** openrouter.ai/models → filter by "Free"
  - Model IDs end in `:free` (e.g. `meta-llama/llama-3.3-70b-instruct:free`)
  - These rotate — a model present today may be paywalled next week
- **Groq:** console.groq.com/docs/models
  - More stable free tier, rate-limited (~30 req/min, ~14,400 req/day per model)
  - IDs like `llama-3.3-70b-versatile`, `llama-3.1-8b-instant`
- **Gemini:** aistudio.google.com/app/apikey (free tier via `GEMINI_API_KEY`)
  - Use the OpenAI-compat base URL: `https://generativelanguage.googleapis.com/v1beta/openai`
  - IDs like `gemini-2.0-flash`, `gemini-1.5-flash`
- **Cerebras:** inference.cerebras.ai (free tier, very fast)
  - Base URL: `https://api.cerebras.ai/v1`
  - IDs like `llama3.1-8b`, `llama-3.3-70b`

---

## Comparing providers

Run the same task with different configs using `--dry-run` first to confirm
routing, then real runs. Check `usage.json` afterward — it tracks requests,
prompt tokens, and completion tokens per provider across the run, so you
can see exactly which provider handled which agent and how much it cost.

For a structured comparison: run the same task twice with two different
`config/agents.yaml` configurations, save each `usage.json` as
`usage-config-a.json` / `usage-config-b.json`, and diff them.
The `.agent/history/*.jsonl` log has per-call latency for each provider
if you want finer-grained analysis.
