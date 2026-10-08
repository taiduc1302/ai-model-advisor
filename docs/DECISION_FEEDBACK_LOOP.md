# Decision feedback loop

The standalone CLI supports a complete conservative learning loop:

1. run `ai-model-advisor decide --json --output decision.json`;
2. execute the Primary configuration;
3. record the actual result with `ai-model-advisor record-decision`;
4. reuse the same feedback JSONL on later decisions.

## Why record from the saved decision

Copying model IDs, reasoning effort, and execution mode by hand is error-prone.
The saved decision is the audit record of what the Advisor actually recommended.

`record-decision` therefore reads the Primary configuration directly from the
decision JSON and writes a normal `UsageRecord` to the selected feedback store.

## What still requires explicit input

The user or execution system must supply the observed result:

- success / partial / failure;
- retries;
- latency;
- cost;
- token counts;
- stable task ID when paired comparison is desired.

The command never fabricates these values.

## Evidence thresholds remain unchanged

Recording a result does not mean the next decision automatically changes.
Existing sample thresholds, task-category isolation, and paired efficiency
requirements still apply.
