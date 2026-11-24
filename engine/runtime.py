"""Candle-close runtime inference and paper decisions.

The runtime consumes the streaming store's ingest results. It never computes
features from a partial candle: a decision is made only when the store reports a
closed candle, and only when seven contiguous closed candles are available.

Model output is surrounded by deterministic gates. The artifact is validated at
startup and pinned for the session; payouts come from configuration; one open
trade, a cooldown, and a daily loss stop are enforced before any proposal is
allowed to open. Execution is paper-only.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from .config import Config
from .execution import OPEN, PaperBroker, Trade, TradeJournal
from .features import CORE_FEATURES, compute_features
from .models import ModelArtifactError, ModelSuite
from .router import BELOW_HURDLE, MISSING_PAYOUT, NO_MODEL, SignalProposal, route
from .sampler import BarSlice, Snapshot
from .stream import ClosedCandle, IngestResult, StreamStore

WARMUP = "warmup"
TRADE_OPEN = "trade_open"
COOLDOWN = "cooldown"
DAILY_STOP = "daily_stop"
NO_ENTRY_TICK = "no_entry_tick"
STORE_DEGRADED = "store_degraded"
ARTIFACT_INVALID = "artifact_invalid"
WINDOW_INCOMPLETE = "window_incomplete"
BROKER_REJECTED = "broker_rejected"
GAP = "gap"
SHUTDOWN = "shutdown"

ROUTER_REASONS = {
    NO_MODEL: "no_model",
    MISSING_PAYOUT: "no_payout",
    BELOW_HURDLE: "below_hurdle",
}


@dataclass
class PendingEntry:
    """A decision waiting for the first tick at or after its entry target."""

    candle: ClosedCandle
    snapshot: Snapshot
    proposal: SignalProposal
    values: list[float | None]
    probabilities: dict[int, float]
    target_epoch: float
    deadline_epoch: float
    decision_epoch: float
    latency_ms: float


@dataclass
class RuntimeCounters:
    decisions: int = 0
    trades: int = 0
    no_trades: int = 0
    warmup: int = 0
    trade_open: int = 0
    cooldown: int = 0
    daily_stop: int = 0
    no_entry_tick: int = 0
    store_degraded: int = 0
    shadow: int = 0
    resolved: int = 0
    gap_closes: int = 0

    def as_dict(self) -> dict[str, int]:
        return {
            "decisions": self.decisions,
            "trades": self.trades,
            "no_trades": self.no_trades,
            "warmup": self.warmup,
            "trade_open": self.trade_open,
            "cooldown": self.cooldown,
            "daily_stop": self.daily_stop,
            "no_entry_tick": self.no_entry_tick,
            "store_degraded": self.store_degraded,
            "shadow": self.shadow,
            "resolved": self.resolved,
            "gap_closes": self.gap_closes,
        }


class DecisionJournal:
    """Append-only JSONL decision journal, rotated by UTC hour."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def path_for(self, moment: datetime) -> Path:
        return self.root / moment.strftime("%Y-%m-%d") / f"{moment.strftime('%H')}.jsonl"

    def append(self, record: dict[str, Any]) -> Path:
        moment = datetime.fromisoformat(str(record["candle_closed_at"]))
        path = self.path_for(moment)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, default=str) + "\n")
        return path


