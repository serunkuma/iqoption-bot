"""Replay raw events into candles and compare with recorded tables.

Replay uses the same :class:`~engine.stream.candles.CandleBuilder`, window, and
feature code as the runtime. A divergence therefore points at data or state, not
at a second implementation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from .config import Config
from .features import CORE_FEATURES, compute_features
from .sampler import BarSlice, Snapshot
from .stream import CandleBuilder, ClosedCandle, TickEvent

CANDLE_FIELDS = (
    "open",
    "high",
    "low",
    "close",
    "tick_count",
    "first_sequence",
    "last_sequence",
)


@dataclass
class CandleMismatch:
    bucket_key: int
    field: str
    expected: Any
    actual: Any

    def as_dict(self) -> dict[str, Any]:
        return {
            "bucket_key": self.bucket_key,
            "field": self.field,
            "expected": self.expected,
            "actual": self.actual,
        }


@dataclass
class ReplayReport:
    events: int = 0
    rebuilt_candles: int = 0
    recorded_candles: int = 0
    missing: list[int] = field(default_factory=list)
    extra: list[int] = field(default_factory=list)
    mismatches: list[CandleMismatch] = field(default_factory=list)
    feature_rows_checked: int = 0
    feature_mismatches: list[dict[str, Any]] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not (
            self.missing
            or self.extra
            or self.mismatches
            or self.feature_mismatches
        )

    @property
    def first_divergence(self) -> str | None:
        if self.missing:
            return f"missing candle bucket {self.missing[0]}"
        if self.extra:
            return f"unexpected candle bucket {self.extra[0]}"
        if self.mismatches:
            item = self.mismatches[0]
            return (
                f"candle {item.bucket_key} {item.field}: "
                f"recorded={item.expected} rebuilt={item.actual}"
            )
        if self.feature_mismatches:
            item = self.feature_mismatches[0]
            return (
                f"feature {item['feature']} at {item['timestamp']}: "
                f"recorded={item['expected']} rebuilt={item['actual']}"
            )
        return None

    def as_dict(self) -> dict[str, Any]:
        return {
            "events": self.events,
            "rebuilt_candles": self.rebuilt_candles,
            "recorded_candles": self.recorded_candles,
            "missing": self.missing,
            "extra": self.extra,
            "mismatches": [item.as_dict() for item in self.mismatches],
            "feature_rows_checked": self.feature_rows_checked,
            "feature_mismatches": self.feature_mismatches,
            "first_divergence": self.first_divergence,
            "ok": self.ok,
        }


def rebuild_candles(
    events: pd.DataFrame, interval_seconds: int = 60
) -> list[ClosedCandle]:
    """Rebuild closed candles from an event table in sequence order."""

    if events.empty:
        return []

    builder = CandleBuilder(interval_seconds)
    candles: list[ClosedCandle] = []
    frame = events.sort_values("sequence", kind="mergesort")
    for row in frame.itertuples(index=False):
        event = TickEvent(
            sequence=int(row.sequence),
            received_at=pd.Timestamp(row.received_at).to_pydatetime(),
            active_id=int(row.active_id),
            price=float(row.price),
            utc_offset_seconds=int(row.utc_offset_seconds),
        )
        update = builder.ingest(event)
        candles.extend(update.closed)
    return candles


def compare_candles(
    rebuilt: Iterable[ClosedCandle], recorded: pd.DataFrame
) -> ReplayReport:
    rebuilt_list = list(rebuilt)
    report = ReplayReport(
        rebuilt_candles=len(rebuilt_list),
        recorded_candles=len(recorded),
    )
    by_key = {candle.bucket_key: candle for candle in rebuilt_list}
    recorded_keys = (
        set(int(value) for value in recorded["bucket_key"].tolist())
        if not recorded.empty
        else set()
    )
    report.missing = sorted(recorded_keys - set(by_key))
    report.extra = sorted(set(by_key) - recorded_keys)

    for row in recorded.itertuples(index=False):
        key = int(row.bucket_key)
        candle = by_key.get(key)
        if candle is None:
            continue
        for name in CANDLE_FIELDS:
            expected = getattr(row, name)
            actual = getattr(candle, name)
            if name in {"open", "high", "low", "close"}:
                same = abs(float(expected) - float(actual)) <= 1e-12
            else:
                same = int(expected) == int(actual)
            if not same:
                report.mismatches.append(
                    CandleMismatch(key, name, expected, actual)
                )
    return report


def compare_features(
    rebuilt: list[ClosedCandle], dataset: pd.DataFrame, config: Config
) -> list[dict[str, Any]]:
    """Compare runtime-style features with an offline dataset, by decision time."""

    if dataset.empty or len(rebuilt) < config.context.macro_candles:
        return []

    macro = config.context.macro_candles
    rows = dataset.drop_duplicates(subset=["timestamp"]).copy()
    rows["moment_utc"] = pd.to_datetime(rows["timestamp"], utc=True)
    by_moment = {
        row.moment_utc.to_pydatetime(): row for row in rows.itertuples(index=False)
    }

    mismatches: list[dict[str, Any]] = []
    # The first eligible decision uses candles 0..macro-1.
    start = macro - 1
    for index in range(start, len(rebuilt)):
        candle = rebuilt[index]
        window = list(rebuilt[index - macro + 1 : index + 1])
        decision = candle.bucket_end
        recorded = by_moment.get(decision)
        if recorded is not None:
            snapshot = Snapshot(
                snapshot_id=candle.bucket_key,
                active_id=candle.active_id,
                snapshot_time=decision,
                completed_bars=tuple(
                    BarSlice(
                        bucket_key=item.bucket_key,
                        start_epoch=item.start_epoch,
                        epochs=item.epochs,
                        prices=item.prices,
                    )
                    for item in window
                ),
                price=window[-1].close,
                window_ticks=sum(item.tick_count for item in window),
                entry_timestamp=None,
                entry_price=None,
                entry_delay_seconds=None,
                outcomes={},
                utc_offset_seconds=candle.utc_offset_seconds,
            )
            vector = compute_features(snapshot, config)
            for name in CORE_FEATURES:
                expected = getattr(recorded, name)
                actual = vector.core[name]
                if expected is None or pd.isna(expected):
                    same = actual is None
                elif actual is None:
                    same = False
                else:
                    same = abs(float(expected) - float(actual)) <= 1e-9
                if not same:
                    mismatches.append(
                        {
                            "timestamp": decision.isoformat(),
                            "feature": name,
                            "expected": None if pd.isna(expected) else float(expected),
                            "actual": actual,
                        }
                    )
    return mismatches


def replay_from_dirs(
    events_dir: str | Path,
    candles_dir: str | Path | None = None,
    *,
    interval_seconds: int = 60,
    dataset: pd.DataFrame | None = None,
    config: Config | None = None,
) -> ReplayReport:
    event_paths = sorted(Path(events_dir).glob("*/*/part-*.parquet"))
    if not event_paths:
        raise FileNotFoundError(f"no event parts under {events_dir}")
    events = pd.concat(
        [pd.read_parquet(path) for path in event_paths], ignore_index=True
    )
    rebuilt = rebuild_candles(events, interval_seconds)

    recorded = pd.DataFrame()
    if candles_dir is not None:
        candle_paths = sorted(Path(candles_dir).glob("*/*/part-*.parquet"))
        if candle_paths:
            recorded = pd.concat(
                [pd.read_parquet(path) for path in candle_paths], ignore_index=True
            )

    report = compare_candles(rebuilt, recorded)
    report.events = len(events)
    if dataset is not None and config is not None:
        report.feature_mismatches = compare_features(rebuilt, dataset, config)
        report.feature_rows_checked = int(
            dataset["timestamp"].nunique() if not dataset.empty else 0
        )
    return report
