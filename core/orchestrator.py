from __future__ import annotations

import os
import subprocess

import requests

from agents.architect import ArchitectAgent
from agents.developer import DeveloperAgent
from agents.planner import PlannerAgent
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
        self.planner = PlannerAgent(router, tasks, fs)
        self.developer = DeveloperAgent(router, tasks, fs)
        self.tester = TesterAgent(router, tasks, fs, terminal, test_command)
        self.reviewer = ReviewerAgent(router, tasks, fs, git)

    def _confirm(self, prompt: str) -> bool:
        if not self.safe_mode:
            return True
        answer = input(f"\n[APPROVAL NEEDED] {prompt} [y/N] ")
        return answer.strip().lower() == "y"

    def run(self, task: str, branch: str = "agent/task-1") -> str:
        print(f"[ARCHITECT] Analyzing repository for: {task}")
        architecture = self.architect.run(task)
        print(architecture[:500])

        print("[PLANNER] Creating subtasks...")
        plan = self.planner.run(task, architecture)
        print(f"[PLANNER] {len(plan)} subtask(s) planned.")
        for s in plan:
            print(f"  - {s.get('title')}")

        if not self._confirm(f"Proceed with {len(plan)} subtask(s)?"):
            return "Aborted before implementation."

        self.git.checkout_branch(branch)

        any_edits = False

        for subtask in plan:
            print(f"\n[DEVELOPER] Implementing: {subtask.get('title', subtask)}")
            edits = self.developer.implement(subtask, subtask.get("files", []))

            if not edits:
                print(f"[DEVELOPER] No files written for '{subtask.get('title')}' — skipping tester/reviewer.")
                continue

            any_edits = True
            passed = False
            result = {}
            for i in range(self.max_iterations):
                result = self.tester.test()
                print(f"[TESTER] {'PASS' if result['passed'] else 'FAIL'} (attempt {i + 1})")
                if result["passed"]:
                    passed = True
                    break
                self.developer.fix(result["stderr"] or result["stdout"], subtask)

            if not passed:
                print(f"[ORCHESTRATOR] Tests still failing after {self.max_iterations} attempts — committing anyway and moving on.")

            self.git.commit(f"Implement: {subtask.get('title')}")

            review = {"approved": False}
            for i in range(self.max_iterations):
                review = self.reviewer.review()
                print(f"[REVIEWER] {'APPROVED' if review['approved'] else 'CHANGES REQUESTED'}")
                if review["approved"]:
                    break
                feedback = "\n".join(review.get("comments", []))
                self.developer.fix(feedback, subtask)
                self.tester.test()
                self.git.commit(f"Address review: {subtask.get('title')}")

        if not any_edits:
            return "No files were written by any subtask — nothing to push."

        if not self._confirm(f"Push branch '{branch}' and open a PR?"):
            return f"Changes committed locally on '{branch}'. Push manually when ready."

        print(f"[GIT] Pushing branch '{branch}'...")
        self.git.push(branch)

        pr_url = self._create_pr(branch, task)
        if pr_url:
            print(f"[GITHUB] PR opened: {pr_url}")
        else:
            print(f"[GITHUB] Branch '{branch}' pushed. Open a PR manually on GitHub.")

        return f"Completed. Branch: {branch}" + (f" PR: {pr_url}" if pr_url else "")

    def _create_pr(self, branch: str, task: str) -> str | None:
        """Open a PR via the GitHub API using GH_TOKEN from the environment.
        Works in GitHub Actions without needing the gh CLI installed.
        """
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            return self._try_gh_cli(branch, task)

        # Determine owner/repo from the remote URL
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.git.root, capture_output=True, text=True
            )
            remote_url = result.stdout.strip()
            # Parse https://github.com/owner/repo.git or git@github.com:owner/repo.git
            if "github.com" in remote_url:
                if remote_url.startswith("https://"):
                    # strip trailing .git, split by /
                    parts = remote_url.rstrip("/").rstrip(".git").split("/")
                    owner, repo = parts[-2], parts[-1].replace(".git", "")
                else:
                    # git@github.com:owner/repo.git
                    slug = remote_url.split(":")[-1].replace(".git", "")
                    owner, repo = slug.split("/")
            else:
                return None
        except Exception as e:
            print(f"[GITHUB] Could not parse remote URL: {e}")
            return None

        try:
            resp = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={
                    "title": f"Agent: {task[:72]}",
                    "head": branch,
                    "base": "main",
                    "body": (
                        f"Automated PR from multi-agent-lab.\n\n"
                        f"**Task:** {task}\n\n"
                        f"*Generated by the Developer → Tester → Reviewer agent pipeline.*"
                    ),
                },
                timeout=30,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("html_url")
            print(f"[GITHUB] PR API returned {resp.status_code}: {resp.text[:200]}")
            return None
        except Exception as e:
            print(f"[GITHUB] PR creation failed: {e}")
            return None

    def _try_gh_cli(self, branch: str, task: str) -> str | None:
        """Fallback: try gh CLI if no token env var found."""
        try:
            result = subprocess.run(
                ["gh", "pr", "create",
                 "--title", f"Agent: {task[:72]}",
                 "--body", "Automated PR from multi-agent-lab.",
                 "--head", branch],
                cwd=self.git.root, capture_output=True, text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except OSError:
            return None
