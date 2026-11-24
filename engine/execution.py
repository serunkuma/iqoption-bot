"""Paper execution and trade resolution.

This component turns a routed proposal into a paper trade, holds it open until
its expiry, and resolves it against the recorded exit price. Live and demo
adapters are deliberately unimplemented; the mode flag is validated and then
rejected.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from .config import Config
from .router import SignalProposal
from .sampler import Snapshot


class ExecutionError(RuntimeError):
    """Raised when execution is requested in an unsupported mode."""


OPEN = "open"
WON = "won"
LOST = "lost"
VOID = "void"


@dataclass
class Trade:
    trade_id: int
    snapshot_id: int
    active_id: int
    direction: str
    horizon_seconds: int
    stake: float
    payout: float
    entry_timestamp: datetime
    entry_price: float
    expiry_timestamp: datetime
    expected_value: float
    status: str = OPEN
    exit_price: float | None = None
    resolved_at: datetime | None = None
    pnl: float | None = None
    reason: str = ""

    def to_dict(self) -> dict:
        """Serialize to a JSON-safe record."""

        record = asdict(self)
        for key in ("entry_timestamp", "expiry_timestamp", "resolved_at"):
            value = record.get(key)
            if isinstance(value, datetime):
                record[key] = value.isoformat()
        return record

    @classmethod
    def from_dict(cls, record: dict) -> "Trade":
        """Rebuild a trade from a journal record."""

        def moment(value):
            if value is None:
                return None
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(str(value))

        return cls(
            trade_id=int(record["trade_id"]),
            snapshot_id=int(record["snapshot_id"]),
            active_id=int(record["active_id"]),
            direction=str(record["direction"]),
            horizon_seconds=int(record["horizon_seconds"]),
            stake=float(record["stake"]),
            payout=float(record["payout"]),
            entry_timestamp=moment(record["entry_timestamp"]),
            entry_price=float(record["entry_price"]),
            expiry_timestamp=moment(record["expiry_timestamp"]),
            expected_value=float(record["expected_value"]),
            status=str(record.get("status", OPEN)),
            exit_price=(
                None
                if record.get("exit_price") is None
                else float(record["exit_price"])
            ),
            resolved_at=moment(record.get("resolved_at")),
            pnl=None if record.get("pnl") is None else float(record["pnl"]),
            reason=str(record.get("reason", "")),
        )

    def resolve(self, exit_price: float, resolved_at: datetime | None = None) -> "Trade":
        """Resolve the trade against an exit price.

        A tie is a void trade: the stake is returned and PnL is zero. The model
        never sees a tie as a directional outcome, so voiding is consistent.
        """

        if self.status != OPEN:
            raise ExecutionError(f"trade {self.trade_id} is already resolved")
        self.exit_price = exit_price
        self.resolved_at = resolved_at or self.expiry_timestamp
        if exit_price == self.entry_price:
            self.status = VOID
            self.pnl = 0.0
        elif (exit_price > self.entry_price) == (self.direction == "call"):
            self.status = WON
            self.pnl = self.stake * self.payout
        else:
            self.status = LOST
            self.pnl = -self.stake
        return self


@dataclass
class PaperBroker:
    """Paper broker with a hard one-open-trade limit per instrument."""

    config: Config
    trades: list[Trade] = field(default_factory=list)
    _next_id: int = 0
    _outcome_lookup: dict[int, dict] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.config.execution.mode != "paper":
            raise ExecutionError(
                f"execution.mode={self.config.execution.mode!r} is not implemented; "
                "only 'paper' is supported"
            )

    @property
    def open_trades(self) -> list[Trade]:
        return [trade for trade in self.trades if trade.status == OPEN]

    def restore(self, trades: list[Trade]) -> None:
        """Replace the in-memory trade book after a restart."""

        self.trades = list(trades)
        self._next_id = max((trade.trade_id for trade in trades), default=-1) + 1

    def can_open(self, now: datetime) -> bool:
        # A trade past its expiry carries no market risk, even if it has not
        # been resolved yet; only genuinely live positions count.
        live = [trade for trade in self.open_trades if trade.expiry_timestamp > now]
        return len(live) < self.config.execution.max_open_trades

    def open(self, proposal: SignalProposal, snapshot: Snapshot) -> Trade | None:
        """Open a paper trade if the proposal is actionable and a slot is free."""

        if not proposal.actionable:
            return None
        if snapshot.entry_timestamp is None or snapshot.entry_price is None:
            return None
        if not self.can_open(snapshot.entry_timestamp):
            return None

        assert proposal.horizon_seconds is not None
        assert proposal.payout is not None
        assert proposal.expected_value is not None

        trade = Trade(
            trade_id=self._next_id,
            snapshot_id=snapshot.snapshot_id,
            active_id=snapshot.active_id,
            direction=proposal.direction,
            horizon_seconds=proposal.horizon_seconds,
            stake=self.config.execution.stake,
            payout=proposal.payout,
            entry_timestamp=snapshot.entry_timestamp,
            entry_price=snapshot.entry_price,
            expiry_timestamp=snapshot.entry_timestamp
            + timedelta(seconds=proposal.horizon_seconds),
            expected_value=proposal.expected_value,
            reason=proposal.reason,
        )
        self._next_id += 1
        self.trades.append(trade)
        return trade

    def resolve_due(self, upto: datetime) -> list[Trade]:
        """Resolve open trades whose expiry has passed and whose outcome is known."""

        resolved: list[Trade] = []
        for trade in self.open_trades:
            if trade.expiry_timestamp > upto:
                continue
            outcome = self._outcome_lookup.get(trade.snapshot_id, {}).get(
                trade.horizon_seconds
            )
            if outcome is None or outcome.exit_price is None:
                continue
            trade.resolve(outcome.exit_price)
            resolved.append(trade)
        return resolved

    def register_outcomes(self, snapshot: Snapshot) -> None:
        """Attach a snapshot's known expiry outcomes for later resolution."""

        self._outcome_lookup[snapshot.snapshot_id] = snapshot.outcomes

    def realized_pnl(self, on_date=None) -> float:
        """Sum resolved PnL, optionally limited to one UTC date."""

        total = 0.0
        for trade in self.trades:
            if trade.pnl is None:
                continue
            if on_date is not None:
                if trade.resolved_at is None or trade.resolved_at.date() != on_date:
                    continue
            total += trade.pnl
        return total

    # -- reporting -------------------------------------------------------
    def summary(self) -> dict[str, float | int]:
        closed = [trade for trade in self.trades if trade.status != OPEN]
        pnl = sum(trade.pnl or 0.0 for trade in closed)
        wins = sum(1 for trade in closed if trade.status == WON)
        return {
            "trades": len(self.trades),
            "closed": len(closed),
            "open": len(self.open_trades),
            "wins": wins,
            "losses": sum(1 for trade in closed if trade.status == LOST),
            "voids": sum(1 for trade in closed if trade.status == VOID),
            "pnl": round(pnl, 6),
            "win_rate": round(wins / len(closed), 6) if closed else 0.0,
        }


@dataclass
class TradeJournal:
    """Append-only JSONL journal of paper trades."""

    path: Path

    def append(self, trade: Trade) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = trade.to_dict()
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")

    def append_many(self, trades: list[Trade]) -> None:
        for trade in trades:
            self.append(trade)

    def load(self) -> list[Trade]:
        """Return the latest record for each trade id.

        The journal appends a record when a trade opens and again when it
        resolves. A malformed journal raises instead of silently resetting the
        runtime gates to a clean state.
        """

        if not self.path.is_file():
            return []
        latest: dict[int, Trade] = {}
        with self.path.open("r", encoding="utf-8") as handle:
            for line_no, line in enumerate(handle, start=1):
                text = line.strip()
                if not text:
                    continue
                try:
                    record = json.loads(text)
                    trade = Trade.from_dict(record)
                except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
                    raise ExecutionError(
                        f"trade journal {self.path} line {line_no} is unreadable"
                    ) from exc
                latest[trade.trade_id] = trade
        return [latest[trade_id] for trade_id in sorted(latest)]
