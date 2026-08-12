#!/usr/bin/env python3
"""Send a run notification to Discord and/or Slack.

Usage (called from workflow steps):
  python scripts/notify.py start  "Add /health endpoint" "https://github.com/..."
  python scripts/notify.py pr     "Add /health endpoint" "https://github.com/.../pull/7"
  python scripts/notify.py fail   "Add /health endpoint" "https://github.com/.../actions/runs/123"
  python scripts/notify.py requeue "Add /health endpoint" "https://github.com/.../issues/3"

Reads DISCORD_WEBHOOK_URL and/or SLACK_WEBHOOK_URL from environment.
Silent (exit 0) if neither is set — notification is always optional.
"""
from __future__ import annotations

import os
import sys

import requests

ICONS = {
    "start":   "🤖",
    "pr":      "✅",
    "fail":    "❌",
    "requeue": "🔁",
}

LABELS = {
    "start":   "Starting task",
    "pr":      "PR opened",
    "fail":    "Run failed",
    "requeue": "Task requeued",
}


def build_message(event: str, task: str, url: str) -> str:
    icon  = ICONS.get(event, "ℹ️")
    label = LABELS.get(event, event)
    return f"{icon} **{label}**\n`{task}`\n{url}"


def send_discord(webhook_url: str, text: str) -> None:
    resp = requests.post(webhook_url, json={"content": text}, timeout=10)
    resp.raise_for_status()


def send_slack(webhook_url: str, text: str) -> None:
    resp = requests.post(webhook_url, json={"text": text}, timeout=10)
    resp.raise_for_status()


def main() -> None:
    if len(sys.argv) < 4:
        print(f"Usage: {sys.argv[0]} <event> <task> <url>", file=sys.stderr)
        sys.exit(1)

    _, event, task, url = sys.argv[:4]
    message = build_message(event, task, url)

    discord = os.environ.get("DISCORD_WEBHOOK_URL", "")
    slack   = os.environ.get("SLACK_WEBHOOK_URL", "")

    if not discord and not slack:
        print("[notify] No webhook configured — skipping.")
        return

    errors = []
    if discord:
        try:
            send_discord(discord, message)
            print(f"[notify] Discord: {event} sent.")
        except Exception as e:
            errors.append(f"Discord: {e}")

    if slack:
        try:
            send_slack(slack, message)
            print(f"[notify] Slack: {event} sent.")
        except Exception as e:
            errors.append(f"Slack: {e}")

    if errors:
        print(f"[notify] Some notifications failed: {errors}", file=sys.stderr)


if __name__ == "__main__":
    main()
