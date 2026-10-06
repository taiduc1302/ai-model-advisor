# AI Model Advisor

AI Model Advisor is a standalone, evidence-driven system for choosing and validating AI model configurations for real workloads.

It separates three decisions that are often mixed together:

- model/provider;
- reasoning effort;
- execution/orchestration mode.

The project tracks model capabilities, builds workload-aware recommendations, records outcome/cost/latency feedback, runs controlled experiments, evaluates empirical leaderboards, and prepares review-only promotion/canary/rollback decisions.

## Origin

This repository is extracted from the AI Model Advisor work originally developed inside `taiduc1302/hive`. The last pre-extraction development line reached internal version 0.41.0.

The standalone project restarts release numbering at **0.1.0**; the current standalone package line is **0.2.x**. The old 0.41 number describes the internal Hive-era iteration history, not a public standalone release.

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
recommendations = advisor.recommend(
    WorkloadProfile(
        coding=4.0,
        reasoning=4.5,
        agentic=3.5,
        ambiguity=4.0,
        categories={"coding": 8},
        activity_count=8,
    )
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
