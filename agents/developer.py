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

CRITICAL RULES:
- Output ONLY the JSON array. No explanation, no markdown fences, no backticks.
- The "content" value MUST be a valid JSON string:
  - Escape double quotes inside content with \"
  - Represent newlines as \\n (NOT literal newlines inside the string)
  - Escape backslashes as \\\\
- Include ONLY files you are creating or changing.
- "content" must be the COMPLETE new file — not a diff or snippet.
- Preserve existing code style and conventions.
- If the subtask needs no file changes, output: []
"""

# Higher token limit — full file content for a Flask app easily exceeds 2000 tokens.
# 8000 gives enough headroom for most real files without hitting provider limits.
MAX_TOKENS = 8000


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, subtask: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context(context_files)
        user = (
            f"Subtask:\n{subtask.get('title')}\n{subtask.get('description', '')}"
            f"\n\nRelevant files:\n{context if context else '(no existing files — create from scratch)'}"
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
        raw = self.ask(SYSTEM, user, max_tokens=MAX_TOKENS)
        edits = self._parse_edits(raw)
        if not edits:
            print(f"[DEVELOPER] Warning: no edits parsed. Raw starts with: {raw[:200]!r}")
        else:
            for edit in edits:
                self.fs.write_file(edit["path"], edit["content"])
                print(f"[DEVELOPER] Wrote: {edit['path']}")
        return edits

    @staticmethod
    def _parse_edits(raw: str) -> list[dict]:
        text = raw.strip()

        # Strategy 1: strip markdown code fence
        fence_match = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Strategy 2: direct parse
        try:
            return _validate_edits(json.loads(text))
        except json.JSONDecodeError:
            pass

        # Strategy 3: extract first [...] array from anywhere in the response
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            chunk = text[start:end + 1]
            try:
                return _validate_edits(json.loads(chunk))
            except json.JSONDecodeError:
                repaired = _repair_json(chunk)
                if repaired is not None:
                    return _validate_edits(repaired)

        # Strategy 4: single {...} object
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(text[start:end + 1])
                if isinstance(obj, dict) and "path" in obj and "content" in obj:
                    return [obj]
            except json.JSONDecodeError:
                pass

        return []


def _validate_edits(result: object) -> list[dict]:
    if isinstance(result, list):
        return [e for e in result if isinstance(e, dict) and "path" in e and "content" in e]
    if isinstance(result, dict) and "path" in result and "content" in result:
        return [result]
    return []


def _repair_json(text: str) -> object | None:
    try:
        fixed = re.sub(
            r'(?<="content":\s*")(.*?)(?="\s*[,}\]])',
            lambda m: m.group(1)
            .replace("\\", "\\\\")
            .replace("\n", "\\n")
            .replace('"', '\\"'),
            text,
            flags=re.DOTALL,
        )
        return json.loads(fixed)
    except (json.JSONDecodeError, TypeError, AttributeError):
        try:
            if text.count("[") > text.count("]"):
                text += "]" * (text.count("[") - text.count("]"))
            if text.count("{") > text.count("}"):
                text += "}" * (text.count("{") - text.count("}"))
            return json.loads(text)
        except json.JSONDecodeError:
            return None
