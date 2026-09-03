# Upstream tracking (Milestone 8)

This project is a from-scratch Linux/Python reimplementation of
[`Lurmel/UnRen-forall`](https://github.com/Lurmel/UnRen-forall), a Windows
batch-script toolkit. `.github/workflows/upstream-check.yml` runs weekly
and tells us when upstream changes — it never pulls in upstream code
automatically.

## What the workflow does

Every Monday at 06:00 UTC (and on manual `workflow_dispatch`):

1. `.github/scripts/upstream_check.py` queries the GitHub REST API for
   `Lurmel/UnRen-forall`'s default branch HEAD commit and latest release,
   and compares them against the last state recorded in
   `.github/upstream-state.json` (committed to this repo).
2. If nothing changed, the workflow exits quietly (only the
   `last_checked_at` timestamp advances).
3. If the upstream HEAD SHA or latest release tag changed since the last
   check, the workflow:
   - checks whether an issue labeled `upstream-update` is already open
     (avoids duplicate issues across consecutive weekly runs while a
     previous change is still under review);
   - if not, opens a new issue titled
     `Upstream update detected: Lurmel/UnRen-forall @ <sha>` containing:
     - the previous and current upstream commit SHAs,
     - the latest upstream release tag/link, if any,
     - the list of commits between the two SHAs (with links),
     - the list of changed files (with a compare link for the full diff),
     - a reminder that compatibility review is required before anything
       is ported;
   - advances `.github/upstream-state.json` to the new SHA/tag **only
     after** the issue is filed successfully, and commits that file back
     to the repo (`[skip ci]`). If issue creation fails, the state file is
     left as-is so the next scheduled run retries the same change instead
     of silently losing it.
4. The workflow never checks out, merges, cherry-picks, or otherwise
   touches upstream source in this repo. It only reads the upstream repo
   over the GitHub API.

## First run / baseline

The very first time the workflow runs (no `.github/upstream-state.json`
in the repo yet), there is nothing to compare against, so it records the
current upstream HEAD as a baseline and does **not** open an issue. Every
run after that compares against the previous recorded state.

## Manual compatibility review process

When an `upstream-update` issue appears:

1. Read the linked upstream commits/compare view to understand what
   changed (new Ren'Py version support, new detection logic, bugfixes,
   new toolkit features, vendored-tool version bumps, etc.).
2. Cross-reference against `docs/UPSTREAM-BEHAVIOR.md` (the parity matrix
   from the original archaeology pass) to see whether the change affects
   behavior this port already implements, or introduces something new.
3. Decide and record the outcome as a comment on the issue:
   - **No action needed** — upstream change is cosmetic/Windows-specific
     (e.g. batch-script-only refactor, registry/UAC/PowerShell-only
     change) and has no Linux-port equivalent to update.
   - **Port needed** — file a follow-up implementation task/issue
     describing the concrete change required in `src/unren/`, referencing
     the upstream commit(s).
   - **Investigate further** — open questions that need a deeper look
     before deciding.
4. Close the `upstream-update` issue once triaged (either directly, or by
   linking it to a follow-up implementation issue and closing it once
   that's filed).

No upstream code is ever merged automatically by this workflow — every
port of an upstream change goes through the normal PR/review process for
this repo, same as any other change.

## Local dry-run

You can run the checker script locally against the real upstream repo
without touching `.github/upstream-state.json`:

```sh
cp .github/upstream-state.json /tmp/upstream-state-backup.json  # if it exists
python3 .github/scripts/upstream_check.py
git checkout -- .github/upstream-state.json  # discard the local state change
```

Set `GH_TOKEN`/`GITHUB_TOKEN` in your environment first if you hit
GitHub API rate limits (60 requests/hour unauthenticated).

## Files

- `.github/workflows/upstream-check.yml` — the scheduled workflow.
- `.github/scripts/upstream_check.py` — stdlib-only Python script that
  does the actual comparison and issue-body generation.
- `.github/upstream-state.json` — persisted last-seen upstream SHA/release
  tag; committed back to the repo by the workflow after each detected
  change. Not present until the workflow's first run.
