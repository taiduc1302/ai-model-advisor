"""Benchmark tests use fake transports; no paid provider calls."""
import hashlib
import json
import subprocess
import sys

import pytest

from ai_model_advisor.benchmark_runner import (
    BenchmarkRunnerError,
    fixtures,
    preview,
    run_one,
)
from ai_model_advisor.experiment_protocol import evaluate_plan, make_plan
from tools.ai_model_advisor.registry import ModelRegistry


def setup():
    prompts = {f"holdout-{i}": f"Answer exactly 42. Case {i}." for i in range(3)}
    spec = {
        "schema_version": 1, "experiment_id": "runner-fixture", "seed": 42,
        "dataset_id": "tiny-v1", "environment_id": "python311",
        "evaluator_id": "deterministic-v1", "training_task_ids": ["train-1"],
        "arms": {
            "A": {"provider": "openai", "model_id": "gpt-6-luna", "effort": "low", "execution_mode": "single"},
            "B": {"provider": "openai", "model_id": "gpt-6-luna", "effort": "medium", "execution_mode": "single"},
        },
        "tasks": [
            {"task_id": task, "category": "coding", "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest()}
            for task, prompt in prompts.items()
        ],
        "minimum_pairs": 3,
    }
    tasks = {"schema_version": 1, "tasks": [
        {"task_id": task, "prompt": prompt} for task, prompt in prompts.items()
    ]}
    oracle = {"schema_version": 1, "evaluator_id": "deterministic-v1", "checks": [
        {"task_id": task, "mode": "strip-exact", "expected": "42"}
        for task in prompts
    ]}
    return make_plan(spec), tasks, oracle


def fake_transport(calls):
    def transport(request, timeout):
        calls.append((request, timeout))
        return {
            "status": "completed", "model": request.configuration["model_id"],
            "reasoning": {"effort": request.configuration["effort"]},
            "output_text": "42", "usage": {"input_tokens": 17, "output_tokens": 3},
        }
    return transport


def test_preview_is_offline_without_api_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    plan, tasks, oracle = setup()
    report = preview(
        plan, tasks, oracle, ModelRegistry(),
        run_id=plan["runs"][0]["run_id"],
        max_cost_usd=1.0, max_output_tokens=48,
    )
    assert report["requires_explicit_apply"] is True
    assert report["budget_preflight_passed"] is True
    assert report["safe_to_apply"] is False
    assert "provider-enforced" in report["caveat"]


def test_single_run_records_judged_result_without_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "secret-test-token")
    plan, tasks, oracle = setup()
    first = plan["runs"][0]
    path = tmp_path / "runs.jsonl"
    calls = []
    result = run_one(
        plan, tasks, oracle, ModelRegistry(), run_id=first["run_id"],
        observations_path=path, max_cost_usd=1.0, max_output_tokens=48,
        transport=fake_transport(calls),
    )
    assert result["recorded"] is True
    assert result["outcome"] == "success"
    assert result["billed_cost_usd"] is None
    assert len(calls) == 1
    assert calls[0][0].body["max_output_tokens"] == 48
    assert calls[0][0].body["store"] is False
    stored = path.read_text(encoding="utf-8")
    assert "secret-test-token" not in stored
    assert "Answer exactly 42" not in stored
    row = json.loads(stored.strip())
    assert row["input_tokens"] == 17
    assert row["output_tokens"] == 3
    assert row["estimated_cost_usd"] >= 0
    assert "cost_usd" not in row
    assert evaluate_plan(plan, [row])["received_runs"] == 1
    assert path.with_name(path.name + ".attempts.jsonl").exists()


