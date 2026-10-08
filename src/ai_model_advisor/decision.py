from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from tools.ai_model_advisor.feedback import FeedbackStore
from tools.ai_model_advisor.models import ModelProfile, Recommendation, WorkloadProfile


def _model_key(recommendation: Recommendation) -> tuple[str, str]:
    return recommendation.provider, recommendation.model_id


def _price_proxy(model: ModelProfile) -> float:
    """Simple list-price proxy used only for relative fallback/escalation checks."""
    return float(model.input_usd_per_mtok + model.output_usd_per_mtok)


def _capability_index(model: ModelProfile) -> float:
    keys = ("reasoning", "coding", "agentic", "long_horizon", "ambiguity")
    values = [float(model.capabilities.get(key, 3.0)) for key in keys]
    return sum(values) / len(values)


def _primary_category(profile: WorkloadProfile) -> str | None:
    if not profile.categories:
        return None
    return max(profile.categories.items(), key=lambda item: (item[1], item[0]))[0]


@dataclass(frozen=True)
class RoutingDecision:
    task: str
    profile: WorkloadProfile
    primary: Recommendation
    cheaper_fallback: Recommendation | None
    escalation: Recommendation | None
    escalation_triggers: tuple[str, ...]
    personal_evidence: tuple[str, ...]
    decision_notes: tuple[str, ...]
    registry_as_of: str

    def as_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "profile": self.profile.as_dict(),
            "primary": self.primary.as_dict(),
            "cheaper_fallback": (
                self.cheaper_fallback.as_dict() if self.cheaper_fallback else None
            ),
            "escalation": self.escalation.as_dict() if self.escalation else None,
            "escalation_triggers": list(self.escalation_triggers),
            "personal_evidence": list(self.personal_evidence),
            "decision_notes": list(self.decision_notes),
            "registry_as_of": self.registry_as_of,
        }


def build_routing_decision(
    *,
    task: str,
    profile: WorkloadProfile,
    recommendations: list[Recommendation],
    models: tuple[ModelProfile, ...],
    feedback: FeedbackStore,
    registry_as_of: str,
    fallback_score_gap: float = 6.0,
) -> RoutingDecision:
    if not recommendations:
        raise ValueError("no current model candidates are available")
    if fallback_score_gap < 0:
        raise ValueError("fallback_score_gap must be >= 0")

    model_by_key = {(model.provider, model.model_id): model for model in models}
    primary = recommendations[0]
    primary_model = model_by_key[_model_key(primary)]
    primary_price = _price_proxy(primary_model)

    cheaper_candidates: list[tuple[Recommendation, float]] = []
    for candidate in recommendations[1:]:
        model = model_by_key.get(_model_key(candidate))
        if model is None:
            continue
        price = _price_proxy(model)
        if price >= primary_price:
            continue
        if candidate.score < primary.score - fallback_score_gap:
            continue
        cheaper_candidates.append((candidate, price))

    cheaper_fallback = None
    if cheaper_candidates:
        cheaper_fallback = max(
            cheaper_candidates,
            key=lambda item: (item[0].score, -item[1]),
        )[0]

    primary_capability = _capability_index(primary_model)
    escalation_candidates: list[tuple[Recommendation, float, float]] = []
    for candidate in recommendations[1:]:
        model = model_by_key.get(_model_key(candidate))
        if model is None:
            continue
        capability = _capability_index(model)
        price = _price_proxy(model)
        if capability < primary_capability + 0.10:
            continue
        if price < primary_price:
            continue
        escalation_candidates.append((candidate, capability, price))

    escalation = None
    if escalation_candidates:
        escalation = max(
            escalation_candidates,
            key=lambda item: (item[1], item[0].score, -item[2]),
        )[0]

    triggers: list[str] = []
    if escalation is not None:
        triggers.append("Escalate after one failed or partial primary attempt.")
        if profile.ambiguity >= 4.0:
            triggers.append(
                "Escalate if requirements or root cause remain materially ambiguous after the first pass."
            )
        if profile.agentic >= 4.0 or profile.breadth >= 4.0:
            triggers.append(
                "Escalate if the task expands into a longer-horizon or broader multi-component investigation."
            )
        if primary.confidence < 0.72:
            triggers.append(
                "Escalate when the primary recommendation remains low-confidence after new evidence arrives."
            )
    else:
        effort_order = ("none", "low", "medium", "high", "xhigh", "max")
        available = [item for item in effort_order if item in primary_model.efforts]
        if primary.effort in available:
            index = available.index(primary.effort)
            if index + 1 < len(available):
                triggers.append(
                    f"No stronger current model qualified; retry the primary at {available[index + 1]} effort after a failed or partial attempt."
                )
        if not triggers:
            triggers.append(
                "No stronger current model qualified; use manual review after a failed or partial primary attempt."
            )

    category = _primary_category(profile)
    quality_samples, quality_adjustment = feedback.summary(
        primary.model_id,
        primary.effort,
        primary.execution_mode,
        category,
    )
    quality_scope = feedback.evidence_scope(
        primary.model_id,
        primary.effort,
        primary.execution_mode,
        category,
    )
    efficiency_samples, efficiency_adjustment = feedback.efficiency_summary(
        primary.model_id,
        primary.effort,
        primary.execution_mode,
        category,
        profile.latency_sensitivity,
        profile.cost_sensitivity,
    )

    evidence: list[str] = []
    if quality_adjustment:
        evidence.append(
            f"Outcome evidence affected the primary score: {quality_samples} {quality_scope} observations, {quality_adjustment:+.3f} adjustment."
        )
    elif quality_samples:
        evidence.append(
            f"{quality_samples} outcome observations exist for the primary configuration, but they are below the routing threshold and did not change the score."
        )

    if efficiency_adjustment:
        evidence.append(
            f"Paired same-task efficiency evidence affected the primary score: {efficiency_samples} comparable tasks, {efficiency_adjustment:+.3f} adjustment."
        )
    elif efficiency_samples:
        evidence.append(
            f"{efficiency_samples} paired same-task efficiency observations exist, but they are below the routing threshold and did not change the score."
        )

    if not evidence:
        evidence.append(
            "No qualifying personal evidence affected the primary score; this decision is currently driven by the workload profile and registry priors."
        )

    notes: list[str] = []
    if cheaper_fallback is not None:
        notes.append(
            f"Cheaper fallback is {primary.score - cheaper_fallback.score:.2f} score points behind the primary and has a lower provider list-price proxy."
        )
    else:
        notes.append(
            f"No cheaper current candidate is within {fallback_score_gap:.2f} score points of the primary."
        )

    if escalation is not None:
        escalation_model = model_by_key[_model_key(escalation)]
        notes.append(
            f"Escalation moves from capability index {primary_capability:.2f} to {_capability_index(escalation_model):.2f}."
        )
    else:
        notes.append(
            "The primary already sits at the top of the qualified current capability set for this decision."
        )

    return RoutingDecision(
        task=task,
        profile=profile,
        primary=primary,
        cheaper_fallback=cheaper_fallback,
        escalation=escalation,
        escalation_triggers=tuple(triggers),
        personal_evidence=tuple(evidence),
        decision_notes=tuple(notes),
        registry_as_of=registry_as_of,
    )
