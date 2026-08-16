"""Orchestrator: Architect → Planner → [Tester writes tests →] Developer → Tester → Reviewer

Standard mode:  Architect → Planner → Developer → Tester → Reviewer
TDD mode:       Architect → Planner → Tester(write) → Developer → Tester(run) → Reviewer

In TDD mode the Tester writes failing tests from the spec before Developer
runs. Developer's only job then is making those tests pass — no need to
write tests themselves, harder to fake coverage.
"""
from __future__ import annotations

import json
import os
import subprocess

import requests

import time

from agents.architect import ArchitectAgent
from agents.developer import DeveloperAgent
from agents.planner import PlannerAgent
from agents.reviewer import ReviewerAgent
from agents.tester import TesterAgent


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
        self.wall_time_limit = wall_time_limit  # seconds; 0 = no limit
        self._start_time = time.time()

        self.architect = ArchitectAgent(router, tasks, fs)
        self.planner   = PlannerAgent(router, tasks, fs)
        self.developer = DeveloperAgent(router, tasks, fs)
        self.tester    = TesterAgent(router, tasks, fs, terminal, test_command, tdd_mode)
        self.reviewer  = ReviewerAgent(router, tasks, fs, git)

    def _elapsed(self) -> float:
        return time.time() - self._start_time

    def _near_timeout(self) -> bool:
        """Return True if we are within 90 seconds of the wall-time limit.

        Inspired by mini-swe-agent's wall_time_limit_seconds: the agent
        monitors its own elapsed time and exits cleanly rather than being
        killed mid-operation by the job timeout.
        """
        if not self.wall_time_limit:
            return False
        return self._elapsed() >= self.wall_time_limit - 90

    def _confirm(self, prompt: str) -> bool:
        if not self.safe_mode:
            return True
        return input(f"\n[APPROVAL NEEDED] {prompt} [y/N] ").strip().lower() == "y"

    def run(self, task: str, branch: str = "agent/task-1") -> str:
        mode_tag = "[TDD]" if self.tdd_mode else "[standard]"
        print(f"\n[ORCHESTRATOR] Starting {mode_tag} run: {task}")

        # ── Step 1: Architect ───────────────────────────────────────────────
        print("\n[ARCHITECT] Reading repo and prioritising context...")
        architecture = self.architect.run(task)
        print(architecture[:400])

        # ── Step 2: Planner → technical spec ───────────────────────────────
        print("\n[PLANNER] Producing technical spec...")
        spec = self.planner.run(task, architecture)
        print(f"  Approach  : {str(spec.get('approach',''))[:120]}")
        print(f"  Modify    : {spec.get('files_to_modify', [])}")
        print(f"  Create    : {spec.get('files_to_create', [])}")
        print(f"  Tests     : {spec.get('tests_to_write', [])}")
        print(f"  Edge cases: {spec.get('edge_cases', [])}")

        if not self._confirm("Proceed with implementation?"):
            return "Aborted."

        self.git.checkout_branch(branch)
        context_files = spec.get("files_to_modify", []) + spec.get("files_to_create", [])

        # ── Step 3 (TDD only): Tester writes failing tests ──────────────────
        if self.tdd_mode:
            print("\n[TESTER] Writing failing tests from spec...")
            test_files = self.tester.write_tests(spec)
            if test_files:
                self.git.commit(f"TDD tests: {task[:60]}")
                context_files += [f["path"] for f in test_files]
                print(f"[TESTER] Committed {len(test_files)} test file(s). "
                      f"Developer must make them pass.")
            else:
                print("[TESTER] Warning: no test files written — continuing anyway.")

        # ── Step 4: Developer implements ────────────────────────────────────
        print(f"\n[DEVELOPER] Implementing: {spec.get('title', task)}")
        edits = self.developer.implement(spec, context_files)
        if not edits:
            return "Developer produced no file edits — nothing to commit."

        # Reinstall requirements if Developer modified requirements.txt.
        # Critical: if Developer adds 'flask' to requirements.txt but pip
        # never installs it, every Tester run fails until timeout.
        if any("requirements" in str(op.get("path", "")) for op in edits):
            print("[ORCHESTRATOR] requirements.txt changed — reinstalling...")
            self.terminal.run_command("pip install -r requirements.txt -q")

        # ── Step 5: Tester runs — retry loop ────────────────────────────────
        passed = False
        for i in range(self.max_iterations):
            result = self.tester.test()
            status = "PASS" if result["passed"] else "FAIL"
            print(f"[TESTER] {status} (attempt {i + 1}/{self.max_iterations})")
            if result["passed"]:
                passed = True
                break
            if self._near_timeout():
                print(f"[ORCHESTRATOR] Approaching wall-time limit ({self._elapsed():.0f}s elapsed) "
                      f"— committing partial work and exiting early.")
                break
            print("[DEVELOPER] Fixing based on test output...")
            fix_edits = self.developer.fix(result["stderr"] or result["stdout"], spec)
            if any("requirements" in str(op.get("path", "")) for op in fix_edits):
                self.terminal.run_command("pip install -r requirements.txt -q")

        if not passed:
            print("[ORCHESTRATOR] Tests still failing — committing for review.")

        self.git.commit(f"Agent: {task[:72]}")

        # ── Step 6: Reviewer checks diff against spec ───────────────────────
        for i in range(self.max_iterations):
            review = self.reviewer.review()
            approved = review.get("approved", False)
            print(f"[REVIEWER] {'APPROVED' if approved else 'CHANGES REQUESTED'} "
                  f"(attempt {i + 1}/{self.max_iterations})")
            if approved:
                break
            self.developer.fix("\n".join(review.get("comments", [])), spec)
            self.tester.test()
            self.git.commit(f"Agent review fix: {task[:60]}")

        if not self._confirm(f"Push '{branch}' and open PR?"):
            return f"Committed locally on '{branch}'."

        print(f"[GIT] Pushing '{branch}'...")
        self.git.push(branch)

        pr_url = self._create_pr(branch, task, spec)
        if pr_url:
            print(f"[GITHUB] PR: {pr_url}")
        else:
            print("[GITHUB] Branch pushed — open PR manually.")

        # Generate run summary report
        report = self.tasks.generate_report(task, branch, pr_url)
        print("\n[SUMMARY]")
        print(report)

        return "Done. Branch: " + branch + (f" | PR: {pr_url}" if pr_url else "")

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

        tdd_note = "\n\n*TDD mode: tests written before implementation.*" if self.tdd_mode else ""
        tests_md = "\n".join(f"- {t}" for t in spec.get("tests_to_write", []))
        body = (
            f"Automated PR from multi-agent-lab.\n\n"
            f"**Task:** {task}\n\n"
            f"**Approach:** {spec.get('approach', '')}\n\n"
            + (f"**Tests written:**\n{tests_md}\n" if tests_md else "")
            + tdd_note
            + "\n\n*Architect → Planner → Developer → Tester → Reviewer pipeline.*"
        )
        try:
            resp = requests.post(
                f"https://api.github.com/repos/{owner}/{repo}/pulls",
                headers={"Authorization": f"Bearer {token}",
                         "Accept": "application/vnd.github+json"},
                json={"title": f"Agent: {task[:72]}", "head": branch,
                      "base": "main", "body": body},
                timeout=30,
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
