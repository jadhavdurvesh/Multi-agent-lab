from __future__ import annotations

import json
import re

from .base import BaseAgent

SYSTEM = """You are the Developer agent in a multi-agent coding system.

You will receive a TECHNICAL SPEC produced by the Planner agent, plus the
current content of relevant files. Implement exactly what the spec describes.

Your ONLY output is a raw JSON array of file edits:
[
  {"path": "relative/path/to/file.py", "content": "full new file content here"},
  {"path": "another/file.py", "content": "full content here"}
]

Rules:
- Output ONLY the JSON array. No explanation, no markdown fences, no backticks.
- "content" must be the COMPLETE new file content, not a diff or snippet.
- Cover the edge cases listed in the spec.
- Include the tests described in the spec — write them in the appropriate test file.
- If new dependencies are listed, add them to requirements.txt.
- Preserve existing code style and conventions.
- If nothing needs changing, output: []
"""


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, spec: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context(context_files)
        user = self._build_prompt(spec, context)
        return self._call_and_apply(user, spec)

    def fix(self, feedback: str, spec: dict) -> list[dict]:
        user = (
            f"Your previous implementation of '{spec.get('title')}' needs fixes.\n\n"
            f"Original spec approach: {spec.get('approach', '')}\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output the corrected files as a raw JSON array. No fences, no prose."
        )
        return self._call_and_apply(user, spec)

    def _build_prompt(self, spec: dict, context: str) -> str:
        parts = [f"Technical spec:\n{json.dumps(spec, indent=2)}"]
        if context:
            parts.append(f"Current file contents:\n{context}")
        return "\n\n".join(parts)

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
        edits = self._parse_edits(raw)
        if not edits:
            print(f"[DEVELOPER] Warning: no file edits parsed from response for "
                  f"'{spec.get('title')}'. Raw output starts with: {raw[:120]!r}")
        for edit in edits:
            self.fs.write_file(edit["path"], edit["content"])
            print(f"[DEVELOPER] Wrote: {edit['path']}")
        return edits

    @staticmethod
    def _parse_edits(raw: str) -> list[dict]:
        text = raw.strip()
        fence = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            result = json.loads(text)
            return _validate_edits(result)
        except json.JSONDecodeError:
            pass
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                return _validate_edits(json.loads(text[start:end + 1]))
            except json.JSONDecodeError:
                pass
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start:end + 1])
                if isinstance(result, dict) and "path" in result and "content" in result:
                    return [result]
            except json.JSONDecodeError:
                pass
        return []


def _validate_edits(result: object) -> list[dict]:
    if isinstance(result, list):
        return [e for e in result if isinstance(e, dict) and "path" in e and "content" in e]
    if isinstance(result, dict) and "path" in result and "content" in result:
        return [result]
    return []
