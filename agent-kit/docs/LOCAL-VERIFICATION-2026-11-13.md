# Local verification — Civil AI Agent Kit (2026-11-13)

Status: **local synthetic checks PASS; Windows, GitHub checkout, native integrations and real-tender checks NOT RUN.**

## Execution record

- Environment: isolated container, Linux, Python 3.13.5, standard library only.
- Network/provider calls: none. GitHub Actions: none.
- Inputs: the new Agent Kit verifier, runner, synthetic fixture matrix and unit tests, reproduced locally before pushing their equivalent source to a feature branch.
- Command: `python tools/run_local.py --json-report /mnt/data/agentkit-verify-report.json`
- Observed: **40/40** synthetic cases PASS; **20/20** unittest methods PASS; runner **PASS**, exit 0.
- Positive controls: valid synthetic takeoff, HeavyBid mapping, tender, automation and distinct IDs.
- Negative controls: stale revision, invalid/unverified scale, invalid unit, nonfinite/negative quantities, duplicated markup IDs, duplicate idempotency keys, inaccurate addenda conflict counts (including 701), unauthorized production import/signature/approval, invalid booleans and malformed JSON.
- Runner check: refuses to save a generated JSON report inside the repository; records SHA-256 of local source/fixture files.

## Boundaries

- Metadata is asserted, not independently authenticated; e.g. `scale_verified: true` is not evidence of measurement precision.
- Native Bluebeam Revu, AGTEK Gradework and HCSS HeavyBid were **not opened or tested**.
- The Windows `RUN_CHECKS_WINDOWS.cmd` launcher was added but **not run on Windows**.
- This run did **not** clone or execute the GitHub-hosted branch verbatim; the local environment could not resolve `github.com`. Review the uploaded diff and run the local command from a fresh Git checkout before production use.
- CI for the whole `ai-model-advisor` application is outside this Agent Kit pilot. Existing GitHub Actions workflows remain on `main`; no PR was opened for this pilot.

## Safe next gate

1. Compare final feature branch against current `main`: no overlapping non-kit files, no lost changes, and no GitHub Actions workflow introduced by Agent Kit.
2. Run the launcher on Windows 11 with installed Python, retain the JSON report locally (not in public Git).
3. Have a human inspect any native system adapters and verify actual scale, units, revisions and read-back independently before allowing real estimating work.

No estimate, tender, pricing decision, codebook mapping, or production import was approved by this run.
