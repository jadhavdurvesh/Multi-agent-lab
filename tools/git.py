"""Git operations agents use to work in isolated branches."""
from __future__ import annotations

import subprocess
from pathlib import Path


class GitTools:
    def __init__(self, repo_root: str):
        self.root = Path(repo_root).resolve()

    def _run(self, *args: str) -> str:
        result = subprocess.run(["git", *args], cwd=self.root, capture_output=True, text=True)
        if result.returncode != 0:
            raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.strip()

    def current_branch(self) -> str:
        return self._run("rev-parse", "--abbrev-ref", "HEAD")

    def checkout_branch(self, name: str, base: str = "main") -> None:
        exists = self._run("branch", "--list", name)
        if exists:
            self._run("checkout", name)
        else:
            self._run("checkout", "-b", name, base)

    def diff(self, base: str = "main") -> str:
        current = self.current_branch()
        return self._run("diff", f"{base}...{current}")

    def add_all(self) -> None:
        self._run("add", ".")

    def commit(self, message: str) -> str:
        self.add_all()
        # --allow-empty: a subtask that produced no real edits (bad model
        # output, a no-op fix) still needs to commit cleanly rather than
        # crash the whole run on "nothing to commit".
        return self._run("commit", "--allow-empty", "-m", message)

    def push(self, branch: str | None = None, remote: str = "origin") -> str:
        branch = branch or self.current_branch()
        return self._run("push", remote, branch)
