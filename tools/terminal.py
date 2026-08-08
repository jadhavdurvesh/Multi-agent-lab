"""Terminal access for agents. Commands run with cwd fixed to the repo root —
that scopes accidental damage to the target repo, but it is NOT a sandbox.
See the README safety note before running --autonomous against anything you
don't have a disposable copy of.
"""
from __future__ import annotations

import subprocess
from pathlib import Path


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
                "stdout": result.stdout[-8000:],
                "stderr": result.stderr[-4000:],
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
