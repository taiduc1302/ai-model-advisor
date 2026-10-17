"""Offline controlled A/B protocol with deterministic plans and fail-closed evidence.

The protocol never calls a provider or changes routing policy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

OUTCOME_SCORE = {"success": 1.0, "partial": 0.5, "failure": 0.0}
CONFIG_FIELDS = ("provider", "model_id", "effort", "execution_mode")
RUN_FIELDS = (
    "experiment_id", "plan_hash", "run_id", "task_id", "arm",
    "category", "prompt_sha256", "dataset_id", "environment_id",
    "evaluator_id", *CONFIG_FIELDS,
)
METRIC_FIELDS = ("cost_usd", "latency_seconds", "retries", "input_tokens", "output_tokens")
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
DIGEST = re.compile(r"^[a-f0-9]{64}$")


def _digest(payload: Any) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _keys(value: Any, *, required: set[str], optional: set[str] | None = None, label: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be an object")
    missing = required - value.keys()
    extra = value.keys() - required - (optional or set())
    if missing or extra:
        raise ValueError(f"{label}: missing={sorted(missing)}, unexpected={sorted(extra)}")


def _identifier(value: Any, label: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise ValueError(f"{label} must be a nonempty safe identifier")
    return value


def _positive_metric(value: Any, label: str, *, allow_zero: bool) -> None:
    if (not isinstance(value, (int, float)) or isinstance(value, bool)
        or not float("-inf") < float(value) < float("inf")
        or value < 0 or (not allow_zero and value == 0)):
        raise ValueError(f"invalid {label}")


def _validate_spec(spec: dict[str, Any]) -> dict[str, Any]:
    fields = {
        "schema_version", "experiment_id", "seed", "dataset_id", "environment_id",
        "evaluator_id", "training_task_ids", "arms", "tasks", "minimum_pairs",
    }
    _keys(spec, required=fields, label="experiment spec")
    if spec["schema_version"] != 1:
        raise ValueError("unsupported experiment schema")
    for name in ("experiment_id", "dataset_id", "environment_id", "evaluator_id"):
        _identifier(spec[name], name)
    if type(spec["seed"]) is not int or not 0 <= spec["seed"] < 2**32:
        raise ValueError("seed must be an unsigned 32-bit integer")
    if type(spec["minimum_pairs"]) is not int or spec["minimum_pairs"] < 3:
        raise ValueError("minimum_pairs must be >= 3")

    _keys(spec["arms"], required={"A", "B"}, label="arms")
    for arm in ("A", "B"):
        conf = spec["arms"][arm]
        _keys(conf, required=set(CONFIG_FIELDS), label=f"arm {arm}")
        for name in CONFIG_FIELDS:
            _identifier(conf[name], f"arm {arm} {name}")
    if spec["arms"]["A"] == spec["arms"]["B"]:
        raise ValueError("A and B configurations must differ")

    training = spec["training_task_ids"]
    if not isinstance(training, list):
        raise ValueError("training_task_ids must be an array")
    for task_id in training:
        _identifier(task_id, "training task ID")
    if len(set(training)) != len(training):
        raise ValueError("duplicate training task IDs")
    tasks = spec["tasks"]
    if not isinstance(tasks, list) or not tasks:
        raise ValueError("tasks must be a non-empty array")
    seen: set[str] = set()
    for task in tasks:
        _keys(task, required={"task_id", "category", "prompt_sha256"}, label="task")
        task_id = _identifier(task["task_id"], "task_id")
        _identifier(task["category"], "category")
        if not isinstance(task["prompt_sha256"], str) or not DIGEST.fullmatch(
            task["prompt_sha256"]
        ):
            raise ValueError("prompt_sha256 must be a lowercase SHA-256 hex digest")
        if task_id in seen:
            raise ValueError("duplicate holdout task IDs")
        seen.add(task_id)
    if seen.intersection(training):
        raise ValueError("training/holdout task ID leakage")
    # A JSON round-trip freezes caller-supplied mutable structures.
    return json.loads(json.dumps(spec, sort_keys=True))


def make_plan(spec: dict[str, Any]) -> dict[str, Any]:
    frozen = _validate_spec(spec)
    plan_hash = _digest(frozen)
    tasks = sorted(
        frozen["tasks"],
        key=lambda task: (_digest([frozen["seed"], task["task_id"]]), task["task_id"]),
    )
    runs: list[dict[str, Any]] = []
    for index, task in enumerate(tasks):
        for order, arm in enumerate(("A", "B") if index % 2 == 0 else ("B", "A"), 1):
            config = frozen["arms"][arm]
            run_id = _digest([plan_hash, task["task_id"], arm])[:24]
            runs.append({
                "experiment_id": frozen["experiment_id"],
                "plan_hash": plan_hash,
                "run_id": run_id,
                "task_id": task["task_id"],
                "arm": arm,
                "order": order,
                "category": task["category"],
                "prompt_sha256": task["prompt_sha256"],
                "dataset_id": frozen["dataset_id"],
                "environment_id": frozen["environment_id"],
                "evaluator_id": frozen["evaluator_id"],
                **config,
            })
    return {
        "schema_version": 1,
        "safe_to_apply": False,
        "plan_hash": plan_hash,
        "spec": frozen,
        "runs": runs,
        "order_balance": {
            "A_first": sum(run["arm"] == "A" and run["order"] == 1 for run in runs),
            "B_first": sum(run["arm"] == "B" and run["order"] == 1 for run in runs),
        },
    }


def _validate_plan(plan: dict[str, Any]) -> None:
    if not isinstance(plan, dict) or "spec" not in plan:
        raise ValueError("invalid experiment plan")
    expected = make_plan(plan["spec"])
    if plan != expected:
        raise ValueError("experiment plan has been modified or corrupted")


def _paired_metrics(pairs: list[tuple[dict[str, Any], dict[str, Any]]]) -> dict[str, Any]:
    quality = [
        OUTCOME_SCORE[b["outcome"]] - OUTCOME_SCORE[a["outcome"]]
        for a, b in pairs
    ]
    def deltas(field: str) -> list[float]:
        return [
            float(b[field]) - float(a[field])
            for a, b in pairs
            if a.get(field) is not None and b.get(field) is not None
        ]
    cost = deltas("cost_usd")
    latency = deltas("latency_seconds")
    retries = deltas("retries")
    return {
        "paired_tasks": len(pairs),
        "candidate_B_minus_A_mean_quality": round(sum(quality) / len(quality), 4)
        if quality else None,
        "candidate_B_minus_A_median_cost_usd": median(cost) if cost else None,
        "paired_cost_count": len(cost),
        "candidate_B_minus_A_median_latency_seconds": median(latency) if latency else None,
        "paired_latency_count": len(latency),
        "candidate_B_minus_A_median_retries": median(retries) if retries else None,
        "paired_retries_count": len(retries),
    }


def evaluate_plan(
    plan: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    additional_training_task_ids: set[str] | None = None,
) -> dict[str, Any]:
    _validate_plan(plan)
    training = set(plan["spec"]["training_task_ids"]) | (additional_training_task_ids or set())
    scheduled = {run["run_id"]: run for run in plan["runs"]}
    if not isinstance(observations, list):
        raise ValueError("observations must be an array")
    observed: dict[str, dict[str, Any]] = {}
    for row in observations:
        _keys(
            row,
            required=set(RUN_FIELDS) | {"outcome"},
            optional=set(METRIC_FIELDS) | {"note"},
            label="outcome record",
        )
        run_id = row["run_id"]
        if run_id not in scheduled:
            raise ValueError(f"unscheduled run: {run_id}")
        if run_id in observed:
            raise ValueError(f"duplicate outcome for run: {run_id}")
        expected = scheduled[run_id]
        for field in RUN_FIELDS:
            if row[field] != expected[field]:
                raise ValueError(f"mismatched {field} for run {run_id}")
        if row["task_id"] in training:
            raise ValueError("training/holdout task ID leakage")
        if row["outcome"] not in OUTCOME_SCORE:
            raise ValueError("invalid outcome")
        for field in METRIC_FIELDS:
            value = row.get(field)
            if value is not None:
                _positive_metric(value, field, allow_zero=field != "latency_seconds")
                if field in ("retries", "input_tokens", "output_tokens") and type(value) is not int:
                    raise ValueError(f"{field} must be an integer")
        if "note" in row and not isinstance(row["note"], str):
            raise ValueError("note must be a string")
        observed[run_id] = row

    # Reject leakage even if that holdout task has not yet been executed.
    if set(task["task_id"] for task in plan["spec"]["tasks"]) & training:
        raise ValueError("training/holdout task ID leakage")

    grouped: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for run in plan["runs"]:
        if run["run_id"] in observed:
            grouped[run["task_id"]][run["arm"]] = observed[run["run_id"]]
    category_by_task = {task["task_id"]: task["category"] for task in plan["spec"]["tasks"]}
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    categories: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    missing: list[str] = []
    for task_id in sorted(category_by_task):
        arms = grouped.get(task_id, {})
        if "A" not in arms or "B" not in arms:
            missing.append(task_id)
            continue
        pair = (arms["A"], arms["B"])
        pairs.append(pair)
        categories[category_by_task[task_id]].append(pair)

    threshold = plan["spec"]["minimum_pairs"]
    return {
        "schema_version": 1,
        "experiment_id": plan["spec"]["experiment_id"],
        "plan_hash": plan["plan_hash"],
        "status": "review_ready" if len(pairs) >= threshold else "insufficient_evidence",
        "safe_to_apply": False,
        "minimum_pairs": threshold,
        "scheduled_runs": len(scheduled),
        "received_runs": len(observed),
        "incomplete_task_ids": missing,
        "order_balance": plan["order_balance"],
        "overall": _paired_metrics(pairs),
        "categories": {
            category: _paired_metrics(items) for category, items in sorted(categories.items())
        },
        "limitations": [
            "Run metadata validates declared equivalence, not that real execution conditions were identical.",
            "A review_ready status is not statistical significance or permission to promote a model.",
            "Quality depends on an independently verified evaluator and truthful recorded outcomes.",
            "Missing pairs and missing cost/latency are not imputed.",
        ],
    }


def _read_json(path: str) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline, review-only controlled A/B protocol")
    sub = parser.add_subparsers(dest="command", required=True)
    planning = sub.add_parser("plan", help="Build an immutable counterbalanced execution schedule")
    planning.add_argument("--spec", required=True)
    planning.add_argument("--output", required=True)
    review = sub.add_parser("evaluate", help="Check observed outcomes against the frozen schedule")
    review.add_argument("--plan", required=True)
    review.add_argument("--observations", required=True)
    review.add_argument("--training-task-ids", help="Optional additional JSON array of fitted task IDs")
    review.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    if args.command == "plan":
        result = make_plan(_read_json(args.spec))
    else:
        rows = [
            json.loads(line)
            for line in Path(args.observations).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        extra = set(_read_json(args.training_task_ids)) if args.training_task_ids else None
        result = evaluate_plan(
            _read_json(args.plan), rows, additional_training_task_ids=extra
        )
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote {args.command} result to {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
