from __future__ import annotations

import json
import re

from .base import BaseAgent

SYSTEM = """You are the Planner agent. Given a task and an architecture analysis,
break the work into a numbered list of concrete, independently testable subtasks.
Respond ONLY as a raw JSON array of objects — no markdown fences, no prose.

Each object must have:
  "id"          integer
  "title"       short name for the subtask
  "description" what to implement, in detail
  "files"       list of file paths the developer should read or create

Example:
[
  {"id": 1, "title": "Add greet function", "description": "Add a greet(name) function to app.py that returns Hello, name!", "files": ["app.py"]},
  {"id": 2, "title": "Add test", "description": "Add test_greet() to tests/test_app.py", "files": ["tests/test_app.py"]}
]"""


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, task: str, architecture: str) -> list[dict]:
        user = f"Task:\n{task}\n\nArchitecture:\n{architecture}"
        raw = self.ask(SYSTEM, user)
        plan = self._parse_plan(raw, task)
        self.tasks.save_tasks(plan)
        return plan

    @staticmethod
    def _parse_plan(raw: str, task: str) -> list[dict]:
        """Parse a JSON plan from model output, same multi-strategy approach
        as DeveloperAgent._parse_edits so fence-wrapping doesn't kill the run.
        """
        text = raw.strip()

        # Strip markdown fences
        fence_match = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence_match:
            text = fence_match.group(1).strip()

        # Direct parse
        try:
            result = json.loads(text)
            if isinstance(result, list) and result:
                return result
        except json.JSONDecodeError:
            pass

        # Extract first [...] from anywhere in the response
        start = text.find("[")
        end = text.rfind("]")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start:end + 1])
                if isinstance(result, list) and result:
                    return result
            except json.JSONDecodeError:
                pass

        # Fallback: one subtask from the whole task string
        print(f"[PLANNER] Warning: could not parse plan JSON. Raw starts with: {raw[:120]!r}")
        return [{"id": 1, "title": task, "description": task, "files": []}]
