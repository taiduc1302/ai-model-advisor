# Benchmark Runner v0.14

The real-provider runner is **explicitly opt-in** and limited to **one run_id
per invocation**. A preview is offline and is the default.

## Workflow

1. Use v0.13 to generate a frozen \`plan.json\` containing two current OpenAI
   or Anthropic configurations with \`execution_mode=single\`.
2. Make \`tasks.json\` containing exactly one object with \`task_id\` and
   \`prompt\` per scheduled task. The SHA-256 of its exact UTF-8 prompt must
   match the frozen plan.
3. Make \`oracle.json\` containing \`schema_version: 1\`, the plan's
   \`evaluator_id\` and \`checks\`, one per task. A check has \`task_id\`,
   \`expected\` and \`mode\`: \`exact\`, \`strip-exact\`, \`contains\`,
   or \`json-equal\`.
4. Preview a run:

\`\`\`bash
python -m ai_model_advisor.benchmark_runner \
  --plan plan.json --tasks tasks.json --oracle oracle.json \
  --run-id YOUR_RUN_ID --observations observations.jsonl \
  --max-output-tokens 256 --max-cost-usd 0.25
\`\`\`

5. If the preview is acceptable, provide credentials in the environment
   (\`OPENAI_API_KEY\` or \`ANTHROPIC_API_KEY\`) and add **\`--apply\`** to authorize
   one API call with the chosen configuration.
6. Review the resulting ledger with:

\`\`\`bash
python -m ai_model_advisor.experiment_protocol evaluate \
  --plan plan.json --observations observations.jsonl --output report.json
\`\`\`

## Safety and evidence

- \`--max-cost-usd\` is an **estimate-based preflight**, not an enforceable
  provider-side spending limit. It uses registry list prices and a conservative
  input-byte proxy. Actual charges and provider billing can differ. Set
  provider-side usage limits to prevent unexpected expense.
- Output tokens are capped per API request (up to 8,192). No automatic batch
  run, automatic routing promotion or provider calls from CI.
- Before transport, the runner writes an append-only
  \`observations.jsonl.attempts.jsonl\` marker. A connection failure may already
  have incurred charges, so retries are refused until manually reconciled.
  A lock prevents two local writers from processing the same ledger at once.
- Provider errors never become fabricated failed benchmark tasks. A completed
  provider response with verifiable usage is independently checked using the
  deterministic expected-output oracle. The oracle is a limited proxy for
  task correctness, not independent expert judgment.
- Prompts, outputs, API keys, and raw provider bodies are not stored in the
  observation ledger. It stores fixed metadata, tokens, elapsed time,
  output hashes and verdicts. The task and oracle input fixtures may be
  sensitive and should remain private.
- \`estimated_cost_usd\` and \`cost_usd\` are deliberately separate. Real cost
  requires externally verified billing; the former uses registry list prices.
  Paired reports never silently treat an estimate as a bill.
- A successful experiment requires independently established prompt, tools,
  evaluator, and environment equivalence. \`review_ready\` is not a
  statistically established winner or permission to change production routing.

Tests use injected fake transport responses. CI makes no paid API calls.
