#!/usr/bin/env python3
"""Offline, dependency-free Agent Kit test runner; never invokes GitHub Actions."""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

KIT_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = KIT_ROOT.parent
CHECKED_FILES = ("tools/verify.py", "tools/run_local.py", "tests/test_verify.py",
                 "tests/test_run_local.py", "fixtures/synthetic_cases.json")


def safe_report_path(path: Path) -> Path:
    """Prevent writing a report to the working repository or its git metadata."""
    target = path.resolve()
    if target == REPO_ROOT or REPO_ROOT in target.parents:
        raise ValueError("JSON evidence report must be outside the repository")
    return target


def run_checks(output: Path | None = None) -> int:
    if output is not None:
        try:
            output = safe_report_path(output)
        except ValueError as error:
            print(f"BLOCKED: {error}", file=sys.stderr)
            return 2
    commands = [
        ("synthetic_cases", [sys.executable, "tools/verify.py", "--self-test"]),
        ("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    ]
    results = []
    for name, argv in commands:
        print(f"\n=== {name}: {' '.join(argv)} ===", flush=True)
        try:
            completed = subprocess.run(argv, cwd=KIT_ROOT, check=False, timeout=90)
            code, reason = completed.returncode, None
        except subprocess.TimeoutExpired:
            code, reason = None, "timeout"
        except OSError as error:
            code, reason = None, str(error)
        outcome = {"check": name, "status": "PASS" if code == 0 else "FAIL", "exit_code": code}
        if reason:
            outcome["reason"] = reason
        results.append(outcome)
        print(f"{name}: {outcome['status']}", flush=True)

    verified_sha256 = {}
    for relative in CHECKED_FILES:
        source = KIT_ROOT / relative
        verified_sha256[relative] = hashlib.sha256(source.read_bytes()).hexdigest()

    passed = all(result["status"] == "PASS" for result in results)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "scope": "synthetic metadata only; Windows/native civil tools not tested",
        "files_sha256": verified_sha256,
        "checks": results,
        "result": "PASS" if passed else "FAIL",
    }
    if output is not None:
        try:
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        except OSError as error:
            print(f"BLOCKED: could not save report: {error}", file=sys.stderr)
            return 2
        print(f"JSON evidence: {output}", flush=True)
    print(f"OFFLINE RESULT: {report['result']}", flush=True)
    return 0 if passed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-report", type=Path, help="Optional path outside repository")
    args = parser.parse_args(argv)
    return run_checks(args.json_report)


if __name__ == "__main__":
    raise SystemExit(main())
