"""Public standalone API for AI Model Advisor."""

from .api import Advisor
from .decision import RoutingDecision
from tools.ai_model_advisor.feedback import FeedbackStore, UsageRecord
from tools.ai_model_advisor.models import ModelProfile, Recommendation, WorkloadProfile
from tools.ai_model_advisor.registry import ModelRegistry

__all__ = [
    "Advisor",
    "FeedbackStore",
    "ModelProfile",
    "ModelRegistry",
    "Recommendation",
    "RoutingDecision",
    "UsageRecord",
    "WorkloadProfile",
]

__version__ = "0.7.0"
