"""Matched-task outcome comparison. Review-only; no provider execution."""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from statistics import median

from tools.ai_model_advisor.feedback import FeedbackStore, UsageRecord

OUTCOMES = {"success": 1.0, "partial": 0.5, "failure": 0.0}
MIN_MATCHED_TASKS = 3


def _key(record: UsageRecord) -> tuple[str, str, str, str]:
    return record.provider, record.model_id, record.effort, record.execution_mode


@dataclass(frozen=True)
class MatchedTask:
    task_id: str
    category: str
    left: UsageRecord
    right: UsageRecord


def evaluate_pair(
    feedback: FeedbackStore,
    *,
    left: tuple[str, str, str, str],
    right: tuple[str, str, str, str],
    category: str,
    minimum_tasks: int = MIN_MATCHED_TASKS,
) -> dict[str, object]:
    if left == right:
        raise ValueError("comparison configurations must be different")
    if not category:
        raise ValueError("task category is required")
    if minimum_tasks < MIN_MATCHED_TASKS:
        raise ValueError(f"minimum_tasks must be >= {MIN_MATCHED_TASKS}")

    grouped: dict[str, dict[tuple[str, str, str, str], list[UsageRecord]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for record in feedback.records:
        if (
            not record.task_id
            or record.task_category != category
            or record.effort == "observed"
            or record.execution_mode == "hive_agent_loop"
        ):
            continue
        configuration = _key(record)
        if configuration in (left, right):
            grouped[record.task_id][configuration].append(record)

    matched: list[MatchedTask] = []
    excluded_ambiguous = 0
    excluded_unpaired = 0
    for task_id, configurations in sorted(grouped.items()):
        left_records = configurations.get(left, [])
        right_records = configurations.get(right, [])
        if len(left_records) != 1 or len(right_records) != 1:
            if len(left_records) > 1 or len(right_records) > 1:
                excluded_ambiguous += 1
            else:
                excluded_unpaired += 1
            continue
        matched.append(MatchedTask(task_id, category, left_records[0], right_records[0]))

    def side(records: list[UsageRecord]) -> dict[str, object]:
        costs = [record.cost_usd for record in records if record.cost_usd is not None]
        latencies = [
            record.latency_seconds
            for record in records
            if record.latency_seconds is not None
        ]
        return {
            "outcome_score": round(
                sum(OUTCOMES[record.outcome] for record in records) / len(records), 4
            ) if records else None,
            "mean_retries": round(
                sum(record.retries for record in records) / len(records), 3
            ) if records else None,
            "median_cost_usd": median(costs) if costs else None,
            "median_latency_seconds": median(latencies) if latencies else None,
        }

    pair_costs = [
        (pair.left.cost_usd, pair.right.cost_usd)
        for pair in matched
        if pair.left.cost_usd is not None and pair.right.cost_usd is not None
    ]
    pair_latencies = [
        (pair.left.latency_seconds, pair.right.latency_seconds)
        for pair in matched
        if pair.left.latency_seconds is not None and pair.right.latency_seconds is not None
    ]
    left_stats = side([pair.left for pair in matched])
    right_stats = side([pair.right for pair in matched])
    quality_delta = (
        round(left_stats["outcome_score"] - right_stats["outcome_score"], 4)
        if matched else None
    )
    return {
        "schema_version": 1,
        "status": "review_ready" if len(matched) >= minimum_tasks else "insufficient_evidence",
        "safe_to_apply": False,
        "category": category,
        "left": dict(zip(("provider", "model_id", "effort", "execution_mode"), left)),
        "right": dict(zip(("provider", "model_id", "effort", "execution_mode"), right)),
        "matched_task_count": len(matched),
        "minimum_tasks": minimum_tasks,
        "excluded_ambiguous_task_ids": excluded_ambiguous,
        "excluded_unpaired_task_ids": excluded_unpaired,
        "quality_delta_left_minus_right": quality_delta,
        "paired_cost_count": len(pair_costs),
        "paired_latency_count": len(pair_latencies),
        "median_cost_delta_left_minus_right": (
            median(a - b for a, b in pair_costs) if pair_costs else None
        ),
        "median_latency_delta_left_minus_right": (
            median(a - b for a, b in pair_latencies) if pair_latencies else None
        ),
        "left_metrics": left_stats,
        "right_metrics": right_stats,
        "matched_task_ids": [pair.task_id for pair in matched],
        "limitations": [
            "Matching by task ID and category does not prove identical prompts, tools or environments.",
            "Review-ready means sufficient matched coverage for inspection, not statistical significance.",
            "No model winner or routing promotion is inferred automatically.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review matched task outcomes")
    parser.add_argument("--feedback", required=True)
    parser.add_argument("--category", required=True)
    parser.add_argument("--left", nargs=4, required=True, metavar=("PROVIDER", "MODEL", "EFFORT", "MODE"))
    parser.add_argument("--right", nargs=4, required=True, metavar=("PROVIDER", "MODEL", "EFFORT", "MODE"))
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    report = evaluate_pair(
        FeedbackStore.load(args.feedback),
        left=tuple(args.left),
        right=tuple(args.right),
        category=args.category,
    )
    output = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(output, encoding="utf-8")
    else:
        print(output, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
