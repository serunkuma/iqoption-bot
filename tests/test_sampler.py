import unittest

from engine.sampler import build_snapshots
from engine.store import TickStore

from .helpers import make_config, synthetic_ticks


def store_from(ticks) -> TickStore:
    return TickStore.from_ticks(ticks)


class SamplerTests(unittest.TestCase):
    def test_snapshots_start_after_the_macro_window(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)

        # Minutes 0..11 produce 11 closed candles (the last never closes), so
        # with a 3-bar window only keys 2..10 are eligible: 9 snapshots.
        self.assertEqual(len(report.snapshots), 9)
        self.assertEqual(report.skipped_insufficient_history, 2)
        self.assertEqual(report.candidate_minutes, 11)

    def test_snapshot_lands_on_the_candle_close(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)

        first = report.snapshots[0]
        self.assertEqual(first.snapshot_time.second, 0)
        self.assertEqual(first.snapshot_time.minute, 3)
        self.assertEqual(first.snapshot_time.microsecond, 0)
        self.assertEqual(first.decision_version, "candle-close-v1")

    def test_window_contains_exactly_the_completed_bars(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)

        first = report.snapshots[0]
        self.assertEqual(len(first.completed_bars), 3)
        self.assertTrue(first.contiguous)
        self.assertEqual(first.window_ticks, 180)
        self.assertEqual(first.price, first.completed_bars[-1].close)

    def test_features_never_see_ticks_after_the_candle_close(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)

        for snapshot in report.snapshots:
            cutoff = snapshot.snapshot_time.timestamp()
            for bar in snapshot.completed_bars:
                latest = max(bar.epochs)
                self.assertLess(latest, cutoff)
                self.assertLess(bar.start_epoch, cutoff)

    def test_entry_is_the_first_tick_after_the_delay(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)
        first = report.snapshots[0]

        assert first.entry_timestamp is not None
        delay = first.entry_timestamp.timestamp() - first.snapshot_time.timestamp()
        self.assertGreaterEqual(delay, 0.25)
        self.assertLess(delay, 0.25 + 1.0 + 1e-9)

    def test_outcomes_are_measured_from_the_entry_time(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)
        first = report.snapshots[0]

        assert first.entry_timestamp is not None
        for horizon, outcome in first.outcomes.items():
            if outcome.exit_timestamp is None:
                continue
            elapsed = outcome.exit_timestamp.timestamp() - first.entry_timestamp.timestamp()
            self.assertGreaterEqual(elapsed, horizon - 1e-9)
            self.assertLessEqual(elapsed, horizon + config.snapshot.exit_tolerance_seconds)

    def test_missing_minute_blocks_the_window(self) -> None:
        config = make_config()
        ticks = [
            tick
            for tick in synthetic_ticks(minutes=12)
            if tick.timestamp.minute != 5
        ]
        report = build_snapshots(store_from(ticks), config)

        self.assertGreater(report.skipped_gap, 0)
        self.assertLess(len(report.snapshots), 9)

    def test_sparse_bar_blocks_the_window(self) -> None:
        config = make_config(snapshot={"min_ticks_per_bar": 30})
        ticks = [
            tick
            for tick in synthetic_ticks(minutes=12)
            if not (tick.timestamp.minute == 2 and tick.timestamp.second >= 10)
        ]
        report = build_snapshots(store_from(ticks), config)

        self.assertGreater(report.skipped_sparse_bar, 0)

    def test_no_entry_tick_skips_the_snapshot(self) -> None:
        # One-second ticks cannot land inside [close + 0.25, close + 0.35].
        config = make_config(snapshot={"entry_tolerance_seconds": 0.1})
        report = build_snapshots(store_from(synthetic_ticks(minutes=12)), config)

        self.assertGreater(report.skipped_no_entry_tick, 0)
        self.assertEqual(report.snapshots, [])

    def test_report_serialises_to_a_flat_dictionary(self) -> None:
        config = make_config()
        report = build_snapshots(store_from(synthetic_ticks(minutes=6)), config)
        summary = report.as_dict()

        self.assertIn("snapshots", summary)
        self.assertEqual(summary["snapshots"], len(report.snapshots))

    def test_empty_store_produces_no_snapshots(self) -> None:
        report = build_snapshots(TickStore.empty(), make_config())
        self.assertEqual(report.snapshots, [])


if __name__ == "__main__":
    unittest.main()
