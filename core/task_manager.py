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

    def generate_report(self, task: str, branch: str, pr_url: str | None = None) -> str:
        """Generate a markdown run summary from today's history log.

        Covers: which model/provider each agent used, token counts,
        latency, test pass/fail, reviewer rounds, files written.
        Written to .agent/SUMMARY.md and also returned as a string.
        """
        from datetime import datetime, timezone
        import json

        log_file = self.agent_dir / "history" / f"{datetime.now(timezone.utc):%Y-%m-%d}.jsonl"
        events: list[dict] = []
        if log_file.exists():
            for line in log_file.read_text().splitlines():
                try:
                    events.append(json.loads(line))
                except json.JSONDecodeError:
                    pass

        agent_stats: dict[str, dict] = {}
        test_results: list[dict] = []

        for ev in events:
            agent = ev.get("agent", "?")
            detail = ev.get("detail", {})
            if ev.get("event") == "model_call":
                s = agent_stats.setdefault(agent, {
                    "calls": 0, "prompt_tokens": 0,
                    "completion_tokens": 0, "latency_s": 0.0,
                    "provider": detail.get("provider", "?"),
                    "model": detail.get("model", "?"),
                })
                s["calls"] += 1
                s["prompt_tokens"] += detail.get("prompt_tokens", 0)
                s["completion_tokens"] += detail.get("completion_tokens", 0)
                s["latency_s"] += detail.get("latency_s", 0.0)
            elif ev.get("event") == "test_run":
                test_results.append(detail)

        lines = [
            f"# Agent Run Summary",
            f"",
            f"**Task:** {task}",
            f"**Branch:** `{branch}`",
            f"**PR:** {pr_url or '_not opened_'}",
            f"",
            f"## Agent calls",
            f"",
            f"| Agent | Provider | Model | Calls | Prompt tok | Completion tok | Avg latency |",
            f"|-------|----------|-------|-------|-----------|----------------|-------------|",
        ]
        for agent, s in agent_stats.items():
            avg_lat = f"{s['latency_s'] / s['calls']:.1f}s" if s["calls"] else "-"
            lines.append(
                f"| {agent} | {s['provider']} | {s['model']} | {s['calls']} "
                f"| {s['prompt_tokens']:,} | {s['completion_tokens']:,} | {avg_lat} |"
            )

        total_prompt = sum(s["prompt_tokens"] for s in agent_stats.values())
        total_completion = sum(s["completion_tokens"] for s in agent_stats.values())
        lines += [
            f"",
            f"**Total tokens:** {total_prompt + total_completion:,} "
            f"({total_prompt:,} prompt + {total_completion:,} completion)",
            f"",
            f"## Test runs",
            f"",
        ]
        if test_results:
            passed = sum(1 for t in test_results if t.get("ok"))
            lines.append(f"{passed}/{len(test_results)} attempts passed.")
            for i, t in enumerate(test_results, 1):
                status = "✅ PASS" if t.get("ok") else "❌ FAIL"
                lines.append(f"- Attempt {i}: {status}")
        else:
            lines.append("_No test runs recorded._")

        report = "\n".join(lines) + "\n"
        (self.agent_dir / "SUMMARY.md").write_text(report)
        return report
