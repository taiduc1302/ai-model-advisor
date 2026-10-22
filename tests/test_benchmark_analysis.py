import json
import subprocess
import sys

import pytest

from ai_model_advisor.benchmark_analysis import analyze_results
from ai_model_advisor.experiment_protocol import make_plan


def make_data(count=20, *, multi_factor=False):
    spec = {
        "schema_version": 1, "experiment_id": "review-001", "seed": 42,
        "dataset_id": "synthetic-v1", "environment_id": "isolated-v1",
        "evaluator_id": "json-judge-v1", "training_task_ids": ["train-1"],
        "arms": {
            "A": {"provider": "openai", "model_id": "example-model", "effort": "low", "execution_mode": "single"},
            "B": {"provider": "openai", "model_id": "other-model" if multi_factor else "example-model", "effort": "high", "execution_mode": "single"},
        },
        "tasks": [
            {"task_id": f"held-{i}", "category": "arithmetic" if i % 2 else "coding", "prompt_sha256": "a" * 64}
            for i in range(count)
        ],
        "minimum_pairs": 5,
    }
    plan = make_plan(spec)
    rows = []
    for run in plan["runs"]:
        row = {k: v for k, v in run.items() if k != "order"}
        row.update({
            "outcome": "success" if run["arm"] == "B" else "failure",
            "cost_usd": 1.0 if run["arm"] == "B" else 0.2,
            "estimated_cost_usd": 0.8 if run["arm"] == "B" else 0.1,
            "latency_seconds": 12 if run["arm"] == "B" else 5,
            "retries": 0 if run["arm"] == "B" else 1,
        })
        rows.append(row)
    return plan, rows


def test_empty_experiment_not_a_winner():
    plan, _ = make_data()
    report = analyze_results(plan, [])
    assert report["evidence_status"] == "insufficient_pairs"
    assert report["overall"]["arm_A"]["pass_rate"] is None
    assert report["overall"]["paired_quality"]["mean_delta_B_minus_A"] is None
    assert report["automatic_winner"] is None
    assert report["safe_to_apply"] is False
    assert report["overall"]["pair_coverage"] == 0


def test_twenty_matched_runs_produce_review_signal_not_automatic_winner():
    plan, rows = make_data()
    report = analyze_results(plan, rows, bootstrap_samples=200)
    assert report["evidence_status"] == "directional_signal_manual_review"
    assert report["comparison_scope"]["type"] == "isolated_reasoning_effort"
    assert report["overall"]["arm_A"]["pass_rate"] == 0
    assert report["overall"]["arm_B"]["pass_rate"] == 1
    assert report["overall"]["paired_quality"]["mean_delta_B_minus_A"] == 1
    assert report["overall"]["paired_quality"]["bootstrap_95_descriptive"] == [1.0, 1.0]
    assert report["overall"]["verified_billed_cost_usd"]["median_paired_delta_B_minus_A"] == 0.8
    assert report["overall"]["registry_estimated_cost_usd"]["median_paired_delta_B_minus_A"] == 0.7
    assert report["automatic_winner"] is None
    assert len(report["categories"]) == 2


def test_few_pairs_and_missing_bills_have_cautions():
    plan, rows = make_data()
    rows = rows[:10]
    for row in rows:
        row.pop("cost_usd", None)
    report = analyze_results(plan, rows, bootstrap_samples=200)
    assert report["evidence_status"] == "exploratory_small_sample"
    assert report["overall"]["completed_pairs"] == 5
    assert report["overall"]["verified_billed_cost_usd"]["paired_count"] == 0
    assert report["overall"]["registry_estimated_cost_usd"]["paired_count"] == 5
    assert any("Verified billed cost" in caution for caution in report["cautions"])


def test_multiple_factors_are_not_mislabeled_effort_only():
    plan, rows = make_data(multi_factor=True)
    report = analyze_results(plan, rows, bootstrap_samples=200)
    assert report["comparison_scope"]["type"] == "multiple_configuration_factors"
    assert set(report["comparison_scope"]["changed_fields"]) == {"effort", "model_id"}
    assert any("cannot be attributed solely" in c for c in report["cautions"])


def test_inconsistent_result_and_training_leakage_fail_closed():
    plan, rows = make_data()
    rows[0]["model_id"] = "tampered"
    with pytest.raises(ValueError, match="mismatched model_id"):
        analyze_results(plan, rows)
    plan, rows = make_data()
    with pytest.raises(ValueError, match="leakage"):
        analyze_results(plan, rows, additional_training_task_ids={"held-0"})


def test_seeded_report_is_deterministic():
    plan, rows = make_data()
    a = analyze_results(plan, rows, bootstrap_samples=200)
    b = analyze_results(plan, rows, bootstrap_samples=200)
    assert a == b


def test_cli_generates_json_report(tmp_path):
    plan, rows = make_data(5)
    path = tmp_path / "plan.json"
    ledger = tmp_path / "runs.jsonl"
    out = tmp_path / "report.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    ledger.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    subprocess.run([
        sys.executable, "-m", "ai_model_advisor.benchmark_analysis",
        "--plan", str(path), "--observations", str(ledger),
        "--bootstrap-samples", "200", "--output", str(out),
    ], check=True, capture_output=True, text=True)
    assert json.loads(out.read_text())["safe_to_apply"] is False
