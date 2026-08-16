"""Terminal access for agents. Commands run with cwd fixed to the repo root —
that scopes accidental damage to the target repo, but it is NOT a sandbox.
See the README safety note before running --autonomous against anything you
don't have a disposable copy of.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


def _truncate(text: str, head: int = 4000, tail: int = 2000) -> str:
    """Truncate large output keeping head+tail — inspired by mini-swe-agent.

    Showing huge test output floods the model context. mini-swe-agent warns
    the model and shows only the beginning and end — enough to diagnose the
    failure without context overflow.
    """
    if len(text) <= head + tail:
        return text
    elided = len(text) - head - tail
    return (
        text[:head]
        + f"\n\n[...{elided} characters elided — output too long...]\n\n"
        + text[-tail:]
    )


class TerminalTools:
    def __init__(self, repo_root: str, timeout: int = 120):
        self.root = Path(repo_root).resolve()
        self.timeout = timeout

    def run_command(self, command: str) -> dict:
        try:
            result = subprocess.run(
                command,
                shell=True,
                cwd=self.root,
                capture_output=True,
                text=True,
                timeout=self.timeout,
            )
            return {
                "command": command,
                "returncode": result.returncode,
                "stdout": _truncate(result.stdout, head=4000, tail=2000),
                "stderr": _truncate(result.stderr, head=2000, tail=1000),
                "ok": result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {
                "command": command,
                "returncode": None,
                "stdout": "",
                "stderr": f"timed out after {self.timeout}s",
                "ok": False,
            }
