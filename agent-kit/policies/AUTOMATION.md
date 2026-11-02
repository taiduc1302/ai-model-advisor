# Automation — safe external behavior

Default mode is **offline and dry run**. Each agent task declares authorized read/write scope, target environment, owner, maximum retries, maximum estimated spend and expected audit evidence.

- Any retryable operation must have a stable idempotency key. Check existing state before retry; never duplicate markups, bid submissions, payments, emails, account modifications or job entries.
- Explicit authorization is required for network, secrets, paid models, production filesystem writes, GUI clicks that modify state and any third-party API mutation.
- Never bypass authentication, CAPTCHA, WAF, access rules, approval UI or paid limits.
- Keep credentials in approved runtime secret storage, never in source code, fixtures, screenshots, logs or provider prompts.
- A rate limit, timeout, incomplete extraction, lost tool connection, ambiguous output or mismatch must fail visibly; log `BLOCKED` or `NEEDS_HUMAN_REVIEW` rather than substituting guessed values.
- Record tool and connector versions, input digest/reference, dry-run result, actual observed read-back and side effects.
- Evaluation cannot use the same model's unchecked opinion as the only criterion for quantitative correctness.
- Stop and request human confirmation before external sends, irreversible actions, cost commitments and production imports. An AI agent cannot type/forge that confirmation.
- Use the smallest model/tool budget sufficient for the task and prefer reuse of deterministic checks. Never infer a model's current pricing from stale examples.

**Pilot policy:** zero real network calls, zero paid calls, zero external writes; only fictional local metadata cases. Production access is not covered by pilot approval.
