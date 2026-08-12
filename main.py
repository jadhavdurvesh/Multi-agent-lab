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
    parser = argparse.ArgumentParser(description="Multi-agent coding system")
    parser.add_argument("--repo", required=True, help="Path to a local git repository")
    parser.add_argument("--task", required=True, help="Description of the feature/change to implement")
    parser.add_argument("--branch", default="agent/task-1")
    parser.add_argument("--autonomous", action="store_true", help="Skip approval gates (default: safe mode)")
    parser.add_argument("--dry-run", action="store_true", help="Use a mock provider instead of real API calls")
    parser.add_argument("--test-command", default="pytest -q", help="Command the Tester agent runs, e.g. 'npm test'")
    parser.add_argument("--tdd", action="store_true", help="TDD mode: Tester writes failing tests before Developer implements")
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
    )
    result = orchestrator.run(args.task, branch=args.branch)
    print(f"\n[DONE] {result}")


if __name__ == "__main__":
    main()
