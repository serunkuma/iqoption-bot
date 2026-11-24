"""Tick ingestion and storage.

The store is the first component of the engine. It owns the canonical tick
table, preserves arrival order with a sequence, and provides point-in-time price
lookups so that nothing downstream can accidentally read the future.

Exact duplicate ``(timestamp, price)`` rows are kept. The streaming store rejects
late events; batch loads use a stable sort by ``(timestamp, sequence)`` so replay
is deterministic.

Primary format is Parquet. CSV is accepted only as an import path.
"""

from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd

from .domain.timeframes import Tick

TICK_COLUMNS = (
    "tick_id",
    "sequence",
    "timestamp",
    "utc_offset_seconds",
    "price",
    "active_id",
)


class TickStoreError(ValueError):
    """Raised when tick input violates the tick contract."""


def _parse_timestamp(value: str, line_no: int) -> datetime:
    text = (value or "").strip()
    if not text:
        raise TickStoreError(f"line {line_no}: timestamp is empty")
    try:
        timestamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TickStoreError(f"line {line_no}: invalid timestamp {text!r}") from exc
    if timestamp.tzinfo is None:
        raise TickStoreError(
            f"line {line_no}: timestamp must include a UTC offset, got {text!r}"
        )
    return timestamp


def _parse_price(value: str, line_no: int) -> float:
    text = (value or "").strip()
    if not text:
        raise TickStoreError(f"line {line_no}: price is empty")
    try:
        price = float(text)
    except ValueError as exc:
        raise TickStoreError(f"line {line_no}: invalid price {text!r}") from exc
    if price <= 0:
        raise TickStoreError(f"line {line_no}: price must be positive, got {price}")
    return price


def _parse_active_id(value: str | None, line_no: int) -> int | None:
    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError as exc:
        raise TickStoreError(f"line {line_no}: invalid active_id {text!r}") from exc


def load_ticks_csv(
    path: str | Path,
    *,
    active_id: int | None = None,
) -> tuple[list[Tick], dict[str, int]]:
    """Load ticks from CSV, enforce the contract, and preserve row order.

    Returns the ticks and a counter dictionary for the load report.
    """

    source = Path(path)
    if not source.is_file():
        raise TickStoreError(f"tick file not found: {source}")

    ticks: list[Tick] = []
    total_rows = 0

    with source.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise TickStoreError("tick file is empty")
        missing = {"timestamp", "price"} - set(reader.fieldnames)
        if missing:
            raise TickStoreError(f"tick file is missing columns: {sorted(missing)}")

        for line_no, row in enumerate(reader, start=2):
            total_rows += 1
            timestamp = _parse_timestamp(row.get("timestamp", ""), line_no)
            price = _parse_price(row.get("price", ""), line_no)
            row_active_id = _parse_active_id(row.get("active_id"), line_no)

            if active_id is not None and row_active_id is not None and row_active_id != active_id:
                raise TickStoreError(
                    f"line {line_no}: active_id {row_active_id} does not match {active_id}"
                )

            ticks.append(Tick(timestamp, price, row_active_id))

    return ticks, {"total_rows": total_rows}


