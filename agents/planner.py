from __future__ import annotations

import json

from .base import BaseAgent

SYSTEM = """You are the Planner agent. Given a task and an architecture analysis,
break the work into a numbered list of concrete, independently testable subtasks.
Respond ONLY as a JSON array of objects, each with "id", "title", "description",
and optionally "files" (a list of relevant file paths). No prose, no markdown fences."""


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, task: str, architecture: str) -> list[dict]:
        user = f"Task:\n{task}\n\nArchitecture:\n{architecture}"
        raw = self.ask(SYSTEM, user)
        try:
            plan = json.loads(raw)
        except json.JSONDecodeError:
            # Model didn't return clean JSON — fall back to one subtask
            # rather than crash the run.
            plan = [{"id": 1, "title": task, "description": raw, "files": []}]
        self.tasks.save_tasks(plan)
        return plan
