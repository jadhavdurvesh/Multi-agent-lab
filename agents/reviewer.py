from __future__ import annotations

import json

from .base import BaseAgent

SYSTEM = """You are the Reviewer agent. You review a git diff for correctness, style,
and missing test coverage. Respond ONLY as JSON: {"approved": true|false, "comments":
["...", "..."]}. No prose, no markdown fences."""


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def __init__(self, router, tasks, fs, git):
        super().__init__(router, tasks, fs)
        self.git = git

    def review(self, base_branch: str = "main") -> dict:
        diff = self.git.diff(base_branch)
        if not diff.strip():
            return {"approved": False, "comments": ["No changes to review."]}
        user = f"Diff:\n{diff[:8000]}"
        raw = self.ask(SYSTEM, user)
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) and "approved" in parsed else \
                {"approved": False, "comments": ["Reviewer output missing 'approved' field."]}
        except json.JSONDecodeError:
            return {"approved": False, "comments": [f"Could not parse reviewer output: {raw[:200]}"]}
