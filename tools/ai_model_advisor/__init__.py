"""Backward-compatible internal package for AI Model Advisor.

New code should import :mod:`ai_model_advisor`. Hive-specific symbols remain
available here through lazy attribute loading so importing the core package does
not pull Hive integration modules into memory.
"""

from __future__ import annotations

from importlib import import_module
from typing import Any

from .activity import ActivityAnalyzer
from .canary_evaluate import evaluate_promotion_canary
from .cross_target_decision import build_cross_target_decision
from .cross_target_stability import build_cross_target_stability_report
from .empirical_leaderboard import build_empirical_leaderboard
from .feedback import FeedbackStore, UsageRecord
from .promotion_plan import build_promotion_plans
from .promotion_review import build_promotion_review
from .recommend import RecommendationEngine
from .registry import ModelRegistry
from .routing_proposals import build_routing_proposals
from .target_experiment_plan import build_target_experiment_plan
from .target_routing import recommend_for_target

_LAZY_EXPORTS: dict[str, tuple[str, str]] = {
    "append_hive_promotion_journal": (
        ".hive_promotion_journal",
        "append_hive_promotion_journal",
    ),
    "build_hive_config_preview": (".hive_config_preview", "build_hive_config_preview"),
    "build_hive_promotion_checkpoint": (
        ".hive_promotion_checkpoint",
        "build_hive_promotion_checkpoint",
    ),
    "build_hive_promotion_gate": (".hive_promotion_gate", "build_hive_promotion_gate"),
    "build_hive_promotion_journal": (
        ".hive_promotion_journal",
        "build_hive_promotion_journal",
    ),
    "build_hive_promotion_preview": (
        ".hive_promotion_preview",
        "build_hive_promotion_preview",
    ),
    "build_hive_promotion_receipt": (
        ".hive_promotion_receipt",
        "build_hive_promotion_receipt",
    ),
    "build_hive_promotion_reconciliation": (
        ".hive_promotion_reconcile",
        "build_hive_promotion_reconciliation",
    ),
    "build_hive_promotion_registry": (
        ".hive_promotion_registry",
        "build_hive_promotion_registry",
    ),
    "build_hive_promotion_rollback_audit": (
        ".hive_promotion_rollback",
        "build_hive_promotion_rollback_audit",
    ),
    "build_hive_promotion_rollback_finalization": (
        ".hive_promotion_rollback_finalize",
        "build_hive_promotion_rollback_finalization",
    ),
    "build_hive_promotion_rollback_plan": (
        ".hive_promotion_rollback_plan",
        "build_hive_promotion_rollback_plan",
    ),
    "build_hive_promotion_rollback_preflight": (
        ".hive_promotion_rollback_preflight",
        "build_hive_promotion_rollback_preflight",
    ),
    "build_hive_promotion_status": (
        ".hive_promotion_status",
        "build_hive_promotion_status",
    ),
    "validate_hive_promotion_checkpoint": (
        ".hive_promotion_checkpoint",
        "validate_hive_promotion_checkpoint",
    ),
    "validate_hive_promotion_journal": (
        ".hive_promotion_journal",
        "validate_hive_promotion_journal",
    ),
    "verify_hive_promotion_checkpoint": (
        ".hive_promotion_checkpoint",
        "verify_hive_promotion_checkpoint",
    ),
}

__all__ = [
    "ActivityAnalyzer",
    "FeedbackStore",
    "ModelRegistry",
    "RecommendationEngine",
    "UsageRecord",
    "append_hive_promotion_journal",
    "build_cross_target_decision",
    "build_cross_target_stability_report",
    "build_empirical_leaderboard",
    "build_hive_config_preview",
    "build_hive_promotion_checkpoint",
    "build_hive_promotion_gate",
    "build_hive_promotion_journal",
    "build_hive_promotion_preview",
    "build_hive_promotion_receipt",
    "build_hive_promotion_reconciliation",
    "build_hive_promotion_registry",
    "build_hive_promotion_rollback_audit",
    "build_hive_promotion_rollback_finalization",
    "build_hive_promotion_rollback_plan",
    "build_hive_promotion_rollback_preflight",
    "build_hive_promotion_status",
    "build_promotion_plans",
    "build_promotion_review",
    "build_routing_proposals",
    "build_target_experiment_plan",
    "evaluate_promotion_canary",
    "recommend_for_target",
    "validate_hive_promotion_checkpoint",
    "validate_hive_promotion_journal",
    "verify_hive_promotion_checkpoint",
]

__version__ = "0.4.0"


def __getattr__(name: str) -> Any:
    target = _LAZY_EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name, __name__), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
