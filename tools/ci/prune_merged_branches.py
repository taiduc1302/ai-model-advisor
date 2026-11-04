"""One-time, guarded cleanup of historical GitHub branches.

Only explicit allowlisted branches with merged PRs at the exact same head SHA
can be deleted. Unmerged work, changed branches, main and protected refs are
always preserved. The default mode is dry-run.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

REPOSITORY = "taiduc1302/ai-model-advisor"

MERGED_BRANCHES: dict[str, int | None] = {
    "feature/standalone-v0.2": 1,
    "feature/current-routing-v0.3": 2,
    "feature/model-monitor-v0.4": 3,
    "feature/personal-feedback-v0.5": 4,
    "feature/routing-decision-v0.6": 5,
    "feature/decision-cli-v0.7": 6,
    "feature/decision-feedback-v0.8": 7,
    "feature/task-profiler-v0.9": 8,
    "feature/evaluation-gate-v0.10": 9,
    "feature/paired-outcome-evaluation-v0.11": 10,
    "feature/policy-replay-v0.12": 11,
    "feature/controlled-experiment-v0.13": 12,
    "feature/benchmark-runner-v0.14": 13,
    "feature/benchmark-suite-v0.15": 14,
    "feature/benchmark-analysis-v0.16": 15,
    "feature/web-ux-v0.17": 16,
    "feature/feedback-ux-v0.18": 17,
    "infra/monitor-vercel-branch-hygiene-2026-11": 19,
    # This one-time workflow may delete its own now-merged PR branch.
    "infra/cleanup-merged-branches-once": None,
}
NEVER_DELETE = {
    "main", "docs/ecc-review-first-pilot-2026-10",
    "feat/civil-ai-agent-kit-v0-1",
}


def eligibility(
    branch_name: str,
    branch_data: dict[str, Any],
    pr: dict[str, Any],
    open_heads: set[str],
    *,
    default_branch: str,
) -> tuple[bool, str]:
    """Pure safety decision; never infer merged status from branch age."""
    if branch_name not in MERGED_BRANCHES or branch_name in NEVER_DELETE:
        return False, "not in safe allowlist"
    if branch_name == default_branch or branch_data.get("protected") is not False:
        return False, "default or protected branch"
    if branch_name in open_heads:
        return False, "referenced by an open PR"
    if pr.get("merged_at") is None or pr.get("state") != "closed":
        return False, "PR has not been merged"
    head = pr.get("head") or {}
    head_repo = head.get("repo") or {}
    base = pr.get("base") or {}
    if head.get("ref") != branch_name or head_repo.get("full_name") != REPOSITORY:
        return False, "PR head name/repository mismatch"
    if base.get("ref") != default_branch:
        return False, "PR merged into a different base branch"
    branch_sha = (branch_data.get("commit") or {}).get("sha")
    if branch_sha != head.get("sha"):
        return False, "branch moved after the reviewed merged PR"
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch_name):
        return False, "invalid branch reference"
    if ".." in branch_name or "//" in branch_name:
        return False, "invalid branch reference"
    return True, "confirmed merged, unchanged and unprotected"


def github_request(
    token: str, method: str, path: str,
) -> dict[str, Any] | list[dict[str, Any]] | None:
    url = "https://api.github.com/repos/" + REPOSITORY + path
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "ai-model-advisor-one-time-branch-cleanup",
        },
        method=method,
    )
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            body = response.read()
            return json.loads(body) if body else None
    except urllib.error.HTTPError as exc:
        if exc.code == 404 and method == "GET":
            return None
        # Never print response bodies or tokens.
        raise RuntimeError(f"GitHub {method} failed with HTTP {exc.code}") from None


def prune(*, apply: bool, token: str) -> dict[str, list[str]]:
    repo = github_request(token, "GET", "")
    if not isinstance(repo, dict) or repo.get("default_branch") != "main":
        raise RuntimeError("Unexpected repository or default branch")
    open_prs = github_request(token, "GET", "/pulls?state=open&per_page=100")
    if not isinstance(open_prs, list):
        raise RuntimeError("Unable to read open pull requests")
    if len(open_prs) == 100:
        raise RuntimeError("Open PR inventory might be incomplete; fail closed")
    open_heads = {
        pr["head"]["ref"]
        for pr in open_prs
        if (pr.get("head") or {}).get("repo", {}).get("full_name") == REPOSITORY
    }
    report: dict[str, list[str]] = {
        "deleted": [], "eligible_dry_run": [], "skipped": [], "errors": []
    }
    for name, pr_number in MERGED_BRANCHES.items():
        encoded = urllib.parse.quote(name, safe="/")
        branch_data = github_request(token, "GET", "/branches/" + encoded)
        if branch_data is None:
            report["skipped"].append(name + ": already absent")
            continue
        if not isinstance(branch_data, dict):
            report["errors"].append(name + ": invalid branch response")
            continue
        if pr_number is None:
            prs = github_request(token, "GET", "/pulls?state=closed&per_page=100")
            if not isinstance(prs, list) or len(prs) == 100:
                report["errors"].append(name + ": incomplete merged PR inventory")
                continue
            matches = [
                pr for pr in prs
                if (pr.get("head") or {}).get("ref") == name
                and pr.get("merged_at")
                and (pr.get("head") or {}).get("repo", {}).get("full_name") == REPOSITORY
            ]
            if len(matches) != 1:
                report["skipped"].append(name + ": missing unique merged PR")
                continue
            pr_number = matches[0]["number"]
        pr = github_request(token, "GET", f"/pulls/{pr_number}")
        if not isinstance(pr, dict):
            report["errors"].append(name + ": merged PR not available")
            continue
        good, reason = eligibility(
            name, branch_data, pr, open_heads, default_branch=repo["default_branch"]
        )
        if not good:
            report["skipped"].append(name + ": " + reason)
            continue
        if not apply:
            report["eligible_dry_run"].append(name)
            continue
        try:
            github_request(token, "DELETE", "/git/refs/heads/" + encoded)
            report["deleted"].append(name)
        except RuntimeError as exc:
            report["errors"].append(name + ": " + str(exc))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Guarded merged-branch cleanup")
    parser.add_argument("--apply", action="store_true", help="Actually delete verified merged refs")
    args = parser.parse_args(argv)
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        parser.error("GITHUB_TOKEN must be supplied via the Actions environment")
    report = prune(apply=args.apply, token=token)
    print(json.dumps(report, indent=2, sort_keys=True))
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary_path:
        with open(summary_path, "a", encoding="utf-8") as output:
            output.write("## One-time merged branch cleanup\n\n")
            output.write(f"Deleted: {len(report['deleted'])}\n\n")
            output.write(f"Skipped: {len(report['skipped'])}\n\n")
            output.write(f"Errors: {len(report['errors'])}\n")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
