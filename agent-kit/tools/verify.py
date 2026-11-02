#!/usr/bin/env python3
"""Offline metadata preflight for fictional civil/automation workflows.

This validates declared fields only. It cannot authenticate sources or approve a bid.
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _nonempty(value):
    return isinstance(value, str) and bool(value.strip())


def validate(kind: str, record: dict) -> list[str]:
    """Return blocking reasons. No external actions or state changes."""
    if not isinstance(record, dict):
        return ["record must be an object"]
    reasons = []
    allowed_statuses = {"DRAFT", "BLOCKED", "NEEDS_HUMAN_REVIEW"}
    status = record.get("status")
    if status not in allowed_statuses:
        reasons.append("agent-produced status must be DRAFT, BLOCKED or NEEDS_HUMAN_REVIEW")
    if kind == "takeoff":
        for key in ("source_file", "sheet", "revision", "governing_revision",
                    "scale", "unit", "markup_id", "native_readback_id"):
            if not _nonempty(record.get(key)):
                reasons.append(f"missing {key}")
        if record.get("revision") != record.get("governing_revision"):
            reasons.append("stale or conflicting revision")
        if record.get("scale_verified") is not True:
            reasons.append("scale not verified")
        if record.get("unit") not in {"m", "m2", "m3", "ft", "ft2", "ft3", "ea"}:
            reasons.append("invalid or ambiguous unit")
        quantity = record.get("quantity")
        if isinstance(quantity, bool) or not isinstance(quantity, (int, float)) or not math.isfinite(quantity) or quantity < 0:
            reasons.append("invalid quantity")
        if record.get("markup_id") != record.get("native_readback_id"):
            reasons.append("native markup read-back mismatch")
        if not _nonempty(record.get("method")):
            reasons.append("missing measurement method")
    elif kind == "heavybid":
        for key in ("source_file", "source_revision", "codebook_revision",
                    "code", "unit", "mapping_evidence"):
            if not _nonempty(record.get(key)):
                reasons.append(f"missing {key}")
        if record.get("codebook_verified") is not True:
            reasons.append("codebook revision unverified")
        if record.get("unit_matches") is not True:
            reasons.append("HeavyBid unit mismatch")
        if record.get("production_import") is True or record.get("price_approved_by_agent") is True:
            reasons.append("unauthorized pricing approval or production import")
    elif kind == "tender":
        for key in ("source_file", "governing_addendum", "source_citation"):
            if not _nonempty(record.get(key)):
                reasons.append(f"missing {key}")
        if record.get("addenda_reconciled") is not True or record.get("unresolved_conflicts") != 0:
            reasons.append("unreconciled or conflicting addenda")
        if record.get("final_submit") is True or record.get("agent_signed") is True:
            reasons.append("unauthorized tender submission or signature")
    elif kind == "automation":
        if not _nonempty(record.get("idempotency_key")):
            reasons.append("missing idempotency key")
        if record.get("dry_run") is not True:
            reasons.append("pilot must be dry-run")
        if record.get("network") is not False or record.get("paid_calls") != 0:
            reasons.append("pilot requires offline and zero paid calls")
        if record.get("external_write") is not False:
            reasons.append("pilot cannot write to external systems")
        if record.get("attempt") not in (1,):
            reasons.append("pilot cannot retry without a verified state reconciliation")
    else:
        reasons.append(f"unsupported record kind {kind!r}")
    return reasons


def verify_bundle(bundle: dict) -> list[tuple[int, list[str]]]:
    if not isinstance(bundle, dict) or not isinstance(bundle.get("records"), list):
        return [(0, ["bundle must contain records array"])]
    if not bundle["records"]:
        return [(0, ["bundle cannot be empty"])]
    failures = []
    for index, item in enumerate(bundle["records"]):
        if not isinstance(item, dict):
            problems = ["entry must be an object"]
        else:
            problems = validate(item.get("kind"), item.get("record"))
        if problems:
            failures.append((index, problems))
    return failures


def run_self_test(path: Path) -> bool:
    try:
        fixtures = json.loads(path.read_text(encoding="utf-8"))
        cases = fixtures["cases"]
        if not cases:
            raise ValueError("no cases")
        count_pass, count_fail = 0, 0
        for case in cases:
            reasons = validate(case["kind"], case["record"])
            actual = not reasons
            expected = case["expect_valid"]
            if actual != expected:
                print(f"FAIL {case['name']}: expected valid={expected}, reasons={reasons}")
                count_fail += 1
            else:
                print(f"PASS {case['name']}")
                count_pass += 1
        print(f"{count_pass} passed; {count_fail} failed")
        return count_fail == 0
    except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        print(f"FAIL fixtures: {exc}")
        return False


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    opts = parser.add_mutually_exclusive_group(required=True)
    opts.add_argument("--self-test", action="store_true")
    opts.add_argument("--file", type=Path)
    args = parser.parse_args(argv)
    if args.self_test:
        path = Path(__file__).resolve().parents[1] / "fixtures" / "synthetic_cases.json"
        return 0 if run_self_test(path) else 1
    try:
        bundle = json.loads(args.file.read_text(encoding="utf-8"))
        failures = verify_bundle(bundle)
    except (OSError, ValueError, TypeError) as exc:
        print(f"BLOCKED: could not read bundle: {exc}")
        return 1
    if failures:
        for index, reasons in failures:
            print(f"BLOCKED record {index}: {'; '.join(reasons)}")
        return 1
    print(f"METADATA PASS: {len(bundle['records'])} records; human/native verification still required")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
