# Controlled Experiment Protocol v0.13

Use an **offline, review-only** plan before spending money on model benchmarks.

1. Create a spec with `experiment_id`, fixed `seed`, `dataset_id`, `environment_id`, `evaluator_id`, and the list of training task IDs.
2. Define A/B configurations (provider, model ID, reasoning effort, execution mode) and held-out tasks with category and SHA-256 of exact prompt text.
3. Generate a reproducible plan with counterbalanced A/B, B/A order. Its hash and run IDs bind each execution to the frozen spec.
4. Execute **both** configurations under the declared conditions, using your separate benchmark runner. The protocol itself never calls providers.
5. Record each result as one JSONL record with the scheduled run fields, `outcome` (success/partial/failure), and optional real `cost_usd`, `latency_seconds`, `retries`, token counts.
6. Evaluate. Altered metadata, unscheduled runs, duplicate results and training/holdout overlap fail closed. Missing pairs/metrics are not invented.

```bash
python -m ai_model_advisor.experiment_protocol plan --spec example.json --output plan.json
python -m ai_model_advisor.experiment_protocol evaluate --plan plan.json --observations results.jsonl --output report.json
```

The evaluator checks **declared** environment/prompt/evaluator identity; it cannot verify that the operator truly used them. The seed fixes task ordering and alternates first arm; this is counterbalancing, not proof of random assignment or experimental causality. `review_ready` is **not** significance, proof of superiority, or permission for routing changes. `safe_to_apply` remains false.
