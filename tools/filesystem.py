"""Filesystem tools available to agents, scoped to a single repo root.

Improvements inspired by SWE-agent (Princeton, NeurIPS 2024):
- Linter-gated writes: Python files are syntax-checked before being written.
  If the code is syntactically broken, write_file raises SyntaxError instead
  of silently committing bad code and burning retry cycles on pytest failures.
- Windowed file reader: read_file_window() shows N lines at a time rather than
  dumping whole files. SWE-agent found 100 lines is the sweet spot — enough
  context, not enough to overwhelm the model.
- str_replace: targeted in-place replacement rather than full rewrites. SWE-Edit
  (Microsoft) found that decomposing edits into find-replace ops reduces tokens
  and improves accuracy vs. full-file rewrite.
"""
from __future__ import annotations

import ast
import subprocess
from pathlib import Path

IGNORED_DIR_PARTS = {
    ".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"
}


class FileSystemTools:
    def __init__(self, repo_root: str):
        self.root = Path(repo_root).resolve()

    def _resolve(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if self.root != p and self.root not in p.parents:
            raise ValueError(f"Path escapes repo root: {rel_path}")
        return p

    # ── Core read/write ───────────────────────────────────────────────────────

    def read_file(self, rel_path: str) -> str:
        return self._resolve(rel_path).read_text(encoding="utf-8")

    def read_file_window(self, rel_path: str, start_line: int = 1,
                         window: int = 100) -> str:
        """Return up to ``window`` lines starting at ``start_line`` (1-indexed).

        Inspired by SWE-agent's file viewer: showing 100 lines at a time rather
        than the whole file prevents context overflow and focuses the model on
        the relevant section.
        """
        lines = self._resolve(rel_path).read_text(encoding="utf-8").splitlines()
        total = len(lines)
        start = max(0, start_line - 1)
        end = min(start + window, total)
        header = f"[{rel_path}  lines {start + 1}–{end} of {total}]\n"
        return header + "\n".join(
            f"{i + 1:4d}  {line}" for i, line in enumerate(lines[start:end])
        )

    def write_file(self, rel_path: str, content: str) -> None:
        """Write content to a file, with syntax checking for Python files.

        If the file is .py and the content has a syntax error, raises SyntaxError
        instead of writing — following SWE-agent's principle that bad code should
        never reach the test runner.
        """
        if rel_path.endswith(".py"):
            try:
                ast.parse(content)
            except SyntaxError as e:
                raise SyntaxError(
                    f"Syntax error in {rel_path} — file NOT written: {e}"
                ) from e
        p = self._resolve(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def write_file_checked(self, rel_path: str, content: str) -> dict:
        """Like write_file but returns a status dict instead of raising.

        Useful for the Developer agent — a caught SyntaxError lets the agent
        retry the edit rather than crashing the run.
        """
        try:
            self.write_file(rel_path, content)
            return {"ok": True, "path": rel_path}
        except SyntaxError as e:
            return {"ok": False, "path": rel_path, "error": str(e)}

    # ── str_replace (SWE-Edit / Claude Code style) ────────────────────────────

    def str_replace(self, rel_path: str, old_str: str, new_str: str) -> dict:
        """Replace the first occurrence of old_str with new_str in a file.

        Inspired by SWE-Edit (Microsoft): targeted replacement is more
        token-efficient than full-file rewrites and models make fewer mistakes
        with smaller, focused changes.

        Returns {"ok": True} or {"ok": False, "error": "..."}.
        """
        content = self.read_file(rel_path)
        if old_str not in content:
            return {"ok": False, "error": f"old_str not found in {rel_path}"}
        if content.count(old_str) > 1:
            return {
                "ok": False,
                "error": f"old_str matches {content.count(old_str)} locations — make it unique",
            }
        new_content = content.replace(old_str, new_str, 1)
        return self.write_file_checked(rel_path, new_content)

    # ── Directory listing and search ──────────────────────────────────────────

    def list_files(self, pattern: str = "**/*") -> list[str]:
        results = []
        for p in self.root.glob(pattern):
            if p.is_file() and not any(
                part in IGNORED_DIR_PARTS for part in p.parts
            ):
                results.append(str(p.relative_to(self.root)))
        return sorted(results)

    def search_code(self, query: str,
                    extensions: tuple = (".py", ".js", ".ts", ".md")) -> dict:
        """Return a dict of {file: [matching_line_numbers]}.

        SWE-agent: list only the file names that match, not the full context —
        showing too much context around each match confuses the model.
        """
        hits: dict[str, list[int]] = {}
        for rel in self.list_files():
            if not rel.endswith(extensions):
                continue
            try:
                lines = (
                    self._resolve(rel)
                    .read_text(encoding="utf-8", errors="ignore")
                    .splitlines()
                )
            except (UnicodeDecodeError, OSError):
                continue
            matches = [
                i + 1 for i, line in enumerate(lines)
                if query.lower() in line.lower()
            ]
            if matches:
                hits[rel] = matches
        return hits

    def lint_python(self, rel_path: str) -> dict:
        """Run py_compile (fast) and optionally flake8 on a Python file.

        Returns {"ok": True} or {"ok": False, "errors": [...]}.
        """
        path = self._resolve(rel_path)
        try:
            ast.parse(path.read_text(encoding="utf-8"))
        except SyntaxError as e:
            return {"ok": False, "errors": [str(e)]}
        # Optional: flake8 for style (skipped if not installed)
        try:
            result = subprocess.run(
                ["flake8", "--max-line-length=100", str(path)],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode != 0:
                return {"ok": False, "errors": result.stdout.strip().splitlines()}
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return {"ok": True}
