# Synthetic Benchmark Suite v0.15

This public suite contains **20 synthetic deterministic tasks** across arithmetic,
code comprehension, structured data and text extraction: 4 training examples
and 16 holdout examples. All oracles expect exact JSON structural equality.

**These are public, non-blind fixture tasks, not evidence of production model
superiority.** Providers may have seen analogous tasks. The suite is suitable
for integration checks and controlled experiments, but strong performance
claims require independently sourced private tasks with verified labels.

## Validate and build (offline, free)

```bash
python -m ai_model_advisor.benchmark_suite validate
python -m ai_model_advisor.benchmark_suite build \
  --experiment-id synthetic-effort-001 \
  --arm-a openai gpt-6-luna low single \
  --arm-b openai gpt-6-luna medium single \
  --output-dir .local-bench/synthetic-effort-001
```

The builder emits manifest.json, spec.json, plan.json, tasks.json and oracle.json.
It checks unique prompts/IDs, per-category train/holdout coverage, model support,
SHA-256 prompt identity and the v0.13 experimental plan format. It refuses to
overwrite an existing bundle.

By default it does **not** make API calls. Review each plan and run ID, then
use the opt-in v0.14 benchmark runner if paid execution is desired. Results
can be reviewed through the existing controlled experiment evaluator.

## Measurement limitations

- Keep the four training items out of held-out outcome comparisons.
- Task-specific public answers are deliberately easy to judge; they do not
  measure autonomous software engineering or long-horizon agent reliability.
- Compare identical tasks and conditions across model, effort and execution
  mode; the direct provider runner currently supports **single** mode only.
- Do not claim that a pass rate is calibrated general model accuracy.
- All real usage, costs and latency must come from provider executions.
- Changing the public dataset changes its content hash and dataset_id.
