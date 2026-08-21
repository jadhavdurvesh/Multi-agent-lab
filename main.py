#!/usr/bin/env python3
"""Entry point: python main.py --repo /path/to/repo --task "Add X"

Safe mode (default) pauses for your approval before implementing and again
before pushing. --autonomous skips both. --dry-run uses a mock provider so
you can see the control flow without spending API quota or needing keys yet.
"""
from __future__ import annotations

import argparse

from dotenv import load_dotenv

from core.model_router import ModelRouter
from core.orchestrator import Orchestrator
from core.task_manager import TaskManager
from tools.filesystem import FileSystemTools
from tools.git import GitTools
from tools.terminal import TerminalTools


def main() -> None:
    load_dotenv()

    # Check for API keys before doing anything else.
    # Without at least one key, every provider call returns 403/401 and the
    # orchestrator raises RuntimeError after ~1 second with no useful message.
    import os as _os
    _keys = {
        "GROQ_API_KEY":     _os.environ.get("GROQ_API_KEY", ""),
        "NVIDIA_API_KEY":   _os.environ.get("NVIDIA_API_KEY", ""),
        "GEMINI_API_KEY":   _os.environ.get("GEMINI_API_KEY", ""),
        "GEMINI_API_KEY_2": _os.environ.get("GEMINI_API_KEY_2", ""),
        "CEREBRAS_API_KEY": _os.environ.get("CEREBRAS_API_KEY", ""),
    }
    _set = [k for k, v in _keys.items() if v]
    if not _set:
        print("\n[FATAL] No AI provider API keys found in environment.")
        print("Add at least ONE of the following as a repository secret in")
        print("Multi-agent-lab → Settings → Secrets and variables → Actions:")
        for k in _keys:
            print(f"  {k}")
        print("\nGroq is fastest and has the most generous free tier.")
        print("Get a free key at: https://console.groq.com/keys")
        import sys as _sys; _sys.exit(1)
    print(f"[OK] Provider keys present: {', '.join(_set)}")

    parser = argparse.ArgumentParser(description="Multi-agent coding system")
    parser.add_argument("--repo", required=True, help="Path to a local git repository")
    parser.add_argument("--task", required=True, help="Description of the feature/change to implement")
    parser.add_argument("--branch", default="agent/task-1")
    parser.add_argument("--autonomous", action="store_true", help="Skip approval gates (default: safe mode)")
    parser.add_argument("--dry-run", action="store_true", help="Use a mock provider instead of real API calls")
    parser.add_argument("--test-command", default="pytest -q", help="Command the Tester agent runs, e.g. 'npm test'")
    parser.add_argument("--tdd", action="store_true", help="TDD mode: Tester writes failing tests before Developer implements")
    parser.add_argument("--wall-time", type=int, default=0, help="Exit cleanly N seconds before job kill. E.g. 1080 for 18-min safety margin inside a 20-min job.")
    args = parser.parse_args()

    fs = FileSystemTools(args.repo)
    terminal = TerminalTools(args.repo)
    git = GitTools(args.repo)
    tasks = TaskManager(args.repo)
    router = ModelRouter(dry_run=args.dry_run)

    orchestrator = Orchestrator(
        router, tasks, fs, terminal, git,
        safe_mode=not args.autonomous,
        test_command=args.test_command,
        tdd_mode=args.tdd,
        wall_time_limit=args.wall_time,
    )
    # Quick connectivity test — call the first available provider with a
    # tiny prompt before spending time on git checkout, architect, etc.
    # This catches bad/expired keys in <5 seconds with a clear message.
    print("[PREFLIGHT] Testing provider connectivity...")
    try:
        test = router.call("architect", "Reply with: OK", "OK")
        print(f"[PREFLIGHT] Connected via {test['provider']} ({test['model']}) in {test['latency_s']}s")
    except RuntimeError as e:
        print(f"\n[PREFLIGHT] Provider test FAILED: {e}")
        print("[PREFLIGHT] All configured providers returned errors.")
        print("  Check your API keys are valid and not expired:")
        print("  GROQ_API_KEY   → console.groq.com/keys (free, most reliable)")
        print("  NVIDIA_API_KEY → build.nvidia.com (free, no card)")
        print("  GEMINI_API_KEY → aistudio.google.com/apikey")
        import sys; sys.exit(1)

    result = orchestrator.run(args.task, branch=args.branch)
    print(f"\n[DONE] {result}")


if __name__ == "__main__":
    main()
