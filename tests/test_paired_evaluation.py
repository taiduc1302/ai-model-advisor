import json
import subprocess
import sys

import pytest

from ai_model_advisor.paired_evaluation import evaluate_pair
from tools.ai_model_advisor.feedback import FeedbackStore, UsageRecord

LEFT = ("openai", "model-a", "high", "single")
RIGHT = ("anthropic", "model-b", "medium", "single")


def record(config, task, outcome="success", category="debugging", cost=1.0, latency=10):
    return UsageRecord(
        *config[:2], config[2], config[3], outcome,
        task_id=task, task_category=category,
        cost_usd=cost, latency_seconds=latency,
    )


def test_matched_report_with_real_pairs():
    records = []
    for task in ("one", "two", "three"):
        records.extend([record(LEFT, task, cost=1, latency=5), record(RIGHT, task, "partial", cost=2, latency=10)])
    report = evaluate_pair(FeedbackStore(records), left=LEFT, right=RIGHT, category="debugging")
    assert report["status"] == "review_ready"
    assert report["matched_task_count"] == 3
    assert report["quality_delta_left_minus_right"] == 0.5
    assert report["median_cost_delta_left_minus_right"] == -1
    assert report["median_latency_delta_left_minus_right"] == -5
    assert report["safe_to_apply"] is False


def test_unpaired_and_duplicate_runs_excluded():
    records = [
        record(LEFT, "one"), record(RIGHT, "one"),
        record(LEFT, "dup"), record(LEFT, "dup"), record(RIGHT, "dup"),
        record(LEFT, "lonely"),
        record(RIGHT, "one", category="research"),
    ]
    report = evaluate_pair(FeedbackStore(records), left=LEFT, right=RIGHT, category="debugging")
    assert report["matched_task_count"] == 1
    assert report["excluded_ambiguous_task_ids"] == 1
    assert report["excluded_unpaired_task_ids"] == 1
    assert report["status"] == "insufficient_evidence"


def test_missing_metrics_are_not_fabricated():
    records = [UsageRecord(*LEFT, "success", task_id="x", task_category="debugging"),
               UsageRecord(*RIGHT, "failure", task_id="x", task_category="debugging")]
    report = evaluate_pair(FeedbackStore(records), left=LEFT, right=RIGHT, category="debugging")
    assert report["paired_cost_count"] == 0
    assert report["median_cost_delta_left_minus_right"] is None


def test_invalid_parameters():
    with pytest.raises(ValueError, match="different"):
        evaluate_pair(FeedbackStore(), left=LEFT, right=LEFT, category="debugging")
    with pytest.raises(ValueError, match="minimum_tasks"):
        evaluate_pair(FeedbackStore(), left=LEFT, right=RIGHT, category="debugging", minimum_tasks=1)


def test_command_reads_jsonl(tmp_path):
    feedback = tmp_path / "runs.jsonl"
    lines = [record(LEFT, "x").as_dict(), record(RIGHT, "x").as_dict()]
    feedback.write_text("\n".join(json.dumps(item) for item in lines) + "\n", encoding="utf-8")
    run = subprocess.run([
        sys.executable, "-m", "ai_model_advisor.paired_evaluation",
        "--feedback", str(feedback), "--category", "debugging",
        "--left", *LEFT, "--right", *RIGHT
    ], capture_output=True, text=True, check=True)
    assert json.loads(run.stdout)["matched_task_count"] == 1
