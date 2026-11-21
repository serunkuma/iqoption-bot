"""Candle-close snapshot gate.

A snapshot is the state at a completed one-minute candle. The gate verifies that
the seven most recent bars exist and are contiguous, captures the causal feature
slice (the closed bars only), and attaches a delayed entry price plus the four
future expiry outcomes.

There is exactly one snapshot per decision minute. The intra-minute offset mode
was removed in the streaming redesign: decisions happen at candle close, not at
``:30``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import numpy as np

from .config import DECISION_VERSION, Config
from .domain.labels import classify_direction
from .store import TickStore


@dataclass(frozen=True)
class BarSlice:
    """Ticks belonging to one whole-minute bucket."""

    bucket_key: int
    start_epoch: float
    epochs: tuple[float, ...]
    prices: tuple[float, ...]

    @property
    def tick_count(self) -> int:
        return len(self.prices)

    @property
    def high(self) -> float:
        return max(self.prices)

    @property
    def low(self) -> float:
        return min(self.prices)

    @property
    def open(self) -> float:
        return self.prices[0]

    @property
    def close(self) -> float:
        return self.prices[-1]


@dataclass(frozen=True)
class HorizonOutcome:
    horizon_seconds: int
    exit_timestamp: datetime | None
    exit_price: float | None
    exit_delay_seconds: float | None
    label: str


@dataclass(frozen=True)
class Snapshot:
    """One validated candle-close decision point."""

    snapshot_id: int
    active_id: int
    snapshot_time: datetime
    completed_bars: tuple[BarSlice, ...]
    price: float
    window_ticks: int
    entry_timestamp: datetime | None
    entry_price: float | None
    entry_delay_seconds: float | None
    outcomes: dict[int, HorizonOutcome] = field(default_factory=dict)
    utc_offset_seconds: int = 0
    decision_version: str = DECISION_VERSION

    @property
    def contiguous(self) -> bool:
        if not self.completed_bars:
            return False
        keys = [bar.bucket_key for bar in self.completed_bars]
        return keys[-1] - keys[0] + 1 == len(keys)


@dataclass
class SamplerReport:
    snapshots: list[Snapshot] = field(default_factory=list)
    candidate_minutes: int = 0
    skipped_insufficient_history: int = 0
    skipped_gap: int = 0
    skipped_sparse_bar: int = 0
    skipped_no_entry_tick: int = 0
    snapshots_with_missing_exits: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "candidate_minutes": self.candidate_minutes,
            "snapshots": len(self.snapshots),
            "skipped_insufficient_history": self.skipped_insufficient_history,
            "skipped_gap": self.skipped_gap,
            "skipped_sparse_bar": self.skipped_sparse_bar,
            "skipped_no_entry_tick": self.skipped_no_entry_tick,
            "snapshots_with_missing_exits": self.snapshots_with_missing_exits,
        }


def _bucket_slices(
    epochs: np.ndarray, prices: np.ndarray, interval_seconds: int
) -> dict[int, tuple[int, int]]:
    """Map bucket key -> [start, end) index range in the tick arrays."""

    if epochs.size == 0:
        return {}
    keys = np.floor(epochs / interval_seconds).astype(np.int64)
    # Boundaries where the bucket key changes.
    change = np.flatnonzero(np.diff(keys) != 0) + 1
    starts = np.concatenate(([0], change))
    ends = np.concatenate((change, [keys.size]))
    return {
        int(keys[start]): (int(start), int(end))
        for start, end in zip(starts, ends)
    }


def _bar_slice(
    key: int,
    index_range: tuple[int, int],
    epochs: np.ndarray,
    prices: np.ndarray,
    interval_seconds: int,
) -> BarSlice:
    start, end = index_range
    return BarSlice(
        bucket_key=key,
        start_epoch=float(key * interval_seconds),
        epochs=tuple(float(value) for value in epochs[start:end]),
        prices=tuple(float(value) for value in prices[start:end]),
    )


def _epoch_to_datetime(epoch: float) -> datetime:
    return datetime.fromtimestamp(epoch, tz=timezone.utc)


def build_snapshots(store: TickStore, config: Config) -> SamplerReport:
    """Generate one candle-close snapshot per valid minute plus an exclusion report."""

    report = SamplerReport()
    if store.is_empty:
        return report

    interval = config.candles.interval_seconds
    macro = config.context.macro_candles
    min_ticks = config.snapshot.min_ticks_per_bar
    entry_delay = config.snapshot.entry_delay_ms / 1000.0
    entry_tol = config.snapshot.entry_tolerance_seconds
    exit_tol = config.snapshot.exit_tolerance_seconds
    horizons = tuple(config.labels.horizons_seconds)

    # One instrument at a time: drop every other stream before sampling so
    # features can never mix two instruments.
    frame = store.frame
    if config.instrument.active_id is not None:
        frame = frame.loc[frame["active_id"] == config.instrument.active_id]
        if frame.empty:
            return report
        active_id = int(config.instrument.active_id)
    else:
        present = frame["active_id"].dropna()
        if present.empty:
            active_id = 0
        else:
            active_id = int(present.iloc[0])
            frame = frame.loc[frame["active_id"] == active_id]

    epochs = frame["timestamp"].astype("int64").to_numpy(dtype=np.float64) / 1e9
    prices = frame["price"].to_numpy(dtype=np.float64)
    offsets_column = frame["utc_offset_seconds"].to_numpy(dtype=np.int64)
    buckets = _bucket_slices(epochs, prices, interval)
    # A bucket is only complete once a strictly later bucket has started. The
    # final bucket present in a capture is therefore always the forming candle
    # and must never enter the feature window.
    keys = sorted(buckets)[:-1] if len(buckets) > 1 else []
    report.candidate_minutes = len(keys)

    snapshot_id = 0
    for position, key in enumerate(keys):
        if position + 1 < macro:
            report.skipped_insufficient_history += 1
            continue

        window_keys = keys[position - macro + 1 : position + 1]
        expected = list(range(key - macro + 1, key + 1))
        if window_keys != expected:
            report.skipped_gap += 1
            continue
        if any(buckets[k][1] - buckets[k][0] < min_ticks for k in window_keys):
            report.skipped_sparse_bar += 1
            continue

        completed = tuple(
            _bar_slice(k, buckets[k], epochs, prices, interval) for k in window_keys
        )
        decision_epoch = float((key + 1) * interval)
        price = completed[-1].close
        window_ticks = sum(bar.tick_count for bar in completed)

        # Delayed entry: first tick at or after the candle close + delay.
        entry_target = decision_epoch + entry_delay
        entry_index = int(np.searchsorted(epochs, entry_target, side="left"))
        entry_timestamp = None
        entry_price = None
        entry_delay_actual = None
        if entry_index < epochs.size:
            entry_epoch = float(epochs[entry_index])
            if entry_epoch <= entry_target + entry_tol:
                entry_timestamp = _epoch_to_datetime(entry_epoch)
                entry_price = float(prices[entry_index])
                entry_delay_actual = entry_epoch - decision_epoch

        if entry_timestamp is None or entry_price is None:
            report.skipped_no_entry_tick += 1
            continue

        outcomes: dict[int, HorizonOutcome] = {}
        missing_exit = False
        for horizon in horizons:
            target = float(entry_timestamp.timestamp()) + horizon
            index = int(np.searchsorted(epochs, target, side="left"))
            outcome = HorizonOutcome(
                horizon_seconds=horizon,
                exit_timestamp=None,
                exit_price=None,
                exit_delay_seconds=None,
                label="missing",
            )
            if index < epochs.size:
                exit_epoch = float(epochs[index])
                delay = exit_epoch - target
                if delay <= exit_tol:
                    exit_price = float(prices[index])
                    outcome = HorizonOutcome(
                        horizon_seconds=horizon,
                        exit_timestamp=_epoch_to_datetime(exit_epoch),
                        exit_price=exit_price,
                        exit_delay_seconds=delay,
                        label=classify_direction(entry_price, exit_price),
                    )
            if outcome.label == "missing":
                missing_exit = True
            outcomes[horizon] = outcome

        if missing_exit:
            report.snapshots_with_missing_exits += 1

        report.snapshots.append(
            Snapshot(
                snapshot_id=snapshot_id,
                active_id=active_id,
                snapshot_time=_epoch_to_datetime(decision_epoch),
                completed_bars=completed,
                price=price,
                window_ticks=window_ticks,
                entry_timestamp=entry_timestamp,
                entry_price=entry_price,
                entry_delay_seconds=entry_delay_actual,
                outcomes=outcomes,
                utc_offset_seconds=int(offsets_column[buckets[key][0]]),
            )
        )
        snapshot_id += 1

    return report
