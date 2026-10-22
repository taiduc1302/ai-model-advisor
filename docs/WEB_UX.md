# Local Web UX v0.17

## Start

```bash
pip install -e .
ai-model-advisor-web
```

Open `http://127.0.0.1:8765`. Optional: `ai-model-advisor-web --port 9000`.

The home screen offers a straightforward flow: **describe your task → choose
Balanced, Quality, Cost or Speed → choose provider → see Primary, a qualifying
cheaper fallback and escalation with explanations**. You can copy the result.

The UI is responsive, keyboard-accessible, and uses packaged HTML/CSS/JS
without npm, React runtime, analytics, cookies, external fonts or CDNs.
It calls the existing `Advisor.decide_task` Python API, not a second routing
engine. No task descriptions are saved; no provider API calls are performed.

The server binds to loopback only and rejects non-local Host headers and foreign
Origin values. Requests have content-length and task-length limits. Responses
use restrictive CSP and no-store headers. It is intentionally unauthenticated
and **must not be deployed publicly or reverse-proxied to a public hostname**.

### API

`POST /api/decide` with JSON:

```json
{"task": "Audit my repository and fix failing tests.", "provider": "all", "priority": "balanced"}
```

Returns the complete `RoutingDecision.as_dict()` under `decision`, along
with `provider_calls:false`. `GET /api/meta` reports version and catalog date.

### Scope

v0.17 is an MVP, not a full analytics dashboard. History, durable feedback,
model comparison, experiment lab and user accounts are later enhancements.
The confidence display uses the underlying **heuristic** confidence and should
not be read as statistically calibrated probability of success.
