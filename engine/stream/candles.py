"""One-minute candle construction from the tick stream.

Candles are clock-aligned and half-open: ``[K * 60, (K + 1) * 60)``. A candle is
finalized when the first event of the next minute arrives. For every closed
candle a new forming candle opens.

An event whose minute is older than the forming candle is rejected as late. A
closed candle is never rewritten.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from .events import TickEvent


@dataclass(frozen=True)
class ClosedCandle:
    """A finalized one-minute candle."""

    bucket_key: int
    start_epoch: float
    end_epoch: float
    active_id: int
    open: float
    high: float
    low: float
    close: float
    tick_count: int
    first_sequence: int
    last_sequence: int
    finalized_at: datetime
    utc_offset_seconds: int = 0
    epochs: tuple[float, ...] = ()
    prices: tuple[float, ...] = ()

    @property
    def bucket_start(self) -> datetime:
        return datetime.fromtimestamp(self.start_epoch, tz=timezone.utc)

    @property
    def bucket_end(self) -> datetime:
        return datetime.fromtimestamp(self.end_epoch, tz=timezone.utc)

    def as_row(self) -> dict[str, object]:
        return {
            "bucket_key": self.bucket_key,
            "bucket_start": self.bucket_start,
            "bucket_end": self.bucket_end,
            "active_id": self.active_id,
            "open": self.open,
            "high": self.high,
            "low": self.low,
            "close": self.close,
            "tick_count": self.tick_count,
            "first_sequence": self.first_sequence,
            "last_sequence": self.last_sequence,
            "finalized_at": self.finalized_at,
        }


@dataclass(frozen=True)
class CandleUpdate:
    """Result of ingesting one event into the builder."""

    accepted: bool
    reason: str | None = None
    closed: tuple[ClosedCandle, ...] = ()
    gaps: tuple[int, ...] = ()
    late: bool = False


class CandleBuilder:
    """Maintain the forming candle and finalize it at each minute boundary."""

    def __init__(self, interval_seconds: int = 60) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        self.interval_seconds = interval_seconds
        self._key: int | None = None
        self._active_id: int | None = None
        self._open = 0.0
        self._high = 0.0
        self._low = 0.0
        self._close = 0.0
        self._count = 0
        self._first_sequence = 0
        self._last_sequence = 0
        self._epochs: list[float] = []
        self._prices: list[float] = []
        self._utc_offset_seconds = 0

    @property
    def forming_key(self) -> int | None:
        return self._key

    @property
    def forming_tick_count(self) -> int:
        return self._count

    def ingest(self, event: TickEvent) -> CandleUpdate:
        key = int(event.epoch // self.interval_seconds)

        if self._key is None:
            self._start(event, key)
            return CandleUpdate(accepted=True)

        if event.active_id != self._active_id:
            return CandleUpdate(accepted=False, reason="instrument")

        if key < self._key:
            return CandleUpdate(accepted=False, reason="late", late=True)

        if key == self._key:
            self._update(event)
            return CandleUpdate(accepted=True)

        previous = self._key
        closed = (self._finalize(event.received_at),)
        gaps = tuple(range(previous + 1, key)) if key > previous + 1 else ()
        self._start(event, key)
        return CandleUpdate(accepted=True, closed=closed, gaps=gaps)

    def _start(self, event: TickEvent, key: int) -> None:
        self._key = key
        self._active_id = event.active_id
        self._open = event.price
        self._high = event.price
        self._low = event.price
        self._close = event.price
        self._count = 1
        self._first_sequence = event.sequence
        self._last_sequence = event.sequence
        self._epochs = [event.epoch]
        self._prices = [event.price]
        self._utc_offset_seconds = event.utc_offset_seconds

    def _update(self, event: TickEvent) -> None:
        self._high = max(self._high, event.price)
        self._low = min(self._low, event.price)
        self._close = event.price
        self._count += 1
        self._last_sequence = event.sequence
        self._epochs.append(event.epoch)
        self._prices.append(event.price)
        self._utc_offset_seconds = event.utc_offset_seconds

    def _finalize(self, finalized_at: datetime) -> ClosedCandle:
        assert self._key is not None
        start = float(self._key * self.interval_seconds)
        return ClosedCandle(
            bucket_key=self._key,
            start_epoch=start,
            end_epoch=start + self.interval_seconds,
            active_id=int(self._active_id or 0),
            open=self._open,
            high=self._high,
            low=self._low,
            close=self._close,
            tick_count=self._count,
            first_sequence=self._first_sequence,
            last_sequence=self._last_sequence,
            finalized_at=finalized_at,
            utc_offset_seconds=self._utc_offset_seconds,
            epochs=tuple(self._epochs),
            prices=tuple(self._prices),
        )

    # -- recovery --------------------------------------------------------
    def snapshot(self) -> dict[str, Any] | None:
        """Return the forming candle state for restart recovery."""

        if self._key is None:
            return None
        return {
            "bucket_key": self._key,
            "active_id": self._active_id,
            "open": self._open,
            "high": self._high,
            "low": self._low,
            "close": self._close,
            "tick_count": self._count,
            "first_sequence": self._first_sequence,
            "last_sequence": self._last_sequence,
            "epochs": list(self._epochs),
            "prices": list(self._prices),
            "utc_offset_seconds": self._utc_offset_seconds,
        }

    def restore(self, state: Mapping[str, Any]) -> None:
        """Restore a forming candle saved by :meth:`snapshot`."""

        try:
            key = int(state["bucket_key"])
            active_id = int(state["active_id"])
            open_price = float(state["open"])
            high = float(state["high"])
            low = float(state["low"])
            close = float(state["close"])
            count = int(state["tick_count"])
            first_sequence = int(state["first_sequence"])
            last_sequence = int(state["last_sequence"])
            utc_offset_seconds = int(state.get("utc_offset_seconds", 0))
            epochs = tuple(float(value) for value in state.get("epochs", ()))
            prices = tuple(float(value) for value in state.get("prices", ()))
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"invalid forming-candle state: {exc}") from exc

        if count < 1:
            raise ValueError("forming candle must have at least one tick")
        if low > high:
            raise ValueError("forming candle low must not exceed high")
        if len(prices) != count:
            raise ValueError("forming candle price list does not match tick_count")

        self._key = key
        self._active_id = active_id
        self._open = open_price
        self._high = high
        self._low = low
        self._close = close
        self._count = count
        self._first_sequence = first_sequence
        self._last_sequence = last_sequence
        self._utc_offset_seconds = utc_offset_seconds
        self._epochs = list(epochs)
        self._prices = list(prices)
