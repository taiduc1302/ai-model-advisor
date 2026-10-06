"""Public Hive integration surface.

Hive is an optional backend. Import this module only for Hive-specific preview,
preflight, telemetry, or promotion helpers.
"""

from tools.ai_model_advisor.hive_config_preview import build_hive_config_preview
from tools.ai_model_advisor.hive_experiment_preflight import build_hive_experiment_preflight
from tools.ai_model_advisor.hive_history import import_hive_history
from tools.ai_model_advisor.hive_promotion_gate import build_hive_promotion_gate
from tools.ai_model_advisor.hive_promotion_preview import build_hive_promotion_preview
from tools.ai_model_advisor.hive_trace import import_hive_trace

__all__ = [
    "build_hive_config_preview",
    "build_hive_experiment_preflight",
    "build_hive_promotion_gate",
    "build_hive_promotion_preview",
    "import_hive_history",
    "import_hive_trace",
]
