import json

import pytest

from ai_model_advisor.evaluation import evaluate_cases


def test_curated_profile_expectations_pass():
    report = evaluate_cases()
    assert report["failed"] == 0, report["results"]
    assert report["passed"] == report["total"]
    assert report["kind"] == "curated_expectation_checks_not_empirical_benchmarks"


def test_evaluation_reports_failed_expectation(tmp_path):
    cases = {"schema_version": 1, "cases": [
        {"id": "strict", "task": "Fix a typo.", "expect": {"reasoning_min": 5}}
    ]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    report = evaluate_cases(path)
    assert report["failed"] == 1
    assert report["results"][0]["failures"]


def test_duplicate_case_ids_fail(tmp_path):
    cases = {"schema_version": 1, "cases": [
        {"id": "a", "task": "Fix typo", "expect": {}},
        {"id": "a", "task": "Audit repo", "expect": {}},
    ]}
    path = tmp_path / "cases.json"
    path.write_text(json.dumps(cases), encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate"):
        evaluate_cases(path)
