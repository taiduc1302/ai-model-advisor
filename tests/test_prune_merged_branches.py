from tools.ci.prune_merged_branches import (
    MERGED_BRANCHES, NEVER_DELETE, eligibility,
    REPOSITORY,
)


def fixtures(name="feature/web-ux-v0.17"):
    branch = {"name": name, "protected": False, "commit": {"sha": "abc"}}
    pr = {
        "state": "closed", "merged_at": "2026-10-22T18:48:03Z",
        "head": {
            "ref": name, "sha": "abc",
            "repo": {"full_name": REPOSITORY},
        },
        "base": {"ref": "main"},
    }
    return branch, pr


def test_explicit_merged_branch_is_eligible():
    branch, pr = fixtures()
    assert eligibility(
        branch["name"], branch, pr, set(), default_branch="main"
    )[0]


def test_all_nonrelease_work_is_excluded():
    for name in NEVER_DELETE:
        branch, pr = fixtures(name)
        assert not eligibility(name, branch, pr, set(), default_branch="main")[0]


def test_open_prs_are_never_deleted():
    branch, pr = fixtures()
    assert not eligibility(
        branch["name"], branch, pr, {branch["name"]}, default_branch="main"
    )[0]


def test_head_movement_fails_closed():
    branch, pr = fixtures()
    branch["commit"]["sha"] = "new-commit"
    allowed, reason = eligibility(
        branch["name"], branch, pr, set(), default_branch="main"
    )
    assert not allowed
    assert "moved" in reason


def test_unmerged_pr_and_protected_branch_fail_closed():
    branch, pr = fixtures()
    pr["merged_at"] = None
    assert not eligibility(
        branch["name"], branch, pr, set(), default_branch="main"
    )[0]
    pr["merged_at"] = "2026-10-22T18:48:03Z"
    branch["protected"] = True
    assert not eligibility(
        branch["name"], branch, pr, set(), default_branch="main"
    )[0]


def test_cross_repo_or_other_base_rejected():
    branch, pr = fixtures()
    pr["head"]["repo"]["full_name"] = "someone/other"
    assert not eligibility(
        branch["name"], branch, pr, set(), default_branch="main"
    )[0]
    pr["head"]["repo"]["full_name"] = REPOSITORY
    pr["base"]["ref"] = "release"
    assert not eligibility(
        branch["name"], branch, pr, set(), default_branch="main"
    )[0]


def test_inventory_is_explicit_and_only_one_self_cleanup_branch():
    assert MERGED_BRANCHES["feature/web-ux-v0.17"] == 16
    assert MERGED_BRANCHES["infra/monitor-vercel-branch-hygiene-2026-11"] == 19
    assert MERGED_BRANCHES["infra/cleanup-merged-branches-once"] is None
    assert "main" not in MERGED_BRANCHES
    assert "feat/civil-ai-agent-kit-v0-1" not in MERGED_BRANCHES
