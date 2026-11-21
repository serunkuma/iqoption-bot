"""Streaming store facade.

``StreamStore.ingest`` is the receiver's sink. It assigns a sequence, updates the
forming candle, persists the raw event, and exposes each closed candle to the
rolling window. Persistence is flushed on every candle close and whenever the
event buffer reaches ``flush_events``.

A failed write does not drop the event: it stays buffered, the store reports
itself degraded, and the caller stops making proposals. If the buffer exceeds
``max_buffer_events`` the store refuses further ingestion instead of growing
without bound.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from .candles import CandleBuilder, ClosedCandle
from .events import EventError, TickEvent
from .parquet import HourlyParquetStore, StoreWriteError
from .window import RollingCandleWindow

SCHEMA_VERSION = 1


class StreamBufferError(StoreWriteError):
    """Raised when the unflushed buffer exceeds its configured limit."""


@dataclass(frozen=True)
class IngestResult:
    """Outcome of one accepted or rejected tick."""

    accepted: bool
    sequence: int | None = None
    reason: str | None = None
    late: bool = False
    closed: tuple[ClosedCandle, ...] = ()
    gaps: tuple[int, ...] = ()
    window_ready: bool = False
    event: TickEvent | None = None


class StreamStore:
    """Own event ingestion, candle construction, the rolling window, and storage."""

    def __init__(
        self,
        root: str | Path,
        *,
        interval_seconds: int = 60,
        window_size: int = 7,
        flush_events: int = 500,
        compression: str = "zstd",
        max_buffer_events: int = 50000,
        active_id: int | None = None,
        artifact_id: str | None = None,
    ) -> None:
        if flush_events < 1:
            raise ValueError("flush_events must be at least 1")
        if max_buffer_events < flush_events:
            raise ValueError("max_buffer_events must be at least flush_events")
        self.interval_seconds = interval_seconds
        self.active_id = active_id
        self.flush_events = flush_events
        self.max_buffer_events = max_buffer_events
        self.artifact_id = artifact_id
        self.started_at = datetime.now(timezone.utc).isoformat()
        self.builder = CandleBuilder(interval_seconds)
        self.window = RollingCandleWindow(window_size)
        self.sink = HourlyParquetStore(root, compression=compression)
        self.degraded: str | None = None

        state = self.sink.load_state()
        if state is None:
            state = self.sink.recover()

        self.last_sequence = int(state.get("last_flushed_sequence", -1))
        bucket = state.get("last_finalized_bucket")
        self.last_finalized_bucket: int | None = (
            None if bucket is None else int(bucket)
        )

        forming = state.get("forming")
        if isinstance(forming, dict):
            forming_key = forming.get("bucket_key")
            if forming_key is not None and (
                self.last_finalized_bucket is None
                or int(forming_key) > self.last_finalized_bucket
            ):
                self.builder.restore(forming)

        self.counters: dict[str, int] = {
            "ticks": 0,
            "candles_closed": 0,
            "gap_minutes": 0,
            "late_rejected": 0,
            "invalid": 0,
            "instrument_rejected": 0,
            "flushes": 0,
            "write_failures": 0,
        }

    # -- ingestion -------------------------------------------------------
    def ingest(self, active_id: Any, payload: Mapping[str, Any]) -> IngestResult:
        """Accept one receiver payload and update the stream state."""

        try:
            event = TickEvent.from_payload(
                self.last_sequence + 1, active_id, payload
            )
        except EventError as exc:
            self.counters["invalid"] += 1
            return IngestResult(accepted=False, reason=str(exc))

        if self.active_id is not None and event.active_id != self.active_id:
            self.counters["instrument_rejected"] += 1
            return IngestResult(accepted=False, reason="instrument")

        key = int(event.epoch // self.interval_seconds)
        if (
            self.last_finalized_bucket is not None
            and key <= self.last_finalized_bucket
        ):
            self.counters["late_rejected"] += 1
            return IngestResult(accepted=False, reason="late", late=True)

        update = self.builder.ingest(event)
        if not update.accepted:
            if update.late:
                self.counters["late_rejected"] += 1
            elif update.reason == "instrument":
                self.counters["instrument_rejected"] += 1
            else:
                self.counters["invalid"] += 1
            return IngestResult(
                accepted=False, reason=update.reason, late=update.late
            )

        self.last_sequence = event.sequence
        self.sink.add_event(event)

        for candle in update.closed:
            self.sink.add_candle(candle)
            self.window.append(candle)
            self.last_finalized_bucket = candle.bucket_key
            self.counters["candles_closed"] += 1

        if update.gaps:
            self.counters["gap_minutes"] += len(update.gaps)
        self.counters["ticks"] += 1

        if update.closed or self.sink.pending_events >= self.flush_events:
            self._flush()

        if self.sink.pending_events > self.max_buffer_events:
            self.degraded = "buffer_limit"
            raise StreamBufferError(
                f"unflushed event buffer exceeded {self.max_buffer_events} rows"
            )

        return IngestResult(
            accepted=True,
            sequence=event.sequence,
            closed=update.closed,
            gaps=update.gaps,
            window_ready=self.window.ready,
            event=event,
        )

    # -- lifecycle -------------------------------------------------------
    def close(self) -> None:
        """Flush buffers and persist state. The forming candle is not finalized."""

        self.sink.flush()
        self.sink.save_state(self.state)
        self.counters["flushes"] += 1

    def _flush(self) -> None:
        try:
            self.sink.flush()
            self.sink.save_state(self.state)
        except StoreWriteError as exc:
            self.counters["write_failures"] += 1
            self.degraded = str(exc)
            return
        self.degraded = None
        self.counters["flushes"] += 1

    @property
    def state(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "last_flushed_sequence": self.last_sequence,
            "last_finalized_bucket": self.last_finalized_bucket,
            "interval_seconds": self.interval_seconds,
            "window_size": self.window.size,
            "active_id": self.active_id,
            "artifact_id": self.artifact_id,
            "started_at": self.started_at,
            "forming": self.builder.snapshot(),
        }

    @property
    def window_ready(self) -> bool:
        return self.window.ready

    # -- reading ---------------------------------------------------------
    def read_events(self):
        return self.sink.read_events()

    def read_candles(self):
        return self.sink.read_candles()
