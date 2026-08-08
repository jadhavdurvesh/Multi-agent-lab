"""Shared functionality for all agents: every model call is logged through
the task manager so a run can be reconstructed afterward.
"""
from __future__ import annotations


class BaseAgent:
    name = "base"

    def __init__(self, router, tasks, fs):
        self.router = router
        self.tasks = tasks
        self.fs = fs

    def ask(self, system: str, user: str) -> str:
        result = self.router.call(self.name, system, user)
        self.tasks.log_event(self.name, "model_call", result)
        return result["text"]
