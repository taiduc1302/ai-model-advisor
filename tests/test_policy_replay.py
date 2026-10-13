import pytest

from ai_model_advisor.policy_replay import evaluate_policies


def row(task, policy, outcome, *, cost=None, category="coding"):
    return {
        "task_id": task, "policy_id": policy, "outcome": outcome,
        "category": category, "cost_usd": cost,
    }


def test_holdout_paired_comparison():
    rows = []
    for i in range(5):
        rows.extend([
            row(f"test-{i}", "old", "partial", cost=2.0),
            row(f"test-{i}", "new", "success", cost=1.0),
        ])
    result = evaluate_policies(rows, baseline="old", candidate="new")
    assert result["status"] == "review_ready"
    assert result["candidate_minus_baseline_quality"] == 0.5
    assert result["candidate_minus_baseline_median_cost_usd"] == -1
    assert result["safe_to_apply"] is False


def test_training_leakage_is_rejected():
    with pytest.raises(ValueError, match="leakage"):
        evaluate_policies(
            [row("secret", "old", "success")],
            baseline="old", candidate="new",
            training_task_ids={"secret"},
        )


def test_no_counterfactual_imputation_and_duplicate_exclusion():
    result = evaluate_policies([
        row("only-one", "old", "success"),
        row("duplicate", "old", "success"),
        row("duplicate", "new", "success"),
        row("duplicate", "new", "failure"),
        row("paired", "old", "failure"),
        row("paired", "new", "partial"),
    ], baseline="old", candidate="new")
    assert result["matched_task_count"] == 1
    assert result["excluded_unpaired"] == 1
    assert result["excluded_duplicate_or_category_mismatch"] == 1
    assert result["status"] == "insufficient_evidence"
    assert result["paired_cost_count"] == 0


def test_category_mismatch_excluded():
    result = evaluate_policies([
        row("x", "old", "success", category="coding"),
        row("x", "new", "success", category="research"),
    ], baseline="old", candidate="new")
    assert result["matched_task_count"] == 0
    assert result["excluded_duplicate_or_category_mismatch"] == 1


def test_invalid_observations_rejected():
    with pytest.raises(ValueError, match="outcome"):
        evaluate_policies([row("x", "old", "unknown")], baseline="old", candidate="new")
    with pytest.raises(ValueError, match="different"):
        evaluate_policies([], baseline="old", candidate="old")
