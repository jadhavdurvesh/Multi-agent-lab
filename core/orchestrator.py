"""The orchestrator: Architect -> Planner -> [Developer -> Tester -> Reviewer]* -> push/PR.

Safe mode (default) pauses for your approval before implementation starts and
again before pushing. Pass --autonomous to skip both gates once you trust a
given model/task combination.
"""
from __future__ import annotations

import shutil
import subprocess

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
        print(f"Planned {len(plan)} subtask(s).")

        if not self._confirm(f"Proceed with {len(plan)} subtask(s)?"):
            return "Aborted before implementation."

        self.git.checkout_branch(branch)

        for subtask in plan:
            print(f"\n[DEVELOPER] Implementing: {subtask.get('title', subtask)}")
            self.developer.implement(subtask, subtask.get("files", []))

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
                print(f"[ORCHESTRATOR] Giving up on '{subtask.get('title')}' after {self.max_iterations} attempts.")
                continue

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

            if not review.get("approved"):
                print(f"[ORCHESTRATOR] '{subtask.get('title')}' still has open review comments "
                      f"after {self.max_iterations} attempts; leaving as-is on '{branch}'.")

        if not self._confirm(f"Push branch '{branch}' and open a PR?"):
            return f"Changes committed locally on '{branch}'. Push manually when ready."

        try:
            self.git.push(branch)
        except RuntimeError as e:
            print(f"[GITHUB] Could not push automatically ({e}). Changes are committed "
                  f"locally on '{branch}' — push manually once a remote is configured.")
            return "Completed (local only, push failed)"

        pr_url = self._try_create_pr(branch, task)
        if pr_url:
            print(f"[GITHUB] PR opened: {pr_url}")
        else:
            print(f"[GITHUB] Branch '{branch}' pushed. Open a PR from your GitHub repo page "
                  f"(or install & auth the GitHub CLI 'gh' so this can open one automatically).")
        return "Completed"

    def _try_create_pr(self, branch: str, task: str) -> str | None:
        if not shutil.which("gh"):
            return None
        try:
            result = subprocess.run(
                ["gh", "pr", "create", "--title", f"Agent: {task[:60]}",
                 "--body", "Automated PR from multi-agent-lab.", "--head", branch],
                cwd=self.git.root, capture_output=True, text=True,
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except OSError:
            return None
