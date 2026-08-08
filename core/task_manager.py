"""Manages persistent project memory inside the TARGET repo's .agent/
directory (project.md, architecture.md, decisions.md, tasks.json, history/)
so agents share context across a run instead of starting from zero each time.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path


class TaskManager:
    def __init__(self, repo_root: str):
        self.root = Path(repo_root).resolve()
        self.agent_dir = self.root / ".agent"
        self.agent_dir.mkdir(exist_ok=True)
        (self.agent_dir / "history").mkdir(exist_ok=True)
        self.tasks_path = self.agent_dir / "tasks.json"

    def read_context(self) -> str:
        parts = []
        for name in ("project.md", "architecture.md", "decisions.md"):
            f = self.agent_dir / name
            if f.exists():
                parts.append(f"## {name}\n{f.read_text()}")
        return "\n\n".join(parts)

    def write_architecture(self, content: str) -> None:
        (self.agent_dir / "architecture.md").write_text(content)

    def append_decision(self, decision: str) -> None:
        f = self.agent_dir / "decisions.md"
        existing = f.read_text() if f.exists() else "# Decisions\n"
        f.write_text(existing + f"\n- {decision}")

    def save_tasks(self, tasks: list[dict]) -> None:
        self.tasks_path.write_text(json.dumps(tasks, indent=2))

    def load_tasks(self) -> list[dict]:
        if self.tasks_path.exists():
            return json.loads(self.tasks_path.read_text())
        return []

    def log_event(self, agent: str, event: str, detail: dict) -> None:
        """Appends one JSON line per event — model calls, test runs, reviews —
        so a run can be reconstructed and providers/models compared afterward.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": agent,
            "event": event,
            "detail": detail,
        }
        log_file = self.agent_dir / "history" / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
        with open(log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
