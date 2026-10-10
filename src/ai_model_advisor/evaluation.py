"""Offline deterministic evaluation of curated task-profile expectations.

This is not a measurement of provider success rates or real-world model quality.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tools.ai_model_advisor.activity import ActivityAnalyzer

DIMENSIONS = ("coding", "reasoning", "agentic", "ambiguity", "breadth", "parallelism")
DEFAULT_CASES = Path(__file__).resolve().parents[2] / "evaluations" / "task_cases.json"


def evaluate_cases(path: str | Path = DEFAULT_CASES) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported evaluation schema")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise ValueError("evaluation cases must be a non-empty list")
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    analyzer = ActivityAnalyzer()
    for case in cases:
        case_id = case["id"]
        if case_id in seen:
            raise ValueError(f"duplicate evaluation id: {case_id}")
        seen.add(case_id)
        profile = analyzer.from_texts([case["task"]])
        expectations = case["expect"]
        failures: list[str] = []
        for key, value in expectations.items():
            if key.endswith("_min") or key.endswith("_max"):
                dimension = key.rsplit("_", 1)[0]
                if dimension not in DIMENSIONS:
                    raise ValueError(f"unknown dimension expectation: {key}")
                actual = getattr(profile, dimension)
                if key.endswith("_min") and actual < value:
                    failures.append(f"{dimension}={actual:.2f} below {value}")
                if key.endswith("_max") and actual > value:
                    failures.append(f"{dimension}={actual:.2f} above {value}")
            elif key == "required_categories":
                failures.extend(
                    f"missing category: {category}"
                    for category in value
                    if category not in profile.categories
                )
            elif key == "forbidden_categories":
                failures.extend(
                    f"unexpected category: {category}"
                    for category in value
                    if category in profile.categories
                )
            else:
                raise ValueError(f"unknown expectation: {key}")
        results.append({
            "id": case_id, "passed": not failures, "failures": failures,
            "profile": profile.as_dict(),
        })
    passed = sum(item["passed"] for item in results)
    return {
        "schema_version": 1,
        "kind": "curated_expectation_checks_not_empirical_benchmarks",
        "total": len(results), "passed": passed, "failed": len(results) - passed,
        "pass_rate": round(passed / len(results), 4),
        "results": results,
    }


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate task profiling expectations")
    parser.add_argument("--cases", type=Path, default=DEFAULT_CASES)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args()
    report = evaluate_cases(args.cases)
    for item in report["results"]:
        status = "PASS" if item["passed"] else "FAIL"
        print(f"{status} {item['id']}" + (
            ": " + "; ".join(item["failures"]) if item["failures"] else ""
        ))
    print(f"Curated checks: {report['passed']}/{report['total']}")
    if args.json_output:
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        args.json_output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return 0 if report["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
