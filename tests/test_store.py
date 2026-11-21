import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from engine.domain.timeframes import Tick
from engine.store import TickStore, TickStoreError

from .helpers import BASE, synthetic_ticks


def write_csv(directory: str, content: str) -> Path:
    path = Path(directory) / "ticks.csv"
    path.write_text(content, encoding="utf-8")
    return path


class TickStoreTests(unittest.TestCase):
    def test_loads_and_sorts_ticks(self) -> None:
        content = (
            "timestamp,price,active_id\n"
            "2026-11-18T12:01:00+00:00,1.2,0\n"
            "2026-11-18T12:00:00+00:00,1.1,0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            store = TickStore.from_csv(write_csv(directory, content))

        self.assertEqual(store.prices.tolist(), [1.1, 1.2])
        self.assertEqual(store.stats["out_of_order"], 1)
        self.assertEqual(store.stats["total_rows"], 2)

    def test_exact_duplicates_are_preserved(self) -> None:
        content = (
            "timestamp,price\n"
            "2026-11-18T12:00:00+00:00,1.1\n"
            "2026-11-18T12:00:00+00:00,1.1\n"
            "2026-11-18T12:00:00+00:00,1.2\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            store = TickStore.from_csv(write_csv(directory, content))

        self.assertEqual(len(store), 3)
        self.assertEqual(store.stats["duplicates_dropped"], 0)
        self.assertEqual(store.stats["duplicate_rows"], 1)
        self.assertEqual(store.frame["sequence"].tolist(), [0, 1, 2])

    def test_naive_timestamp_is_rejected(self) -> None:
        content = "timestamp,price\n2026-11-18T12:00:00,1.1\n"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TickStoreError):
                TickStore.from_csv(write_csv(directory, content))

    def test_active_id_mismatch_is_rejected(self) -> None:
        content = "timestamp,price,active_id\n2026-11-18T12:00:00+00:00,1.1,7\n"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TickStoreError):
                TickStore.from_csv(write_csv(directory, content), active_id=0)

    def test_missing_columns_are_rejected(self) -> None:
        content = "timestamp,close\n2026-11-18T12:00:00+00:00,1.1\n"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TickStoreError):
                TickStore.from_csv(write_csv(directory, content))

    def test_point_in_time_lookup_never_peeks_ahead(self) -> None:
        ticks = [
            Tick(BASE, 1.0, 0),
            Tick(BASE + timedelta(seconds=10), 1.1, 0),
            Tick(BASE + timedelta(seconds=20), 1.2, 0),
        ]
        store = TickStore.from_ticks(ticks)

        self.assertEqual(store.last_price_at(BASE + timedelta(seconds=9)), 1.0)
        self.assertEqual(store.last_price_at(BASE + timedelta(seconds=10)), 1.1)
        self.assertIsNone(store.last_price_at(BASE - timedelta(seconds=1)))

    def test_asof_merge_returns_the_last_known_price(self) -> None:
        ticks = [
            Tick(BASE, 1.0, 0),
            Tick(BASE + timedelta(seconds=10), 1.1, 0),
        ]
        store = TickStore.from_ticks(ticks)

        merged = store.price_at(
            [
                BASE + timedelta(seconds=5),
                BASE + timedelta(seconds=10),
                BASE + timedelta(seconds=30),
            ]
        )

        self.assertEqual(merged["price"].tolist(), [1.0, 1.1, 1.1])

    def test_parquet_round_trip_preserves_offsets(self) -> None:
        ticks = [
            Tick(BASE.astimezone(), 1.0, 0),
            Tick(BASE + timedelta(seconds=5), 1.1, 0),
        ]
        store = TickStore.from_ticks(ticks)

        with tempfile.TemporaryDirectory() as directory:
            path = store.write_parquet(Path(directory) / "ticks.parquet")
            reloaded = TickStore.from_parquet(path)

        self.assertEqual(len(reloaded), 2)
        self.assertEqual(reloaded.prices.tolist(), [1.0, 1.1])

    def test_jsonl_capture_round_trip(self) -> None:
        content = (
            '{"received_at":"2026-11-18T12:00:00+00:00","active_id":0,"price":1.1}\n'
            '{"received_at":"2026-11-18T12:00:05+00:00","active_id":0,"price":1.2}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticks.jsonl"
            path.write_text(content, encoding="utf-8")
            store = TickStore.from_jsonl(path, active_id=0)

        self.assertEqual(store.prices.tolist(), [1.1, 1.2])

    def test_jsonl_accepts_close_and_nested_payload(self) -> None:
        content = (
            '{"received_at":"2026-11-18T12:00:00+00:00","active_id":0,"close":1.1}\n'
            '{"received_at":"2026-11-18T12:00:05+00:00","active_id":0,'
            '"payload":{"close":1.2}}\n'
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "ticks.jsonl"
            path.write_text(content, encoding="utf-8")
            store = TickStore.from_jsonl(path, active_id=0)

        self.assertEqual(store.prices.tolist(), [1.1, 1.2])

    def test_synthetic_ticks_keep_every_event(self) -> None:
        store = TickStore.from_ticks(synthetic_ticks(minutes=2, per_minute=60))
        self.assertEqual(len(store), 120)
        self.assertEqual(store.stats["duplicates_dropped"], 0)
        self.assertEqual(store.frame["sequence"].tolist(), list(range(120)))
        timestamps = store.frame["timestamp"]
        self.assertTrue(timestamps.is_monotonic_increasing)


if __name__ == "__main__":
    unittest.main()
