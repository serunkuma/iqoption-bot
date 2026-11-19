"""Flat-sizing backtest harness.

Replays a labelled dataset through the model suite, the EV router, and the
paper broker, respecting a hard one-open-position limit. This is the only
place where a trade is simulated; live execution reuses the same broker.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from .config import Config
from .execution import OPEN, PaperBroker, Trade
from .models import ModelSuite
from .router import SignalProposal, route
from .sampler import HorizonOutcome, Snapshot

MAX_TIME = datetime.max.replace(tzinfo=timezone.utc)


@dataclass
class BacktestResult:
    broker: PaperBroker
    trades: list[Trade]
    skipped_overlap: int = 0
    skipped_no_model: int = 0
    skipped_below_hurdle: int = 0
    routed: int = 0

    def summary(self) -> dict[str, float | int]:
        return {
            "snapshots": self.routed,
            "skipped_overlap": self.skipped_overlap,
            "skipped_no_model": self.skipped_no_model,
            "skipped_below_hurdle": self.skipped_below_hurdle,
            **self.broker.summary(),
        }


def _stub_snapshot(group: pd.DataFrame, snapshot_id: int) -> Snapshot:
    """Rebuild the minimum snapshot the broker needs from dataset rows."""

    first = group.iloc[0]
    entry_timestamp = pd.Timestamp(first["entry_timestamp"]).to_pydatetime()
    entry_price = float(first["entry_price"])
    snapshot_time = pd.Timestamp(first["timestamp"]).to_pydatetime()

    outcomes: dict[int, HorizonOutcome] = {}
    for row in group.itertuples(index=False):
        exit_price = None if pd.isna(row.exit_price) else float(row.exit_price)
        exit_timestamp = (
            None
            if pd.isna(row.exit_timestamp)
            else pd.Timestamp(row.exit_timestamp).to_pydatetime()
        )
        outcomes[int(row.horizon_seconds)] = HorizonOutcome(
            horizon_seconds=int(row.horizon_seconds),
            exit_timestamp=exit_timestamp,
            exit_price=exit_price,
            exit_delay_seconds=(
                None if pd.isna(row.exit_delay_seconds) else float(row.exit_delay_seconds)
            ),
            label=str(row.label),
        )

    return Snapshot(
        snapshot_id=int(snapshot_id),
        active_id=int(first["active_id"]),
        snapshot_time=snapshot_time,
        forming_start=snapshot_time,
        completed_bars=(),
        forming_bar=None,  # type: ignore[arg-type]
        price=float(first["price"]),
        window_ticks=0,
        entry_timestamp=entry_timestamp,
        entry_price=entry_price,
        entry_delay_seconds=None,
        outcomes=outcomes,
    )


def run_backtest(dataset: pd.DataFrame, suite: ModelSuite, config: Config) -> BacktestResult:
    """Replay the held-out evaluation slice through router and paper broker.

    Only snapshots with precomputed, out-of-sample evaluation probabilities are
    traded. The suite's estimators are never asked to predict a snapshot they
    were trained on, so the replay cannot flatter itself.
    """

    result = BacktestResult(broker=PaperBroker(config), trades=[])
    if dataset.empty or not suite.models:
        return result

    if suite.evaluation.empty:
        return result

    grouped = dataset.groupby("snapshot_id", sort=True)

    for snapshot_id, group in grouped:
        group = group.sort_values("timestamp")
        stub = _stub_snapshot(group, int(snapshot_id))
        if stub.entry_timestamp is None:
            continue

        # Time advances even when a snapshot is not evaluated.
        result.broker.resolve_due(stub.entry_timestamp)

        probabilities = suite.evaluate_snapshot(int(snapshot_id))
        if not probabilities:
            result.skipped_no_model += 1
            continue

        result.routed += 1
        result.broker.register_outcomes(stub)

        proposal: SignalProposal = route(probabilities, config)
        if proposal.reason == "no_trade_below_hurdle":
            result.skipped_below_hurdle += 1

        if proposal.actionable and not result.broker.can_open(stub.entry_timestamp):
            result.skipped_overlap += 1
            continue

        trade = result.broker.open(proposal, stub)
        if trade is not None:
            result.trades.append(trade)

    result.broker.resolve_due(MAX_TIME)
    result.trades = list(result.broker.trades)
    return result
