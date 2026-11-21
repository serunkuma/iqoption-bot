"""Hourly Parquet persistence for raw events and closed candles.

Each flush writes one immutable part file under an hour directory:

    <root>/events/YYYY-MM-DD/HH/part-0001.parquet
    <root>/candles/YYYY-MM-DD/HH/part-0001.parquet

Files are written to a temporary name and renamed, so a crash cannot leave a
half-written part in place. ``state.json`` records the last flushed sequence and
the last finalized candle so a restart can resume without replaying the hour.
"""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from .candles import ClosedCandle
from .events import TickEvent

EVENT_COLUMNS = (
    "sequence",
    "received_at",
    "active_id",
    "price",
    "utc_offset_seconds",
    "raw_json",
)

CANDLE_COLUMNS = (
    "bucket_key",
    "bucket_start",
    "bucket_end",
    "active_id",
    "open",
    "high",
    "low",
    "close",
    "tick_count",
    "first_sequence",
    "last_sequence",
    "finalized_at",
)


class StoreWriteError(RuntimeError):
    """Raised when the streaming store cannot persist data safely."""


def _hour_key(moment: datetime) -> tuple[str, str]:
    return moment.strftime("%Y-%m-%d"), moment.strftime("%H")


class HourlyParquetStore:
    """Buffer rows and write immutable hourly Parquet parts."""

    def __init__(self, root: str | Path, *, compression: str = "zstd") -> None:
        self.root = Path(root)
        self.compression = None if compression == "none" else compression
        self._events: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._candles: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
        self._events_dir.mkdir(parents=True, exist_ok=True)
        self._candles_dir.mkdir(parents=True, exist_ok=True)

    @property
    def _events_dir(self) -> Path:
        return self.root / "events"

    @property
    def _candles_dir(self) -> Path:
        return self.root / "candles"

    @property
    def state_path(self) -> Path:
        return self.root / "state.json"

    @property
    def pending_events(self) -> int:
        return sum(len(rows) for rows in self._events.values())

    @property
    def pending_candles(self) -> int:
        return sum(len(rows) for rows in self._candles.values())

    # -- ingestion -------------------------------------------------------
    def add_event(self, event: TickEvent) -> None:
        self._events[_hour_key(event.received_at)].append(
            {
                "sequence": event.sequence,
                "received_at": event.received_at,
                "active_id": event.active_id,
                "price": event.price,
                "utc_offset_seconds": event.utc_offset_seconds,
                "raw_json": json.dumps(dict(event.raw), default=str, sort_keys=True),
            }
        )

    def add_candle(self, candle: ClosedCandle) -> None:
        self._candles[_hour_key(candle.bucket_start)].append(candle.as_row())

    # -- persistence -----------------------------------------------------
    def flush(self) -> None:
        for (date, hour), rows in list(self._events.items()):
            if not rows:
                continue
            self._write(self._events_dir, date, hour, rows, kind="events")
            self._events[(date, hour)] = []

        for (date, hour), rows in list(self._candles.items()):
            if not rows:
                continue
            self._write(self._candles_dir, date, hour, rows, kind="candles")
            self._candles[(date, hour)] = []

    def _write(
        self,
        base: Path,
        date: str,
        hour: str,
        rows: Sequence[dict[str, Any]],
        *,
        kind: str,
    ) -> Path:
        directory = base / date / hour
        try:
            directory.mkdir(parents=True, exist_ok=True)
            index = len(list(directory.glob("part-*.parquet"))) + 1
            path = directory / f"part-{index:04d}.parquet"
            temporary = path.with_name(path.name + ".tmp")
            frame = _frame(rows, kind)
            frame.to_parquet(temporary, index=False, compression=self.compression)
            temporary.replace(path)
        except Exception as exc:  # pragma: no cover - platform dependent
            raise StoreWriteError(
                f"failed to write {kind} for {date} {hour}: {exc}"
            ) from exc
        return path

    def save_state(self, state: Mapping[str, Any]) -> Path:
        payload = dict(state)
        payload.setdefault("updated_at", datetime.now().astimezone().isoformat())
        temporary = self.state_path.with_name(self.state_path.name + ".tmp")
        try:
            temporary.write_text(
                json.dumps(payload, indent=2, sort_keys=True, default=str),
                encoding="utf-8",
            )
            temporary.replace(self.state_path)
        except OSError as exc:
            raise StoreWriteError(f"failed to write state file: {exc}") from exc
        return self.state_path

    def load_state(self) -> dict[str, Any] | None:
        if not self.state_path.is_file():
            return None
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise StoreWriteError(f"state file is unreadable: {exc}") from exc

    def recover(self) -> dict[str, Any]:
        """Scan part files for the last sequence and finalized candle."""

        last_sequence = -1
        last_bucket: int | None = None

        for path in sorted(self._events_dir.glob("*/*/part-*.parquet")):
            try:
                frame = pd.read_parquet(path, columns=["sequence"])
            except Exception as exc:  # pragma: no cover - corrupt file
                raise StoreWriteError(f"cannot read event part {path}: {exc}") from exc
            if not frame.empty:
                last_sequence = max(last_sequence, int(frame["sequence"].max()))

        for path in sorted(self._candles_dir.glob("*/*/part-*.parquet")):
            try:
                frame = pd.read_parquet(path, columns=["bucket_key"])
            except Exception as exc:  # pragma: no cover - corrupt file
                raise StoreWriteError(f"cannot read candle part {path}: {exc}") from exc
            if not frame.empty:
                bucket = int(frame["bucket_key"].max())
                last_bucket = bucket if last_bucket is None else max(last_bucket, bucket)

        return {
            "last_flushed_sequence": last_sequence,
            "last_finalized_bucket": last_bucket,
        }

    # -- reading ---------------------------------------------------------
    def read_events(self) -> pd.DataFrame:
        frames = [
            pd.read_parquet(path)
            for path in sorted(self._events_dir.glob("*/*/part-*.parquet"))
        ]
        if not frames:
            return pd.DataFrame(columns=EVENT_COLUMNS)
        return pd.concat(frames, ignore_index=True)

    def read_candles(self) -> pd.DataFrame:
        frames = [
            pd.read_parquet(path)
            for path in sorted(self._candles_dir.glob("*/*/part-*.parquet"))
        ]
        if not frames:
            return pd.DataFrame(columns=CANDLE_COLUMNS)
        return pd.concat(frames, ignore_index=True)


def _frame(rows: Sequence[dict[str, Any]], kind: str) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    if kind == "events":
        frame["received_at"] = pd.to_datetime(frame["received_at"], utc=True)
    else:
        for column in ("bucket_start", "bucket_end", "finalized_at"):
            frame[column] = pd.to_datetime(frame[column], utc=True)
    return frame
