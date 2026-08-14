from __future__ import annotations

import json
from core.parse import extract_object
from .base import BaseAgent

SYSTEM = """You are the Reviewer agent in a multi-agent coding system.

Review the git diff against the technical spec. Check:
- Does the implementation match the stated approach?
- Are the planned tests present and meaningful?
- Are the edge cases from the spec handled?
- Any obvious bugs or missing error handling?

Respond ONLY as JSON:
{
  "approved": true or false,
  "comments": ["specific actionable comment 1", "specific actionable comment 2"]
}

No prose, no markdown fences. Only the JSON object.
"""


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def __init__(self, router, tasks, fs, git):
        super().__init__(router, tasks, fs)
        self.git = git

    def review(self, base_branch: str = "main") -> dict:
        diff = self.git.diff(base_branch)
        if not diff.strip():
            return {"approved": False, "comments": ["Diff is empty — no changes to review."]}
        spec_list = self.tasks.load_tasks()
        spec = spec_list[0] if spec_list else {}
        user = (
            f"Technical spec:\n{json.dumps(spec, indent=2)}\n\n"
            f"Git diff:\n{diff[:8000]}"
        )
        raw = self.ask(SYSTEM, user)
        result = extract_object(raw, required_keys=["approved"])
        if not result:
            return {"approved": False, "comments": [f"Could not parse reviewer output: {raw[:200]}"]}
        return result
