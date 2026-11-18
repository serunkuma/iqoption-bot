"""AMT feature and label pipeline for the IQ Option bot.

The package turns captured ticks into causal auction features and
fixed-horizon direction labels. It does not train models or place trades.
"""

from .config import (
    FEATURE_VERSION,
    LABEL_VERSION,
    Config,
    ConfigError,
    load_config,
)
from .features import build_features
from .labels import build_labels

__all__ = [
    "Config",
    "ConfigError",
    "FEATURE_VERSION",
    "LABEL_VERSION",
    "build_features",
    "build_labels",
    "load_config",
]
