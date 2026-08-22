#!/usr/bin/env python3
"""Entry point: python3 main.py --repo /path/to/repo --task "Add X"

Flags:
  --dry-run      Use MockProvider — no API calls, no keys needed
  --autonomous   Skip approval prompts (required in CI)
  --tdd          TDD mode: Tester writes failing tests before Developer
  --wall-time N  Exit cleanly N seconds before job kill (e.g. 1080 for 20-min job)
  --test-command Override test runner (default: pytest -q)
"""
from __future__ import annotations

import argparse
import os
import sys

from dotenv import load_dotenv


def _check_keys() -> None:
    """Exit with clear instructions if no provider keys are configured."""
    keys = {
        "GROQ_API_KEY":     os.environ.get("GROQ_API_KEY", ""),
        "NVIDIA_API_KEY":   os.environ.get("NVIDIA_API_KEY", ""),
        "GEMINI_API_KEY":   os.environ.get("GEMINI_API_KEY", ""),
        "GEMINI_API_KEY_2": os.environ.get("GEMINI_API_KEY_2", ""),
        "CEREBRAS_API_KEY": os.environ.get("CEREBRAS_API_KEY", ""),
    }
    present = [k for k, v in keys.items() if v]
    if not present:
        print("\n[FATAL] No AI provider API keys found.")
        print("Add at least one to repo Secrets → Actions:")
        print("  GROQ_API_KEY    free → console.groq.com/keys")
        print("  NVIDIA_API_KEY  free → build.nvidia.com  (nvapi-...)")
        print("  GEMINI_API_KEY  free → aistudio.google.com/apikey")
        sys.exit(1)
    print(f"[OK] Keys present: {', '.join(present)}")


def _test_providers() -> None:
    """Quick connectivity check — tries each configured provider with a
    tiny request. Prints which ones work and which fail. Does not abort
    the run — a failing provider just falls through to the next one.
    """
    import requests as _req
    checks = [
        ("Groq",     "GROQ_API_KEY",     "https://api.groq.com/openai/v1",                      "llama-3.1-8b-instant"),
        ("NVIDIA",   "NVIDIA_API_KEY",   "https://integrate.api.nvidia.com/v1",                  "meta/llama-3.1-8b-instruct"),
        ("Gemini",   "GEMINI_API_KEY",   "https://generativelanguage.googleapis.com/v1beta/openai","gemini-2.0-flash"),
        ("Cerebras", "CEREBRAS_API_KEY", "https://api.cerebras.ai/v1",                           "llama-3.1-8b"),
    ]
    print("\n[PROVIDERS] Connectivity check:")
    working = []
    for name, env_var, base_url, model in checks:
        key = os.environ.get(env_var, "")
        if not key:
            print(f"  {name:10s}: skipped (no key)")
            continue
        try:
            r = _req.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 5},
                timeout=10,
            )
            if r.status_code == 200:
                print(f"  {name:10s}: OK ✓")
                working.append(name)
            else:
                print(f"  {name:10s}: HTTP {r.status_code} — {r.text[:80]}")
        except Exception as e:
            print(f"  {name:10s}: {type(e).__name__}: {str(e)[:60]}")

    if not working:
        print("\n[FATAL] No providers responded successfully.")
        print("Check that your API keys are valid and not expired.")
        print("  Groq:   console.groq.com → API Keys")
        print("  NVIDIA: build.nvidia.com → API Key")
        sys.exit(1)
    print(f"[OK] {len(working)} provider(s) working: {', '.join(working)}\n")


def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(description="Multi-agent coding system")
    parser.add_argument("--repo",         required=True,  help="Path to a local git repository")
    parser.add_argument("--task",         required=True,  help="Feature or change to implement")
    parser.add_argument("--branch",       default="agent/task-1")
    parser.add_argument("--autonomous",   action="store_true", help="Skip approval prompts")
    parser.add_argument("--dry-run",      action="store_true", help="Mock providers — no API calls")
    parser.add_argument("--tdd",          action="store_true", help="TDD: Tester writes tests first")
    parser.add_argument("--test-command", default="pytest -q", help="Test runner command")
    parser.add_argument("--wall-time",    type=int, default=0,
                        help="Exit cleanly N seconds before job timeout (e.g. 1080 for 20-min job)")
    args = parser.parse_args()

    if not args.dry_run:
        _check_keys()
        _test_providers()

    from core.model_router import ModelRouter
    from core.orchestrator import Orchestrator
    from core.task_manager import TaskManager
    from tools.filesystem import FileSystemTools
    from tools.git import GitTools
    from tools.terminal import TerminalTools

    fs       = FileSystemTools(args.repo)
    terminal = TerminalTools(args.repo)
    git      = GitTools(args.repo)
    tasks    = TaskManager(args.repo)
    router   = ModelRouter(dry_run=args.dry_run)

    orchestrator = Orchestrator(
        router, tasks, fs, terminal, git,
        safe_mode=not args.autonomous,
        test_command=args.test_command,
        tdd_mode=args.tdd,
        wall_time_limit=getattr(args, "wall_time", 0),
    )

    try:
        result = orchestrator.run(args.task, branch=args.branch)
        print(f"\n[DONE] {result}")
    except Exception as e:
        print(f"\n[ERROR] {type(e).__name__}: {e}")
        print("Check the .agent/history/ logs for the full trace.")
        sys.exit(1)


if __name__ == "__main__":
    main()
