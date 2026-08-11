"""Planner agent.

Its job is NOT to split one task into five subtasks. It is to think
carefully about HOW to implement one specific thing well — producing a
detailed blueprint that the Developer follows. This means the Developer
gets a clear plan (approach, files, edge cases, pitfalls) instead of
just a vague task description.
"""
from __future__ import annotations

import re

from .base import BaseAgent

SYSTEM = """You are the Planner agent in a multi-agent coding system.

You receive:
- A task (one focused feature or change)
- An architecture analysis of the existing codebase

Your job is to produce a detailed IMPLEMENTATION BLUEPRINT for that one task.
Do NOT split it into multiple subtasks. Think deeply about the single best way
to implement it, then describe that plan in detail.

Your output must cover:

1. APPROACH — what strategy to use and why (e.g. "Add a new route in app.py
   using Flask's @app.route decorator, store data in the existing db.py layer")

2. FILES TO CHANGE — exact file paths, and what changes to make in each one
   (e.g. "app.py: add POST /api/shorten route; db.py: add insert_url() function;
   tests/test_app.py: add test_shorten_valid_url() and test_shorten_missing_url()")

3. IMPLEMENTATION DETAILS — the key logic to implement, including:
   - Function signatures
   - Data structures / schema changes
   - Error cases to handle
   - Validation rules

4. WATCH-OUTS — things that could break existing code or tests

Write in clear prose. This goes directly to the Developer as a coding brief.
The Developer will implement everything you describe as a single unit.
Do NOT output JSON. Do NOT create numbered subtask lists."""


class PlannerAgent(BaseAgent):
    name = "planner"

    def run(self, task: str, architecture: str) -> str:
        """Returns a detailed implementation blueprint as a plain string."""
        user = f"Task:\n{task}\n\nArchitecture analysis:\n{architecture}"
        blueprint = self.ask(SYSTEM, user, max_tokens=2000)
        # Save it to project memory so it persists across the run
        self.tasks.log_event("planner", "blueprint", {"task": task, "blueprint": blueprint})
        return blueprint

    @staticmethod
    def extract_file_paths(blueprint: str) -> list[str]:
        """Pull file paths mentioned in the blueprint to pass as context to Developer."""
        paths = re.findall(
            r'\b[\w./][\w./]*\.(?:py|md|yaml|yml|json|txt|html|js|ts|css)\b',
            blueprint
        )
        seen, result = set(), []
        for p in paths:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result[:12]