class TickStore:
    """Immutable, ordered tick table. Duplicate rows are preserved."""

    def __init__(self, frame: pd.DataFrame) -> None:
        required = {"timestamp", "price"}
        missing = required - set(frame.columns)
        if missing:
            raise TickStoreError(f"tick frame is missing columns: {sorted(missing)}")

        frame = frame.copy()
        if frame.empty:
            frame = pd.DataFrame(
                {
                    "timestamp": pd.Series(dtype="datetime64[ns, UTC]"),
                    "sequence": pd.Series(dtype="int64"),
                    "utc_offset_seconds": pd.Series(dtype="int64"),
                    "price": pd.Series(dtype="float64"),
                    "active_id": pd.Series(dtype="Int64"),
                }
            )
            duplicate_rows = 0
        else:
            frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
            frame["price"] = frame["price"].astype("float64")
            if "active_id" in frame.columns:
                frame["active_id"] = pd.array(frame["active_id"], dtype="Int64")
            if "utc_offset_seconds" not in frame.columns:
                frame["utc_offset_seconds"] = 0
            frame["utc_offset_seconds"] = frame["utc_offset_seconds"].astype("int64")
            if "sequence" not in frame.columns:
                frame["sequence"] = np.arange(len(frame), dtype=np.int64)
            frame["sequence"] = frame["sequence"].astype("int64")
            duplicate_rows = int(
                frame.duplicated(subset=["timestamp", "price"]).sum()
            )
            frame = frame.sort_values(
                ["timestamp", "sequence"], kind="mergesort"
            ).reset_index(drop=True)

        frame = frame.drop(columns=["tick_id"], errors="ignore")
        frame.insert(0, "tick_id", np.arange(len(frame), dtype=np.int64))
        self._frame = frame.loc[:, [c for c in TICK_COLUMNS if c in frame.columns]]
        self.stats: dict[str, int] = {
            "total_rows": len(frame),
            "duplicates_dropped": 0,
            "duplicate_rows": duplicate_rows,
            "out_of_order": 0,
        }

    # -- constructors ----------------------------------------------------
    @classmethod
    def empty(cls) -> "TickStore":
        return cls(pd.DataFrame({"timestamp": [], "price": []}))

    @classmethod
    def from_ticks(cls, ticks: Sequence[Tick]) -> "TickStore":
        if not ticks:
            return cls.empty()

        next_sequence = max(
            (tick.sequence for tick in ticks if tick.sequence is not None),
            default=-1,
        ) + 1
        sequences: list[int] = []
        for tick in ticks:
            if tick.sequence is None:
                sequences.append(next_sequence)
                next_sequence += 1
            else:
                sequences.append(tick.sequence)
                next_sequence = max(next_sequence, tick.sequence + 1)

        frame = pd.DataFrame(
            {
                "timestamp": [tick.timestamp for tick in ticks],
                "sequence": sequences,
                "utc_offset_seconds": [
                    int(tick.timestamp.utcoffset().total_seconds())
                    for tick in ticks
                ],
                "price": [tick.price for tick in ticks],
                "active_id": [tick.active_id for tick in ticks],
            }
        )
        return cls(frame)

    @classmethod
    def from_csv(cls, path: str | Path, *, active_id: int | None = None) -> "TickStore":
        ticks, counters = load_ticks_csv(path, active_id=active_id)
        store = cls.from_ticks(ticks)
        store.stats["total_rows"] = counters["total_rows"]
        store.stats["out_of_order"] = _count_out_of_order(ticks)
        return store

    @classmethod
    def from_parquet(cls, path: str | Path) -> "TickStore":
        source = Path(path)
        if not source.is_file():
            raise TickStoreError(f"tick store not found: {source}")
        return cls(pd.read_parquet(source))

    @classmethod
    def from_jsonl(
        cls, path: str | Path, *, active_id: int | None = None
    ) -> "TickStore":
        """Load the receiver's raw JSONL capture.

        Each line is ``{"received_at", "active_id", "price", "payload"}``. Older
        captures may carry ``close`` or nest the price under ``payload``; both
        shapes are accepted so existing files stay readable. The payload is
        preserved on disk but not promoted into the tick table.
        """

        import json

        source = Path(path)
        if not source.is_file():
            raise TickStoreError(f"raw capture not found: {source}")

        def price_from(record: dict) -> object:
            if "price" in record:
                return record["price"]
            if "close" in record:
                return record["close"]
            payload = record.get("payload")
            if isinstance(payload, dict) and "close" in payload:
                return payload["close"]
            raise KeyError("price")

        ticks: list[Tick] = []
        with source.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                except json.JSONDecodeError as exc:
                    raise TickStoreError(
                        f"line {line_no}: invalid JSON record"
                    ) from exc
                if not isinstance(record, dict):
                    raise TickStoreError(f"line {line_no}: record must be an object")
                stamp = record.get("received_at", record.get("timestamp"))
                try:
                    timestamp = _parse_timestamp(str(stamp), line_no)
                    price = _parse_price(str(price_from(record)), line_no)
                except KeyError as exc:
                    raise TickStoreError(
                        f"line {line_no}: missing field {exc.args[0]!r}"
                    ) from exc
                row_active_id = record.get("active_id")
                if active_id is not None and row_active_id is not None:
                    if int(row_active_id) != active_id:
                        raise TickStoreError(
                            f"line {line_no}: active_id {row_active_id} does not match {active_id}"
                        )
                ticks.append(
                    Tick(timestamp, price, None if row_active_id is None else int(row_active_id))
                )

        store = cls.from_ticks(ticks)
        store.stats["total_rows"] = len(ticks)
        store.stats["out_of_order"] = _count_out_of_order(ticks)
        return store

    @classmethod
    def from_stream_events(
        cls, root: str | Path, *, active_id: int | None = None
    ) -> "TickStore":
        """Load the streaming store's hourly event parts as a tick table.

        ``root`` may be the stream store root (``data/stream``) or its
        ``events`` directory. Parts are concatenated and then stable-sorted by
        ``(timestamp, sequence)`` exactly like other batch inputs.
        """

        base = Path(root)
        events_dir = base / "events" if (base / "events").is_dir() else base
        if not events_dir.is_dir():
            raise TickStoreError(f"stream events directory not found: {events_dir}")
        paths = sorted(events_dir.glob("*/*/part-*.parquet"))
        if not paths:
            raise TickStoreError(f"no stream event parts under {events_dir}")

        frames = [pd.read_parquet(path) for path in paths]
        frame = pd.concat(frames, ignore_index=True)
        if "received_at" in frame.columns:
            frame = frame.rename(columns={"received_at": "timestamp"})
        columns = [
            name
            for name in (
                "timestamp",
                "sequence",
                "utc_offset_seconds",
                "price",
                "active_id",
            )
            if name in frame.columns
        ]
        frame = frame.loc[:, columns]
        if active_id is not None and "active_id" in frame.columns:
            frame = frame.loc[frame["active_id"].astype("Int64") == active_id]
        return cls(frame)

    # -- mutations -------------------------------------------------------
    def appended(self, ticks: Sequence[Tick]) -> "TickStore":
        """Return a new store with additional ticks merged in arrival order."""

        if not ticks:
            return self
        return TickStore.from_ticks([*self.as_ticks(), *ticks])

    def write_parquet(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        self._frame.to_parquet(destination, index=False)
        return destination

    # -- access ----------------------------------------------------------
    @property
    def frame(self) -> pd.DataFrame:
        return self._frame

    @property
    def is_empty(self) -> bool:
        return self._frame.empty

    def __len__(self) -> int:
        return len(self._frame)

    @property
    def epochs(self) -> np.ndarray:
        return self._frame["timestamp"].astype("int64").to_numpy(dtype=np.float64) / 1e9

    @property
    def prices(self) -> np.ndarray:
        return self._frame["price"].to_numpy(dtype=np.float64)

    def as_ticks(self) -> list[Tick]:
        return [
            Tick(
                row.timestamp.to_pydatetime(),
                float(row.price),
                _as_int(row.active_id),
                int(row.sequence),
            )
            for row in self._frame.itertuples(index=False)
        ]

    def between(self, start: datetime, end: datetime) -> "TickStore":
        mask = (self._frame["timestamp"] >= start) & (self._frame["timestamp"] <= end)
        return TickStore(self._frame.loc[mask])

    def last_price_at(self, timestamp: datetime) -> float | None:
        """Return the last price at or before ``timestamp`` without lookahead."""

        if self._frame.empty:
            return None
        moment = pd.Timestamp(timestamp).tz_convert("UTC") if pd.Timestamp(timestamp).tzinfo else pd.Timestamp(timestamp, tz="UTC")
        mask = self._frame["timestamp"] <= moment
        if not mask.any():
            return None
        return float(self._frame.loc[mask, "price"].iloc[-1])

    def price_at(self, timestamps: Iterable[datetime]) -> pd.DataFrame:
        """Point-in-time merge: each query gets the last price at or before it.

        Returns a frame with ``query_timestamp`` and ``price`` columns. Queries
        before the first tick get a null price.
        """

        queries = pd.DataFrame(
            {"query_timestamp": pd.to_datetime(list(timestamps), utc=True)}
        ).sort_values("query_timestamp", kind="mergesort")
        right = self._frame.loc[:, ["timestamp", "price"]].sort_values(
            "timestamp", kind="mergesort"
        )
        merged = pd.merge_asof(
            queries,
            right,
            left_on="query_timestamp",
            right_on="timestamp",
            direction="backward",
            allow_exact_matches=True,
        )
        return merged.loc[:, ["query_timestamp", "price"]].reset_index(drop=True)


def _count_out_of_order(ticks: Sequence[Tick]) -> int:
    return sum(
        1
        for previous, current in zip(ticks, ticks[1:])
        if current.timestamp < previous.timestamp
    )


def _as_int(value: object) -> int | None:
    if value is None or pd.isna(value):
        return None
    return int(value)
