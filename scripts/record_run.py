#!/usr/bin/env python3
"""Append a one-line entry to AGENT_ACTIVITY.md after every agent run.

This script is called by the workflow AFTER a run completes. The commit
it produces is authored with the repo owner's email, so it counts on their
GitHub contribution graph. Every run = one green square.
"""
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    event = sys.argv[1] if len(sys.argv) > 1 else "run"       # start / done / failed
    task  = sys.argv[2] if len(sys.argv) > 2 else "unknown"
    repo  = sys.argv[3] if len(sys.argv) > 3 else ""

    now = datetime.now(timezone.utc)
    icon = {"start": "🚀", "done": "✅", "failed": "❌"}.get(event, "🤖")
    line = (
        f"| {now:%Y-%m-%d %H:%M} UTC | {icon} {event:6s} "
        f"| {task[:60]:60s} | {repo} |\n"
    )

    log_file = Path(__file__).resolve().parent.parent / "AGENT_ACTIVITY.md"

    if not log_file.exists():
        log_file.write_text(
            "# Agent Activity Log\n\n"
            "Every row is one automated agent run. "
            "Each commit to this file counts as a contribution.\n\n"
            "| Date (UTC) | Status | Task | Target repo |\n"
            "|------------|--------|------|-------------|\n"
        )

    with open(log_file, "a") as f:
        f.write(line)

    print(f"[record_run] Logged: {line.strip()}")


if __name__ == "__main__":
    main()
