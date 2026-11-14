# Civil AI Agent Kit (v0.1 — isolated pilot)

A **portable, original, offline-first** collection of agent instructions and deterministic safety checks for software development, automations, and civil estimating. This pack is maintained independently of ECC. No ECC runtime, hooks, plugins, or MCP servers are required.

**Status:** synthetic policy checks only. NOT validated against live tender packages or native Bluebeam Revu, AGTEK Gradework, or HCSS HeavyBid. All software and estimating decisions remain with a human.

## What is included

| Path | Purpose |
| --- | --- |
| `templates/AGENTS.md` | Agent-neutral repo guidance (Codex and other coding agents) |
| `templates/CLAUDE.md` | Claude-specific entrypoint that defers to the same guidance |
| `templates/.claude/settings.json` | No auto-allow, no hooks, no MCP integration |
| `templates/.codex/config.toml` | On-request approval, workspace sandbox, network off |
| `policies/CODING.md` | Branch, review, and regression workflow |
| `policies/AUTOMATION.md` | External side effects, idempotency, and cost controls |
| `policies/CIVIL-ESTIMATING.md` | Evidence, units, revisions, native-tool read-back and estimator sign-off |
| `fixtures/synthetic_cases.json` | Positive and negative fictional input records |
| `tools/verify.py` | Standard-library-only offline preflight and metadata gate |
| `RUN_CHECKS_WINDOWS.cmd` | Double-clickable Windows Command Prompt launcher |
| `tools/run_local.py` | Local two-stage runner with optional JSON evidence report; no GitHub Actions |
| `tests/test_verify.py` | Regression and negative-control tests |
| `tests/test_run_local.py` | Runner path-safety and manifest checks |

## Verify locally (Python 3.11+, no pip installs, no GitHub Actions)

For Windows, double-click `RUN_CHECKS_WINDOWS.cmd` (or run it from Command Prompt). The launcher uses `py -3` when available, or falls back to `python`. **Windows GUI execution is not yet verified.**

From the `agent-kit` directory in PowerShell, Command Prompt, or a terminal:

```shell
python tools/run_local.py
```

This executes BOTH the **40** fictional positive/negative cases and **20** deterministic `unittest` methods, prints observed exit states and returns nonzero when a check fails. Each generated report also includes SHA-256 hashes of the validation source/fixtures to identify exactly which bytes were tested. No GitHub Actions are required. Optional report (choose a local directory outside this kit):

```powershell
python tools/run_local.py --json-report "$env:TEMP\\civil-agent-kit-report.json"
```

Direct commands remain available if you want to investigate failures:

```shell
python tools/verify.py --self-test
python -m unittest discover -s tests -v
```

The report is not uploaded; it records actual observed exit codes, not estimates or native-system validation. The runner refuses to save reports inside the repository. No dependency installation, secrets or external provider call is required. Avoid committing locally generated reports.

### GitHub usage and quota

The kit's former `.github/workflows/agent-kit.yml` has been **removed** from this feature branch. Draft PR #18 was closed without merging because the **existing repository-wide** `.github/workflows/ci.yml` runs automatically on every PR (and on `main` pushes). Closing the PR avoids new PR-triggered runs for this branch; it does not disable other repositories' Actions or cancel previously started runs. Keep this kit in a feature branch until you are ready for a manual review. If you want **zero GitHub Actions across the whole project**, review and separately disable/remove the repository's existing CI workflow before opening any new PR.


For a machine-generated **metadata record**, run:

```shell
python tools/verify.py --file path/to/records.json
```

Input is JSON with a `records` array of `{"kind":"takeoff|heavybid|tender|automation","record":{...}}` objects. The validator exits nonzero if any record is blocked. It checks *declared metadata*, not actual file authenticity, geometric correctness, or system authorization. A malicious or inaccurate declaration is outside the guarantee.

## Install into a separate repository (manual, review-first)

1. Copy the **whole** `agent-kit/` directory; do not install anything globally.
2. Read existing root `AGENTS.md`, `CLAUDE.md`, `.codex/`, `.claude/`, CI and business approval rules **first**. Merge instructions instead of overwriting them. More restrictive project-specific requirements take precedence.
3. If absent, adapt `templates/AGENTS.md` to the project root. For Claude, adapt `templates/CLAUDE.md` and copy `templates/.claude/settings.json` only after checking current version compatibility; for Codex, similarly review the example `templates/.codex/config.toml`. These are **templates**, not executable installs.
4. Keep `agent-kit/policies/` with the repository; policies are referenced by the templates. Re-run offline tests whenever configuration or gates change.
5. Enable external tools one at a time only after explicit human review and sandboxed tests. Never enable automatic approval of pricing, estimates, bidding, final submits, write imports or releases.

## Evidence required at each stage

`PROPOSED` -> `SYNTHETIC_TESTED` -> `SANDBOX_NATIVE_TESTED` -> `HUMAN_ACCEPTED`. Passing this pack's local tests only qualifies as **SYNTHETIC_TESTED**, and only for the tested metadata examples. It cannot advance an actual estimate, tool integration, or tender to acceptance.

## Operating costs and confidentiality

Default: **zero paid model API calls**, zero network access for tests, zero global hooks, zero autonomous merges. Public repositories may contain only synthetic or otherwise explicitly releasable material; no real drawings, bids, company codebooks, credentials, or customer details.

## Why hosted under ai-model-advisor?

This is a self-contained first pilot in an owned project that already has Python test infrastructure. It can be extracted later to a dedicated `civil-ai-agent-kit` repository without depending on the advisor's package. It does not change routing, pricing, model providers, or runtime code.

## Verification and limits (2026-11-13 local baseline)

- 40/40 synthetic scenarios and 20/20 unit-test methods **PASS** in an isolated local Python **3.13.5** run (Linux), no dependencies or network access. See `docs/LOCAL-VERIFICATION-2026-11-13.md` for exact scope and caveats.
- `.cmd` is a Windows launcher template; not yet executed in real Windows/PowerShell. No native Bluebeam, AGTEK, or HeavyBid tests, real tenders, or production permissions were exercised.
- These metadata gates check **declared** values only. A claim such as `scale_verified: true` is not independent measurement evidence. They are safety preflight checks, not a substitute for drawings, source validation or estimator sign-off.
- Do **not** open a PR just to run this kit: the repository-wide CI still runs on `pull_request` and can consume Actions minutes. Feature-branch pushes alone do not match that workflow's trigger.
