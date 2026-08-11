from __future__ import annotations

import json
import re

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
- Preserve existing code style and conventions in unchanged parts.
- If the subtask needs no file changes (e.g. it is already done), output: []
"""


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, subtask: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context(context_files)
        user = (
            f"Subtask:\n{subtask.get('title')}\n{subtask.get('description', '')}"
            f"\n\nRelevant files:\n{context}"
        )
        return self._call_and_apply(user)

    def fix(self, feedback: str, subtask: dict) -> list[dict]:
        user = (
            f"Your previous change to subtask '{subtask.get('title')}' needs fixes.\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output the corrected files as a raw JSON array. No fences, no prose."
        )
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
        if not edits:
            print(f"[DEVELOPER] Warning: no file edits parsed from response. "
                  f"Raw output starts with: {raw[:120]!r}")
        for edit in edits:
            self.fs.write_file(edit["path"], edit["content"])
            print(f"[DEVELOPER] Wrote: {edit['path']}")
        return edits

    @staticmethod
    def _parse_edits(raw: str) -> list[dict]:
        """Parse a JSON array of file edits from model output.

        Models frequently wrap their JSON in markdown code fences despite
        being told not to. This method strips fences, then tries several
        extraction strategies before giving up.
        """
        text = raw.strip()

        # Strategy 1: strip a surrounding markdown code fence if present.
        # Handles ```json...```, ```...```, and single-line `...`.
        fence_match = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Strategy 2: direct parse of the (now possibly de-fenced) text.
        try:
            result = json.loads(text)
            return _validate_edits(result)
        except json.JSONDecodeError:
            pass

        # Strategy 3: extract the first [...] array from anywhere in the response.
        # Handles responses where the model added prose before or after the JSON.
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start : end + 1])
                return _validate_edits(result)
            except json.JSONDecodeError:
                pass

        # Strategy 4: single-object response ({...}) instead of an array.
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start : end + 1])
                if isinstance(result, dict) and "path" in result and "content" in result:
                    return [result]
            except json.JSONDecodeError:
                pass

        return []


def _validate_edits(result: object) -> list[dict]:
    """Return only valid edit dicts from a parsed value."""
    if isinstance(result, list):
        return [
            e for e in result
            if isinstance(e, dict) and "path" in e and "content" in e
        ]
    if isinstance(result, dict) and "path" in result and "content" in result:
        return [result]
    return []
