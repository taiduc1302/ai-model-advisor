import copy
import json
import subprocess
import sys

import pytest

from ai_model_advisor.benchmark_runner import fixtures, preview
from ai_model_advisor.benchmark_suite import (
    BenchmarkSuiteError,
    build_bundle,
    load_catalog,
    validate_catalog,
    write_bundle,
)
from ai_model_advisor.experiment_protocol import evaluate_plan
from tools.ai_model_advisor.registry import ModelRegistry

A = ("openai", "gpt-6-luna", "low", "single")
B = ("openai", "gpt-6-luna", "medium", "single")


def bundle():
    return build_bundle(
        load_catalog(), experiment_id="synthetic-001", arm_a=A, arm_b=B,
        environment_id="direct-single-v1",
    )


def test_public_suite_is_balanced_and_explicitly_synthetic():
    info = validate_catalog(load_catalog())
    assert info["train_count"] == 4
    assert info["holdout_count"] == 16
    assert len(info["category_counts"]) == 4
    assert all(c == {"holdout": 4, "train": 1} for c in info["category_counts"].values())
    assert "Published" in info["limitations"][0]


def test_bundle_is_reproducible_and_usable_by_existing_runner():
    first = bundle()
    assert first == bundle()
    assert first["manifest"]["evaluation_kind"] == "public_synthetic_objective_tasks"
    assert first["manifest"]["safe_to_apply"] is False
    assert len(first["plan"]["runs"]) == 32
    assert set(first["spec"]["training_task_ids"]).isdisjoint(
        {t["task_id"] for t in first["spec"]["tasks"]}
    )
    assert len(fixtures(first["plan"], first["tasks"], first["oracle"])[0]) == 16
    planned = first["plan"]["runs"][0]
    report = preview(
        first["plan"], first["tasks"], first["oracle"], ModelRegistry(),
        run_id=planned["run_id"], max_cost_usd=1,
    )
    assert report["requires_explicit_apply"]
    assert evaluate_plan(first["plan"], [])["status"] == "insufficient_evidence"


def test_duplicate_prompt_across_splits_is_rejected():
    dataset = load_catalog()
    dataset["tasks"][1]["prompt"] = dataset["tasks"][0]["prompt"]
    with pytest.raises(BenchmarkSuiteError, match="duplicate prompt"):
        validate_catalog(dataset)


def test_missing_category_train_coverage_is_rejected():
    dataset = load_catalog()
    dataset["tasks"] = [
        task for task in dataset["tasks"]
        if task["id"] != "data-001"
    ]
    with pytest.raises(BenchmarkSuiteError, match="train and holdout"):
        validate_catalog(dataset)


def test_tampered_prompt_and_oracle_are_detected():
    first = bundle()
    wrong = copy.deepcopy(first["tasks"])
    wrong["tasks"][0]["prompt"] += " changed"
    with pytest.raises(ValueError, match="SHA-256 mismatch"):
        fixtures(first["plan"], wrong, first["oracle"])
    wrong_oracle = copy.deepcopy(first["oracle"])
    wrong_oracle["evaluator_id"] = "wrong"
    with pytest.raises(ValueError, match="evaluator"):
        fixtures(first["plan"], first["tasks"], wrong_oracle)


def test_invalid_arms_fail_closed():
    catalog = load_catalog()
    with pytest.raises(BenchmarkSuiteError, match="unsupported"):
        build_bundle(catalog, experiment_id="test-001",
                     arm_a=("openai", "gpt-6-luna", "invalid", "single"),
                     arm_b=B, environment_id="direct-single-v1")
    with pytest.raises(ValueError, match="differ"):
        build_bundle(catalog, experiment_id="test-001", arm_a=A,
                     arm_b=A, environment_id="direct-single-v1")


def test_write_bundle_does_not_overwrite(tmp_path):
    report = bundle()
    paths = write_bundle(report, tmp_path)
    assert len(paths) == 5
    assert json.loads((tmp_path / "manifest.json").read_text())["plan_hash"] == report["plan"]["plan_hash"]
    with pytest.raises(BenchmarkSuiteError, match="refusing"):
        write_bundle(report, tmp_path)


def test_cli_validation_and_build(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "ai_model_advisor.benchmark_suite", "validate"],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(proc.stdout)["holdout_count"] == 16
    proc = subprocess.run(
        [sys.executable, "-m", "ai_model_advisor.benchmark_suite", "build",
         "--experiment-id", "example-001", "--arm-a", *A, "--arm-b", *B,
         "--output-dir", str(tmp_path)],
        capture_output=True, text=True, check=True,
    )
    assert json.loads(proc.stdout)["manifest"]["safe_to_apply"] is False
    assert (tmp_path / "plan.json").exists()
