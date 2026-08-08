from __future__ import annotations

from .base import BaseAgent

SYSTEM = """You are the Architect agent in a multi-agent coding system.
Given a repository file listing and a task description, explain:
- the relevant architecture
- which files are relevant to the task
- what needs to change
- what could break
Be concise and concrete. Output markdown."""


class ArchitectAgent(BaseAgent):
    name = "architect"

    def run(self, task: str) -> str:
        files = self.fs.list_files()
        listing = "\n".join(files[:300])  # cap for prompt size on large repos
        user = f"Task:\n{task}\n\nRepository files:\n{listing}"
        architecture = self.ask(SYSTEM, user)
        self.tasks.write_architecture(architecture)
        return architecture
