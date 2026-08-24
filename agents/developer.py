from __future__ import annotations

import re
import json

from .base import BaseAgent

SYSTEM = """You are the Developer agent in a multi-agent coding system.

Output file edits using XML tags — this format never breaks on Python code,
unlike JSON which breaks when code contains newlines or quotes.

For each file to create or modify, use:

<file path="relative/path/to/file.py">
full file content goes here
no escaping needed — write code exactly as it should appear in the file
</file>

Rules:
- Output ONLY the XML file blocks. No prose, no explanation before or after.
- Include the COMPLETE file content — not a diff, not a snippet.
- For new dependencies, include a <file path="requirements.txt"> block.
- Cover the edge cases and tests listed in the spec.
- Preserve existing code style in files you modify.
- If nothing needs changing, output: <no_changes/>
"""


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, spec: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context_windowed(context_files)
        user = (
            f"Technical spec:\n{json.dumps(spec, indent=2)}\n\n"
            f"Current file contents:\n{context}"
        )
        return self._call_and_apply(user, spec)

    def fix(self, feedback: str, spec: dict) -> list[dict]:
        user = (
            f"Your previous implementation of '{spec.get('title')}' needs fixes.\n\n"
            f"Spec approach: {spec.get('approach', '')}\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output corrected files using <file path=\"...\">...</file> XML blocks."
        )
        return self._call_and_apply(user, spec)

    def _read_context_windowed(self, paths: list[str]) -> str:
        chunks = []
        for p in paths:
            try:
                full = self.fs.read_file(p)
                if len(full.splitlines()) > 100:
                    chunks.append(self.fs.read_file_window(p, window=100))
                else:
                    chunks.append(f"### {p}\n{full}")
            except (FileNotFoundError, ValueError):
                chunks.append(f"### {p}\n(new file — does not exist yet)")
        return "\n\n".join(chunks)

    def _call_and_apply(self, user: str, spec: dict) -> list[dict]:
        raw = self.ask(SYSTEM, user)
        edits = self._parse_edits(raw)
        if not edits:
            print(f"[DEVELOPER] Warning: no file edits parsed for "
                  f"'{spec.get('title')}'. Raw starts: {raw[:150]!r}")
        for edit in edits:
            try:
                self.fs.write_file(edit["path"], edit["content"])
                print(f"[DEVELOPER] Wrote: {edit['path']}")
            except SyntaxError as e:
                print(f"[DEVELOPER] Syntax error in {edit['path']}: {e}")
        return edits

    @staticmethod
    def _parse_edits(raw: str) -> list[dict]:
        """Parse <file path="...">content</file> XML blocks.

        This format is immune to the JSON encoding problem where literal
        newlines inside the content field break json.loads. Models generate
        XML file blocks reliably for code-heavy responses.

        Falls back to JSON parsing for backwards compatibility.
        """
        edits = []

        # Primary: XML format
        # Matches <file path="..."> or <file path='...'>
        xml_pattern = re.compile(
            r'<file\s+path=["\']([^"\']+)["\']>\s*(.*?)\s*</file>',
            re.DOTALL,
        )
        for match in xml_pattern.finditer(raw):
            path = match.group(1).strip()
            content = match.group(2)
            # Strip one leading newline if present (common in model output)
            if content.startswith("\n"):
                content = content[1:]
            if path:
                edits.append({"path": path, "content": content})

        if edits:
            return edits

        # Fallback: JSON format (for older responses / other agents)
        # Try to fix the common newline-in-string issue before parsing
        fixed = _repair_json(raw)
        for text in [raw.strip(), fixed]:
            # Strip fences
            fence = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
            if fence:
                text = fence.group(1).strip()
            try:
                result = json.loads(text)
                if isinstance(result, list):
                    return [e for e in result
                            if isinstance(e, dict) and "path" in e and "content" in e]
            except (json.JSONDecodeError, ValueError):
                pass
            # Try extracting array from anywhere in the text
            start, end = text.find("["), text.rfind("]")
            if start != -1 and end > start:
                try:
                    result = json.loads(text[start:end + 1])
                    if isinstance(result, list):
                        return [e for e in result
                                if isinstance(e, dict) and "path" in e and "content" in e]
                except (json.JSONDecodeError, ValueError):
                    pass

        return []


def _repair_json(text: str) -> str:
    """Attempt to fix the most common JSON encoding error: literal newlines
    inside string values. Replaces them with \\n escape sequences.
    This is heuristic and won't fix all cases, but catches the most common
    model output pattern.
    """
    # Find "content": "..." blocks and escape their contents
    def escape_content(m: re.Match) -> str:
        key = m.group(1)
        value = m.group(2)
        # Escape characters that break JSON strings
        value = value.replace("\\", "\\\\")
        value = value.replace('"', '\\"')
        value = value.replace("\n", "\\n")
        value = value.replace("\r", "\\r")
        value = value.replace("\t", "\\t")
        return f'"{key}": "{value}"'

    try:
        return re.sub(
            r'"(content|new_str|old_str)"\s*:\s*"(.*?)"(?=\s*[,}])',
            escape_content,
            text,
            flags=re.DOTALL,
        )
    except Exception:
        return text
