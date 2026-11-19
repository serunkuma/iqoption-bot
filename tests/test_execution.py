import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from engine.execution import LOST, OPEN, VOID, WON, ExecutionError, PaperBroker, TradeJournal
from engine.router import SignalProposal
from engine.sampler import Snapshot

from .helpers import BASE, make_config


def stub_snapshot(entry_price: float = 1.0, snapshot_id: int = 0, offset: int = 0) -> Snapshot:
    entry = BASE + timedelta(seconds=offset)
    return Snapshot(
        snapshot_id=snapshot_id,
        active_id=0,
        snapshot_time=entry,
        forming_start=entry,
        completed_bars=(),
        forming_bar=None,  # type: ignore[arg-type]
        price=entry_price,
        window_ticks=0,
        entry_timestamp=entry,
        entry_price=entry_price,
        entry_delay_seconds=0.25,
        outcomes={},
    )


def proposal(
    direction: str = "call", horizon: int = 60, probability: float = 0.60
) -> SignalProposal:
    return SignalProposal(
        horizon_seconds=horizon,
        direction=direction,
        probability=probability,
        payout=0.80,
        expected_value=probability * 1.8 - 1,
        reason="selected",
    )


class PaperBrokerTests(unittest.TestCase):
    def test_only_paper_mode_is_supported(self) -> None:
        with self.assertRaises(ExecutionError):
            PaperBroker(make_config(execution={"mode": "demo"}))

    def test_non_actionable_proposal_opens_nothing(self) -> None:
        broker = PaperBroker(make_config())
        rejected = SignalProposal(60, "no_trade", 0.5, 0.8, -0.1, "no_trade_below_hurdle")

        self.assertIsNone(broker.open(rejected, stub_snapshot()))
        self.assertEqual(broker.trades, [])

    def test_call_wins_when_exit_is_higher(self) -> None:
        broker = PaperBroker(make_config())
        trade = broker.open(proposal("call"), stub_snapshot(1.0))
        assert trade is not None
        trade.resolve(1.1)

        self.assertEqual(trade.status, WON)
        self.assertAlmostEqual(trade.pnl or 0.0, 0.80)

    def test_call_loses_when_exit_is_lower(self) -> None:
        broker = PaperBroker(make_config())
        trade = broker.open(proposal("call"), stub_snapshot(1.0))
        assert trade is not None
        trade.resolve(0.9)

        self.assertEqual(trade.status, LOST)
        self.assertAlmostEqual(trade.pnl or 0.0, -1.0)

    def test_put_wins_when_exit_is_lower(self) -> None:
        broker = PaperBroker(make_config())
        trade = broker.open(proposal("put"), stub_snapshot(1.0))
        assert trade is not None
        trade.resolve(0.9)

        self.assertEqual(trade.status, WON)

    def test_tie_is_void_and_returns_the_stake(self) -> None:
        broker = PaperBroker(make_config())
        trade = broker.open(proposal("call"), stub_snapshot(1.0))
        assert trade is not None
        trade.resolve(1.0)

        self.assertEqual(trade.status, VOID)
        self.assertEqual(trade.pnl, 0.0)

    def test_a_resolved_trade_cannot_be_resolved_twice(self) -> None:
        broker = PaperBroker(make_config())
        trade = broker.open(proposal("call"), stub_snapshot(1.0))
        assert trade is not None
        trade.resolve(1.1)

        with self.assertRaises(ExecutionError):
            trade.resolve(0.9)

    def test_only_one_trade_may_be_open_at_a_time(self) -> None:
        broker = PaperBroker(make_config())
        first = broker.open(proposal("call"), stub_snapshot(entry_price=1.0, offset=0))
        assert first is not None

        blocked = broker.open(proposal("call"), stub_snapshot(entry_price=1.0, offset=10))
        self.assertIsNone(blocked)

        allowed = broker.open(proposal("call"), stub_snapshot(entry_price=1.0, offset=61))
        self.assertIsNotNone(allowed)

    def test_summary_counts_outcomes(self) -> None:
        broker = PaperBroker(make_config())
        first = broker.open(proposal("call"), stub_snapshot(1.0, 0, 0))
        assert first is not None
        first.resolve(1.1)
        second = broker.open(proposal("call"), stub_snapshot(1.0, 1, 120))
        assert second is not None
        second.resolve(0.9)

        summary = broker.summary()
        self.assertEqual(summary["trades"], 2)
        self.assertEqual(summary["wins"], 1)
        self.assertEqual(summary["losses"], 1)
        self.assertAlmostEqual(summary["pnl"], -0.20)

    def test_resolve_due_uses_registered_outcomes(self) -> None:
        from engine.sampler import HorizonOutcome

        broker = PaperBroker(make_config())
        snapshot = stub_snapshot(1.0)
        snapshot = Snapshot(
            **{
                **snapshot.__dict__,
                "outcomes": {
                    60: HorizonOutcome(
                        horizon_seconds=60,
                        exit_timestamp=BASE + timedelta(seconds=60),
                        exit_price=1.1,
                        exit_delay_seconds=0.0,
                        label="call",
                    )
                },
            }
        )
        broker.register_outcomes(snapshot)
        trade = broker.open(proposal("call"), snapshot)
        assert trade is not None

        self.assertEqual(broker.resolve_due(BASE + timedelta(seconds=59)), [])
        resolved = broker.resolve_due(BASE + timedelta(seconds=61))
        self.assertEqual(len(resolved), 1)
        self.assertEqual(resolved[0].status, WON)

    def test_journal_appends_jsonl(self) -> None:
        broker = PaperBroker(make_config())
        trade = broker.open(proposal("call"), stub_snapshot(1.0))
        assert trade is not None
        trade.resolve(1.1)

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "journal.jsonl"
            TradeJournal(path).append(trade)
            records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["status"], WON)
        self.assertIsInstance(records[0]["entry_timestamp"], str)


if __name__ == "__main__":
    unittest.main()
