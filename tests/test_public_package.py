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
    assert payload["version"] == "0.2.0"
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
