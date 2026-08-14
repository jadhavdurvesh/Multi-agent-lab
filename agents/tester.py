from __future__ import annotations

import json
from core.parse import extract_file_edits
from .base import BaseAgent

WRITE_SYSTEM = """You are the Tester agent in TDD mode.

Write failing pytest tests from the spec BEFORE the Developer implements.
Tests must fail right now because the feature doesn't exist yet.

Output ONLY a raw JSON array of test files:
[{"path": "tests/test_feature.py", "content": "full test file content"}]

Rules:
- No prose, no markdown fences, no backticks.
- Import from correct module paths (check files_to_create in the spec).
- Cover every item in tests_to_write and edge_cases from the spec.
- Use pytest with clear function names that describe what is checked.
"""


class TesterAgent(BaseAgent):
    name = "tester"

    def __init__(self, router, tasks, fs, terminal,
                 test_command: str = "pytest -q", tdd_mode: bool = False):
        super().__init__(router, tasks, fs)
        self.terminal = terminal
        self.test_command = test_command
        self.tdd_mode = tdd_mode

    def write_tests(self, spec: dict) -> list[dict]:
        user = (
            f"Technical spec:\n{json.dumps(spec, indent=2)}\n\n"
            f"Write failing pytest tests for everything in tests_to_write and edge_cases."
        )
        raw = self.ask(WRITE_SYSTEM, user)
        files = extract_file_edits(raw)
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
