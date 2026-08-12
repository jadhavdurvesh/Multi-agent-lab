"""Orchestrator: Architect → Planner → Developer → Tester → Reviewer → push → PR.

All five agents, each doing real work that depends on the previous one:
  Architect  — reads the repo, identifies relevant files and risks
  Planner    — produces a technical spec (approach, files, tests, edge cases)
  Developer  — implements from the spec (not a vague description)
  Tester     — runs tests, sends failures back to Developer with spec context
  Reviewer   — checks the diff against the spec, not just style
"""
from __future__ import annotations

import os
import re
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
        # Step 1: Architect reads the repo
        print(f"\n[ARCHITECT] Reading repo for: {task}")
        architecture = self.architect.run(task)
        print(architecture[:400])

        # Step 2: Planner produces a technical spec
        print("\n[PLANNER] Producing technical spec...")
        spec = self.planner.run(task, architecture)
        print(f"  Approach : {spec.get('approach', '')[:120]}")
        print(f"  Modify   : {spec.get('files_to_modify', [])}")
        print(f"  Create   : {spec.get('files_to_create', [])}")
        print(f"  Tests    : {spec.get('tests_to_write', [])}")

        if not self._confirm("Proceed with implementation?"):
            return "Aborted."

        self.git.checkout_branch(branch)

        # Step 3: Developer implements from the spec
        print(f"\n[DEVELOPER] Implementing: {spec.get('title', task)}")
        context_files = spec.get("files_to_modify", []) + spec.get("files_to_create", [])
        edits = self.developer.implement(spec, context_files)

        if not edits:
            return "Developer produced no file edits — nothing to commit."

        # Step 4: Tester — retry up to max_iterations
        passed = False
        for i in range(self.max_iterations):
            result = self.tester.test()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"[TESTER] {status} (attempt {i + 1}/{self.max_iterations})")
            if result["passed"]:
                passed = True
                break
            print("[DEVELOPER] Fixing based on test output...")
            self.developer.fix(result["stderr"] or result["stdout"], spec)

        if not passed:
            print("[ORCHESTRATOR] Tests still failing — committing for review anyway.")

        self.git.commit(f"Agent: {task[:72]}")

        # Step 5: Reviewer checks diff against the spec
        for i in range(self.max_iterations):
            review = self.reviewer.review()
            approved = review.get("approved", False)
            print(f"[REVIEWER] {'APPROVED' if approved else 'CHANGES REQUESTED'} "
                  f"(attempt {i + 1}/{self.max_iterations})")
            if approved:
                break
            feedback = "\n".join(review.get("comments", []))
            print("[DEVELOPER] Addressing review comments...")
            self.developer.fix(feedback, spec)
            self.tester.test()
            self.git.commit(f"Agent review fix: {task[:60]}")

        if not self._confirm(f"Push '{branch}' and open PR?"):
            return f"Committed locally on '{branch}'. Push manually when ready."

        print(f"[GIT] Pushing '{branch}'...")
        self.git.push(branch)

        pr_url = self._create_pr(branch, task, spec)
        if pr_url:
            print(f"[GITHUB] PR: {pr_url}")
        else:
            print("[GITHUB] Branch pushed. Open a PR manually on GitHub.")

        return f"Done. Branch: {branch}" + (f" | PR: {pr_url}" if pr_url else "")

    def _create_pr(self, branch: str, task: str, spec: dict) -> str | None:
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

        approach = spec.get("approach", "")
        tests = "\n".join(f"- {t}" for t in spec.get("tests_to_write", []))
        body = (
            f"Automated PR from multi-agent-lab.\n\n"
            f"**Task:** {task}\n\n"
            f"**Approach:** {approach}\n\n"
            + (f"**Tests written:**\n{tests}\n\n" if tests else "")
            + "*Architect → Planner → Developer → Tester → Reviewer pipeline.*"
        )
        try:
            resp = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                },
                json={"title": f"Agent: {task[:72]}", "head": branch, "base": "main", "body": body},
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
                ["gh", "pr", "create",
                 "--title", f"Agent: {task[:72]}",
                 "--body", "Automated PR from multi-agent-lab.",
                 "--head", branch],
                cwd=self.git.root, capture_output=True, text=True,
            )
            return r.stdout.strip() if r.returncode == 0 else None
        except OSError:
            return None
