from __future__ import annotations

import json
import re

from .base import BaseAgent

WRITE_SYSTEM = """You are the Tester agent in TDD mode.

Given a technical spec, write failing pytest tests BEFORE the Developer
implements anything. The tests must fail right now because the feature
doesn't exist yet — that's the point.

Output ONLY a raw JSON array of test files:
[
  {"path": "tests/test_feature.py", "content": "full test file content"}
]

Rules:
- Output ONLY the JSON array. No prose, no markdown fences, no backticks.
- Import from the correct module paths (check files_to_create/files_to_modify in the spec).
- Cover every item in tests_to_write from the spec.
- Cover the edge_cases listed in the spec.
- Use pytest. Use clear test function names that describe what they check.
- Tests must reference functions/classes that don't exist yet — that's intentional.
"""


class TesterAgent(BaseAgent):
    name = "tester"

    def __init__(self, router, tasks, fs, terminal, test_command: str = "pytest -q",
                 tdd_mode: bool = False):
        super().__init__(router, tasks, fs)
        self.terminal = terminal
        self.test_command = test_command
        self.tdd_mode = tdd_mode

    def write_tests(self, spec: dict) -> list[dict]:
        """TDD mode only — write failing tests from the spec before Developer runs."""
        user = (
            f"Technical spec:\n{json.dumps(spec, indent=2)}\n\n"
            f"Write failing pytest tests for everything in tests_to_write and edge_cases."
        )
        raw = self.ask(WRITE_SYSTEM, user)
        files = self._parse_files(raw)
        if not files:
            print(f"[TESTER] Warning: no test files parsed. Raw: {raw[:120]!r}")
        for f in files:
            self.fs.write_file(f["path"], f["content"])
            print(f"[TESTER] Wrote test: {f['path']}")
        return files

    def test(self) -> dict:
        result = self.terminal.run_command(self.test_command)
        self.tasks.log_event(self.name, "test_run", result)
        return {
            "passed": result["ok"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    @staticmethod
    def _parse_files(raw: str) -> list[dict]:
        text = raw.strip()
        fence = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        for start_c, end_c in [("[", "]"), ("{", "}")]:
            start, end = text.find(start_c), text.rfind(end_c)
            if start != -1 and end > start:
                try:
                    result = json.loads(text[start:end + 1])
                    if isinstance(result, dict):
                        result = [result]
                    return [f for f in result
                            if isinstance(f, dict) and "path" in f and "content" in f]
                except json.JSONDecodeError:
                    continue
        return []
