# Troubleshooting

Real problems encountered running this, and what actually fixed them —
not a generic checklist.

## "Resource not accessible by personal access token" / git push returns 403

You have a fine-grained PAT, it looks like it should work, but pushing (or
any write call) fails. The GitHub API's `permissions` field on a repo
response (`admin`, `push`, etc.) reflects **your account's** role on that
repo — not what the token itself is actually scoped to. It'll show
`"push": true` even when the token can't push anything. Don't trust it.

Actual fix: go to the token's settings page (Settings → Developer settings →
Fine-grained tokens → the token → Repositories → the repo → Permissions) and
check each permission individually:

- **Contents: Read and write** — required for `git push`. This is the one
  that's usually missing; it's easy to set Pull requests without noticing
  Contents defaulted to no access.
- **Pull requests: Read and write** — required for opening PRs via the API
  or `gh pr create`.
- **Metadata: Read-only** — required, and auto-added; you can't remove it.

After changing permissions, click **Update** on that page — no need to
regenerate the token, the same token string picks up the new scope
immediately.

## A GitHub Actions run fails and you can't tell why

Two things worth knowing:

- **`--autonomous` is hardcoded in both workflows.** A workflow run can't
  pause for the `input()` approval prompt the way a local run can, so there
  is no safe-mode pause in CI — only dispatch a run with a task you're
  genuinely fine with the agents attempting unsupervised.
- **Raw step logs aren't always fetchable via the API.** `GET
  /repos/{owner}/{repo}/actions/jobs/{job_id}/logs` redirects to Azure blob
  storage (`productionresultssa4.blob.core.windows.net` at the time of
  writing) — if you're fetching logs from a sandboxed/restricted network,
  that redirect target needs to be in the allowlist, or the download will
  silently fail. Reading logs from the Actions tab in a browser always
  works; it's only programmatic fetching that can hit this.

If an automated "fix" for a failing job just deletes a file (documentation,
config, whatever) rather than changing the actual failing code — that's a
model giving up and taking the path of least resistance, not a real fix.
Don't merge it; get the actual step log first (from the Actions tab, not
an API call) and diagnose from that.

## A subtask's diff is empty / commits look like no-ops

`git.commit()` uses `--allow-empty` on purpose, so a subtask that produced
no real edits still commits cleanly instead of crashing the run on "nothing
to commit." That's a feature for run stability, but it means an empty
commit in the history usually indicates the Developer agent's response for
that subtask didn't parse into valid edits (bad JSON, wrong format,
model refused) — check `.agent/history/*.jsonl` for that subtask's
`developer` `model_call` event and look at the raw `text` field.

## Reviewer never approves / loops through all retries

Same root cause as above — `ReviewerAgent.review()` returns `"approved":
false` immediately if the diff is empty, and the fix loop can't make
progress if the Developer isn't producing real edits. Fix the Developer
side first; the Reviewer looping is a symptom, not the bug.

## `pytest` reports "no tests ran" against a target repo

The Tester agent runs whatever `--test-command` you gave it (default
`pytest -q`) with `cwd` set to the target repo root. If that repo's test
files exist but are empty stubs, or tests live in a subdirectory pytest
doesn't discover by default, pytest exits with code 5 ("no tests
collected") — verified directly, this is not exit code 0. `TesterAgent`
treats any non-zero exit as `passed: false`, so a target repo with no
real tests will loop through every retry and get reported as a failure,
even though nothing is actually broken. That's a target-repo
test-discovery problem, not a bug in this tool; check `--test-command`
matches how you'd run the target repo's tests manually, and make sure
there's at least one real test for the Tester to find.
