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
    assert payload["version"] == "0.10.0"
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


def test_record_outcome_persists_and_refreshes_feedback(tmp_path) -> None:
    import ai_model_advisor as ama

    feedback_path = tmp_path / "feedback.jsonl"
    advisor = ama.Advisor(feedback=feedback_path)
    record = advisor.record_outcome(
        model_id="gpt-6.1-sol",
        effort="high",
        execution_mode="single",
        outcome="success",
        task="Audit the repository and find the root cause of the failing test.",
        task_id="repo-audit-001",
        latency_seconds=12.5,
        cost_usd=0.08,
    )

    assert record.provider == "openai"
    assert record.task_category in {"debugging", "repo_review"}
    assert feedback_path.exists()
    assert len(advisor.feedback.records) == 1

    reloaded = ama.Advisor(feedback=feedback_path)
    assert len(reloaded.feedback.records) == 1
    assert reloaded.feedback.records[0].task_id == "repo-audit-001"


def test_record_outcome_can_be_in_memory_only() -> None:
    import ai_model_advisor as ama

    advisor = ama.Advisor(feedback=ama.FeedbackStore())
    advisor.record_outcome(
        provider="anthropic",
        model_id="custom-model-not-in-registry",
        effort="default",
        execution_mode="single",
        outcome="partial",
        task_category="research",
    )
    assert len(advisor.feedback.records) == 1
    assert advisor.feedback.records[0].provider == "anthropic"


def test_record_outcome_requires_provider_for_unknown_model() -> None:
    import ai_model_advisor as ama

    with pytest.raises(ValueError, match="provider is required"):
        ama.Advisor().record_outcome(
            model_id="unknown-model",
            effort="default",
            execution_mode="single",
            outcome="success",
        )


def test_decide_task_returns_structured_routing_decision() -> None:
    import ai_model_advisor as ama

    advisor = ama.Advisor()
    decision = advisor.decide_task(
        "Audit the entire repository architecture, investigate unclear failures, and implement the fix.",
        cost_sensitivity=1,
        latency_sensitivity=1,
        fallback_score_gap=100,
    )

    assert isinstance(decision, ama.RoutingDecision)
    assert decision.primary.model_id
    assert decision.registry_as_of == advisor.registry_as_of
    assert decision.personal_evidence
    assert decision.escalation_triggers
    assert decision.decision_notes
    assert decision.as_dict()["primary"]["model_id"] == decision.primary.model_id

    if decision.cheaper_fallback is not None:
        assert decision.cheaper_fallback.model_id != decision.primary.model_id


def test_decision_surfaces_below_threshold_personal_evidence() -> None:
    import ai_model_advisor as ama

    task = "Audit the repository and find the root cause of the failing tests."
    baseline = ama.Advisor()
    initial = baseline.decide_task(task)
    category = max(
        initial.profile.categories.items(),
        key=lambda item: (item[1], item[0]),
    )[0]

    feedback = ama.FeedbackStore(
        [
            ama.UsageRecord(
                provider=initial.primary.provider,
                model_id=initial.primary.model_id,
                effort=initial.primary.effort,
                execution_mode=initial.primary.execution_mode,
                outcome="success",
                task_category=category,
            )
        ]
    )
    decision = ama.Advisor(feedback=feedback).decide_task(task)

    assert any("below the routing threshold" in item for item in decision.personal_evidence)


def test_decision_surfaces_personal_evidence_that_changed_score() -> None:
    import ai_model_advisor as ama

    task = "Audit the repository and find the root cause of the failing tests."
    baseline = ama.Advisor()
    initial = baseline.decide_task(task)
    category = max(
        initial.profile.categories.items(),
        key=lambda item: (item[1], item[0]),
    )[0]

    feedback = ama.FeedbackStore(
        [
            ama.UsageRecord(
                provider=initial.primary.provider,
                model_id=initial.primary.model_id,
                effort=initial.primary.effort,
                execution_mode=initial.primary.execution_mode,
                outcome="success",
                task_category=category,
            )
            for _ in range(4)
        ]
    )
    decision = ama.Advisor(feedback=feedback).decide_task(task)

    assert any("Outcome evidence affected" in item for item in decision.personal_evidence)


def test_decide_task_rejects_negative_fallback_gap() -> None:
    import ai_model_advisor as ama

    with pytest.raises(ValueError, match="fallback_score_gap must be >= 0"):
        ama.Advisor().decide_task(
            "Research the latest model options.",
            fallback_score_gap=-1,
        )


