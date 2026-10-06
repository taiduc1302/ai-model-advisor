from __future__ import annotations

import json
import subprocess
import sys

import pytest


def test_public_package_recommends_without_hive_imports() -> None:
    script = r"""
import json
import sys

import ai_model_advisor as ama

advisor = ama.Advisor()
recommendations = advisor.recommend(
    ama.WorkloadProfile(
        coding=4.0,
        reasoning=4.3,
        agentic=3.8,
        ambiguity=3.7,
        breadth=3.6,
        parallelism=2.5,
        activity_count=10,
        categories={"coding": 10},
    ),
    top_n=2,
)

print(json.dumps({
    "version": ama.__version__,
    "registry_as_of": advisor.registry_as_of,
    "count": len(recommendations),
    "hive_modules": sorted(
        name
        for name in sys.modules
        if name.startswith("tools.ai_model_advisor.hive_")
    ),
}))
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["version"] == "0.3.0"
    assert payload["registry_as_of"]
    assert payload["count"] == 2
    assert payload["hive_modules"] == []


def test_public_advisor_rejects_invalid_top_n() -> None:
    import ai_model_advisor as ama

    with pytest.raises(ValueError, match="top_n must be >= 1"):
        ama.Advisor().recommend(ama.WorkloadProfile(), top_n=0)


def test_hive_integration_is_explicit() -> None:
    import ai_model_advisor.integrations.hive as hive

    assert callable(hive.build_hive_config_preview)
    assert callable(hive.evaluate_hive_experiment_preflight)
    assert callable(hive.import_hive_trace)


def test_current_registry_defaults_to_latest_models() -> None:
    import ai_model_advisor as ama

    advisor = ama.Advisor()
    current_ids = {model.model_id for model in advisor.models()}
    assert advisor.registry_as_of == "2026-10-06"
    assert {"gpt-6-astra", "gpt-6.1-sol", "gpt-6-luna"} <= current_ids
    assert {"claude-fable-5-1", "claude-opus-5-5", "claude-sonnet-5-5"} <= current_ids
    assert "gpt-5.6-sol" not in current_ids
    assert "claude-opus-5" not in current_ids

    historical_ids = {model.model_id for model in advisor.models(include_previous=True)}
    assert "gpt-5.6-sol" in historical_ids
    assert "claude-opus-5" in historical_ids


def test_recommend_task_builds_profile_and_returns_current_candidate() -> None:
    import ai_model_advisor as ama

    advisor = ama.Advisor()
    task = "Audit this repository, find the root cause of failing tests, and implement the fix."
    profile = advisor.profile_task(task, latency_sensitivity=2, cost_sensitivity=4)
    assert profile.coding > 1
    assert profile.reasoning > 1
    assert profile.cost_sensitivity == 4

    recommendations = advisor.recommend_task(
        task,
        top_n=2,
        latency_sensitivity=2,
        cost_sensitivity=4,
    )
    assert len(recommendations) == 2
    current_ids = {model.model_id for model in advisor.models()}
    assert all(item.model_id in current_ids for item in recommendations)


def test_recommend_task_rejects_blank_text() -> None:
    import ai_model_advisor as ama

    with pytest.raises(ValueError, match="task must not be blank"):
        ama.Advisor().recommend_task("   ")
