"""Opt-in single-run provider benchmark with frozen fixtures and deterministic judging.

Preview is offline. Apply sends one direct provider request only after a
per-run budget preflight; cost estimates are NOT provider-enforced limits.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import time
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path
from typing import Any, Callable, Iterator

from tools.ai_model_advisor.expected_output_judge import judge_expected_output
from tools.ai_model_advisor.provider_api_adapter import (
    ProviderRequest,
    _http_json,
    build_provider_request,
    parse_provider_response,
)
from tools.ai_model_advisor.registry import ModelRegistry

from .experiment_protocol import _validate_plan, evaluate_plan

Transport = Callable[[ProviderRequest, float], dict[str, Any]]
MODES = {"exact", "strip-exact", "contains", "json-equal"}


class BenchmarkRunnerError(ValueError):
    """Execution rejected before recording a trustworthy outcome."""


def _digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _object(path: str) -> dict[str, Any]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise BenchmarkRunnerError("JSON fixture root must be an object")
    return data


def _keys(item: Any, keys: set[str], label: str) -> None:
    if not isinstance(item, dict) or set(item) != keys:
        raise BenchmarkRunnerError(f"{label} requires exactly {sorted(keys)}")


def fixtures(
    plan: dict[str, Any], tasks: dict[str, Any], oracle: dict[str, Any]
) -> tuple[dict[str, str], dict[str, tuple[str, str]]]:
    _validate_plan(plan)
    _keys(tasks, {"schema_version", "tasks"}, "task fixtures")
    _keys(oracle, {"schema_version", "evaluator_id", "checks"}, "oracle fixtures")
    if tasks["schema_version"] != 1 or oracle["schema_version"] != 1:
        raise BenchmarkRunnerError("unsupported fixture schema")
    if oracle["evaluator_id"] != plan["spec"]["evaluator_id"]:
        raise BenchmarkRunnerError("frozen evaluator identity does not match")
    if not isinstance(tasks["tasks"], list) or not isinstance(oracle["checks"], list):
        raise BenchmarkRunnerError("fixture entries must be arrays")
    prompts: dict[str, str] = {}
    expected: dict[str, tuple[str, str]] = {}
    for item in tasks["tasks"]:
        _keys(item, {"task_id", "prompt"}, "task fixture")
        if not isinstance(item["task_id"], str) or not isinstance(item["prompt"], str):
            raise BenchmarkRunnerError("task fixture must contain strings")
        if not item["prompt"].strip() or item["task_id"] in prompts:
            raise BenchmarkRunnerError("empty or duplicate task fixture")
        prompts[item["task_id"]] = item["prompt"]
    for item in oracle["checks"]:
        _keys(item, {"task_id", "expected", "mode"}, "oracle check")
        if not all(isinstance(item[k], str) for k in ("task_id", "expected", "mode")):
            raise BenchmarkRunnerError("oracle fixture must contain strings")
        if item["task_id"] in expected or item["mode"] not in MODES:
            raise BenchmarkRunnerError("duplicate oracle check or unsupported mode")
        if item["mode"] == "json-equal":
            try:
                json.loads(item["expected"])
            except json.JSONDecodeError as exc:
                raise BenchmarkRunnerError("invalid JSON oracle fixture") from exc
        expected[item["task_id"]] = item["expected"], item["mode"]
    scheduled = {item["task_id"]: item["prompt_sha256"] for item in plan["spec"]["tasks"]}
    if set(prompts) != set(scheduled) or set(expected) != set(scheduled):
        raise BenchmarkRunnerError("fixtures must exactly cover scheduled holdout tasks")
    if any(_digest(prompts[task]) != sha for task, sha in scheduled.items()):
        raise BenchmarkRunnerError("prompt SHA-256 mismatch")
    return prompts, expected


def _model(run: dict[str, Any], registry: ModelRegistry) -> Any:
    if run["provider"] not in ("openai", "anthropic"):
        raise BenchmarkRunnerError("only OpenAI and Anthropic direct APIs are supported")
    if run["execution_mode"] != "single":
        raise BenchmarkRunnerError("direct runner supports only single execution mode")
    matches = [
        model for model in registry.candidates()
        if model.provider == run["provider"] and model.model_id == run["model_id"]
    ]
    if len(matches) != 1:
        raise BenchmarkRunnerError("model must belong to current registry candidates")
    model = matches[0]
    if run["effort"] != "default" and run["effort"] not in model.efforts:
        raise BenchmarkRunnerError("reasoning effort unsupported by registry model")
    return model


def _read_lines(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        rows = [
            json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except json.JSONDecodeError as exc:
        raise BenchmarkRunnerError("invalid existing JSONL ledger") from exc
    if not all(isinstance(row, dict) for row in rows):
        raise BenchmarkRunnerError("existing JSONL ledger contains non-objects")
    return rows


def _write_line(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        raise


@contextmanager
def _lock(path: Path) -> Iterator[None]:
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_name(path.name + ".lock")
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise BenchmarkRunnerError("observation ledger is locked by another runner") from exc
    try:
        os.close(fd)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def preview(
    plan: dict[str, Any],
    tasks: dict[str, Any],
    oracle: dict[str, Any],
    registry: ModelRegistry,
    *,
    run_id: str,
    observations: list[dict[str, Any]] | None = None,
    attempts: list[dict[str, Any]] | None = None,
    max_output_tokens: int = 512,
    max_cost_usd: float | None = None,
) -> dict[str, Any]:
    prompts, _ = fixtures(plan, tasks, oracle)
    if type(max_output_tokens) is not int or not 1 <= max_output_tokens <= 8192:
        raise BenchmarkRunnerError("max_output_tokens must be 1..8192")
    if max_cost_usd is not None and (
        type(max_cost_usd) not in (int, float)
        or not math.isfinite(max_cost_usd) or max_cost_usd <= 0
    ):
        raise BenchmarkRunnerError("max_cost_usd must be positive and finite")
    runs = {item["run_id"]: item for item in plan["runs"]}
    if run_id not in runs:
        raise BenchmarkRunnerError("run_id was not scheduled")
    run = runs[run_id]
    model = _model(run, registry)
    if max_output_tokens > model.max_output_tokens:
        raise BenchmarkRunnerError("max_output_tokens exceeds model output limit")
    current = observations or []
    evaluate_plan(plan, current)
    if any(row["run_id"] == run_id for row in current):
        raise BenchmarkRunnerError("run_id already recorded")
    if any(row.get("run_id") == run_id for row in (attempts or [])):
        raise BenchmarkRunnerError(
            "run_id already attempted; manually reconcile uncertain billing before retry"
        )
    if run["order"] == 2:
        first = next(
            item for item in plan["runs"]
            if item["task_id"] == run["task_id"] and item["order"] == 1
        )
        if not any(row["run_id"] == first["run_id"] for row in current):
            raise BenchmarkRunnerError("first scheduled arm has no recorded result")
    prompt_bytes = len(prompts[run["task_id"]].encode("utf-8"))
    reserve = (
        prompt_bytes * model.input_usd_per_mtok
        + max_output_tokens * model.output_usd_per_mtok
    ) / 1_000_000
    return {
        "schema_version": 1,
        "run_id": run_id,
        "model_id": run["model_id"],
        "provider": run["provider"],
        "effort": run["effort"],
        "execution_mode": run["execution_mode"],
        "plan_hash": run["plan_hash"],
        "reserved_list_price_proxy_usd": round(reserve, 8),
        "max_cost_usd": max_cost_usd,
        "budget_preflight_passed": max_cost_usd is not None and reserve <= max_cost_usd,
        "requires_explicit_apply": True,
        "safe_to_apply": False,
        "caveat": (
            "Registry list-price proxy is NOT a provider-enforced spending cap; "
            "provider billing may differ."
        ),
    }


def run_one(
    plan: dict[str, Any],
    tasks: dict[str, Any],
    oracle: dict[str, Any],
    registry: ModelRegistry,
    *,
    run_id: str,
    observations_path: str | Path,
    max_cost_usd: float,
    max_output_tokens: int = 512,
    timeout_seconds: float = 180.0,
    transport: Transport | None = None,
) -> dict[str, Any]:
    if not math.isfinite(timeout_seconds) or not 0 < timeout_seconds <= 600:
        raise BenchmarkRunnerError("timeout_seconds must be >0 and <=600")
    path = Path(observations_path)
    attempt_path = path.with_name(path.name + ".attempts.jsonl")
    with _lock(path):
        previous = _read_lines(path)
        attempts = _read_lines(attempt_path)
        report = preview(
            plan, tasks, oracle, registry, run_id=run_id,
            observations=previous, attempts=attempts,
            max_output_tokens=max_output_tokens, max_cost_usd=max_cost_usd,
        )
        if not report["budget_preflight_passed"]:
            raise BenchmarkRunnerError("list-price reservation exceeds max_cost_usd")
        run = next(item for item in plan["runs"] if item["run_id"] == run_id)
        prompt, (expected, mode) = (
            fixtures(plan, tasks, oracle)[0][run["task_id"]],
            fixtures(plan, tasks, oracle)[1][run["task_id"]],
        )
        payload = {
            "schema_version": 1,
            "acceptance_mode": "external_judge",
            "task": prompt,
            "task_sha256": run["prompt_sha256"],
            "configuration": {
                field: run[field]
                for field in ("provider", "model_id", "effort", "execution_mode")
            },
        }
        try:
            request = build_provider_request(payload)
        except Exception:
            raise BenchmarkRunnerError("provider credentials or configuration unavailable") from None
        body = dict(request.body)
        body["max_output_tokens" if run["provider"] == "openai" else "max_tokens"] = (
            max_output_tokens
        )
        request = replace(request, body=body)

        # Durable marker precedes transport. An uncertain/charged attempt cannot
        # silently be retried even when the response was lost.
        _write_line(attempt_path, {
            "run_id": run_id, "plan_hash": run["plan_hash"],
            "status": "attempted", "provider": run["provider"],
        })
        start = time.perf_counter()
        try:
            raw = (transport or _http_json)(request, timeout_seconds)
            parsed = parse_provider_response(request, raw)
        except Exception:
            # Never print untrusted provider errors that might contain secrets.
            raise BenchmarkRunnerError(
                "provider execution failed; attempt recorded for manual reconciliation"
            ) from None
        elapsed = time.perf_counter() - start
        if parsed.get("resolved_model") != run["model_id"]:
            raise BenchmarkRunnerError("resolved model mismatch; attempt requires review")
        if run["provider"] == "openai" and parsed.get("provider_status") != "completed":
            raise BenchmarkRunnerError("OpenAI response not completed; attempt requires review")
        if run["provider"] == "anthropic" and parsed.get("provider_status") not in (
            "end_turn", "stop_sequence"
        ):
            raise BenchmarkRunnerError("Anthropic response not completed; attempt requires review")
        if not isinstance(parsed.get("response_text"), str):
            raise BenchmarkRunnerError("missing response text; attempt requires review")
        inp, out = parsed.get("input_tokens"), parsed.get("output_tokens")
        if type(inp) is not int or type(out) is not int or inp < 0 or out < 0:
            raise BenchmarkRunnerError("missing provider usage; attempt requires review")
        verdict = judge_expected_output(
            {"adapter_result": parsed}, expected=expected, mode=mode
        )
        if verdict["outcome"] not in ("success", "failure"):
            raise BenchmarkRunnerError("invalid deterministic judge outcome")
        model = _model(run, registry)
        cost_estimate = (
            inp * model.input_usd_per_mtok
            + out * model.output_usd_per_mtok
        ) / 1_000_000
        row = {
            key: run[key]
            for key in (
                "experiment_id", "plan_hash", "run_id", "task_id", "arm",
                "category", "prompt_sha256", "dataset_id", "environment_id",
                "evaluator_id", "provider", "model_id", "effort", "execution_mode",
            )
        }
        row.update({
            "outcome": verdict["outcome"],
            "latency_seconds": max(elapsed, 1e-9),
            "input_tokens": inp,
            "output_tokens": out,
            "estimated_cost_usd": round(cost_estimate, 8),
            "note": (
                f"judge={mode};response_sha256={_digest(parsed['response_text'])};"
                "list_price_estimate_not_invoice"
            ),
        })
        evaluate_plan(plan, [*previous, row])
        _write_line(path, row)
        return {
            "recorded": True, "run_id": run_id, "outcome": verdict["outcome"],
            "latency_seconds": row["latency_seconds"],
            "estimated_cost_usd": row["estimated_cost_usd"],
            "billed_cost_usd": None,
            "safe_to_apply": False,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Offline preview or opt-in one-run benchmark")
    parser.add_argument("--plan", required=True)
    parser.add_argument("--tasks", required=True)
    parser.add_argument("--oracle", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--observations", required=True)
    parser.add_argument("--registry")
    parser.add_argument("--max-output-tokens", type=int, default=512)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-cost-usd", type=float)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args(argv)
    plan, tasks, oracle = _object(args.plan), _object(args.tasks), _object(args.oracle)
    registry = ModelRegistry(args.registry)
    if args.apply:
        if args.max_cost_usd is None:
            parser.error("--apply requires --max-cost-usd")
        result = run_one(
            plan, tasks, oracle, registry,
            run_id=args.run_id, observations_path=args.observations,
            max_cost_usd=args.max_cost_usd, max_output_tokens=args.max_output_tokens,
            timeout_seconds=args.timeout_seconds,
        )
    else:
        path = Path(args.observations)
        result = preview(
            plan, tasks, oracle, registry, run_id=args.run_id,
            observations=_read_lines(path),
            attempts=_read_lines(path.with_name(path.name + ".attempts.jsonl")),
            max_output_tokens=args.max_output_tokens,
            max_cost_usd=args.max_cost_usd,
        )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
