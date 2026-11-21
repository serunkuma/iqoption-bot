import tempfile
import unittest
from pathlib import Path

import pandas as pd

from engine.build import build_from_ticks
from engine.replay import (
    compare_candles,
    compare_features,
    rebuild_candles,
    replay_from_dirs,
)
from engine.stream import CandleBuilder, HourlyParquetStore, TickEvent

from .helpers import make_config, synthetic_ticks


def events_frame(ticks) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "sequence": list(range(len(ticks))),
            "received_at": [tick.timestamp for tick in ticks],
            "active_id": [tick.active_id for tick in ticks],
            "price": [tick.price for tick in ticks],
            "utc_offset_seconds": [0] * len(ticks),
        }
    )


def recorded_candles(ticks) -> pd.DataFrame:
    builder = CandleBuilder(60)
    rows = []
    for sequence, tick in enumerate(ticks):
        event = TickEvent(
            sequence=sequence,
            received_at=tick.timestamp,
            active_id=tick.active_id or 0,
            price=tick.price,
        )
        for candle in builder.ingest(event).closed:
            rows.append(candle.as_row())
    return pd.DataFrame(rows)


class ReplayTests(unittest.TestCase):
    def test_rebuilt_candles_match_recorded_candles(self) -> None:
        ticks = synthetic_ticks(minutes=12)
        rebuilt = rebuild_candles(events_frame(ticks))
        recorded = recorded_candles(ticks)

        report = compare_candles(rebuilt, recorded)

        self.assertTrue(report.ok, report.first_divergence)
        self.assertEqual(report.rebuilt_candles, len(recorded))
        self.assertEqual(report.missing, [])
        self.assertEqual(report.extra, [])

    def test_a_price_mismatch_is_reported(self) -> None:
        ticks = synthetic_ticks(minutes=12)
        rebuilt = rebuild_candles(events_frame(ticks))
        recorded = recorded_candles(ticks)
        recorded.loc[0, "close"] = 999.0

        report = compare_candles(rebuilt, recorded)

        self.assertFalse(report.ok)
        self.assertIn("close", {item.field for item in report.mismatches})
        self.assertIn("recorded=999.0", report.first_divergence or "")

    def test_missing_and_extra_buckets_are_reported(self) -> None:
        ticks = synthetic_ticks(minutes=12)
        rebuilt = rebuild_candles(events_frame(ticks))
        recorded = recorded_candles(ticks)

        report = compare_candles(rebuilt[:-1], recorded)

        self.assertTrue(report.missing)
        self.assertEqual(report.extra, [])

        report = compare_candles(rebuilt, recorded.iloc[1:])
        self.assertTrue(report.extra)
        self.assertEqual(report.missing, [])

    def test_features_match_the_offline_dataset(self) -> None:
        config = make_config()
        ticks = synthetic_ticks(minutes=12)
        artifacts = build_from_ticks(ticks, config)
        rebuilt = rebuild_candles(events_frame(ticks))

        mismatches = compare_features(rebuilt, artifacts.dataset, config)

        self.assertEqual(mismatches, [])

    def test_replay_from_dirs_reads_written_parts(self) -> None:
        ticks = synthetic_ticks(minutes=12)
        with tempfile.TemporaryDirectory() as directory:
            sink = HourlyParquetStore(Path(directory) / "stream", compression="none")
            builder = CandleBuilder(60)
            for sequence, tick in enumerate(ticks):
                event = TickEvent(
                    sequence=sequence,
                    received_at=tick.timestamp,
                    active_id=tick.active_id or 0,
                    price=tick.price,
                )
                sink.add_event(event)
                for candle in builder.ingest(event).closed:
                    sink.add_candle(candle)
            sink.flush()

            report = replay_from_dirs(
                Path(directory) / "stream" / "events",
                Path(directory) / "stream" / "candles",
                interval_seconds=60,
            )

        self.assertTrue(report.ok, report.first_divergence)
        self.assertGreater(report.events, 0)
        self.assertEqual(report.rebuilt_candles, report.recorded_candles)


if __name__ == "__main__":
    unittest.main()
