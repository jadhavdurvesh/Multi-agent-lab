from __future__ import annotations

import json
from core.parse import extract_file_edits
from .base import BaseAgent

SYSTEM = """You are the Developer agent in a multi-agent coding system.

Your ONLY output is a raw JSON array of file edits — nothing else.

Format:
[
  {"path": "relative/path/to/file.py", "content": "full new file content here"},
  {"path": "another/file.md", "content": "full content here"}
]

Rules:
- Output ONLY the JSON array. No explanation, no markdown fences, no backticks.
- Include ONLY files you are creating or changing.
- "content" must be the COMPLETE new file content, not a diff or snippet.
- Cover the edge cases listed in the spec.
- Include the tests described in the spec in the appropriate test file.
- If new dependencies are listed in the spec, add them to requirements.txt.
- Preserve existing code style and conventions.
- If nothing needs changing, output: []
"""


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, spec: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context(context_files)
        user = f"Technical spec:\n{json.dumps(spec, indent=2)}\n\nCurrent file contents:\n{context}"
        return self._call_and_apply(user, spec)

    def fix(self, feedback: str, spec: dict) -> list[dict]:
        user = (
            f"Your previous implementation of '{spec.get('title')}' needs fixes.\n\n"
            f"Original spec approach: {spec.get('approach', '')}\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output the corrected files as a raw JSON array. No fences, no prose."
        )
        return self._call_and_apply(user, spec)

    def _read_context(self, paths: list[str]) -> str:
        chunks = []
        for p in paths:
            try:
                chunks.append(f"### {p}\n{self.fs.read_file(p)}")
            except (FileNotFoundError, ValueError):
                continue
        return "\n\n".join(chunks)

    def _call_and_apply(self, user: str, spec: dict) -> list[dict]:
        raw = self.ask(SYSTEM, user)
        edits = extract_file_edits(raw)
        if not edits:
            print(f"[DEVELOPER] Warning: no file edits parsed for "
                  f"'{spec.get('title')}'. Raw starts with: {raw[:120]!r}")
        for edit in edits:
            self.fs.write_file(edit["path"], edit["content"])
            print(f"[DEVELOPER] Wrote: {edit['path']}")
        return edits
