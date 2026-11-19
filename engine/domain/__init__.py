"""Domain primitives for the engine.

These modules are pure, stateless, and depend only on the standard library
(plus numpy where noted). They are shared by the offline builder, the
snapshot sampler, and live inference so that research and production use the
same definitions.
"""

from .labels import LABEL_COLUMNS, classify_direction, snapshot_label_rows
from .profile import Profile, bin_index, build_profile
from .timeframes import (
    Candle,
    Tick,
    bucket_key,
    completed_window,
    group_candles,
    window_has_gap,
)

__all__ = [
    "Candle",
    "LABEL_COLUMNS",
    "Profile",
    "Tick",
    "bin_index",
    "bucket_key",
    "build_profile",
    "classify_direction",
    "completed_window",
    "group_candles",
    "snapshot_label_rows",
    "window_has_gap",
]
