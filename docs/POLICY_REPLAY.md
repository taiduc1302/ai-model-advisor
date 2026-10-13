# Held-out policy comparison v0.12

Run:

```bash
python -m ai_model_advisor.policy_replay --observations outcomes.jsonl --baseline policy-v1 --candidate policy-v2 --train-task-ids training-ids.json
```

The observation file uses one JSON object per line with `task_id`, `policy_id`, `category`, `outcome` (success/partial/failure), and optionally `cost_usd`, `latency_seconds`, `retries`.

A task is compared only when both policies have exactly one recorded execution on that task in the same category. Duplicated, unmatched or mismatched task IDs are excluded. Any overlap with the supplied training-task IDs fails closed to prevent train/holdout leakage.

At least five matched tasks produce a review-ready report. **This does not imply statistical significance, causal attribution, or permission to change routing.** Real execution conditions must be reviewed. No synthetic counterfactual successes, costs or timings are invented. No provider calls or routing policy mutations occur.
