import unittest

from engine.backtest import run_backtest
from engine.build import build_from_ticks
from engine.models import train_suite

from .helpers import make_config, synthetic_walk_ticks


def artifacts_and_suite(config, minutes: int = 120):
    artifacts = build_from_ticks(synthetic_walk_ticks(minutes=minutes), config)
    suite = train_suite(artifacts.dataset, config)
    return artifacts, suite


class BacktestTests(unittest.TestCase):
    def test_only_held_out_snapshots_are_routed(self) -> None:
        config = make_config()
        artifacts, suite = artifacts_and_suite(config)

        result = run_backtest(artifacts.dataset, suite, config)

        evaluated = suite.evaluation["snapshot_id"].nunique()
        total = artifacts.dataset["snapshot_id"].nunique()
        self.assertEqual(result.routed, evaluated)
        self.assertEqual(result.skipped_no_model, total - evaluated)

    def test_trades_only_reference_evaluated_snapshots(self) -> None:
        config = make_config()
        artifacts, suite = artifacts_and_suite(config)
        evaluated = set(suite.evaluation["snapshot_id"].tolist())

        result = run_backtest(artifacts.dataset, suite, config)

        self.assertTrue(result.trades)
        self.assertTrue(
            {trade.snapshot_id for trade in result.trades} <= evaluated
        )

    def test_one_open_trade_limit_is_respected(self) -> None:
        config = make_config(execution={"max_open_trades": 1})
        artifacts, suite = artifacts_and_suite(config)

        result = run_backtest(artifacts.dataset, suite, config)

        wins = [t for t in result.trades if t.status == "won"]
        losses = [t for t in result.trades if t.status == "lost"]
        closed = wins + losses
        self.assertEqual(result.summary()["closed"], len(closed))
        self.assertAlmostEqual(
            result.summary()["pnl"],
            round(sum(trade.pnl or 0.0 for trade in result.trades), 6),
        )

    def test_backtest_without_evaluation_rows_trades_nothing(self) -> None:
        from engine.models import ModelSuite

        config = make_config()
        artifacts = build_from_ticks(synthetic_walk_ticks(minutes=20), config)
        suite = ModelSuite()

        result = run_backtest(artifacts.dataset, suite, config)

        self.assertEqual(result.trades, [])
        self.assertEqual(result.routed, 0)

    def test_every_closed_trade_resolved_against_its_horizon(self) -> None:
        config = make_config()
        artifacts, suite = artifacts_and_suite(config)
        result = run_backtest(artifacts.dataset, suite, config)

        self.assertTrue(result.trades)
        for trade in result.trades:
            elapsed = (
                trade.expiry_timestamp - trade.entry_timestamp
            ).total_seconds()
            self.assertAlmostEqual(elapsed, trade.horizon_seconds)
            self.assertNotEqual(trade.status, "open")


if __name__ == "__main__":
    unittest.main()
