"""Tick loading, validation, and CSV output helpers."""

from __future__ import annotations

import csv
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from .timeframes import Tick


class TickDataError(ValueError):
    """Raised when the tick input file violates the tick contract."""


@dataclass
class TickSet:
    ticks: list[Tick] = field(default_factory=list)
    total_rows: int = 0
    duplicates_dropped: int = 0
    out_of_order: int = 0

    def __len__(self) -> int:
        return len(self.ticks)


def _parse_timestamp(value: str, line_no: int) -> datetime:
    text = (value or "").strip()
    if not text:
        raise TickDataError(f"line {line_no}: timestamp is empty")
    try:
        timestamp = datetime.fromisoformat(text)
    except ValueError as exc:
        raise TickDataError(f"line {line_no}: invalid timestamp {text!r}") from exc
    if timestamp.tzinfo is None:
        raise TickDataError(
            f"line {line_no}: timestamp must include a UTC offset, got {text!r}"
        )
    return timestamp


def _parse_price(value: str, line_no: int) -> float:
    text = (value or "").strip()
    if not text:
        raise TickDataError(f"line {line_no}: price is empty")
    try:
        price = float(text)
    except ValueError as exc:
        raise TickDataError(f"line {line_no}: invalid price {text!r}") from exc
    if price <= 0:
        raise TickDataError(f"line {line_no}: price must be positive, got {price}")
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
        raise TickDataError(f"line {line_no}: invalid active_id {text!r}") from exc


def load_ticks(
    path: str | Path,
    *,
    active_id: int | None = None,
) -> TickSet:
    """Load ticks from CSV, enforce the contract, sort, and deduplicate.

    Required columns: ``timestamp`` and ``price``. An optional ``active_id``
    column must match the configured instrument when both are present.
    """

    source = Path(path)
    if not source.is_file():
        raise TickDataError(f"tick file not found: {source}")

    ticks: list[Tick] = []
    total_rows = 0

    with source.open("r", newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise TickDataError("tick file is empty")
        missing = {"timestamp", "price"} - set(reader.fieldnames)
        if missing:
            raise TickDataError(f"tick file is missing columns: {sorted(missing)}")

        for line_no, row in enumerate(reader, start=2):
            total_rows += 1
            timestamp = _parse_timestamp(row.get("timestamp", ""), line_no)
            price = _parse_price(row.get("price", ""), line_no)
            row_active_id = _parse_active_id(row.get("active_id"), line_no)

            if active_id is not None and row_active_id is not None and row_active_id != active_id:
                raise TickDataError(
                    f"line {line_no}: active_id {row_active_id} does not match {active_id}"
                )

            ticks.append(Tick(timestamp, price, row_active_id))

    out_of_order = sum(
        1
        for previous, current in zip(ticks, ticks[1:])
        if current.timestamp < previous.timestamp
    )
    ticks.sort(key=lambda tick: tick.timestamp)

    deduped: list[Tick] = []
    seen: set[tuple[datetime, float]] = set()
    for tick in ticks:
        key = (tick.timestamp, tick.price)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(tick)

    return TickSet(
        ticks=deduped,
        total_rows=total_rows,
        duplicates_dropped=len(ticks) - len(deduped),
        out_of_order=out_of_order,
    )


def write_rows(path: str | Path, rows: list[dict], columns: tuple[str, ...]) -> None:
    """Write rows to CSV, creating parent directories as needed."""

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    with destination.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(columns))
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column) for column in columns})
