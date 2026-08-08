from __future__ import annotations

import json

from .base import BaseAgent

SYSTEM = """You are the Developer agent. You implement one subtask at a time in an
existing codebase. You will be shown relevant file contents. Respond ONLY as a JSON
array of file edits: [{"path": "relative/path.py", "content": "<full new file content>"}]
Only include files you are changing or creating. Preserve existing style and conventions.
No prose, no markdown fences."""


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, subtask: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context(context_files)
        user = (f"Subtask:\n{subtask.get('title')}\n{subtask.get('description', '')}"
                f"\n\nRelevant files:\n{context}")
        return self._call_and_apply(user)

    def fix(self, feedback: str, subtask: dict) -> list[dict]:
        user = f"Your previous change to subtask '{subtask.get('title')}' needs fixes:\n{feedback}"
        return self._call_and_apply(user)

    def _read_context(self, paths: list[str]) -> str:
        chunks = []
        for p in paths:
            try:
                chunks.append(f"### {p}\n{self.fs.read_file(p)}")
            except (FileNotFoundError, ValueError):
                continue
        return "\n\n".join(chunks)

    def _call_and_apply(self, user: str) -> list[dict]:
        raw = self.ask(SYSTEM, user)
        edits = self._parse_edits(raw)
        for edit in edits:
            self.fs.write_file(edit["path"], edit["content"])
        return edits

    @staticmethod
    def _parse_edits(raw: str) -> list[dict]:
        try:
            edits = json.loads(raw)
            return edits if isinstance(edits, list) else []
        except json.JSONDecodeError:
            return []
