"""Orchestrator: Architect → Planner → Developer → Tester → Reviewer

Wall-time monitoring: checks elapsed time before EVERY major step (not just
inside the tester loop). If approaching the job timeout, commits whatever
exists and exits cleanly. Inspired by mini-swe-agent's per-step time check.
"""
from __future__ import annotations

import json
import os
import subprocess
import time

import requests

from agents.architect import ArchitectAgent
from agents.developer import DeveloperAgent
from agents.planner import PlannerAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent


class WallTimeExceeded(Exception):
    pass


class Orchestrator:
    def __init__(self, router, tasks, fs, terminal, git,
                 safe_mode: bool = True, max_iterations: int = 3,
                 test_command: str = "pytest -q", tdd_mode: bool = False,
                 wall_time_limit: int = 0):
        self.tasks = tasks
        self.git = git
        self.safe_mode = safe_mode
        self.max_iterations = max_iterations
        self.tdd_mode = tdd_mode
        self.wall_time_limit = wall_time_limit
        self._start_time = time.time()

        self.architect = ArchitectAgent(router, tasks, fs)
        self.planner   = PlannerAgent(router, tasks, fs)
        self.developer = DeveloperAgent(router, tasks, fs)
        self.tester    = TesterAgent(router, tasks, fs, terminal, test_command, tdd_mode)
        self.reviewer  = ReviewerAgent(router, tasks, fs, git)

    # ── Wall-time ─────────────────────────────────────────────────────────────

    def _elapsed(self) -> float:
        return time.time() - self._start_time

    def _near_timeout(self) -> bool:
        """True when within 90s of the wall-time limit.
        
        mini-swe-agent checks this at the top of every agent step — not just
        inside retry loops — so a single slow model call can't push past budget.
        """
        if not self.wall_time_limit:
            return False
        return self._elapsed() >= self.wall_time_limit - 90

    def _check_time(self, stage: str) -> None:
        """Raise WallTimeExceeded if approaching limit. Call before every step."""
        if self._near_timeout():
            raise WallTimeExceeded(
                f"Wall-time limit approaching at '{stage}' "
                f"({self._elapsed():.0f}s elapsed, limit {self.wall_time_limit}s)"
            )

    # ── Safe-mode ─────────────────────────────────────────────────────────────

    def _confirm(self, prompt: str) -> bool:
        if not self.safe_mode:
            return True
        return input(f"\n[APPROVAL NEEDED] {prompt} [y/N] ").strip().lower() == "y"

    # ── Main run loop ──────────────────────────────────────────────────────────

    def run(self, task: str, branch: str = "agent/task-1") -> str:
        mode = "[TDD]" if self.tdd_mode else "[standard]"
        print(f"\n[ORCHESTRATOR] Starting {mode} run: {task}")
        if self.wall_time_limit:
            print(f"[ORCHESTRATOR] Wall-time limit: {self.wall_time_limit}s "
                  f"(exits cleanly at {self.wall_time_limit - 90}s)")

        try:
            return self._run_inner(task, branch)
        except WallTimeExceeded as e:
            print(f"\n[ORCHESTRATOR] {e}")
            return self._emergency_commit_and_push(branch, task)
        except RuntimeError as e:
            msg = str(e)
            if "All providers exhausted" in msg:
                print(f"\n[ORCHESTRATOR] All AI providers failed: {msg}")
                print("[ORCHESTRATOR] Check that your API keys are valid:")
                print("  GROQ_API_KEY   → console.groq.com/keys")
                print("  NVIDIA_API_KEY → build.nvidia.com")
                print("  GEMINI_API_KEY → aistudio.google.com/apikey")
                import sys; sys.exit(1)
            raise
        except Exception as e:
            print(f"\n[ORCHESTRATOR] Unexpected error: {type(e).__name__}: {e}")
            print("[ORCHESTRATOR] Attempting emergency commit of partial work...")
            return self._emergency_commit_and_push(branch, task)

    def _run_inner(self, task: str, branch: str) -> str:
        # Step 1: Architect
        self._check_time("architect")
        print("\n[ARCHITECT] Reading repo and prioritising context...")
        architecture = self.architect.run(task)
        print(architecture[:300])

        # Step 2: Planner
        self._check_time("planner")
        print("\n[PLANNER] Producing technical spec...")
        spec = self.planner.run(task, architecture)
        print(f"  Approach  : {str(spec.get('approach',''))[:100]}")
        print(f"  Files     : {spec.get('files_to_modify',[])} + {spec.get('files_to_create',[])}")
        print(f"  Tests     : {spec.get('tests_to_write',[])}")

        if not self._confirm("Proceed with implementation?"):
            return "Aborted."

        self.git.checkout_branch(branch)
        context_files = spec.get("files_to_modify", []) + spec.get("files_to_create", [])

        # Step 3 (TDD only): Tester writes failing tests
        if self.tdd_mode:
            self._check_time("tester-write")
            print("\n[TESTER] Writing failing tests from spec...")
            test_files = self.tester.write_tests(spec)
            if test_files:
                self.git.commit(f"TDD tests: {task[:60]}")
                context_files += [f["path"] for f in test_files]

        # Step 4: Developer implements
        self._check_time("developer")
        print(f"\n[DEVELOPER] Implementing: {spec.get('title', task)}")
        edits = self.developer.implement(spec, context_files)
        if not edits:
            return "Developer produced no file edits."

        # Reinstall requirements if Developer changed them
        if any("requirements" in str(op.get("path", "")) for op in edits):
            print("[ORCHESTRATOR] requirements.txt changed — reinstalling...")
            self.tester.terminal.run_command("pip install -r requirements.txt -q")

        # Step 5: Tester retry loop
        passed = False
        for i in range(self.max_iterations):
            self._check_time(f"tester-run-{i+1}")
            result = self.tester.test()
            print(f"[TESTER] {'PASS' if result['passed'] else 'FAIL'} "
                  f"(attempt {i+1}/{self.max_iterations})")
            if result["passed"]:
                passed = True
                break
            self._check_time(f"developer-fix-{i+1}")
            print("[DEVELOPER] Fixing based on test output...")
            fix_edits = self.developer.fix(result["stderr"] or result["stdout"], spec)
            if any("requirements" in str(op.get("path","")) for op in fix_edits):
                self.tester.terminal.run_command("pip install -r requirements.txt -q")

        if not passed:
            print("[ORCHESTRATOR] Tests still failing — committing for review.")

        self.git.commit(f"Agent: {task[:72]}")

        # Step 6: Reviewer loop
        for i in range(self.max_iterations):
            self._check_time(f"reviewer-{i+1}")
            review = self.reviewer.review()
            approved = review.get("approved", False)
            print(f"[REVIEWER] {'APPROVED' if approved else 'CHANGES REQUESTED'} "
                  f"(attempt {i+1}/{self.max_iterations})")
            if approved:
                break
            self._check_time(f"developer-review-fix-{i+1}")
            self.developer.fix("\n".join(review.get("comments", [])), spec)
            self.tester.test()
            self.git.commit(f"Agent review fix: {task[:60]}")

        # Step 7: Push + PR
        if not self._confirm(f"Push '{branch}' and open PR?"):
            return f"Committed locally on '{branch}'."

        self._check_time("push")
        print(f"[GIT] Pushing '{branch}'...")
        self.git.push(branch)

        # Generate summary report
        report = self.tasks.generate_report(task, branch)
        print("\n[SUMMARY]\n" + report[:600])

        pr_url = self._create_pr(branch, task, spec)
        if pr_url:
            print(f"[GITHUB] PR: {pr_url}")

        return "Done. Branch: " + branch + (f" | PR: {pr_url}" if pr_url else "")

    def _emergency_commit_and_push(self, branch: str, task: str) -> str:
        """Commit and push whatever partial work exists before the job kills us.
        
        Inspired by SWE-agent's auto-submit: on any fatal error (timeout, cost
        overrun, context overflow), ship the partial patch rather than losing work.
        """
        print("[ORCHESTRATOR] Emergency commit — saving partial work...")
        try:
            self.git.commit(f"Agent (partial — wall-time): {task[:60]}")
        except Exception as e:
            print(f"[ORCHESTRATOR] Commit failed: {e}")
        try:
            self.git.push(branch)
            print(f"[GIT] Partial work pushed to '{branch}'.")
        except Exception as e:
            print(f"[GIT] Push failed: {e}")
        return f"Partial — wall-time limit reached. Branch: {branch}"

    # ── PR creation ───────────────────────────────────────────────────────────

    def _create_pr(self, branch: str, task: str, spec: dict) -> str | None:
        token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
        if not token:
            return self._try_gh_cli(branch, task)
        try:
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                cwd=self.git.root, capture_output=True, text=True)
            remote = result.stdout.strip()
            if "github.com" not in remote:
                return None
            if remote.startswith("https://"):
                parts = remote.rstrip("/").split("/")
                owner, repo = parts[-2], parts[-1].replace(".git", "")
            else:
                slug = remote.split(":")[-1].replace(".git", "")
                owner, repo = slug.split("/")
        except Exception as e:
            print(f"[GITHUB] Remote parse failed: {e}")
            return None

        tests_md = "\n".join(f"- {t}" for t in spec.get("tests_to_write", []))
        body = (
            f"Automated PR from multi-agent-lab.\n\n"
            f"**Task:** {task}\n\n"
            f"**Approach:** {spec.get('approach', '')}\n\n"
            + (f"**Tests written:**\n{tests_md}\n" if tests_md else "")
            + "\n*Architect → Planner → Developer → Tester → Reviewer pipeline.*"
        )
        try:
            resp = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json"},
                json={"title": f"Agent: {task[:72]}", "head": branch,
                      "base": "main", "body": body},
                timeout=15,
            )
            if resp.status_code in (200, 201):
                return resp.json().get("html_url")
            print(f"[GITHUB] PR API {resp.status_code}: {resp.text[:200]}")
        except Exception as e:
            print(f"[GITHUB] PR error: {e}")
        return None

    def _try_gh_cli(self, branch: str, task: str) -> str | None:
        try:
            r = subprocess.run(
                ["gh", "pr", "create", "--title", f"Agent: {task[:72]}",
                 "--body", "Automated PR from multi-agent-lab.", "--head", branch],
                cwd=self.git.root, capture_output=True, text=True)
            return r.stdout.strip() if r.returncode == 0 else None
        except OSError:
            return None
