# Personal feedback API

AI Model Advisor can learn from real task outcomes without Hive.

## Recording an outcome

Use `Advisor.record_outcome(...)` after a task finishes. When the Advisor was
constructed with a feedback JSONL path, the record is appended to disk and the
in-memory routing engine is refreshed immediately.

The API can infer the provider for a known registry model and can infer a task
category from supplied task text. Explicit values remain available when the
model or task taxonomy is external.

## Evidence safety

Recording one result does not immediately change routing.

The existing evidence thresholds still apply:

- exact model + effort + execution evidence needs repeated observations;
- cross-configuration evidence is discounted and needs a larger sample;
- paired latency/cost evidence requires comparable task IDs;
- category-tagged evidence does not leak into unrelated categories.

This keeps personalization useful without turning a single good or bad run into
a permanent routing rule.
