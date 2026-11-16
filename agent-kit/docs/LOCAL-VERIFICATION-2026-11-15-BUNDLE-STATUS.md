# Offline verification — bundle status gate (2026-11-15)

**Status: PASS for synthetic metadata checks only.** The verifier has not been tested with a native Windows GUI or actual Bluebeam Revu, AGTEK, HeavyBid, or live tender documents.

## What changed

The preflight previously treated `BLOCKED` and `NEEDS_HUMAN_REVIEW` as acceptable record statuses, then returned an overall `METADATA PASS` for otherwise valid records. The statuses remain safe for an agent to *emit*, but `verify_bundle` now fails the bundle whenever a record's status is not `DRAFT`.

New test method checks all four record kinds with both blocked/review statuses. Two fictional bundle fixtures explicitly cover BLOCKED takeoff and NEEDS_HUMAN_REVIEW tender.

## Exact verification

- Runtime: isolated Linux, Python 3.13.5, standard library only, no network/paid-model calls.
- Command: `python tools/run_local.py --json-report <external local path>`.
- Observed: **50 / 50** positive and negative synthetic scenarios PASS; **23 / 23** unittest methods PASS; exit code **0**.
- Separate CLI smoke: a valid DRAFT tender exits **0**; BLOCKED tender, NEEDS_HUMAN_REVIEW tender, and tender with `submit_bid: true` each exit **1**.
- Offline report SHA-256: `16f1283e70d3afe1984e28d77d738aa52d47a5bf3c793c0a1661d2c8995887fc`.
- Report generated at: `2026-11-16T02:45:26.249673+00:00` (November 15 in Vancouver).

## Published source identity

The following Git blob SHA-1 hashes were verified against the published feature branch; the same hashes were produced locally before running the suite.

| Path | Exact Git blob SHA-1 |
| --- | --- |
| `agent-kit/tools/verify.py` | `dba2b7ca9e55335fa2d0468c13996a97953d6ca7` |
| `agent-kit/tools/run_local.py` | `d79f0d7fe88d53f4a7d9f235ea7485d3ca7660b7` |
| `agent-kit/tests/test_verify.py` | `f0eae9a67625858a3deaa941871e5f99da07751a` |
| `agent-kit/tests/test_run_local.py` | `8b52188bbf258119a377a184572ae7dc1d19844a` |
| `agent-kit/fixtures/synthetic_cases.json` | `d99bd144cb9340e4311a8d740349c318a3eed3cd` |

## Scope restrictions

This is **not** a verified Git clone (the environment blocks direct github.com resolution), but the manually reconstituted five-file test source was byte-identical to the GitHub blobs listed above. This does **not** verify the whole application, third-party integrations, native GUI automation, the Windows `.cmd`/`.bat` launchers, the correctness of document sources, real measurements, or human acceptance.

No GitHub Actions workflow was created or run for this test, no new PR opened, and no production or tender approvals were issued.

## Next gate

1. On Windows: run `agent-kit\\RUN_CHECKS_WINDOWS.bat` from a controlled checkout, retain the external JSON report.
2. Before expanding to tender-finder or native civil apps: run repository-specific deterministic regressions and separately verify drawing revision, actual scale/units, tool read-back, and estimator approval.
3. Human-review any integration or merge. Do not open a PR merely to trigger hosted CI.
