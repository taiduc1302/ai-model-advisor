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
| `tests/test_verify.py` | Regression and negative-control tests |

## Verify first (Python 3.11+, no pip installs)

From the `agent-kit` directory:

```shell
python tools/verify.py --self-test
python -m unittest discover -s tests -v
```

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
