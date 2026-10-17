import copy
import hashlib
import json
import subprocess
import sys

import pytest

from ai_model_advisor.experiment_protocol import evaluate_plan, make_plan


def spec():
    return {
        "schema_version": 1, "experiment_id": "controlled-001", "seed": 42,
        "dataset_id": "fixture-v1", "environment_id": "python311",
        "evaluator_id": "rubric-v1", "training_task_ids": ["training-1"],
        "arms": {
            "A": {"provider": "openai", "model_id": "model-a", "effort": "high", "execution_mode": "single"},
            "B": {"provider": "anthropic", "model_id": "model-b", "effort": "medium", "execution_mode": "single"},
        },
        "tasks": [
            {"task_id": f"holdout-{n}", "category": "debugging",
             "prompt_sha256": hashlib.sha256(f"task-{n}".encode()).hexdigest()}
            for n in range(5)
        ],
        "minimum_pairs": 5,
    }


def results(plan):
    rows = []
    for run in plan["runs"]:
        row = {key: value for key, value in run.items() if key != "order"}
        row.update({
            "outcome": "success" if run["arm"] == "B" else "partial",
            "cost_usd": 0.5 if run["arm"] == "B" else 1.0,
            "latency_seconds": 5 if run["arm"] == "B" else 10,
            "retries": 0 if run["arm"] == "B" else 1,
        })
        rows.append(row)
    return rows


def test_counterbalanced_plan_is_reproducible():
    first = make_plan(spec())
    assert first == make_plan(spec())
    assert first["order_balance"] == {"A_first": 3, "B_first": 2}
    assert len(first["runs"]) == 10
    assert len({r["run_id"] for r in first["runs"]}) == 10
    assert first["safe_to_apply"] is False


def test_complete_observations_are_review_ready_not_promotion():
    plan = make_plan(spec())
    report = evaluate_plan(plan, results(plan))
    assert report["status"] == "review_ready"
    assert report["safe_to_apply"] is False
    assert report["overall"]["paired_tasks"] == 5
    assert report["overall"]["candidate_B_minus_A_mean_quality"] == 0.5
    assert report["overall"]["candidate_B_minus_A_median_cost_usd"] == -0.5
    assert report["overall"]["candidate_B_minus_A_median_latency_seconds"] == -5
    assert report["overall"]["candidate_B_minus_A_median_retries"] == -1


def test_missing_pairs_do_not_generate_counterfactuals():
    plan = make_plan(spec())
    report = evaluate_plan(plan, results(plan)[:-1])
    assert report["status"] == "insufficient_evidence"
    assert report["overall"]["paired_tasks"] == 4
    assert len(report["incomplete_task_ids"]) == 1


def test_tampering_and_duplicate_results_fail_closed():
    plan = make_plan(spec())
    rows = results(plan)
    corrupted = copy.deepcopy(plan)
    corrupted["runs"][0]["effort"] = "max"
    with pytest.raises(ValueError, match="modified"):
        evaluate_plan(corrupted, rows)
    altered = copy.deepcopy(rows)
    altered[0]["prompt_sha256"] = "f" * 64
    with pytest.raises(ValueError, match="mismatched prompt_sha256"):
        evaluate_plan(plan, altered)
    with pytest.raises(ValueError, match="duplicate outcome"):
        evaluate_plan(plan, rows + [rows[0]])


def test_training_holdout_and_unknown_runs_rejected():
    data = spec()
    data["training_task_ids"].append("holdout-0")
    with pytest.raises(ValueError, match="leakage"):
        make_plan(data)
    plan = make_plan(spec())
    with pytest.raises(ValueError, match="leakage"):
        evaluate_plan(plan, results(plan), additional_training_task_ids={"holdout-0"})
    rows = results(plan)
    rows[0]["run_id"] = "unknown-run"
    with pytest.raises(ValueError, match="unscheduled"):
        evaluate_plan(plan, rows)


def test_missing_metrics_are_not_imputed():
    plan = make_plan(spec())
    rows = results(plan)
    for row in rows:
        row.pop("cost_usd")
        row.pop("latency_seconds")
    report = evaluate_plan(plan, rows)
    assert report["overall"]["paired_cost_count"] == 0
    assert report["overall"]["candidate_B_minus_A_median_cost_usd"] is None


def test_cli_plan_and_evaluate(tmp_path):
    spec_file = tmp_path / "spec.json"
    plan_file = tmp_path / "plan.json"
    rows_file = tmp_path / "results.jsonl"
    report_file = tmp_path / "report.json"
    spec_file.write_text(json.dumps(spec()), encoding="utf-8")
    subprocess.run([
        sys.executable, "-m", "ai_model_advisor.experiment_protocol",
        "plan", "--spec", str(spec_file), "--output", str(plan_file),
    ], check=True)
    plan = json.loads(plan_file.read_text(encoding="utf-8"))
    rows_file.write_text(
        "\n".join(json.dumps(row) for row in results(plan)) + "\n", encoding="utf-8"
    )
    subprocess.run([
        sys.executable, "-m", "ai_model_advisor.experiment_protocol",
        "evaluate", "--plan", str(plan_file),
        "--observations", str(rows_file), "--output", str(report_file),
    ], check=True)
    assert json.loads(report_file.read_text(encoding="utf-8"))["status"] == "review_ready"
