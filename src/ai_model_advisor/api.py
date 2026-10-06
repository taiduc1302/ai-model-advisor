from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from tools.ai_model_advisor.activity import ActivityAnalyzer
from tools.ai_model_advisor.feedback import FeedbackStore, UsageRecord
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
        self.feedback_path = (
            Path(feedback)
            if isinstance(feedback, (str, Path))
            else None
        )
        self.feedback = (
            feedback
            if isinstance(feedback, FeedbackStore)
            else FeedbackStore.load(self.feedback_path)
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
        include_previous: bool = False,
    ) -> tuple[ModelProfile, ...]:
        return self.registry.candidates(
            providers=providers,
            include_limited=include_limited,
            include_previous=include_previous,
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


    def profile_task(
        self,
        task: str,
        *,
        latency_sensitivity: float = 3.0,
        cost_sensitivity: float = 3.0,
    ) -> WorkloadProfile:
        if not task or not task.strip():
            raise ValueError("task must not be blank")
        profile = ActivityAnalyzer().from_texts([task])
        profile.latency_sensitivity = max(1.0, min(5.0, float(latency_sensitivity)))
        profile.cost_sensitivity = max(1.0, min(5.0, float(cost_sensitivity)))
        return profile

    def recommend_task(
        self,
        task: str,
        *,
        providers: Iterable[str] | None = None,
        include_limited: bool = False,
        top_n: int = 3,
        latency_sensitivity: float = 3.0,
        cost_sensitivity: float = 3.0,
    ) -> list[Recommendation]:
        profile = self.profile_task(
            task,
            latency_sensitivity=latency_sensitivity,
            cost_sensitivity=cost_sensitivity,
        )
        return self.recommend(
            profile,
            providers=providers,
            include_limited=include_limited,
            top_n=top_n,
        )


    def record_outcome(
        self,
        *,
        model_id: str,
        effort: str,
        execution_mode: str,
        outcome: str,
        provider: str | None = None,
        task: str | None = None,
        task_category: str | None = None,
        task_id: str | None = None,
        retries: int = 0,
        latency_seconds: float | None = None,
        cost_usd: float | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
        note: str = "",
    ) -> UsageRecord:
        matching = [
            model
            for model in self.registry.models
            if model.model_id == model_id
            and (provider is None or model.provider == provider)
        ]
        if provider is None:
            if len(matching) != 1:
                raise ValueError(
                    "provider is required when model_id is unknown or ambiguous"
                )
            provider = matching[0].provider

        if task_category is None and task:
            profile = self.profile_task(task)
            if profile.categories:
                task_category = max(
                    profile.categories.items(),
                    key=lambda item: (item[1], item[0]),
                )[0]

        record = UsageRecord(
            provider=provider,
            model_id=model_id,
            effort=effort,
            execution_mode=execution_mode,
            outcome=outcome,
            retries=retries,
            latency_seconds=latency_seconds,
            cost_usd=cost_usd,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            task_category=task_category,
            task_id=task_id,
            note=note,
        )

        if self.feedback_path is not None:
            FeedbackStore.append(self.feedback_path, record)

        self.feedback = FeedbackStore((*self.feedback.records, record))
        self.engine = RecommendationEngine(self.registry, self.feedback)
        return record
