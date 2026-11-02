# Local outcome feedback (v0.18)

After generating a recommendation, the UI provides an optional **How did it work?** panel. Choose which offered configuration you actually used, Success / Partial / Failure, and optionally the observed duration in seconds and verified billed cost in USD.

Feedback is written **only upon explicit submission** to a local JSONL file (default `~/.ai-model-advisor/feedback.jsonl`). No task description is saved. The server issues an opaque, short-lived decision token and binds it to its own recommended configurations so a browser cannot substitute arbitrary models. A token can be used once; a server restart invalidates unused tokens.

Run with a custom file:

```bash
ai-model-advisor-web --feedback ./local-feedback.jsonl
```

A saved outcome becomes available to the routing engine in the current process. Its conservative evidence thresholds remain unchanged; one successful result should not automatically change routing.

**Limitations:** This is self-reported observational feedback, not a verified benchmark; the UI does not execute the recommended model. The local server is unauthenticated and must never be exposed publicly. The UI currently has no persistent task history or ability to retract saved outcomes. Do not enter personally identifying information in task descriptions; the server does not persist them but browser extensions or system software may have separate access.