def test_ordered_runs_and_duplicates_are_blocked(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    plan, tasks, oracle = setup()
    first, second = plan["runs"][:2]
    path = tmp_path / "result.jsonl"
    calls = []
    with pytest.raises(BenchmarkRunnerError, match="first scheduled arm"):
        run_one(
            plan, tasks, oracle, ModelRegistry(), run_id=second["run_id"],
            observations_path=path, max_cost_usd=1, transport=fake_transport(calls),
        )
    assert calls == []
    run_one(
        plan, tasks, oracle, ModelRegistry(), run_id=first["run_id"],
        observations_path=path, max_cost_usd=1, transport=fake_transport(calls),
    )
    with pytest.raises(BenchmarkRunnerError, match="already recorded"):
        run_one(
            plan, tasks, oracle, ModelRegistry(), run_id=first["run_id"],
            observations_path=path, max_cost_usd=1, transport=fake_transport(calls),
        )
    assert len(calls) == 1


def test_budget_failure_calls_nobody(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    plan, tasks, oracle = setup()
    path = tmp_path / "result.jsonl"
    calls = []
    with pytest.raises(BenchmarkRunnerError, match="exceeds"):
        run_one(
            plan, tasks, oracle, ModelRegistry(), run_id=plan["runs"][0]["run_id"],
            observations_path=path, max_cost_usd=0.00000000001,
            transport=fake_transport(calls),
        )
    assert calls == []
    assert not path.exists()


def test_uncertain_provider_failure_blocks_retries(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake")
    plan, tasks, oracle = setup()
    path = tmp_path / "result.jsonl"
    calls = []

    def failed(request, timeout):
        calls.append("attempt")
        raise RuntimeError("secret-raw-error")

    with pytest.raises(BenchmarkRunnerError, match="manual reconciliation") as exc:
        run_one(
            plan, tasks, oracle, ModelRegistry(), run_id=plan["runs"][0]["run_id"],
            observations_path=path, max_cost_usd=1, transport=failed,
        )
    assert "secret-raw-error" not in str(exc.value)
    assert len(calls) == 1
    assert not path.exists()
    with pytest.raises(BenchmarkRunnerError, match="already attempted"):
        run_one(
            plan, tasks, oracle, ModelRegistry(), run_id=plan["runs"][0]["run_id"],
            observations_path=path, max_cost_usd=1, transport=failed,
        )
    assert len(calls) == 1


def test_fixture_tampering_and_oracle_coverage_rejected():
    plan, tasks, oracle = setup()
    tasks["tasks"][0]["prompt"] = "changed prompt"
    with pytest.raises(BenchmarkRunnerError, match="SHA-256 mismatch"):
        fixtures(plan, tasks, oracle)
    plan, tasks, oracle = setup()
    oracle["checks"].pop()
    with pytest.raises(BenchmarkRunnerError, match="exactly cover"):
        fixtures(plan, tasks, oracle)


def test_list_price_estimates_do_not_become_billed_costs():
    plan, _, _ = setup()
    rows = []
    for run in plan["runs"]:
        record = {k: v for k, v in run.items() if k != "order"}
        record.update({
            "outcome": "success",
            "estimated_cost_usd": 0.1 if run["arm"] == "A" else 0.08,
        })
        rows.append(record)
    stats = evaluate_plan(plan, rows)["overall"]
    assert stats["paired_cost_count"] == 0
    assert stats["paired_estimated_cost_count"] == 3
    assert stats["candidate_B_minus_A_median_estimated_cost_usd"] == pytest.approx(-0.02)


def test_cli_dry_run_requires_no_credentials(tmp_path, monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    plan, tasks, oracle = setup()
    paths = [tmp_path / filename for filename in ("plan.json", "tasks.json", "oracle.json")]
    for path, obj in zip(paths, (plan, tasks, oracle)):
        path.write_text(json.dumps(obj), encoding="utf-8")
    proc = subprocess.run([
        sys.executable, "-m", "ai_model_advisor.benchmark_runner",
        "--plan", str(paths[0]), "--tasks", str(paths[1]),
        "--oracle", str(paths[2]), "--run-id", plan["runs"][0]["run_id"],
        "--observations", str(tmp_path / "results.jsonl"), "--max-cost-usd", "1",
    ], capture_output=True, text=True, check=True)
    assert json.loads(proc.stdout)["requires_explicit_apply"] is True
    assert not (tmp_path / "results.jsonl").exists()
