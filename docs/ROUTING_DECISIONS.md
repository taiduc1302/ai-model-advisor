# Routing decisions

`Advisor.decide_task(...)` is the preferred high-level decision API.

It returns a structured `RoutingDecision` with:

- **primary** — the best current configuration for the workload;
- **cheaper_fallback** — a genuinely cheaper current model that remains within
  the allowed score gap;
- **escalation** — a higher-capability current model when one qualifies;
- **escalation_triggers** — concrete conditions for moving off the primary;
- **personal_evidence** — an explanation of how stored outcomes affected, or
  did not yet affect, the score;
- **decision_notes** — concise tradeoff information and registry provenance.

## Fallback policy

Fallback is not synonymous with second place.

A candidate must have a lower provider list-price proxy than the primary and
must remain within `fallback_score_gap` score points. The default gap is 6.0.

This deliberately returns no fallback when the only cheaper options would
require too much predicted capability loss.

## Escalation policy

Escalation is also not synonymous with second place.

A candidate must be at least one small capability tier above the primary on the
Advisor's reasoning/coding/agentic/long-horizon/ambiguity composite and must not
be cheaper than the primary.

If no stronger current model qualifies, the decision suggests increasing the
primary model's effort when a higher supported effort exists; otherwise it
falls back to manual review.

## Personal evidence

The decision layer uses the existing conservative feedback rules.

It explicitly distinguishes:

- repeated evidence that changed the primary score;
- paired same-task efficiency evidence that changed the score;
- observations that exist but remain below threshold;
- no qualifying personal evidence yet.

The decision layer does not weaken any feedback threshold.
