from __future__ import annotations

import json

from .base import BaseAgent

SYSTEM = """You are the Reviewer agent in a multi-agent coding system.

You will receive a git diff AND the technical spec the Developer was working
from. Review the diff against the spec — not just for style, but for whether
the implementation actually matches the agreed approach, covers the specified
edge cases, and includes the planned tests.

Respond ONLY as JSON:
{
  "approved": true or false,
  "comments": [
    "specific actionable comment 1",
    "specific actionable comment 2"
  ]
}

Approve if:
- The implementation matches the approach described in the spec
- The edge cases in the spec are handled
- Tests described in the spec are present and meaningful
- No obvious bugs or missing error handling

Request changes if any of those are missing. Be specific — say exactly what
file and what is missing, so the Developer can fix it without guessing.

No prose, no markdown fences, just the JSON object.
"""


class ReviewerAgent(BaseAgent):
    name = "reviewer"

    def __init__(self, router, tasks, fs, git):
        super().__init__(router, tasks, fs)
        self.git = git

    def review(self, base_branch: str = "main") -> dict:
        diff = self.git.diff(base_branch)
        if not diff.strip():
            return {"approved": False, "comments": ["No changes to review — diff is empty."]}

        # Load the spec so the reviewer can check against it
        spec_list = self.tasks.load_tasks()
        spec = spec_list[0] if spec_list else {}

        user = (
            f"Technical spec the Developer was working from:\n"
            f"{json.dumps(spec, indent=2)}\n\n"
            f"Git diff:\n{diff[:8000]}"
        )
        raw = self.ask(SYSTEM, user)
        return self._parse_review(raw)

    @staticmethod
    def _parse_review(raw: str) -> dict:
        import re
        text = raw.strip()
        fence = re.search(r"^```(?:json)?\s*\n?(.*?)\n?```\s*$", text, re.DOTALL)
        if fence:
            text = fence.group(1).strip()
        try:
            parsed = json.loads(text)
            if isinstance(parsed, dict) and "approved" in parsed:
                return parsed
        except json.JSONDecodeError:
            pass
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
                if isinstance(parsed, dict) and "approved" in parsed:
                    return parsed
            except json.JSONDecodeError:
                pass
        return {"approved": False, "comments": [f"Could not parse reviewer output: {raw[:200]}"]}
