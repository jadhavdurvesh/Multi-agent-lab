from __future__ import annotations

from .base import BaseAgent


class TesterAgent(BaseAgent):
    """No LLM call needed here — running the test suite is deterministic.
    Point it at whatever the target repo actually uses via test_command
    (e.g. "npm test", "go test ./...", "python -m pytest -q").
    """
    name = "tester"

    def __init__(self, router, tasks, fs, terminal, test_command: str = "pytest -q"):
        super().__init__(router, tasks, fs)
        self.terminal = terminal
        self.test_command = test_command

    def test(self) -> dict:
        result = self.terminal.run_command(self.test_command)
        self.tasks.log_event(self.name, "test_run", result)
        return {"passed": result["ok"], "stdout": result["stdout"], "stderr": result["stderr"]}
