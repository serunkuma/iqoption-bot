"""The tick event contract for the streaming store.

One event is one accepted price update from the extension. Events are kept in
arrival order and carry a monotonic ``sequence``; equal timestamps and repeated
prices are never collapsed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Mapping


class EventError(ValueError):
    """Raised when a payload cannot become a valid tick event."""


@dataclass(frozen=True)
class TickEvent:
    """One accepted price update."""

    sequence: int
    received_at: datetime
    active_id: int
    price: float
    utc_offset_seconds: int = 0
    raw: Mapping[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.sequence < 0:
            raise EventError("sequence must be non-negative")
        if self.received_at.tzinfo is None:
            raise EventError("received_at must be timezone-aware")
        if isinstance(self.price, bool) or not isinstance(self.price, (int, float)):
            raise EventError("price must be numeric")
        if self.price <= 0:
            raise EventError("price must be positive")
        if isinstance(self.active_id, bool) or not isinstance(self.active_id, int):
            raise EventError("active_id must be an integer")
        if self.active_id < 0:
            raise EventError("active_id must be non-negative")

    @property
    def epoch(self) -> float:
        return self.received_at.timestamp()

    @classmethod
    def from_payload(
        cls,
        sequence: int,
        active_id: Any,
        payload: Mapping[str, Any],
    ) -> "TickEvent":
        """Build an event from the receiver's accepted payload.

        ``received_at`` is the local receipt stamp; the broker's ``at`` field is
        never promoted to a timestamp. ``close`` is the price field the
        extension forwards today. The whole payload is preserved so frame
        semantics can be re-verified later.
        """

        if not isinstance(payload, Mapping):
            raise EventError("payload must be a mapping")

        stamp = payload.get("received_at")
        if not isinstance(stamp, str):
            raise EventError("payload is missing received_at")
        try:
            moment = datetime.fromisoformat(stamp)
        except ValueError as exc:
            raise EventError(f"invalid received_at: {stamp!r}") from exc
        if moment.tzinfo is None:
            raise EventError("received_at must include a UTC offset")

        price = payload.get("close")
        if isinstance(price, bool) or not isinstance(price, (int, float)):
            raise EventError("payload is missing a numeric close price")

        try:
            instrument = int(active_id)
        except (TypeError, ValueError) as exc:
            raise EventError(f"invalid active_id: {active_id!r}") from exc

        offset = int(moment.utcoffset().total_seconds())
        return cls(
            sequence=sequence,
            received_at=moment,
            active_id=instrument,
            price=float(price),
            utc_offset_seconds=offset,
            raw=dict(payload),
        )
