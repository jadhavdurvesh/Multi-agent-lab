from __future__ import annotations

import json

from .base import BaseAgent

SYSTEM = """You are the Planner agent in a multi-agent coding system.

Your job is NOT to split the task into many subtasks — the task is already
a single focused unit. Your job is to produce a TECHNICAL SPEC that the
Developer, Tester, and Reviewer agents will all work from.

Given a task description and an architecture analysis, output ONLY a JSON
object with this exact shape:

{
  "title": "short title for the task",
  "approach": "2-4 sentences describing the implementation approach — what pattern to follow, what to avoid, key decisions",
  "files_to_modify": ["list", "of", "existing", "file", "paths", "to", "change"],
  "files_to_create": ["list", "of", "new", "file", "paths", "to", "create"],
  "tests_to_write": ["describe test 1", "describe test 2"],
  "edge_cases": ["edge case or error condition to handle 1", "edge case 2"],
  "dependencies": ["any new pip package needed — empty list if none"]
}

Rules:
- Output ONLY the JSON object. No prose, no markdown fences, no backticks.
- Be concrete and specific — file paths should be real paths from the repo.
- tests_to_write should describe what the tests actually check, not just "write tests".
- If a file does not exist yet, put it in files_to_create, not files_to_modify.
"""


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, task: str, architecture: str) -> dict:
        """Returns a technical spec dict that flows through the whole agent chain."""
        user = f"Task:\n{task}\n\nArchitecture analysis:\n{architecture}"
        raw = self.ask(SYSTEM, user)
        spec = self._parse_spec(raw)
        # Save to task manager so other agents can reference it
        self.tasks.save_tasks([spec])
        return spec

    @staticmethod
    def _parse_spec(raw: str) -> dict:
        import re
        text = raw.strip()
        # Strip markdown fences if present
        fence = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            result = json.loads(text)
            if isinstance(result, dict) and "approach" in result:
                return result
        except json.JSONDecodeError:
            pass
        # Try extracting {} from anywhere in response
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start:end + 1])
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass
        # Fallback: return a minimal spec so the run doesn't crash
        return {
            "title": raw[:80],
            "approach": raw[:300],
            "files_to_modify": [],
            "files_to_create": [],
            "tests_to_write": [],
            "edge_cases": [],
            "dependencies": [],
        }
