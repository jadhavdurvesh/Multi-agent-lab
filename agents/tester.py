"""Tester agent.

Two jobs:
1. Run the existing test suite and report results
2. If the suite passes but no new tests cover the new feature, write them
"""
from __future__ import annotations

from .base import BaseAgent

WRITE_TESTS_SYSTEM = """You are the Tester agent. The existing test suite just passed.
Your job is to write NEW tests that cover the feature just implemented.

You will be given:
- The implementation blueprint (what was built)
- The current test file contents

Output ONLY a raw JSON array of file edits:
[{"path": "tests/test_app.py", "content": "<full updated test file>"}]

Rules:
- Write tests for the happy path AND error/edge cases
- Do not remove existing tests
- Output the COMPLETE updated test file, not just the new tests
- No markdown fences, no prose — just the JSON array"""


class TesterAgent(BaseAgent):
    name = "tester"

    def __init__(self, router, tasks, fs, terminal, test_command: str = "pytest -q"):
        super().__init__(router, tasks, fs)
        self.terminal = terminal
        self.test_command = test_command

    def test(self) -> dict:
        """Run the test suite and return results."""
        result = self.terminal.run_command(self.test_command)
        self.tasks.log_event(self.name, "test_run", result)
        return {
            "passed": result["ok"],
            "stdout": result["stdout"],
            "stderr": result["stderr"],
        }

    def write_tests(self, blueprint: str, test_files: list[str]) -> list[dict]:
        """After a passing run, write new tests covering the implemented feature."""
        import json
        import re

        context = []
        for p in test_files:
            try:
                context.append(f"### {p}\n{self.fs.read_file(p)}")
            except (FileNotFoundError, ValueError):
                context.append(f"### {p}\n(file does not exist yet — create it)")

        user = (
            f"Implementation blueprint:\n{blueprint}\n\n"
            f"Current test files:\n" + "\n\n".join(context)
        )
        raw = self.ask(WRITE_TESTS_SYSTEM, user, max_tokens=4000)

        # Parse using same fence-stripping strategy as Developer
        text = raw.strip()
        fence = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            edits = json.loads(text)
        except json.JSONDecodeError:
            start, end = text.find("["), text.rfind("]")
            if start != -1 and end > start:
                try:
                    edits = json.loads(text[start:end + 1])
                except json.JSONDecodeError:
                    return []
            else:
                return []

        valid = [e for e in edits if isinstance(e, dict) and "path" in e and "content" in e]
        for edit in valid:
            self.fs.write_file(edit["path"], edit["content"])
            print(f"[TESTER] Wrote tests: {edit['path']}")
        return valid
