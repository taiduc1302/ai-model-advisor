from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from tools.ai_model_advisor.feedback import FeedbackStore
from tools.ai_model_advisor.models import ModelProfile, Recommendation, WorkloadProfile
from tools.ai_model_advisor.recommend import RecommendationEngine
from tools.ai_model_advisor.registry import ModelRegistry


class Advisor:
    """Stable standalone facade over the routing engine."""

    def __init__(
        self,
        registry: str | Path | None = None,
        feedback: str | Path | FeedbackStore | None = None,
    ) -> None:
        self.registry = ModelRegistry(registry)
        self.feedback = (
            feedback
            if isinstance(feedback, FeedbackStore)
            else FeedbackStore.load(feedback)
        )
        self.engine = RecommendationEngine(self.registry, self.feedback)

    @property
    def registry_as_of(self) -> str:
        return self.registry.as_of

    def models(
        self,
        providers: Iterable[str] | None = None,
        *,
        include_limited: bool = False,
    ) -> tuple[ModelProfile, ...]:
        return self.registry.candidates(
            providers=providers,
            include_limited=include_limited,
        )

    def recommend(
        self,
        workload: WorkloadProfile,
        *,
        providers: Iterable[str] | None = None,
        include_limited: bool = False,
        top_n: int = 3,
    ) -> list[Recommendation]:
        if top_n < 1:
            raise ValueError("top_n must be >= 1")
        return self.engine.recommend(
            workload,
            providers=providers,
            include_limited=include_limited,
            top_n=top_n,
        )
