from __future__ import annotations

import re

from .base import BaseAgent

SYSTEM = """You are the Architect agent in a multi-agent coding system.
Given a repository file listing and a task description, explain:
- the relevant architecture
- which files are relevant to the task (use their exact paths)
- what needs to change and what approach makes sense
- what could break or needs careful handling
Be concise and concrete. Reference specific file paths. Output markdown."""


class ArchitectAgent(BaseAgent):
    name = "architect"

    def run(self, task: str) -> str:
        all_files = self.fs.list_files()
        relevant = self._prioritize_files(task, all_files)
        listing = "\n".join(relevant)
        skipped = len(all_files) - len(relevant)
        note = f"\n({skipped} lower-relevance files omitted)" if skipped else ""

        user = f"Task:\n{task}\n\nRepository files (ranked by relevance):\n{listing}{note}"
        architecture = self.ask(SYSTEM, user)
        self.tasks.write_architecture(architecture)
        return architecture

    def _prioritize_files(self, task: str, all_files: list[str]) -> list[str]:
        """Score and rank files by relevance to the task.

        Strategy:
          1. Path-level keyword match  (fast, no disk reads)
          2. Content-level keyword match on the top-100 candidates (reads first 1 KB)
          3. Import-graph expansion: add files that import the top-10 matches
          4. Cap at 50 files so the prompt stays manageable
        """
        STOP_WORDS = {
            "the", "and", "for", "with", "that", "this", "add", "make",
            "create", "implement", "into", "from", "using", "based",
            "should", "will", "also", "file", "new", "each",
        }
        keywords = {
            w for w in re.findall(r"\b\w{3,}\b", task.lower())
            if w not in STOP_WORDS
        }

        # Step 1: path scoring (free)
        path_scores: dict[str, int] = {}
        for f in all_files:
            f_lower = f.lower()
            score = sum(10 for kw in keywords if kw in f_lower)
            if f.endswith(".py") and "__pycache__" not in f:
                score += 2
            if "test" in f_lower:
                score += 1
            if "__pycache__" in f or f.endswith(".pyc"):
                score -= 100
            path_scores[f] = score

        ranked = sorted(all_files, key=lambda f: (-path_scores[f], f))
        top_100 = ranked[:100]

        # Step 2: content scoring (reads first 1 KB of each candidate)
        final_scores: dict[str, int] = dict(path_scores)
        for f in top_100:
            try:
                snippet = self.fs.read_file(f)[:1000].lower()
                final_scores[f] += sum(2 for kw in keywords if kw in snippet)
            except (FileNotFoundError, ValueError, UnicodeDecodeError):
                pass

        top_10 = sorted(top_100, key=lambda f: (-final_scores[f], f))[:10]

        # Step 3: import graph — add files that import any of the top-10
        top_names = {f.replace("/", ".").replace("\\", ".").rstrip(".py")
                     for f in top_10}
        for f in all_files:
            if f in top_10:
                continue
            try:
                content = self.fs.read_file(f)[:2000]
                if any(name.split(".")[-1] in content for name in top_names
                       if "import" in content):
                    final_scores[f] = final_scores.get(f, 0) + 5
            except (FileNotFoundError, ValueError, UnicodeDecodeError):
                pass

        return sorted(all_files, key=lambda f: (-final_scores.get(f, 0), f))[:50]
