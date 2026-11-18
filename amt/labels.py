"""Fixed-horizon direction labels for tick-based predictions.

Each tick is an entry. For every configured horizon the exit is the first
tick at or after ``entry + horizon`` within the tolerance window. Ties and
missing exits stay explicit; ties are excluded from directional training by
default but are never silently mapped to Put.
"""

from __future__ import annotations

import numpy as np

from .config import Config
from .timeframes import Tick

LABEL_COLUMNS = (
    "tick_id",
    "timestamp",
    "active_id",
    "entry_price",
    "horizon_seconds",
    "exit_timestamp",
    "exit_price",
    "exit_delay_seconds",
    "label",
    "usable",
)


def _direction(entry: float, exit_price: float) -> str:
    if exit_price > entry:
        return "call"
    if exit_price < entry:
        return "put"
    return "tie"


def build_labels(ticks: list[Tick], config: Config) -> list[dict]:
    """Build long-format labels: one row per tick per horizon."""

    if not ticks:
        return []

    epochs = np.asarray([tick.epoch for tick in ticks], dtype=float)
    prices = [tick.price for tick in ticks]

    horizons = tuple(config.labels.horizons_seconds)
    tolerance = config.labels.exit_tolerance_seconds
    tie_policy = config.labels.tie_policy

    rows: list[dict] = []

    for tick_id, tick in enumerate(ticks):
        entry_price = tick.price
        for horizon in horizons:
            target = tick.epoch + horizon
            index = int(np.searchsorted(epochs, target, side="left"))

            exit_timestamp = None
            exit_price = None
            exit_delay = None
            label = "missing"
            usable = 0

            if index < len(ticks):
                candidate = ticks[index]
                delay = candidate.epoch - target
                if delay <= tolerance:
                    exit_timestamp = candidate.timestamp.isoformat()
                    exit_price = prices[index]
                    exit_delay = delay
                    label = _direction(entry_price, exit_price)
                    if label in {"call", "put"}:
                        usable = 1
                    elif label == "tie" and tie_policy == "keep":
                        usable = 1

            rows.append(
                {
                    "tick_id": tick_id,
                    "timestamp": tick.timestamp.isoformat(),
                    "active_id": tick.active_id,
                    "entry_price": entry_price,
                    "horizon_seconds": horizon,
                    "exit_timestamp": exit_timestamp,
                    "exit_price": exit_price,
                    "exit_delay_seconds": exit_delay,
                    "label": label,
                    "usable": usable,
                }
            )

    return rows