class RuntimeEngine:
    """Turn closed candles into journaled paper decisions."""

    def __init__(
        self,
        store: StreamStore,
        suite: ModelSuite,
        config: Config,
        *,
        decisions_dir: str | Path | None = None,
        trade_journal: TradeJournal | None = None,
        shadow: bool = False,
    ) -> None:
        problems = suite.validate(config)
        if problems:
            raise ModelArtifactError(
                "model artifact is incompatible: " + "; ".join(problems)
            )

        self.store = store
        self.suite = suite
        self.config = config
        self.shadow = shadow
        self.broker = PaperBroker(config)
        self.journal = DecisionJournal(
            decisions_dir
            if decisions_dir is not None
            else Path(store.sink.root) / "decisions"
        )
        self.trade_journal = trade_journal
        self.pending: PendingEntry | None = None
        self.last_close_epoch: float | None = None
        self.last_decision_bucket: int | None = None
        self.decision_id = 0
        self.counters = RuntimeCounters()
        self._restore_trades()

    def _restore_trades(self) -> None:
        """Reload paper trades so the risk gates survive a restart.

        A shadow session starts with an empty book: prior paper positions must
        not suppress shadow predictions.
        """

        if self.trade_journal is None or self.shadow:
            return
        restored = self.trade_journal.load()
        if not restored:
            return
        self.broker.restore(restored)
        resolved = [
            trade.resolved_at.timestamp()
            for trade in restored
            if trade.resolved_at is not None
        ]
        if resolved:
            self.last_close_epoch = max(resolved)

    # -- ingestion hook --------------------------------------------------
    def on_ingest(self, result: IngestResult) -> None:
        """Process one accepted store result."""

        if not result.accepted or result.event is None:
            return
        started = time.perf_counter()
        event = result.event

        self._resolve_due(event)

        if result.closed:
            if len(result.closed) > 1:
                self.counters.gap_closes += len(result.closed) - 1
            self._decide(result.closed[-1], event, started)

        if self.pending is not None:
            self._try_entry(event)

    # -- decisions -------------------------------------------------------
    def _decide(
        self, candle: ClosedCandle, event, started: float
    ) -> None:
        if self.last_decision_bucket == candle.bucket_key:
            return
        self.last_decision_bucket = candle.bucket_key
        self.counters.decisions += 1
        decision_epoch = candle.end_epoch
        latency_ms = (time.perf_counter() - started) * 1000.0

        if self.store.degraded:
            self.counters.store_degraded += 1
            self._journal(
                candle, [], {}, latency_ms, action="no_trade", reason=STORE_DEGRADED
            )
            return

        if not self.store.window.ready:
            self.counters.warmup += 1
            self._journal(
                candle, [], {}, latency_ms, action="no_trade", reason=WARMUP
            )
            return

        bars = tuple(
            BarSlice(
                bucket_key=closed.bucket_key,
                start_epoch=closed.start_epoch,
                epochs=closed.epochs,
                prices=closed.prices,
            )
            for closed in self.store.window.candles
        )
        if any(not bar.prices for bar in bars):
            self._journal(
                candle,
                [],
                {},
                latency_ms,
                action="no_trade",
                reason=WINDOW_INCOMPLETE,
            )
            return

        snapshot = Snapshot(
            snapshot_id=candle.bucket_key,
            active_id=candle.active_id,
            snapshot_time=candle.bucket_end,
            completed_bars=bars,
            price=candle.close,
            window_ticks=sum(bar.tick_count for bar in bars),
            entry_timestamp=None,
            entry_price=None,
            entry_delay_seconds=None,
            outcomes={},
            utc_offset_seconds=candle.utc_offset_seconds,
        )
        vector = compute_features(snapshot, self.config)
        values = vector.as_list()
        probabilities = self.suite.predict_vector(values)
        proposal = route(probabilities, self.config)

        if not proposal.actionable:
            reason = ROUTER_REASONS.get(proposal.reason, proposal.reason)
            self._journal(
                candle,
                values,
                probabilities,
                latency_ms,
                action="no_trade",
                reason=reason,
                proposal=proposal,
            )
            return

        gate = self._gate(decision_epoch)
        if gate is not None:
            self.counters.no_trades += 1
            self._journal(
                candle,
                values,
                probabilities,
                latency_ms,
                action="no_trade",
                reason=gate,
                proposal=proposal,
            )
            return

        if self.shadow:
            self.counters.shadow += 1
            self._journal(
                candle,
                values,
                probabilities,
                latency_ms,
                action="shadow",
                reason=None,
                proposal=proposal,
            )
            return

        target = decision_epoch + self.config.snapshot.entry_delay_ms / 1000.0
        deadline = target + self.config.snapshot.entry_tolerance_seconds
        self.pending = PendingEntry(
            candle=candle,
            snapshot=snapshot,
            proposal=proposal,
            values=values,
            probabilities=probabilities,
            target_epoch=target,
            deadline_epoch=deadline,
            decision_epoch=decision_epoch,
            latency_ms=latency_ms,
        )

    def _gate(self, decision_epoch: float) -> str | None:
        now = datetime.fromtimestamp(decision_epoch, tz=timezone.utc)
        if not self.broker.can_open(now):
            self.counters.trade_open += 1
            return TRADE_OPEN
        cooldown = self.config.execution.cooldown_seconds
        if (
            cooldown > 0
            and self.last_close_epoch is not None
            and decision_epoch - self.last_close_epoch < cooldown
        ):
            self.counters.cooldown += 1
            return COOLDOWN
        limit = self.config.execution.daily_loss_limit
        if limit is not None:
            realized = self.broker.realized_pnl(now.date())
            if realized <= -limit:
                self.counters.daily_stop += 1
                return DAILY_STOP
        return None

    def _try_entry(self, event) -> None:
        pending = self.pending
        if pending is None:
            return
        if event.epoch < pending.target_epoch:
            return
        if event.epoch > pending.deadline_epoch:
            self.counters.no_entry_tick += 1
            self._journal(
                pending.candle,
                pending.values,
                pending.probabilities,
                pending.latency_ms,
                action="no_trade",
                reason=NO_ENTRY_TICK,
                proposal=pending.proposal,
            )
            self.pending = None
            return

        snapshot = replace(
            pending.snapshot,
            entry_timestamp=event.received_at,
            entry_price=event.price,
            entry_delay_seconds=event.epoch - pending.decision_epoch,
        )
        trade = self.broker.open(pending.proposal, snapshot)
        if trade is None:
            self.counters.no_trades += 1
            self._journal(
                pending.candle,
                pending.values,
                pending.probabilities,
                pending.latency_ms,
                action="no_trade",
                reason=BROKER_REJECTED,
                proposal=pending.proposal,
            )
            self.pending = None
            return

        self.counters.trades += 1
        if self.trade_journal is not None:
            self.trade_journal.append(trade)
        self._journal(
            pending.candle,
            pending.values,
            pending.probabilities,
            pending.latency_ms,
            action="trade",
            reason=None,
            proposal=pending.proposal,
            trade=trade,
        )
        self.pending = None

    # -- trade lifecycle -------------------------------------------------
    def _resolve_due(self, event) -> None:
        for trade in list(self.broker.open_trades):
            if event.epoch < trade.expiry_timestamp.timestamp():
                continue
            trade.resolve(event.price, event.received_at)
            self.last_close_epoch = event.epoch
            self.counters.resolved += 1
            if self.trade_journal is not None:
                self.trade_journal.append(trade)

    # -- journal ---------------------------------------------------------
    def _journal(
        self,
        candle: ClosedCandle,
        values: list[float | None],
        probabilities: dict[int, float],
        latency_ms: float,
        *,
        action: str,
        reason: str | None,
        proposal: SignalProposal | None = None,
        trade: Trade | None = None,
    ) -> None:
        self.decision_id += 1
        record = {
            "decision_id": self.decision_id,
            "candle_closed_at": candle.bucket_end.isoformat(),
            "sequence": candle.last_sequence,
            "artifact_id": self.suite.artifact_id,
            "feature_version": self.config.feature_version,
            "core_feature_version": self.config.core_feature_version,
            "decision_version": self.config.decision_version,
            "values": values,
            "probabilities": {
                str(horizon): probability
                for horizon, probability in sorted(probabilities.items())
            },
            "action": action,
            "direction": proposal.direction if proposal is not None else None,
            "horizon": proposal.horizon_seconds if proposal is not None else None,
            "ev": proposal.expected_value if proposal is not None else None,
            "reason": reason,
            "trade_id": trade.trade_id if trade is not None else None,
            "latency_ms": round(latency_ms, 3),
        }
        self.journal.append(record)
        if action == "no_trade":
            self.counters.no_trades += 1

    # -- lifecycle -------------------------------------------------------
    def close(self) -> dict[str, int]:
        if self.pending is not None:
            pending = self.pending
            self._journal(
                pending.candle,
                pending.values,
                pending.probabilities,
                pending.latency_ms,
                action="no_trade",
                reason=SHUTDOWN,
                proposal=pending.proposal,
            )
            self.pending = None
        return self.counters.as_dict()

    @property
    def open_trades(self) -> list[Trade]:
        return self.broker.open_trades
