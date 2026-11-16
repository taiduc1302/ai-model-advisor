# Offline validation evidence — strict metadata hardening (2026-11-15)

**Outcome:** SYNTHETIC_TESTED for this metadata verifier; native/Windows/real-world acceptance is **NOT RUN**.

## Purpose

Address a discovered bypass: the previous validation permitted unknown fields such as `submit_bid: true` and `approve_price: true`. A strict allowlist now rejects unrecognized metadata keys and treats missing explicit side-effect-denial fields as blocking errors.

## Local verification

- Platform: isolated Linux container; Python **3.13.5**; standard library only.
- Runner: `python tools/run_local.py --json-report <local output outside repository>`.
- Observed local execution: **48 / 48** synthetic cases PASS, **22 / 22** unit tests PASS, runner exit **0**.
- New negative cases: unknown tender submission field, unknown pricing approval field, unknown takeoff verification claim, unknown email-send field; missing explicit `final_submit: false`, `agent_signed: false`, `production_import: false`, and `price_approved_by_agent: false`.
- Existing negative cases retained: 701 addenda conflicts, unknown/mismatched scale, invalid units, failed read-back, duplicate markups and idempotency keys, malformed input, unauthorized side effects.

## Published Git blob identity checks

The following **published feature-branch files** match the exact Git blob SHA of locally exercised test source. GitHub contents API writes returned the same blob IDs as observed locally:

| Path | Git blob SHA |
| --- | --- |
| `agent-kit/tools/verify.py` | `3d482756cda318225eaed3bc4c497403ad845ed3` |
| `agent-kit/tests/test_verify.py` | `915b6d03076bb4818e68750eb6c5b2776337f79c` |
| `agent-kit/fixtures/synthetic_cases.json` | `f277823611c6ba8e2c644645265453cc0a8f7760` |
| `agent-kit/tools/run_local.py` | `d79f0d7fe88d53f4a7d9f235ea7485d3ca7660b7` |
| `agent-kit/tests/test_run_local.py` | `8b52188bbf258119a377a184572ae7dc1d19844a` |

**Interpretation:** this confirms identity of the exercised core source and fixture bytes, not a successful full GitHub checkout, Windows batch launch, entire Advisor application test suite, or native civil workflow.

## Remaining gates

1. Run `RUN_CHECKS_WINDOWS.bat` on Windows and preserve an external JSON log.
2. Validate any real Bluebeam, AGTEK, HeavyBid, addenda and source provenance through native read-back on controlled copies with estimator review.
3. Review all `agent-kit/` files plus root `AGENTS.md` and `CLAUDE.md` before merging into `main`.
4. Keep feature-branch testing local. The application repo still contains GitHub Actions workflows on `main`; avoid opening a PR just to run tests.

No actual tender/quantity/pricing approval or production import was performed or authorized.
