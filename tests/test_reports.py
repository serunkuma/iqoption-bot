import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from engine.execution import Trade
from engine.models import ModelSuite
from engine.reports import (
    ReportBundle,
    calibration_summary,
    concurrency,
    reliability_curve,
)

BASE = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)


def trade(start: int, horizon: int, pnl: float = 0.0, status: str = "won") -> Trade:
    return Trade(
        trade_id=start,
        snapshot_id=start,
        active_id=0,
        direction="call",
        horizon_seconds=horizon,
        stake=1.0,
        payout=0.8,
        entry_timestamp=BASE + timedelta(seconds=start),
        entry_price=1.0,
        expiry_timestamp=BASE + timedelta(seconds=start + horizon),
        expected_value=0.1,
        status=status,
        pnl=pnl,
    )


class CalibrationTests(unittest.TestCase):
    def test_reliability_bins_cover_every_row(self) -> None:
        labels = np.array([0, 0, 1, 1, 1, 0])
        probabilities = np.array([0.05, 0.15, 0.45, 0.55, 0.85, 0.95])

        curve = reliability_curve(labels, probabilities, bins=5)

        self.assertEqual(len(curve), 5)
        self.assertEqual(sum(row["count"] for row in curve), len(labels))

    def test_perfect_predictions_score_a_low_brier(self) -> None:
        labels = np.array([0, 0, 1, 1])
        probabilities = np.array([0.01, 0.02, 0.98, 0.99])

        summary = calibration_summary(labels, probabilities)

        self.assertLess(summary["brier"], 0.01)
        self.assertGreater(summary["auc"], 0.99)
        self.assertLess(summary["ece"], 0.05)

    def test_single_class_reports_zero_auc_without_raising(self) -> None:
        labels = np.array([1, 1, 1])
        probabilities = np.array([0.7, 0.8, 0.9])

        summary = calibration_summary(labels, probabilities)

        self.assertEqual(summary["auc"], 0.0)


class ConcurrencyTests(unittest.TestCase):
    def test_overlapping_trades_are_counted(self) -> None:
        trades = [trade(0, 120), trade(60, 120), trade(300, 60)]

        stats = concurrency(trades)

        self.assertEqual(stats["trades"], 3)
        self.assertEqual(stats["max_concurrent"], 2)
        self.assertGreaterEqual(stats["overlapping_trades"], 1)

    def test_empty_portfolio_is_zero(self) -> None:
        stats = concurrency([])

        self.assertEqual(stats["trades"], 0)
        self.assertEqual(stats["max_concurrent"], 0)


class ReportBundleTests(unittest.TestCase):
    def test_writes_json_and_markdown_without_tabulate(self) -> None:
        bundle = ReportBundle(
            calibration={"60": {"rows": 10}},
            horizons=ModelSuite().evaluation,
            importance=ModelSuite().evaluation,
            execution={"trades": 0},
        )

        with tempfile.TemporaryDirectory() as directory:
            json_path = bundle.write(directory, name="unit")
            payload = json.loads(json_path.read_text(encoding="utf-8"))
            markdown = (Path(directory) / "unit.md").read_text(encoding="utf-8")

        self.assertIn("calibration", payload)
        self.assertIn("# unit", markdown)
        self.assertIn("No horizon models", markdown)


if __name__ == "__main__":
    unittest.main()
