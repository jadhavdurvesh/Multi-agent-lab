from __future__ import annotations

import json
from core.parse import extract_file_edits, extract_object
from .base import BaseAgent

SYSTEM = """You are the Developer agent in a multi-agent coding system.

Before outputting your JSON, write a brief THOUGHT section explaining:
- which files need to change and why
- which edit mode (str_replace vs full write) you will use for each
- any edge cases from the spec you are handling

Then output your JSON array of edits.

You have two editing modes. Choose the right one per file:

MODE A — str_replace (preferred for edits to existing files):
Use when you need to change a specific section of an existing file.
Output a JSON array of str_replace operations:
[
  {"mode": "str_replace", "path": "src/app.py",
   "old_str": "exact text to find (must be unique in the file)",
   "new_str": "replacement text"}
]

MODE B — full write (required for new files or major rewrites):
Output a JSON array of full file writes:
[
  {"mode": "write", "path": "src/new_file.py", "content": "full file content here"}
]

You can mix both modes in one response:
[
  {"mode": "str_replace", "path": "existing.py", "old_str": "...", "new_str": "..."},
  {"mode": "write", "path": "tests/test_new.py", "content": "..."}
]

Rules:
- Output ONLY the JSON array. No prose, no markdown fences, no backticks.
- For str_replace: old_str must appear exactly once in the file.
- For write: content is the COMPLETE file, not a snippet.
- Cover the edge cases and include the tests listed in the spec.
- If new pip packages are needed, add them to requirements.txt with a write operation.
- If nothing needs changing, output: []
"""


class DeveloperAgent(BaseAgent):
    name = "developer"

    def implement(self, spec: dict, context_files: list[str]) -> list[dict]:
        context = self._read_context_windowed(context_files)
        user = f"Technical spec:\n{json.dumps(spec, indent=2)}\n\nRelevant files:\n{context}"
        return self._call_and_apply(user, spec)

    def fix(self, feedback: str, spec: dict) -> list[dict]:
        user = (
            f"Your previous implementation of '{spec.get('title')}' needs fixes.\n\n"
            f"Spec approach: {spec.get('approach', '')}\n\n"
            f"Feedback:\n{feedback}\n\n"
            f"Output a JSON array of str_replace or write operations. No fences, no prose."
        )
        return self._call_and_apply(user, spec)

    def _read_context_windowed(self, paths: list[str]) -> str:
        """Read relevant files using windowed view (100 lines) to avoid context overflow.
        Inspired by SWE-agent's file viewer design.
        """
        chunks = []
        for p in paths:
            try:
                # Use windowed view for large files, full read for small ones
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
        operations = extract_file_edits(raw)
        if not operations:
            print(f"[DEVELOPER] Warning: no operations parsed for "
                  f"'{spec.get('title')}'. Raw starts: {raw[:120]!r}")
            return []

        applied = []
        for op in operations:
            mode = op.get("mode", "write")
            path = op.get("path", "")

            if mode == "str_replace":
                result = self.fs.str_replace(
                    path, op.get("old_str", ""), op.get("new_str", "")
                )
                if result["ok"]:
                    print(f"[DEVELOPER] str_replace: {path}")
                    applied.append(op)
                else:
                    print(f"[DEVELOPER] str_replace FAILED {path}: {result['error']}")
            else:
                result = self.fs.write_file_checked(path, op.get("content", ""))
                if result["ok"]:
                    print(f"[DEVELOPER] wrote: {path}")
                    applied.append(op)
                else:
                    print(f"[DEVELOPER] write FAILED {path}: {result.get('error')}")

        return applied
