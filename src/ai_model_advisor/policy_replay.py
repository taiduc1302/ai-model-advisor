"""Compare historical policy outcomes on the same held-out task IDs.

No inference of counterfactual outcomes; no automatic promotion.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from statistics import median
from typing import Any

OUTCOME = {"failure": 0.0, "partial": 0.5, "success": 1.0}


def evaluate_policies(
    observations: list[dict[str, Any]],
    *,
    baseline: str,
    candidate: str,
    training_task_ids: set[str] | None = None,
    minimum_pairs: int = 5,
) -> dict[str, Any]:
    if not baseline or not candidate or baseline == candidate:
        raise ValueError("different non-empty policy identifiers are required")
    if minimum_pairs < 3:
        raise ValueError("minimum_pairs must be >= 3")
    training = training_task_ids or set()
    by_task: dict[str, dict[str, list[dict[str, Any]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for row in observations:
        task_id = row.get("task_id")
        policy_id = row.get("policy_id")
        if not isinstance(task_id, str) or not task_id.strip():
            raise ValueError("every observation requires task_id")
        if not isinstance(policy_id, str) or not policy_id.strip():
            raise ValueError("every observation requires policy_id")
        if row.get("outcome") not in OUTCOME:
            raise ValueError("invalid observed outcome")
        for field in ("cost_usd", "latency_seconds"):
            value = row.get(field)
            if value is not None and (
                not isinstance(value, (float, int))
                or isinstance(value, bool)
                or value < 0
                or (field == "latency_seconds" and value == 0)
            ):
                raise ValueError(f"invalid {field}")
        if task_id in training and policy_id in (baseline, candidate):
            raise ValueError(f"training/holdout leakage for task_id: {task_id}")
        if policy_id in (baseline, candidate):
            by_task[task_id][policy_id].append(row)

    pairs = []
    ambiguous = 0
    unpaired = 0
    for task_id, arms in sorted(by_task.items()):
        a, b = arms.get(baseline, []), arms.get(candidate, [])
        if len(a) > 1 or len(b) > 1:
            ambiguous += 1
            continue
        if len(a) != 1 or len(b) != 1:
            unpaired += 1
            continue
        if a[0].get("category") != b[0].get("category"):
            ambiguous += 1
            continue
        pairs.append((task_id, a[0], b[0]))

    quality_deltas = [OUTCOME[b["outcome"]] - OUTCOME[a["outcome"]] for _, a, b in pairs]
    retry_deltas = [
        b["retries"] - a["retries"]
        for _, a, b in pairs
        if isinstance(a.get("retries"), int) and isinstance(b.get("retries"), int)
    ]
    def metric_deltas(field: str) -> list[float]:
        return [
            float(b[field]) - float(a[field])
            for _, a, b in pairs
            if a.get(field) is not None and b.get(field) is not None
        ]

    costs = metric_deltas("cost_usd")
    latencies = metric_deltas("latency_seconds")
    n = len(pairs)
    return {
        "schema_version": 1,
        "baseline_policy": baseline,
        "candidate_policy": candidate,
        "status": "review_ready" if n >= minimum_pairs else "insufficient_evidence",
        "safe_to_apply": False,
        "matched_task_count": n,
        "minimum_pairs": minimum_pairs,
        "excluded_duplicate_or_category_mismatch": ambiguous,
        "excluded_unpaired": unpaired,
        "candidate_minus_baseline_quality": round(sum(quality_deltas) / n, 4) if n else None,
        "candidate_minus_baseline_median_retries": median(retry_deltas) if retry_deltas else None,
        "candidate_minus_baseline_median_cost_usd": median(costs) if costs else None,
        "candidate_minus_baseline_median_latency_seconds": median(latencies) if latencies else None,
        "paired_cost_count": len(costs),
        "paired_latency_count": len(latencies),
        "task_ids": [task_id for task_id, _, _ in pairs],
        "limitations": [
            "Matched IDs alone do not prove identical task conditions or randomized assignment.",
            "A review_ready status is not statistical significance or a policy promotion.",
            "Counterfactual results are never imputed for tasks executed by only one policy.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review held-out paired policy outcomes")
    parser.add_argument("--observations", required=True)
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--train-task-ids", help="JSON array of task IDs used for fitting")
    parser.add_argument("--minimum-pairs", type=int, default=5)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    rows = [json.loads(line) for line in Path(args.observations).read_text(encoding="utf-8").splitlines() if line.strip()]
    train = set(json.loads(Path(args.train_task_ids).read_text(encoding="utf-8"))) if args.train_task_ids else set()
    report = evaluate_policies(rows, baseline=args.baseline, candidate=args.candidate, training_task_ids=train, minimum_pairs=args.minimum_pairs)
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
