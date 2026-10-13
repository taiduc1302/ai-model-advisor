# Matched-task empirical evaluation (v0.11)

Run `python -m ai_model_advisor.paired_evaluation --feedback results.jsonl --category debugging --left openai model-a high single --right anthropic model-b medium single`.

Only matched task IDs with exactly one observation on each side, in the same category, are counted. Duplicate attempts and unmatched IDs are excluded, not averaged or mistaken for independent samples.

Reported metrics include quality (success=1, partial=0.5, failure=0), retries, and paired cost/latency deltas when both runs provide those values.

At least three matched task IDs produce `review_ready`, **not** a winner or statistical proof. Prompt and environment equivalence cannot be verified from feedback records, so a human must review experiment controls. Routing changes remain disabled (`safe_to_apply=false`). No real provider calls are made.
