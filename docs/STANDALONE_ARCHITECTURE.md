# Standalone architecture

## Product goal

AI Model Advisor should answer one operational question well:

> For this real task and this user's observed history, which model, reasoning
> effort, and execution mode should be used now?

The answer should be current, inspectable, conservative about sparse evidence,
and able to improve from repeated outcomes.

## Layers

### Public API

`ai_model_advisor` is the stable user-facing package.

It exposes a small `Advisor` facade plus data models needed to describe a
workload. Consumers should not need to know the historical Hive-era package
layout.

### Core engine

The current proven implementation remains under
`tools.ai_model_advisor` during the staged migration. Core responsibilities
include model/source provenance, workload profiling, routing, feedback,
experiments, empirical leaderboards, and review-only promotion logic.

Importing the core package must not import Hive modules.

### Integrations

Optional backends live under `ai_model_advisor.integrations`.

Hive is one backend, not the owner of the Advisor. Future provider or execution
backends should follow the same boundary.

## Compatibility strategy

v0.2 introduces the stable public package without rewriting all proven modules
at once.

The historical `tools.ai_model_advisor` package remains importable. Hive
symbols exported from its root are resolved lazily so existing callers keep
working while normal core imports stay Hive-free.

A later refactor can physically move implementation modules into `src/`
behind the stable public API with substantially lower risk.

## Evidence hierarchy

Routing decisions should prefer, in order:

1. current official provider/model facts;
2. exact same-category, same-configuration outcome evidence;
3. paired same-task latency/cost evidence;
4. discounted cross-configuration evidence;
5. static capability heuristics.

Sparse or mismatched evidence must not silently override stronger priors.
