"""Engine package: the prediction pipeline as decoupled components.

``runner.py`` wires these together. Each module owns one responsibility and
exposes a small, testable surface.

Import order matters: ``.models`` is imported first so LightGBM's Windows DLL
loads before pandas and pyarrow. See the note in ``engine/models.py``.
"""

from .models import ModelArtifactError, ModelSuite, train_suite
from .backtest import run_backtest
from .build import (
    BuildArtifacts,
    build_dataset,
    build_from_csv,
    build_from_store,
    build_from_ticks,
)
from .config import (
    CANDLE_VERSION,
    CORE_FEATURE_VERSION,
    DECISION_VERSION,
    FEATURE_VERSION,
    LABEL_VERSION,
    MODEL_FORMAT_VERSION,
    Config,
    ConfigError,
    config_hash,
    load_config,
)
from .features import CORE_FEATURES, FeatureVector, compute_features
from .replay import ReplayReport, replay_from_dirs
from .router import SignalProposal, breakeven_win_rate, expected_value, route
from .runtime import DecisionJournal, RuntimeEngine
from .sampler import Snapshot, build_snapshots
from .store import TickStore
from .stream import ClosedCandle, StreamStore, TickEvent

__all__ = [
    "CANDLE_VERSION",
    "CORE_FEATURES",
    "CORE_FEATURE_VERSION",
    "DECISION_VERSION",
    "Config",
    "ConfigError",
    "BuildArtifacts",
    "ClosedCandle",
    "DecisionJournal",
    "FEATURE_VERSION",
    "FeatureVector",
    "LABEL_VERSION",
    "MODEL_FORMAT_VERSION",
    "ModelArtifactError",
    "ModelSuite",
    "ReplayReport",
    "RuntimeEngine",
    "SignalProposal",
    "Snapshot",
    "StreamStore",
    "TickEvent",
    "TickStore",
    "breakeven_win_rate",
    "build_dataset",
    "build_from_csv",
    "build_from_store",
    "build_from_ticks",
    "build_snapshots",
    "compute_features",
    "config_hash",
    "expected_value",
    "load_config",
    "replay_from_dirs",
    "route",
    "run_backtest",
    "train_suite",
]
