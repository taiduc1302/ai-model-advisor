"""Build a reproducible offline benchmark bundle for controlled A/B execution.

The bundled dataset is public, synthetic, and NOT a blind/independent
benchmark. Operators may provide a separate private JSON catalog.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from importlib.resources import files
from pathlib import Path
from typing import Any

from tools.ai_model_advisor.registry import ModelRegistry

from .benchmark_runner import fixtures
from .experiment_protocol import make_plan

_FIELDS = ("provider", "model_id", "effort", "execution_mode")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


class BenchmarkSuiteError(ValueError):
    """A suite, configuration, or output bundle is not safe to use."""


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_catalog(path: str | Path | None = None) -> dict[str, Any]:
    if path is None:
        content = files("ai_model_advisor").joinpath(
            "data/synthetic_suite_v1.json"
        ).read_text(encoding="utf-8")
    else:
        content = Path(path).read_text(encoding="utf-8")
    catalog = json.loads(content)
    validate_catalog(catalog)
    return catalog


def validate_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(catalog, dict) or set(catalog) != {
        "schema_version", "dataset_name", "description", "tasks"
    }:
        raise BenchmarkSuiteError("invalid benchmark catalog schema")
    if catalog["schema_version"] != 1:
        raise BenchmarkSuiteError("unsupported catalog schema_version")
    for key in ("dataset_name", "description"):
        if not isinstance(catalog[key], str) or not catalog[key].strip():
            raise BenchmarkSuiteError(f"{key} must be a nonempty string")
    if not isinstance(catalog["tasks"], list) or not catalog["tasks"]:
        raise BenchmarkSuiteError("catalog tasks must be a non-empty list")

    ids: set[str] = set()
    prompts: set[str] = set()
    split_counts: Counter[str] = Counter()
    categories: dict[str, Counter[str]] = {}
    for item in catalog["tasks"]:
        if not isinstance(item, dict) or set(item) != {
            "id", "split", "category", "prompt", "expected"
        }:
            raise BenchmarkSuiteError("task must contain id/split/category/prompt/expected")
        for key in ("id", "category"):
            value = item[key]
            if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
                raise BenchmarkSuiteError(f"invalid {key}")
        if item["id"] in ids:
            raise BenchmarkSuiteError("duplicate task id")
        ids.add(item["id"])
        if item["split"] not in ("train", "holdout"):
            raise BenchmarkSuiteError("split must be train or holdout")
        if not isinstance(item["prompt"], str) or not item["prompt"].strip():
            raise BenchmarkSuiteError("task prompt must be nonblank")
        prompt_digest = _sha(item["prompt"])
        if prompt_digest in prompts:
            raise BenchmarkSuiteError("duplicate prompt across suite splits")
        prompts.add(prompt_digest)
        if not isinstance(item["expected"], dict) or not item["expected"]:
            raise BenchmarkSuiteError("expected must be a nonempty JSON object")
        if not all(isinstance(k, str) for k in item["expected"]):
            raise BenchmarkSuiteError("expected JSON object keys must be strings")
        split_counts[item["split"]] += 1
        categories.setdefault(item["category"], Counter())[item["split"]] += 1

    if split_counts["train"] < 1 or split_counts["holdout"] < 3:
        raise BenchmarkSuiteError("catalog needs >=1 train and >=3 holdout tasks")
    if any(count["holdout"] < 1 or count["train"] < 1 for count in categories.values()):
        raise BenchmarkSuiteError("every category needs train and holdout coverage")

    return {
        "schema_version": 1,
        "dataset_name": catalog["dataset_name"],
        "catalog_sha256": _sha(_canonical(catalog)),
        "train_count": split_counts["train"],
        "holdout_count": split_counts["holdout"],
        "category_counts": {
            category: dict(sorted(counts.items()))
            for category, counts in sorted(categories.items())
        },
        "limitations": [
            "Published tasks/oracles are synthetic, not private or blind.",
            "Model accuracy and cost require real, matched provider executions.",
            "Do not train or tune the evaluated policy on holdout tasks.",
        ],
    }


def _validate_arm(
    values: tuple[str, ...] | list[str],
    registry: ModelRegistry,
) -> dict[str, str]:
    if len(values) != 4:
        raise BenchmarkSuiteError("arm requires provider, model_id, effort, execution_mode")
    provider, model_id, effort, execution_mode = values
    if execution_mode != "single":
        raise BenchmarkSuiteError("direct provider benchmark requires single mode")
    matches = [
        item for item in registry.candidates()
        if item.provider == provider and item.model_id == model_id
    ]
    if len(matches) != 1:
        raise BenchmarkSuiteError("arm model must be current and in the registry")
    model = matches[0]
    if effort not in model.efforts:
        raise BenchmarkSuiteError("arm reasoning effort is unsupported for model")
    if execution_mode not in model.execution_modes:
        raise BenchmarkSuiteError("arm execution mode is unsupported for model")
    if provider not in {"openai", "anthropic"}:
        raise BenchmarkSuiteError("benchmark runner supports OpenAI and Anthropic only")
    return dict(zip(_FIELDS, values))


def build_bundle(
    catalog: dict[str, Any],
    *,
    experiment_id: str,
    arm_a: tuple[str, ...] | list[str],
    arm_b: tuple[str, ...] | list[str],
    environment_id: str,
    seed: int = 42,
    minimum_pairs: int = 5,
    registry: ModelRegistry | None = None,
) -> dict[str, Any]:
    info = validate_catalog(catalog)
    for name, value in (("experiment_id", experiment_id), ("environment_id", environment_id)):
        if not isinstance(value, str) or not _IDENTIFIER.fullmatch(value):
            raise BenchmarkSuiteError(f"invalid {name}")
    current_registry = registry or ModelRegistry()
    arms = {
        "A": _validate_arm(arm_a, current_registry),
        "B": _validate_arm(arm_b, current_registry),
    }
    train_ids = sorted(
        item["id"] for item in catalog["tasks"] if item["split"] == "train"
    )
    held_out = sorted(
        (item for item in catalog["tasks"] if item["split"] == "holdout"),
        key=lambda item: item["id"],
    )
    task_payload = {
        "schema_version": 1,
        "tasks": [{"task_id": item["id"], "prompt": item["prompt"]} for item in held_out],
    }
    oracle_payload = {
        "schema_version": 1,
        "evaluator_id": "",
        "checks": [
            {
                "task_id": item["id"], "mode": "json-equal",
                "expected": _canonical(item["expected"]),
            }
            for item in held_out
        ],
    }
    oracle_hash = _sha(_canonical(oracle_payload["checks"]))
    evaluator_id = f"json-oracle-{oracle_hash[:16]}"
    oracle_payload["evaluator_id"] = evaluator_id
    spec = {
        "schema_version": 1,
        "experiment_id": experiment_id,
        "seed": seed,
        "dataset_id": f"dataset-{info['catalog_sha256'][:16]}",
        "environment_id": environment_id,
        "evaluator_id": evaluator_id,
        "training_task_ids": train_ids,
        "arms": arms,
        "tasks": [
            {
                "task_id": item["id"],
                "category": item["category"],
                "prompt_sha256": _sha(item["prompt"]),
            }
            for item in held_out
        ],
        "minimum_pairs": minimum_pairs,
    }
    plan = make_plan(spec)
    fixtures(plan, task_payload, oracle_payload)
    return {
        "manifest": {
            **info,
            "experiment_id": experiment_id,
            "plan_hash": plan["plan_hash"],
            "registry_as_of": current_registry.as_of,
            "evaluation_kind": "public_synthetic_objective_tasks",
            "safe_to_apply": False,
        },
        "spec": spec,
        "plan": plan,
        "tasks": task_payload,
        "oracle": oracle_payload,
    }


def write_bundle(bundle: dict[str, Any], output_dir: str | Path) -> tuple[Path, ...]:
    directory = Path(output_dir)
    names = ("manifest", "spec", "plan", "tasks", "oracle")
    targets = tuple(directory / f"{name}.json" for name in names)
    if any(target.exists() for target in targets):
        raise BenchmarkSuiteError("output bundle exists; refusing to overwrite evidence")
    directory.mkdir(parents=True, exist_ok=True)
    for name, target in zip(names, targets):
        target.write_text(
            json.dumps(bundle[name], indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    return targets


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline reproducible benchmark suite")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate", help="Validate a public or private suite")
    validate.add_argument("--catalog", type=Path)
    build = sub.add_parser("build", help="Build immutable A/B experiment fixtures")
    build.add_argument("--catalog", type=Path)
    build.add_argument("--experiment-id", required=True)
    build.add_argument("--environment-id", default="direct-single-v1")
    build.add_argument("--arm-a", nargs=4, required=True, metavar=_FIELDS)
    build.add_argument("--arm-b", nargs=4, required=True, metavar=_FIELDS)
    build.add_argument("--seed", type=int, default=42)
    build.add_argument("--minimum-pairs", type=int, default=5)
    build.add_argument("--registry", type=Path)
    build.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args(argv)
    catalog = load_catalog(args.catalog)
    if args.command == "validate":
        result = validate_catalog(catalog)
    else:
        bundle = build_bundle(
            catalog,
            experiment_id=args.experiment_id,
            arm_a=args.arm_a,
            arm_b=args.arm_b,
            environment_id=args.environment_id,
            seed=args.seed,
            minimum_pairs=args.minimum_pairs,
            registry=ModelRegistry(args.registry),
        )
        files_written = write_bundle(bundle, args.output_dir)
        result = {
            "manifest": bundle["manifest"],
            "files": [str(path) for path in files_written],
        }
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
