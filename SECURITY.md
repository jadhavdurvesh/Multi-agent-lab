# 🔒 Security Policy

Thank you for helping keep Multi-agent-lab secure.

---

## Supported Versions

| Version | Supported |
|---------|:---------:|
| Latest (`main`) | ✅ |
| Older branches | ❌ |

---

## Reporting a Vulnerability

**Do not open a public GitHub Issue for security vulnerabilities.**

Report privately via **GitHub Security Advisories** (preferred):
Repository → Security tab → "Report a vulnerability".

Or email: jadhavdurvesh65@gmail.com

---

## What to Include

- Description of the vulnerability
- Steps to reproduce
- Affected component (`agents/`, `tools/`, `providers/`, workflows, etc.)
- Potential impact
- Suggested mitigation (optional)

---

## Response Process

1. Acknowledge receipt of the report.
2. Investigate and determine severity.
3. Develop and test a fix.
4. Release the fix.
5. Publicly disclose when appropriate.

Please allow reasonable time to investigate before public disclosure.

---

## Scope

This project is a **code-execution tool** — it runs real shell commands,
writes files, commits to git, and pushes to GitHub on your behalf. That
makes these categories especially relevant:

- **Prompt injection** — a malicious task description or file content in
  the target repo that causes an agent to run unintended commands or write
  malicious files
- **Secret exposure** — anything that could cause API keys or tokens to
  be printed in logs, committed to git, or included in PR descriptions
- **Path traversal** — bypassing the `FileSystemTools` repo-root guard to
  read or write files outside the target repo
- **Remote code execution** — via the `TerminalTools` shell command
  interface (note: this is intentionally present for the Tester agent —
  report anything that bypasses the intended scope)
- **Dependency vulnerabilities** — in `requirements.txt`
- **Workflow injection** — GitHub Actions expression injection via
  untrusted inputs (task descriptions, issue titles, etc.)

General bugs and feature requests go through GitHub Issues instead.

---

## Security Notes for Users

- **Never commit real API keys.** `.env` is gitignored. Workflow keys go
  in GitHub Actions secrets, never in workflow YAML files.
- **Safe mode is the default** (`--autonomous` must be explicitly passed).
  Running in safe mode lets you inspect the plan before any files are
  written or commands are executed.
- **The `TerminalTools` shell interface is not a sandbox.** It runs with
  the same permissions as the process that launched it. Only point the
  agents at repos you have a disposable copy of, or run in a container.
- **`TARGET_REPO_PAT` should be scoped to minimum permissions** — Contents
  and Pull requests (Read and write) on the target repo only, not your
  entire account.
