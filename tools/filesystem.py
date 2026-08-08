"""Filesystem tools available to agents, scoped to a single repo root."""
from __future__ import annotations

from pathlib import Path

IGNORED_DIR_PARTS = {".git", "__pycache__", "node_modules", ".venv", "venv", ".pytest_cache"}


class FileSystemTools:
    def __init__(self, repo_root: str):
        self.root = Path(repo_root).resolve()

    def _resolve(self, rel_path: str) -> Path:
        p = (self.root / rel_path).resolve()
        if self.root != p and self.root not in p.parents:
            raise ValueError(f"Path escapes repo root: {rel_path}")
        return p

    def read_file(self, rel_path: str) -> str:
        return self._resolve(rel_path).read_text(encoding="utf-8")

    def write_file(self, rel_path: str, content: str) -> None:
        p = self._resolve(rel_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")

    def list_files(self, pattern: str = "**/*") -> list[str]:
        results = []
        for p in self.root.glob(pattern):
            if p.is_file() and not any(part in IGNORED_DIR_PARTS for part in p.parts):
                results.append(str(p.relative_to(self.root)))
        return sorted(results)

    def search_code(self, query: str, extensions: tuple = (".py", ".js", ".ts", ".md")) -> dict:
        hits = {}
        for rel in self.list_files():
            if not rel.endswith(extensions):
                continue
            try:
                lines = self._resolve(rel).read_text(encoding="utf-8", errors="ignore").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            matches = [i + 1 for i, line in enumerate(lines) if query.lower() in line.lower()]
            if matches:
                hits[rel] = matches
        return hits
