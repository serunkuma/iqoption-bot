"""Local-minute candle bucketing.

Ticks carry one timestamp: the local receipt time stored as an ISO 8601
string with an offset. Buckets are whole minutes in absolute time, which
coincide with whole local minutes for every real UTC offset. Using absolute
time also keeps repeated local minutes distinct across a daylight-saving
change.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Tick:
    """One accepted price update."""

    timestamp: datetime
    price: float
    active_id: int | None = None
    sequence: int | None = None

    @property
    def epoch(self) -> float:
        return self.timestamp.timestamp()


@dataclass(frozen=True)
class Candle:
    """One whole-minute bucket of ticks."""

    bucket_key: int
    start_epoch: float
    end_epoch: float
    tick_indices: tuple[int, ...]

    @property
    def tick_count(self) -> int:
        return len(self.tick_indices)

    @property
    def duration_seconds(self) -> float:
        return self.end_epoch - self.start_epoch


def bucket_key(timestamp: datetime, interval_seconds: int = 60) -> int:
    """Return the integer bucket index for an aware timestamp."""

    if interval_seconds <= 0:
        raise ValueError("interval_seconds must be positive")
    if timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware")
    return int(timestamp.timestamp() // interval_seconds)


def group_candles(ticks: list[Tick], interval_seconds: int = 60) -> list[Candle]:
    """Group chronologically sorted ticks into whole-minute candles."""

    candles: list[Candle] = []
    current_key: int | None = None
    current_indices: list[int] = []

    def flush(key: int, indices: list[int]) -> None:
        start = key * interval_seconds
        candles.append(
            Candle(
                bucket_key=key,
                start_epoch=float(start),
                end_epoch=float(start + interval_seconds),
                tick_indices=tuple(indices),
            )
        )

    for index, tick in enumerate(ticks):
        key = bucket_key(tick.timestamp, interval_seconds)
        if current_key is not None and key < current_key:
            raise ValueError("ticks must be sorted by timestamp before grouping")
        if current_key is not None and key != current_key:
            flush(current_key, current_indices)
            current_indices = []
        current_key = key
        current_indices.append(index)

    if current_key is not None:
        flush(current_key, current_indices)

    return candles


def completed_window(candles: list[Candle], current_index: int, count: int) -> tuple[int, int]:
    """Return the `[start, end)` candle slice of the last `count` completed candles.

    The candle at `current_index` is still forming and is never included.
    """

    if count < 1:
        raise ValueError("count must be at least 1")
    end = current_index
    start = max(0, end - count)
    return start, end


def window_has_gap(candles: list[Candle], start: int, end: int) -> bool:
    """Report whether the candle slice skips any whole-minute bucket."""

    if end <= start:
        return False
    keys = [candles[index].bucket_key for index in range(start, end)]
    span = keys[-1] - keys[0] + 1
    return span != len(keys)
