from __future__ import annotations

from core.parse import extract_object
from .base import BaseAgent

SYSTEM = """You are the Planner agent in a multi-agent coding system.

Your job is to produce a TECHNICAL SPEC that the Developer, Tester, and
Reviewer agents will all work from. Output ONLY a JSON object:

{
  "title": "short title for the task",
  "approach": "2-4 sentences describing the implementation approach",
  "files_to_modify": ["existing file paths to change"],
  "files_to_create": ["new file paths to create"],
  "tests_to_write": ["describe what each test checks"],
  "edge_cases": ["error conditions to handle"],
  "dependencies": ["new pip packages needed — empty list if none"]
}

No prose, no markdown fences, no backticks. Only the JSON object.
"""


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, task: str, architecture: str) -> dict:
        user = f"Task:\n{task}\n\nArchitecture analysis:\n{architecture}"
        raw = self.ask(SYSTEM, user)
        spec = extract_object(raw, required_keys=["approach"])
        if not spec:
            # Fallback: minimal spec so the run doesn't crash
            spec = {
                "title": task[:80],
                "approach": raw[:300],
                "files_to_modify": [],
                "files_to_create": [],
                "tests_to_write": [],
                "edge_cases": [],
                "dependencies": [],
            }
        self.tasks.save_tasks([spec])
        return spec
