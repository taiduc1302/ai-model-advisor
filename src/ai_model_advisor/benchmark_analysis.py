"""Review-only analysis of matched A/B benchmark outcomes.

This module does not call providers, fill missing counterfactuals, or recommend
automatic routing changes. It uses frozen v0.13 plans and observed v0.14 data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median
from typing import Any

from .experiment_protocol import OUTCOME_SCORE, evaluate_plan

Z_95 = 1.959963984540054
MIN_DIRECTIONAL_PAIRS = 20


def _wilson(successes: int, total: int) -> list[float] | None:
    if total == 0:
        return None
    p = successes / total
    z2 = Z_95**2
    d = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / d
    radius = Z_95 * math.sqrt(p * (1 - p) / total + z2 / (4 * total**2)) / d
    return [round(max(0.0, centre - radius), 4), round(min(1.0, centre + radius), 4)]


def _quantile(sorted_values: list[float], fraction: float) -> float:
    point = (len(sorted_values) - 1) * fraction
    lower = math.floor(point)
    upper = math.ceil(point)
    return sorted_values[lower] * (upper - point) + sorted_values[upper] * (point - lower)


def _paired_bootstrap(
    deltas: list[float],
    *,
    seed: str,
    samples: int,
) -> list[float] | None:
    """A descriptive paired bootstrap interval, NOT a calibrated causal CI."""
    if len(deltas) < 2:
        return None
    digest = hashlib.sha256(seed.encode("utf-8")).digest()
    rng = random.Random(int.from_bytes(digest[:8], "big"))
    n = len(deltas)
    means = sorted(
        sum(deltas[rng.randrange(n)] for _ in range(n)) / n
        for _ in range(samples)
    )
    return [round(_quantile(means, 0.025), 4), round(_quantile(means, 0.975), 4)]


def _arm_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    outcomes = Counter(row["outcome"] for row in rows)
    successes = outcomes["success"]
    return {
        "count": total,
        "success_count": successes,
        "partial_count": outcomes["partial"],
        "failure_count": outcomes["failure"],
        "pass_rate": round(successes / total, 4) if total else None,
        "pass_rate_wilson_95": _wilson(successes, total),
        "mean_quality": round(mean(OUTCOME_SCORE[row["outcome"]] for row in rows), 4)
        if total else None,
    }


def _paired_values(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    field: str,
) -> dict[str, Any]:
    """Pairwise complete observations only, with B minus A orientation."""
    complete = [
        (float(a[field]), float(b[field]))
        for a, b in pairs
        if a.get(field) is not None and b.get(field) is not None
    ]
    deltas = [b - a for a, b in complete]
    return {
        "paired_count": len(deltas),
        "missing_pairs": len(pairs) - len(deltas),
        "median_A": round(median(a for a, _ in complete), 6) if complete else None,
        "median_B": round(median(b for _, b in complete), 6) if complete else None,
        "median_paired_delta_B_minus_A": round(median(deltas), 6) if complete else None,
        "mean_paired_delta_B_minus_A": round(mean(deltas), 6) if complete else None,
    }


def _category_report(
    pairs: list[tuple[dict[str, Any], dict[str, Any]]],
    *,
    scheduled_count: int,
    plan_hash: str,
    label: str,
    bootstrap_samples: int,
) -> dict[str, Any]:
    arms_a = [a for a, _ in pairs]
    arms_b = [b for _, b in pairs]
    quality_deltas = [
        OUTCOME_SCORE[b["outcome"]] - OUTCOME_SCORE[a["outcome"]]
        for a, b in pairs
    ]
    n = len(pairs)
    quality = {
        "paired_count": n,
        "mean_delta_B_minus_A": round(mean(quality_deltas), 4) if n else None,
        "bootstrap_95_descriptive": _paired_bootstrap(
            quality_deltas, seed=f"{plan_hash}:{label}", samples=bootstrap_samples
        ),
        "B_better_task_count": sum(delta > 0 for delta in quality_deltas),
        "A_better_task_count": sum(delta < 0 for delta in quality_deltas),
        "tied_task_count": sum(delta == 0 for delta in quality_deltas),
    }
    return {
        "scheduled_tasks": scheduled_count,
        "completed_pairs": n,
        "pair_coverage": round(n / scheduled_count, 4) if scheduled_count else None,
        "arm_A": _arm_summary(arms_a),
        "arm_B": _arm_summary(arms_b),
        "paired_quality": quality,
        "verified_billed_cost_usd": _paired_values(pairs, "cost_usd"),
        "registry_estimated_cost_usd": _paired_values(pairs, "estimated_cost_usd"),
        "latency_seconds": _paired_values(pairs, "latency_seconds"),
        "retries": _paired_values(pairs, "retries"),
    }


def _experiment_scope(arm_a: dict[str, str], arm_b: dict[str, str]) -> dict[str, Any]:
    dimensions = [
        key for key in ("provider", "model_id", "effort", "execution_mode")
        if arm_a[key] != arm_b[key]
    ]
    if dimensions == ["effort"]:
        label = "isolated_reasoning_effort"
    elif dimensions == ["model_id"]:
        label = "isolated_model_id"
    elif dimensions == ["execution_mode"]:
        label = "isolated_execution_mode"
    else:
        label = "multiple_configuration_factors"
    return {"type": label, "changed_fields": dimensions}


def _review_state(
    report: dict[str, Any],
    *,
    minimum_pairs: int,
    directional_pairs: int,
) -> tuple[str, list[str]]:
    n = report["completed_pairs"]
    flags: list[str] = []
    if n < minimum_pairs:
        return "insufficient_pairs", [f"Need at least {minimum_pairs} matched tasks."]
    if n < directional_pairs:
        flags.append(
            f"Only {n} matched tasks; directional interpretation requires at least "
            f"{directional_pairs} and still needs human review."
        )
    if report["pair_coverage"] < 1:
        flags.append("Incomplete task-pair coverage; missing outcomes may be non-random.")
    interval = report["paired_quality"]["bootstrap_95_descriptive"]
    if interval is None:
        flags.append("No descriptive paired uncertainty interval available.")
    elif interval[0] <= 0 <= interval[1]:
        flags.append("Paired quality uncertainty interval crosses zero.")
    else:
        flags.append(
            "Paired quality interval does not cross zero; this is exploratory "
            "and not proof of causality or a model winner."
        )
    if report["verified_billed_cost_usd"]["paired_count"] < n:
        flags.append("Verified billed cost unavailable for one or more matched pairs.")
    if report["latency_seconds"]["paired_count"] < n:
        flags.append("Latency unavailable for one or more matched pairs.")
    if n < directional_pairs:
        return "exploratory_small_sample", flags
    if interval is None or interval[0] <= 0 <= interval[1]:
        return "review_inconclusive", flags
    return "directional_signal_manual_review", flags


def analyze_results(
    plan: dict[str, Any],
    observations: list[dict[str, Any]],
    *,
    directional_pairs: int = MIN_DIRECTIONAL_PAIRS,
    bootstrap_samples: int = 2000,
    additional_training_task_ids: set[str] | None = None,
) -> dict[str, Any]:
    """Summarize actual matching results with conservative uncertainty language."""
    if type(directional_pairs) is not int or directional_pairs < MIN_DIRECTIONAL_PAIRS:
        raise ValueError(f"directional_pairs must be >= {MIN_DIRECTIONAL_PAIRS}")
    if type(bootstrap_samples) is not int or not 200 <= bootstrap_samples <= 20000:
        raise ValueError("bootstrap_samples must be 200..20000")
    base = evaluate_plan(
        plan, observations, additional_training_task_ids=additional_training_task_ids
    )
    recorded = {record["run_id"]: record for record in observations}
    paired: list[tuple[dict[str, Any], dict[str, Any]]] = []
    by_category: dict[str, list[tuple[dict[str, Any], dict[str, Any]]]] = defaultdict(list)
    counts: Counter[str] = Counter()
    incomplete_count = 0
    for task in plan["spec"]["tasks"]:
        counts[task["category"]] += 1
    schedule: dict[str, dict[str, dict[str, Any]]] = defaultdict(dict)
    for item in plan["runs"]:
        if item["run_id"] in recorded:
            schedule[item["task_id"]][item["arm"]] = recorded[item["run_id"]]
    for task in plan["spec"]["tasks"]:
        pair = schedule[task["task_id"]]
        if "A" not in pair or "B" not in pair:
            incomplete_count += 1
            continue
        a, b = pair["A"], pair["B"]
        paired.append((a, b))
        by_category[task["category"]].append((a, b))
    overall = _category_report(
        paired,
        scheduled_count=len(plan["spec"]["tasks"]),
        plan_hash=plan["plan_hash"],
        label="overall",
        bootstrap_samples=bootstrap_samples,
    )
    state, cautions = _review_state(
        overall, minimum_pairs=plan["spec"]["minimum_pairs"],
        directional_pairs=directional_pairs,
    )
    scope = _experiment_scope(plan["spec"]["arms"]["A"], plan["spec"]["arms"]["B"])
    if scope["type"] != "isolated_reasoning_effort":
        cautions.append(
            "This experiment changes " + ", ".join(scope["changed_fields"])
            + "; differences cannot be attributed solely to reasoning effort."
        )
    return {
        "schema_version": 1,
        "report_type": "observed_matched_benchmark_review",
        "plan_hash": base["plan_hash"],
        "experiment_id": base["experiment_id"],
        "dataset_id": plan["spec"]["dataset_id"],
        "environment_id": plan["spec"]["environment_id"],
        "evaluator_id": plan["spec"]["evaluator_id"],
        "configurations": plan["spec"]["arms"],
        "comparison_scope": scope,
        "evidence_status": state,
        "safe_to_apply": False,
        "automatic_winner": None,
        "minimum_pairs": plan["spec"]["minimum_pairs"],
        "directional_pairs": directional_pairs,
        "recorded_runs": base["received_runs"],
        "scheduled_runs": base["scheduled_runs"],
        "incomplete_tasks": incomplete_count,
        "overall": overall,
        "categories": {
            category: _category_report(
                by_category.get(category, []),
                scheduled_count=count,
                plan_hash=plan["plan_hash"],
                label=category,
                bootstrap_samples=bootstrap_samples,
            )
            for category, count in sorted(counts.items())
        },
        "cautions": cautions,
        "methodology": [
            "All outcomes come from declared ledger records; no provider calls or imputation.",
            "Pass rate counts success only; partial counts as 0.5 in quality score.",
            "Wilson intervals describe observed success rates, not causal effects.",
            "Seeded paired bootstrap intervals are descriptive, not calibrated proof.",
            "Cost comparisons use pairwise verified billing or, separately, registry estimates.",
            "Category slices are exploratory; repeated comparisons amplify selection risk.",
            "Human review is required even if directional intervals exclude zero.",
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Review matched A/B benchmark results offline")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--training-task-ids", help="JSON list of extra fitted task IDs")
    parser.add_argument("--directional-pairs", type=int, default=MIN_DIRECTIONAL_PAIRS)
    parser.add_argument("--bootstrap-samples", type=int, default=2000)
    parser.add_argument("--output")
    args = parser.parse_args(argv)
    plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
    rows = [
        json.loads(line)
        for line in Path(args.observations).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    extra = (
        set(json.loads(Path(args.training_task_ids).read_text(encoding="utf-8")))
        if args.training_task_ids else None
    )
    report = analyze_results(
        plan,
        rows,
        directional_pairs=args.directional_pairs,
        bootstrap_samples=args.bootstrap_samples,
        additional_training_task_ids=extra,
    )
    result = json.dumps(report, indent=2, ensure_ascii=False) + "\n"
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(result, encoding="utf-8")
    else:
        print(result, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
