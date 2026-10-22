# Benchmark Results & Decision Quality (v0.16)

This is an **offline, review-only** analysis of real paired observations from a frozen v0.13 plan and the optional v0.14 runner. It never executes providers, fabricates missing trials, or modifies routing.

Run:

```bash
python -m ai_model_advisor.benchmark_analysis \
  --plan plan.json --observations observations.jsonl \
  --output analysis.json
```

The report separates strict pass rate (success only) from graded quality (success=1, partial=0.5, failure=0); it reports matched-task coverage, per-category results, and Wilson score intervals for descriptive observed pass rates.

A deterministic paired bootstrap gives an *exploratory* interval for mean quality difference (B minus A), using observed matched tasks only. This interval is **not** a calibrated causal confidence bound or a significance test. The default directional threshold is 20 matched tasks and can only be raised, not lowered. Sparse, incomplete or uncertain evidence remains exploratory.

Verified billed cost and registry-estimated cost are reported separately. Paired cost, latency and retries include only tasks with measurements on both arms; missing values are never imputed.

The comparison scope identifies whether only `effort`, only `model_id`, only `execution_mode`, or multiple configuration fields changed. Simultaneous changes **cannot** be attributed to a single factor.

Possible evidence statuses: `insufficient_pairs`, `exploratory_small_sample`, `review_inconclusive`, `directional_signal_manual_review`. No status automatically declares a winner; `automatic_winner` is always null and `safe_to_apply` always false. Manual review must verify task equivalence, evaluator reliability and possible overfitting. Public synthetic benchmarks are not blind real-world evaluations.
