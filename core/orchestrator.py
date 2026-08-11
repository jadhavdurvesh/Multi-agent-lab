"""Orchestrator: Architect → Developer → Tester → Reviewer → push → PR.

One task per run. The Planner is intentionally removed from this loop —
each task in the queue is already a single focused thing (one endpoint,
one file, one feature). Breaking it further just gives the models more
chances to go off-track. The Architect still runs to understand the repo,
then the Developer implements the whole task as one unit.
"""
from __future__ import annotations

import os
import subprocess

import requests

from agents.architect import ArchitectAgent
from agents.developer import DeveloperAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent


class Orchestrator:
    def __init__(self, router, tasks, fs, terminal, git, safe_mode: bool = True,
                 max_iterations: int = 3, test_command: str = "pytest -q"):
        self.tasks = tasks
        self.git = git
        self.safe_mode = safe_mode
        self.max_iterations = max_iterations

        self.architect = ArchitectAgent(router, tasks, fs)
        self.developer = DeveloperAgent(router, tasks, fs)
        self.tester = TesterAgent(router, tasks, fs, terminal, test_command)
        self.reviewer = ReviewerAgent(router, tasks, fs, git)

    def _confirm(self, prompt: str) -> bool:
        if not self.safe_mode:
            return True
        answer = input(f"\n[APPROVAL NEEDED] {prompt} [y/N] ")
        return answer.strip().lower() == "y"

    def run(self, task: str, branch: str = "agent/task-1") -> str:
        # Step 1: Architect reads the repo and produces context
        print(f"\n[ARCHITECT] Reading repo for: {task}")
        architecture = self.architect.run(task)
        print(architecture[:400])

        if not self._confirm(f"Proceed with implementation?"):
            return "Aborted."

        self.git.checkout_branch(branch)

        # Step 2: Developer implements the whole task as one unit
        print(f"\n[DEVELOPER] Implementing: {task}")
        subtask = {
            "title": task,
            "description": task,
            "files": self._relevant_files(architecture),
        }
        edits = self.developer.implement(subtask, subtask["files"])

        if not edits:
            return "Developer produced no file edits — nothing to commit."

        # Step 3: Tester — retry up to max_iterations if failing
        passed = False
        for i in range(self.max_iterations):
            result = self.tester.test()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"[TESTER] {status} (attempt {i + 1}/{self.max_iterations})")
            if result["passed"]:
                passed = True
                break
            print(f"[DEVELOPER] Fixing based on test output...")
            self.developer.fix(result["stderr"] or result["stdout"], subtask)

        if not passed:
            print("[ORCHESTRATOR] Tests still failing — committing anyway for review.")

        self.git.commit(f"Agent: {task[:72]}")

        # Step 4: Reviewer — retry up to max_iterations
        for i in range(self.max_iterations):
            review = self.reviewer.review()
            approved = review.get("approved", False)
            print(f"[REVIEWER] {'APPROVED' if approved else 'CHANGES REQUESTED'} (attempt {i + 1}/{self.max_iterations})")
            if approved:
                break
            feedback = "\n".join(review.get("comments", []))
            print(f"[DEVELOPER] Addressing review comments...")
            self.developer.fix(feedback, subtask)
            self.tester.test()
            self.git.commit(f"Agent review fix: {task[:60]}")

        if not self._confirm(f"Push '{branch}' and open PR?"):
            return f"Committed locally on '{branch}'. Push manually when ready."

        # Step 5: Push + PR
        print(f"[GIT] Pushing '{branch}'...")
        self.git.push(branch)

        pr_url = self._create_pr(branch, task)
        if pr_url:
            print(f"[GITHUB] PR: {pr_url}")
        else:
            print(f"[GITHUB] Branch pushed. Open a PR manually on GitHub.")

        return f"Done. Branch: {branch}" + (f" | PR: {pr_url}" if pr_url else "")

    def _relevant_files(self, architecture: str) -> list[str]:
        """Extract file paths mentioned in the architecture analysis."""
        import re
        # Pull anything that looks like a file path from the architect's output
        paths = re.findall(r'\b[\w./]+\.(?:py|md|yaml|yml|json|txt|html|js|ts|css)\b', architecture)
        # Deduplicate, keep order
        seen = set()
        result = []
        for p in paths:
            if p not in seen:
                seen.add(p)
                result.append(p)
        return result[:10]  # cap at 10 files so the prompt doesn't balloon

    def _create_pr(self, branch: str, task: str) -> str | None:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            return self._try_gh_cli(branch, task)
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.git.root, capture_output=True, text=True
            )
            remote_url = result.stdout.strip()
            if "github.com" not in remote_url:
                return None
            if remote_url.startswith("https://"):
                parts = remote_url.rstrip("/").split("/")
                owner, repo = parts[-2], parts[-1].replace(".git", "")
            else:
                slug = remote_url.split(":")[-1].replace(".git", "")
                owner, repo = slug.split("/")
        except Exception as e:
            print(f"[GITHUB] Could not parse remote URL: {e}")
            return None

        try:
            resp = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"},
                json={
                    "title": f"Agent: {task[:72]}",
                    "head": branch,
                    "base": "main",
                    "body": (
                        f"Automated PR from multi-agent-lab.\n\n"
                        f"**Task:** {task}\n\n"
                        f"*One task · one run · one PR.*"
                    ),
                },
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("html_url")
            print(f"[GITHUB] PR API {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[GITHUB] PR creation error: {e}")
        return None

    def _try_gh_cli(self, branch: str, task: str) -> str | None:
        try:
            r = subprocess.run(
                ["gh", "pr", "create", "--title", f"Agent: {task[:72]}",
                 "--body", "Automated PR from multi-agent-lab.", "--head", branch],
                cwd=self.git.root, capture_output=True, text=True,
            )
            return r.stdout.strip() if r.returncode == 0 else None
        except OSError:
            return None
