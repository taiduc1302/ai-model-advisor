#!/usr/bin/env python3
"""Offline metadata preflight; this cannot authenticate sources or approve bids."""
from __future__ import annotations

import argparse
import json
import math
import re
from pathlib import Path
from typing import Any

ALLOWED_STATUSES = frozenset({"DRAFT", "BLOCKED", "NEEDS_HUMAN_REVIEW"})
UNAUTHORIZED_AGENT_FLAGS = frozenset({
    "approved_by_agent", "approval", "approval_status", "agent_approved",
    "agent_signed", "authorization_override", "final_submit", "human_approved",
    "markups_approved_by_agent", "price_approved_by_agent", "production_import",
})
TAKEOFF_UNITS = frozenset({"m", "m2", "m3", "ft", "ft2", "ft3", "ea"})
SCALE_PATTERN = re.compile(r"1:([1-9][0-9]*)\Z", re.ASCII)


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _nonnegative_finite(value: Any) -> bool:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        return math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _exact_nonnegative_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def validate(kind: str, record: dict) -> list[str]:
    """Validate declarations only; return blocking reasons; no side effects."""
    if not isinstance(record, dict):
        return ["record must be an object"]
    reasons: list[str] = []
    status = record.get("status")
    if not isinstance(status, str) or status not in ALLOWED_STATUSES:
        reasons.append("agent-produced status must be DRAFT, BLOCKED or NEEDS_HUMAN_REVIEW")

    for key in sorted(UNAUTHORIZED_AGENT_FLAGS.intersection(record)):
        # A false explicit acknowledgement is allowed; any other claimed approval is not.
        if record[key] is not False:
            reasons.append(f"unauthorized agent approval, submission or import: {key}")

    if kind == "takeoff":
        for key in ("source_file", "sheet", "revision", "governing_revision",
                    "scale", "unit", "markup_id", "native_readback_id", "method"):
            if not _nonempty(record.get(key)):
                reasons.append(f"missing {key}")
        if record.get("revision") != record.get("governing_revision"):
            reasons.append("stale or conflicting revision")
        scale = record.get("scale")
        if not (isinstance(scale, str) and SCALE_PATTERN.fullmatch(scale)):
            reasons.append("invalid scale; expected positive 1:N")
        if record.get("scale_verified") is not True:
            reasons.append("scale not verified")
        if not (isinstance(record.get("unit"), str) and record["unit"] in TAKEOFF_UNITS):
            reasons.append("invalid or ambiguous unit")
        if not _nonnegative_finite(record.get("quantity")):
            reasons.append("invalid quantity")
        if record.get("markup_id") != record.get("native_readback_id"):
            reasons.append("native markup read-back mismatch")

    elif kind == "heavybid":
        for key in ("source_file", "source_revision", "codebook_revision", "code", "unit",
                    "mapping_evidence"):
            if not _nonempty(record.get(key)):
                reasons.append(f"missing {key}")
        if record.get("codebook_verified") is not True:
            reasons.append("codebook revision unverified")
        if record.get("unit_matches") is not True:
            reasons.append("HeavyBid unit mismatch")

    elif kind == "tender":
        for key in ("source_file", "governing_addendum", "source_citation"):
            if not _nonempty(record.get(key)):
                reasons.append(f"missing {key}")
        if record.get("addenda_reconciled") is not True:
            reasons.append("addenda not reconciled")
        conflicts = record.get("unresolved_conflicts")
        if not _exact_nonnegative_int(conflicts) or conflicts != 0:
            reasons.append("unreconciled, malformed or conflicting addenda")

    elif kind == "automation":
        if not _nonempty(record.get("idempotency_key")):
            reasons.append("missing idempotency key")
        if record.get("dry_run") is not True:
            reasons.append("pilot must be dry-run")
        if record.get("network") is not False:
            reasons.append("pilot requires network disabled")
        if not _exact_nonnegative_int(record.get("paid_calls")) or record["paid_calls"] != 0:
            reasons.append("pilot requires zero paid calls")
        if record.get("external_write") is not False:
            reasons.append("pilot cannot write to external systems")
        if type(record.get("attempt")) is not int or record["attempt"] != 1:
            reasons.append("pilot retry requires explicit state reconciliation")

    else:
        reasons.append(f"unsupported record kind {kind!r}")
    return reasons


def verify_bundle(bundle: dict) -> list[tuple[int, list[str]]]:
    """Fail closed on malformed entries, exact duplicates, and duplicate markup/action keys."""
    if not isinstance(bundle, dict) or not isinstance(bundle.get("records"), list):
        return [(0, ["bundle must contain records array"])]
    if not bundle["records"]:
        return [(0, ["bundle cannot be empty"])]
    failures: list[tuple[int, list[str]]] = []
    seen_exact: set[str] = set()
    seen_business_keys: set[tuple[str, ...]] = set()
    for index, item in enumerate(bundle["records"]):
        if not isinstance(item, dict):
            failures.append((index, ["entry must be an object"]))
            continue
        kind, record = item.get("kind"), item.get("record")
        problems = validate(kind, record)
        try:
            normalized = json.dumps(item, sort_keys=True, ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            normalized = None
            problems.append("invalid or non-finite record content")
        if normalized is not None:
            if normalized in seen_exact:
                problems.append("duplicate record")
            seen_exact.add(normalized)
        if isinstance(record, dict):
            key = None
            if kind == "takeoff" and all(_nonempty(record.get(k)) for k in ("source_file", "sheet", "markup_id")):
                key = (kind, record["source_file"], record["sheet"], record["markup_id"])
            elif kind == "automation" and _nonempty(record.get("idempotency_key")):
                key = (kind, record["idempotency_key"])
            if key is not None:
                if key in seen_business_keys:
                    problems.append("duplicate markup or idempotency key")
                seen_business_keys.add(key)
        if problems:
            failures.append((index, problems))
    return failures


def run_self_test(path: Path) -> bool:
    try:
        fixtures = json.loads(path.read_text(encoding="utf-8"))
        cases = fixtures["cases"]
        if not isinstance(cases, list) or not cases:
            raise ValueError("no cases")
        passed, failed = 0, 0
        for case in cases:
            # Per-record cases retain the v0.1 format; bundle cases test cross-record rules.
            if "records" in case:
                problems = verify_bundle({"records": case["records"]})
                valid = not problems
            else:
                problems = validate(case["kind"], case["record"])
                valid = not problems
            if type(case["expect_valid"]) is not bool:
                raise ValueError("expect_valid must be boolean")
            if valid == case["expect_valid"]:
                print(f"PASS {case['name']}")
                passed += 1
            else:
                print(f"FAIL {case['name']}: expected={case['expect_valid']}; reasons={problems}")
                failed += 1
        print(f"{passed} passed; {failed} failed")
        return failed == 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"FAIL fixtures: {exc}")
        return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    opts = parser.add_mutually_exclusive_group(required=True)
    opts.add_argument("--self-test", action="store_true")
    opts.add_argument("--file", type=Path)
    args = parser.parse_args(argv)
    if args.self_test:
        fixture_path = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_cases.json"
        return 0 if run_self_test(fixture_path) else 1
    try:
        bundle = json.loads(args.file.read_text(encoding="utf-8"))
        failures = verify_bundle(bundle)
    except (OSError, ValueError, TypeError) as exc:
        print(f"BLOCKED: invalid bundle: {exc}")
        return 1
    if failures:
        for index, problems in failures:
            print(f"BLOCKED record {index}: {'; '.join(problems)}")
        return 1
    print(f"METADATA PASS: {len(bundle['records'])} records; human/native verification still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
