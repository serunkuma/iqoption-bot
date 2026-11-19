"""Snapshot-horizon direction labels.

A label is attached to a *snapshot*, not to every tick. For each snapshot and
horizon the exit is the first tick at or after ``entry_time + horizon`` inside
the tolerance window. Ties and missing exits stay explicit: they are never
silently mapped to a direction and are excluded from directional training by
default.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from engine.sampler import Snapshot

LABEL_VERSION = "snapshot-horizon-v1"

LABEL_COLUMNS = (
    "snapshot_id",
    "timestamp",
    "active_id",
    "entry_timestamp",
    "entry_price",
    "horizon_seconds",
    "exit_timestamp",
    "exit_price",
    "exit_delay_seconds",
    "label",
    "usable",
    "label_version",
)


def classify_direction(entry_price: float, exit_price: float) -> str:
    """Return ``call``, ``put``, or ``tie``.

    A tie is returned explicitly; callers decide whether it is usable.
    """

    if exit_price > entry_price:
        return "call"
    if exit_price < entry_price:
        return "put"
    return "tie"


def is_usable(label: str, tie_policy: str) -> bool:
    if label in {"call", "put"}:
        return True
    if label == "tie" and tie_policy == "keep":
        return True
    return False


def snapshot_label_rows(snapshots: "list[Snapshot]", tie_policy: str) -> list[dict]:
    """Flatten snapshots into long-format label rows."""

    rows: list[dict] = []
    for snapshot in snapshots:
        for horizon, outcome in snapshot.outcomes.items():
            label = outcome.label
            rows.append(
                {
                    "snapshot_id": snapshot.snapshot_id,
                    "timestamp": snapshot.snapshot_time.isoformat(),
                    "active_id": snapshot.active_id,
                    "entry_timestamp": (
                        snapshot.entry_timestamp.isoformat()
                        if snapshot.entry_timestamp is not None
                        else None
                    ),
                    "entry_price": snapshot.entry_price,
                    "horizon_seconds": horizon,
                    "exit_timestamp": (
                        outcome.exit_timestamp.isoformat()
                        if outcome.exit_timestamp is not None
                        else None
                    ),
                    "exit_price": outcome.exit_price,
                    "exit_delay_seconds": outcome.exit_delay_seconds,
                    "label": label,
                    "usable": int(is_usable(label, tie_policy)),
                    "label_version": LABEL_VERSION,
                }
            )
    return rows
