from __future__ import annotations


class BaseAgent:
    name = "base"

    def __init__(self, router, tasks, fs):
        self.router = router
        self.tasks = tasks
        self.fs = fs

    def ask(self, system: str, user: str, max_tokens: int = 2000) -> str:
        result = self.router.call(self.name, system, user, max_tokens=max_tokens)
        self.tasks.log_event(self.name, "model_call", result)
        return result["text"]
