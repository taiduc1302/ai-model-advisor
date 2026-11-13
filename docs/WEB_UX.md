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


## Decision comparison pilot (2026-11-12)

The results view now includes a keyboard-scrollable, semantically labeled table that compares **primary**, **lower-priced qualified option**, and **escalation** from the actual `RoutingDecision`. Missing paths are clearly marked `Not available`, never silently filled. Cells are constructed with `textContent`; data stays local and the server/API/CSP are unchanged.

This adapts the accessible data-table pattern from [design-reference-library](https://github.com/taiduc1302/design-reference-library/tree/2539c661ac0b21d10cffc34ffe719998384bf49d/components) instead of importing its unrelated light-theme CSS or creating a runtime network dependency. It retains the Advisor's dark palette and local-only architecture. The primary suggestion is explicitly *heuristic*, not a calibrated success probability.

**Review gate:** PR must pass the existing Python suite, browser visual checks at 320/390/768/1440 px (including the results and API failure views), keyboard/screen-reader inspection, and backend safety tests before merging. In this execution, full packaged HTTP/CSP visual QA is not claimed when localhost navigation is policy-blocked.
