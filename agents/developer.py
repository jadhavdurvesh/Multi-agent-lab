from __future__ import annotations

import json
import re

from .base import BaseAgent

# ---------------------------------------------------------------------------
# System prompt – instructs the LLM to output a clean JSON array of file edits.
# Includes explicit escaping rules that many models otherwise forget.
# ---------------------------------------------------------------------------
SYSTEM = """You are the Developer agent in a multi-agent coding system.
Your ONLY output is a raw JSON array of file edits — nothing else.

Format:
[
  {"path": "relative/path/to/file.py", "content": "full new file content here"},
  {"path": "another/file.md", "content": "full content here"}
]

CRITICAL RULES:
- Output ONLY the JSON array. No explanation, no markdown fences, no backticks.
- The "content" value MUST be a valid JSON string.
  - Use double quotes for the string.
  - Escape any double quotes inside the content with \\".
  - Represent newlines as \\n (do NOT put literal newlines inside the string).
  - Escape backslashes as \\\\.
- If the subtask needs no file changes (e.g. it is already done), output: []
- Preserve existing code style and conventions in unchanged parts.
"""


class DeveloperAgent(BaseAgent):
    """Agent that writes code by returning a JSON array of file edits."""

    name = "developer"

    def implement(self, subtask: dict, context_files: list[str]) -> list[dict]:
        """Implement a subtask given a title, description, and context files."""
        context = self._read_context(context_files)
        user = (
            f"Subtask:\n{subtask.get('title')}\n{subtask.get('description', '')}"
            f"\n\nRelevant files:\n{context}"
        )
        return self._call_and_apply(user)

    def fix(self, feedback: str, subtask: dict) -> list[dict]:
        """Fix a previously implemented subtask based on feedback (test failures / review comments)."""
        user = (
            f"Your previous change to subtask '{subtask.get('title')}' needs fixes.\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output the corrected files as a raw JSON array. No fences, no prose."
        )
        return self._call_and_apply(user)

    def _read_context(self, paths: list[str]) -> str:
        """Read the contents of the given file paths and return a single string."""
        chunks = []
        for p in paths:
            try:
                chunks.append(f"### {p}\n{self.fs.read_file(p)}")
            except (FileNotFoundError, ValueError):
                continue
        return "\n\n".join(chunks)

    def _call_and_apply(self, user: str) -> list[dict]:
        """Call the LLM, parse the edits, write files, and return the edit dicts."""
        raw = self.ask(SYSTEM, user)
        edits = self._parse_edits(raw)
        if not edits:
            print(
                f"[DEVELOPER] Warning: no file edits parsed from response. "
                f"Raw output starts with: {raw[:200]!r}"
            )
        else:
            for edit in edits:
                self.fs.write_file(edit["path"], edit["content"])
                print(f"[DEVELOPER] Wrote: {edit['path']}")
        return edits

    # -----------------------------------------------------------------------
    # JSON parsing with multiple recovery strategies
    # -----------------------------------------------------------------------
    @staticmethod
    def _parse_edits(raw: str) -> list[dict]:
        """Parse a JSON array of file edits from model output.

        Models frequently:
          - Wrap JSON in markdown code fences
          - Forget to escape newlines or quotes inside strings
          - Truncate JSON

        This method attempts several repair strategies before giving up.
        """
        text = raw.strip()

        # Strategy 1: strip a surrounding markdown code fence (```json ... ```)
        fence_match = re.search(
            r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL
        )
        if fence_match:
            text = fence_match.group(1).strip()

        # Strategy 2: direct parse
        try:
            return _validate_edits(json.loads(text))
        except json.JSONDecodeError:
            pass

        # Strategy 3: extract the first [...] array from the response
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            chunk = text[start : end + 1]
            try:
                return _validate_edits(json.loads(chunk))
            except json.JSONDecodeError:
                # Attempt to repair common JSON issues (unescaped newlines, etc.)
                repaired = _repair_json(chunk)
                if repaired is not None:
                    return _validate_edits(repaired)

        # Strategy 4: single-object response {...} that contains "path" & "content"
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                obj = json.loads(text[start : end + 1])
                if isinstance(obj, dict) and "path" in obj and "content" in obj:
                    return [obj]
            except json.JSONDecodeError:
                pass

        return []


# ---------------------------------------------------------------------------
# Helper: validate that parsed JSON is the expected list of edit objects
# ---------------------------------------------------------------------------
def _validate_edits(result: object) -> list[dict]:
    """Return only valid edit dicts from a parsed JSON value."""
    if isinstance(result, list):
        return [
            e
            for e in result
            if isinstance(e, dict) and "path" in e and "content" in e
        ]
    if isinstance(result, dict) and "path" in result and "content" in result:
        return [result]
    return []


# ---------------------------------------------------------------------------
# Helper: attempt to repair malformed JSON (newlines, truncation)
# ---------------------------------------------------------------------------
def _repair_json(text: str) -> object | None:
    """Try to fix common JSON errors: unescaped newlines inside strings,
    missing closing brackets. Returns parsed object if successful, else None.
    """
    try:
        # Replace literal newlines inside "content" strings with \\n
        # This regex targets the value of "content" and escapes newlines/quotes.
        fixed = re.sub(
            r'(?<="content":\s*")(.*?)(?="\s*[,}\]])',
            lambda m: m.group(1)
            .replace("\\", "\\\\")   # escape backslashes first
            .replace("\n", "\\n")
            .replace('"', '\\"'),
            text,
            flags=re.DOTALL,
        )
        return json.loads(fixed)
    except (json.JSONDecodeError, TypeError, AttributeError):
        # Second attempt: add missing closing brackets if JSON was truncated
        try:
            if text.count("[") > text.count("]"):
                text += "]" * (text.count("[") - text.count("]"))
            if text.count("{") > text.count("}"):
                text += "}" * (text.count("{") - text.count("}"))
            return json.loads(text)
        except json.JSONDecodeError:
            return None