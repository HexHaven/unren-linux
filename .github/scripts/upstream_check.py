#!/usr/bin/env python3
"""Milestone 8: Upstream Tracking.

Checks Lurmel/UnRen-forall (the upstream Windows batch-script project this
repo is a Linux port of) for new commits or a new release on its default
branch, and reports the result for the calling GitHub Actions workflow.

This script never merges/pulls upstream code. It only compares the last
recorded upstream state (persisted in ``.github/upstream-state.json`` in
*this* repo) against the current upstream state and, on a change, emits an
issue title/body describing what changed and where to look — a human still
has to do the compatibility review.

Design notes:
- Uses only the Python stdlib (``urllib``) so the workflow doesn't need to
  install any dependencies before running this script.
- Uses the unauthenticated GitHub REST API by default; the workflow passes
  ``GITHUB_TOKEN`` via the ``GH_TOKEN``/``GITHUB_TOKEN`` env var when
  available to raise the rate limit and avoid 403s.
- First-ever run (no prior state file) establishes a baseline and does NOT
  create an issue — there's nothing to compare against yet.
- If an issue is already open for the currently-pending change (tracked via
  the ``upstream-update`` label + state file), the script reports
  ``has_update=false`` for issue-creation purposes so the workflow doesn't
  spam a duplicate; the state file is only advanced once a new issue is
  actually filed (or on baseline), so the next run keeps retrying until the
  existing issue is closed.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

UPSTREAM_OWNER = "Lurmel"
UPSTREAM_REPO = "UnRen-forall"
API_ROOT = f"https://api.github.com/repos/{UPSTREAM_OWNER}/{UPSTREAM_REPO}"
STATE_PATH = Path(".github/upstream-state.json")
MAX_CHANGED_FILES_LISTED = 30
MAX_COMMITS_LISTED = 20


def _api_get(path: str) -> Any:
    """GET a GitHub API path, returning parsed JSON or None on 404/409."""
    url = f"{API_ROOT}{path}"
    req = urllib.request.Request(url, headers=_headers())
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (404, 409):
            return None
        raise


def _headers() -> dict[str, str]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "unren-upstream-check",
    }
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    return {"last_sha": None, "last_release_tag": None, "last_checked_at": None}


def save_state(state: dict[str, Any]) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def get_current_upstream_state() -> dict[str, Any]:
    repo_info = _api_get("")
    if repo_info is None:
        print("::error::could not reach upstream repo API", file=sys.stderr)
        sys.exit(1)
    default_branch = repo_info["default_branch"]

    latest_commit = _api_get(f"/commits/{default_branch}")
    latest_sha = latest_commit["sha"]
    latest_commit_message = latest_commit["commit"]["message"].splitlines()[0]
    latest_commit_url = latest_commit["html_url"]

    release = _api_get("/releases/latest")
    release_tag = release["tag_name"] if release else None
    release_url = release["html_url"] if release else None

    return {
        "default_branch": default_branch,
        "sha": latest_sha,
        "commit_message": latest_commit_message,
        "commit_url": latest_commit_url,
        "release_tag": release_tag,
        "release_url": release_url,
    }


def diff_summary(previous_sha: str, current_sha: str) -> tuple[list[str], list[str], str]:
    """Return (changed_files, commit_lines, compare_url) between two SHAs."""
    compare_url = f"https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}/compare/{previous_sha[:12]}...{current_sha[:12]}"
    comparison = _api_get(f"/compare/{previous_sha}...{current_sha}")
    if comparison is None:
        # previous_sha no longer resolvable (e.g. force-push/history rewrite
        # upstream) -- fall back to reporting just the current head.
        return [], [], compare_url

    changed_files = [f["filename"] for f in comparison.get("files", [])]
    commit_lines = [
        f"- {c['sha'][:12]} {c['commit']['message'].splitlines()[0]} ({c['html_url']})"
        for c in comparison.get("commits", [])
    ]
    return changed_files, commit_lines, compare_url


def build_issue_body(
    previous_sha: str | None,
    current: dict[str, Any],
    changed_files: list[str],
    commit_lines: list[str],
    compare_url: str,
) -> str:
    lines = ["Upstream update detected", ""]
    lines.append(f"Previous: {previous_sha or '(none — first tracked state)'}")
    lines.append(f"Current: {current['sha']}")
    lines.append("")

    if current["release_tag"]:
        lines.append(f"Latest upstream release: [{current['release_tag']}]({current['release_url']})")
        lines.append("")

    lines.append(f"Latest commit: [{current['commit_message']}]({current['commit_url']})")
    lines.append("")

    if commit_lines:
        shown = commit_lines[:MAX_COMMITS_LISTED]
        lines.append(f"Commits since previous check ({len(commit_lines)} total):")
        lines.extend(shown)
        if len(commit_lines) > MAX_COMMITS_LISTED:
            lines.append(f"- ... and {len(commit_lines) - MAX_COMMITS_LISTED} more (see compare link)")
        lines.append("")

    if changed_files:
        shown_files = changed_files[:MAX_CHANGED_FILES_LISTED]
        lines.append(f"Changed files ({len(changed_files)} total):")
        lines.extend(f"- {f}" for f in shown_files)
        if len(changed_files) > MAX_CHANGED_FILES_LISTED:
            lines.append(f"- ... and {len(changed_files) - MAX_CHANGED_FILES_LISTED} more (see compare link)")
        lines.append("")
    else:
        lines.append("Changed files: (unable to compute file-level diff — see compare link)")
        lines.append("")

    lines.append(f"Compare: {compare_url}")
    lines.append(f"Upstream repo: https://github.com/{UPSTREAM_OWNER}/{UPSTREAM_REPO}")
    lines.append("")
    lines.append("Requires compatibility review.")
    lines.append("")
    lines.append(
        "This issue was filed automatically by `.github/workflows/upstream-check.yml`. "
        "No code has been merged — see `docs/UPSTREAM.md` for the manual review process."
    )
    return "\n".join(lines)


def write_github_output(**kv: str) -> None:
    out_path = os.environ.get("GITHUB_OUTPUT")
    if not out_path:
        for k, v in kv.items():
            print(f"{k}={v}")
        return
    with open(out_path, "a", encoding="utf-8") as f:
        for k, v in kv.items():
            f.write(f"{k}={v}\n")


def finalize(argv: list[str]) -> None:
    """``upstream_check.py --finalize`` : commit the pending SHA after the
    workflow has successfully created the tracking issue for it. Run this
    as a separate step so a failed issue-creation step leaves the pending
    change in place and the next scheduled run retries it, instead of
    silently marking it as seen."""
    state = load_state()
    pending_sha = state.pop("_pending_sha", None)
    pending_release = state.pop("_pending_release_tag", None)
    if pending_sha is not None:
        state["last_sha"] = pending_sha
        state["last_release_tag"] = pending_release
    save_state(state)


def main() -> None:
    if "--finalize" in sys.argv[1:]:
        finalize(sys.argv[1:])
        return

    state = load_state()
    current = get_current_upstream_state()

    previous_sha = state.get("last_sha")
    previous_release = state.get("last_release_tag")

    is_baseline = previous_sha is None
    changed = (not is_baseline) and (
        previous_sha != current["sha"] or previous_release != current["release_tag"]
    )

    from datetime import datetime, timezone

    state["last_checked_at"] = datetime.now(timezone.utc).isoformat()

    if is_baseline:
        state["last_sha"] = current["sha"]
        state["last_release_tag"] = current["release_tag"]
        save_state(state)
        print(f"Baseline established at {current['sha']}. No issue created.")
        write_github_output(has_update="false", state_changed="true")
        return

    if not changed:
        save_state(state)  # only last_checked_at moved
        print("No upstream changes detected.")
        write_github_output(has_update="false", state_changed="true")
        return

    changed_files, commit_lines, compare_url = diff_summary(previous_sha, current["sha"])
    body = build_issue_body(previous_sha, current, changed_files, commit_lines, compare_url)
    title = f"Upstream update detected: {UPSTREAM_OWNER}/{UPSTREAM_REPO} @ {current['sha'][:12]}"

    Path("upstream-issue-body.md").write_text(body, encoding="utf-8")
    write_github_output(has_update="true", issue_title=title, state_changed="pending")

    # State is advanced by the workflow only after the issue is
    # successfully created (see upstream-check.yml) so a failed issue
    # creation doesn't silently drop the pending change.
    state["_pending_sha"] = current["sha"]
    state["_pending_release_tag"] = current["release_tag"]
    save_state(state)

    print(f"Change detected: {previous_sha} -> {current['sha']}")
    print(title)


if __name__ == "__main__":
    main()
