# AI Model Advisor

AI Model Advisor is a standalone, evidence-driven system for choosing and validating AI model configurations for real workloads.

It separates three decisions that are often mixed together:

- model/provider;
- reasoning effort;
- execution/orchestration mode.

The project tracks model capabilities, builds workload-aware recommendations, records outcome/cost/latency feedback, runs controlled experiments, evaluates empirical leaderboards, and prepares review-only promotion/canary/rollback decisions.

## Origin

This repository is extracted from the AI Model Advisor work originally developed inside `taiduc1302/hive`. The last pre-extraction development line reached internal version 0.41.0.

The standalone project restarts release numbering at **0.1.0**; the current standalone package line is **0.3.x**. The old 0.41 number describes the internal Hive-era iteration history, not a public standalone release.

## Architecture boundary

The Advisor core does not own Hive.

Core:
- model registry and source freshness;
- workload profiling and routing;
- feedback and telemetry scoring;
- controlled A/B experiments;
- empirical leaderboard;
- routing proposals;
- promotion/canary/rollback analysis.

Integrations:
- Hive runtime/telemetry adapters;
- direct provider execution adapters;
- future execution backends.

Hive-specific modules are kept as optional integration code. Installing and testing the standalone core does not require Hive.

## Install

```bash
python -m pip install -e .
```

## CLI

```bash
ai-model-advisor --help
```

Python users should prefer the stable public package:

```python
from ai_model_advisor import Advisor, WorkloadProfile

advisor = Advisor(feedback="feedback.jsonl")
recommendations = advisor.recommend_task(
    "Audit this repository, find the root cause of failing tests, and implement the fix.",
    cost_sensitivity=3,
    latency_sensitivity=2,
)
```

Hive is optional and explicit:

```python
from ai_model_advisor.integrations.hive import import_hive_trace
```

The legacy module entrypoint remains available during migration:

```bash
python -m tools.ai_model_advisor.cli --help
```

## Safety model

The Advisor is review-first. Recommendation, preflight, leaderboard, promotion planning and rollback planning do not automatically mutate production routing or Hive configuration. Provider execution must be explicit.

## Migration status

Source snapshot: Hive AI Model Advisor internal v0.41.0.

See `MIGRATION.md` for extraction decisions and remaining cleanup.

## Freshness monitoring

The scheduled **Model Registry Monitor** checks only official provider sources
once per day. It carries a source-signal baseline forward through GitHub Actions
cache, publishes a Markdown/JSON report, and fails only when a newly observed
unregistered model-like signal appears on a source that already has history.
A changed webpage fingerprint alone is not treated as proof that a model changed.


## Personal learning without Hive

The standalone API can record the outcome of real work directly:

```python
advisor = Advisor(feedback="~/.ai-model-advisor/feedback.jsonl")

decision = advisor.recommend_task(
    "Audit this repository and fix the failing CI test.",
)

advisor.record_outcome(
    model_id=decision[0].model_id,
    effort=decision[0].effort,
    execution_mode=decision[0].execution_mode,
    outcome="success",
    task="Audit this repository and fix the failing CI test.",
    task_id="repo-ci-001",
    latency_seconds=42,
    cost_usd=0.17,
)
```

The new observation is immediately available to the same `Advisor` instance.
Exact configuration evidence still has to meet the existing conservative sample
thresholds before it can change routing scores.
