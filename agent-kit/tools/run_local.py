#!/usr/bin/env python3
"""Run the Civil AI Agent Kit offline checks without GitHub Actions.

Standard library only; no model API, dependency install, network call, or native tool.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_checks(output: Path | None = None) -> int:
    commands = [
        ("synthetic_cases", [sys.executable, "tools/verify.py", "--self-test"]),
        ("unittest", [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"]),
    ]
    checks = []
    for name, command in commands:
        print(f"\n=== {name}: {' '.join(command)} ===", flush=True)
        try:
            completed = subprocess.run(command, cwd=ROOT, check=False, timeout=90)
            status = "PASS" if completed.returncode == 0 else "FAIL"
            checks.append({"check": name, "status": status, "exit_code": completed.returncode})
        except subprocess.TimeoutExpired:
            status = "FAIL"
            checks.append({"check": name, "status": status, "exit_code": None, "reason": "timeout"})
        except OSError as error:
            status = "FAIL"
            checks.append({"check": name, "status": status, "exit_code": None, "reason": str(error)})
        print(f"{name}: {status}", flush=True)

    passed = all(check["status"] == "PASS" for check in checks)
    report = {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "scope": "fictional metadata cases only; native civil tools not tested",
        "checks": checks,
        "result": "PASS" if passed else "FAIL",
    }
    if output is not None:
        # Reports may contain local environment information; use a user-selected path
        # outside the repository. Never write a generated report by default.
        target = output.resolve()
        if target == ROOT or ROOT in target.parents:
            print("Refusing to write generated report inside agent-kit", file=sys.stderr)
            return 2
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
        print(f"JSON report: {target}", flush=True)
    print(f"\nOFFLINE RESULT: {report['result']}", flush=True)
    return 0 if passed else 1


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json-report", type=Path, help="Optional JSON report path outside agent-kit")
    args = parser.parse_args(argv)
    return run_checks(args.json_report)


if __name__ == "__main__":
    raise SystemExit(main())
