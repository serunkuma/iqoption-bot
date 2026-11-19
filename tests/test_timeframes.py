import unittest
from datetime import datetime, timedelta, timezone

from engine.domain.timeframes import (
    Tick,
    bucket_key,
    completed_window,
    group_candles,
    window_has_gap,
)

BASE = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)


def tick(seconds: float, price: float) -> Tick:
    return Tick(BASE + timedelta(seconds=seconds), price, 0)


class TimeframeTests(unittest.TestCase):
    def test_ticks_in_same_minute_share_a_bucket(self) -> None:
        self.assertEqual(bucket_key(BASE), bucket_key(BASE + timedelta(seconds=59)))

    def test_next_minute_starts_a_new_bucket(self) -> None:
        self.assertEqual(bucket_key(BASE + timedelta(seconds=60)), bucket_key(BASE) + 1)

    def test_group_candles_splits_by_minute(self) -> None:
        ticks = [tick(0, 1.0), tick(30, 1.1), tick(60, 1.2)]

        candles = group_candles(ticks)

        self.assertEqual(len(candles), 2)
        self.assertEqual(candles[0].tick_count, 2)
        self.assertEqual(candles[0].tick_indices, (0, 1))
        self.assertEqual(candles[1].tick_count, 1)
        self.assertEqual(candles[1].tick_indices, (2,))

    def test_completed_window_excludes_forming_candle(self) -> None:
        self.assertEqual(completed_window([], 3, 2), (1, 3))
        self.assertEqual(completed_window([], 1, 7), (0, 1))

    def test_window_has_gap_detects_missing_minute(self) -> None:
        ticks = [tick(0, 1.0), tick(60, 1.1), tick(180, 1.2)]
        candles = group_candles(ticks)

        self.assertTrue(window_has_gap(candles, 0, 3))
        self.assertFalse(window_has_gap(candles, 0, 2))

    def test_unsorted_ticks_are_rejected(self) -> None:
        with self.assertRaises(ValueError):
            group_candles([tick(60, 1.0), tick(0, 1.1)])

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            bucket_key(datetime(2026, 11, 18, 12, 0, 0))


if __name__ == "__main__":
    unittest.main()