def test_decide_cli_emits_json() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_model_advisor.cli",
            "decide",
            "--task",
            "Audit this repository, investigate the failing tests, and implement the fix.",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["primary"]["model_id"]
    assert "cheaper_fallback" in payload
    assert "escalation" in payload
    assert payload["escalation_triggers"]
    assert payload["personal_evidence"]


def test_decide_cli_emits_human_report() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_model_advisor.cli",
            "decide",
            "--task",
            "Research and compare current AI models for a complex coding workflow.",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert "# AI Model Routing Decision" in completed.stdout
    assert "## Primary" in completed.stdout
    assert "## Cheaper fallback" in completed.stdout
    assert "## Escalation" in completed.stdout
    assert "## Personal evidence" in completed.stdout


def test_record_decision_cli_closes_feedback_loop(tmp_path) -> None:
    decision_path = tmp_path / "decision.json"
    feedback_path = tmp_path / "feedback.jsonl"

    subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_model_advisor.cli",
            "decide",
            "--task",
            "Audit this repository, investigate failing tests, and implement the fix.",
            "--json",
            "--output",
            str(decision_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_model_advisor.cli",
            "record-decision",
            "--decision",
            str(decision_path),
            "--feedback",
            str(feedback_path),
            "--outcome",
            "success",
            "--task-id",
            "repo-fix-001",
            "--latency-seconds",
            "31.5",
            "--cost-usd",
            "0.12",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = json.loads(completed.stdout)
    decision = json.loads(decision_path.read_text(encoding="utf-8"))
    records = [
        json.loads(line)
        for line in feedback_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert result["recorded"] is True
    assert len(records) == 1
    assert records[0]["model_id"] == decision["primary"]["model_id"]
    assert records[0]["effort"] == decision["primary"]["effort"]
    assert records[0]["execution_mode"] == decision["primary"]["execution_mode"]
    assert records[0]["outcome"] == "success"
    assert records[0]["task_id"] == "repo-fix-001"
    assert records[0]["task_category"]


def test_record_decision_cli_rejects_malformed_decision(tmp_path) -> None:
    decision_path = tmp_path / "decision.json"
    feedback_path = tmp_path / "feedback.jsonl"
    decision_path.write_text('{"primary": {"model_id": "missing-fields"}}', encoding="utf-8")

    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "ai_model_advisor.cli",
            "record-decision",
            "--decision",
            str(decision_path),
            "--feedback",
            str(feedback_path),
            "--outcome",
            "success",
        ],
        capture_output=True,
        text=True,
    )

    assert completed.returncode != 0
    assert "missing required fields" in completed.stderr
    assert not feedback_path.exists()

def test_simple_and_complex_tasks_are_distinct() -> None:
    import ai_model_advisor as ama

    advisor = ama.Advisor()
    tiny = advisor.profile_task("Fix a typo in one file.")
    complex_task = advisor.profile_task(
        "Audit the entire repository architecture, investigate an unknown root cause "
        "across many modules, implement the fix, run the tests, and verify every result."
    )
    assert tiny.reasoning < 2
    assert tiny.agentic < 2
    assert tiny.breadth < 2
    assert tiny.parallelism < 2
    assert complex_task.coding >= 4
    assert complex_task.reasoning >= 4
    assert complex_task.breadth >= 4
    assert complex_task.agentic >= 3
    assert complex_task.parallelism >= 2.5


def test_profiler_ignores_negated_research() -> None:
    import ai_model_advisor as ama

    profile = ama.Advisor().profile_task(
        "Fix a typo in one file. Do not research or compare anything."
    )
    assert "research" not in profile.categories
    assert profile.breadth < 2


def test_profiler_reports_weighted_signals() -> None:
    import ai_model_advisor as ama

    profile = ama.Advisor().profile_task(
        "Compare multiple official sources, investigate the trade-offs, and verify results."
    )
    assert profile.reasoning > profile.coding
    assert "research" in profile.categories
    assert profile.category_signals["research"]
    assert profile.dimension_signals["reasoning"]


def test_profiler_detects_multi_step_agentic_execution() -> None:
    import ai_model_advisor as ama

    profile = ama.Advisor().profile_task(
        "Build the feature, run the tests, fix failures, verify the output, "
        "and create a pull request."
    )
    assert profile.agentic >= 3
    assert "three-or-more requested actions" in profile.dimension_signals["agentic"]
