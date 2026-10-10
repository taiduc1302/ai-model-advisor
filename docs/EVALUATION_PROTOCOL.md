# Evaluation protocol (v0.10)

This suite is a reproducible, deterministic **curated expectation check** for task
profiling. It does not compare real provider responses and must not be reported
as model accuracy or win rates.

Run locally:

```bash
python -m ai_model_advisor.evaluation --json-output evaluation-results.json
pytest -q tests/test_task_evaluation.py
```

Cases are stored in `evaluations/task_cases.json`. Each case has a synthetic
task and explicit expected dimension bounds/categories. Every case is checked
individually and failures surface the exact violated constraint.

CI runs this evaluation separately from the existing unit tests. Changes that
break these expectations must update the profiler or justify a reviewed fixture
change. The next evaluation layer should use paired, real, same-task outcomes
with costs, latency and verified success, and should preserve strict separation
from these hand-authored priors.
