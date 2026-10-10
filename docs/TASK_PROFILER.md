# Explainable task profiler v0.9

The task profiler maps natural-language task descriptions into six 1-5 dimensions: coding, reasoning, agentic execution, ambiguity, breadth, and parallelism. It uses weighted, bounded keyword/category signals rather than remote LLM inference.

- A tiny one-file change should not be scored like a repository-wide investigation.
- Explicit negations such as "do not research" suppress nearby matching research signals.
- Multi-step execution contributes to agentic demand.
- The workload JSON now includes category_signals and dimension_signals, allowing each score to be reviewed.

The rules remain heuristics rather than calibrated predictions, and they must be evaluated against real task outcomes. Personal evidence thresholds are unchanged.
