import unittest
from datetime import datetime, timedelta, timezone

from amt.config import Config, LabelConfig
from amt.labels import build_labels
from amt.timeframes import Tick

BASE = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)


def tick(seconds: float, price: float) -> Tick:
    return Tick(BASE + timedelta(seconds=seconds), price, 0)


def config(**overrides) -> Config:
    values = {
        "horizons_seconds": (60,),
        "exit_tolerance_seconds": 5.0,
        "tie_policy": "exclude",
    }
    values.update(overrides)
    return Config(labels=LabelConfig(**values))


class LabelTests(unittest.TestCase):
    def test_exit_uses_first_tick_at_or_after_horizon(self) -> None:
        ticks = [
            tick(0, 1.000),
            tick(30, 1.001),
            tick(60, 1.002),
            tick(90, 1.0005),
            tick(120, 1.003),
            tick(180, 0.999),
        ]
        rows = {row["tick_id"]: row for row in build_labels(ticks, config())}

        self.assertEqual(rows[0]["label"], "call")
        self.assertAlmostEqual(rows[0]["exit_price"], 1.002)
        self.assertAlmostEqual(rows[0]["exit_delay_seconds"], 0.0)
        self.assertEqual(rows[0]["usable"], 1)

        self.assertEqual(rows[1]["label"], "put")
        self.assertEqual(rows[2]["label"], "call")
        self.assertEqual(rows[3]["label"], "missing")
        self.assertEqual(rows[4]["label"], "put")
        self.assertEqual(rows[5]["label"], "missing")

    def test_ties_are_explicit_and_excluded_by_default(self) -> None:
        ticks = [tick(0, 1.0), tick(60, 1.0)]
        row = build_labels(ticks, config())[0]

        self.assertEqual(row["label"], "tie")
        self.assertEqual(row["usable"], 0)

    def test_ties_can_be_kept(self) -> None:
        ticks = [tick(0, 1.0), tick(60, 1.0)]
        row = build_labels(ticks, config(tie_policy="keep"))[0]

        self.assertEqual(row["label"], "tie")
        self.assertEqual(row["usable"], 1)

    def test_tolerance_accepts_near_tick_and_rejects_late_tick(self) -> None:
        near = [tick(0, 1.0), tick(64, 1.1)]
        late = [tick(0, 1.0), tick(66, 1.1)]

        self.assertEqual(build_labels(near, config())[0]["label"], "call")
        self.assertEqual(build_labels(late, config())[0]["label"], "missing")

    def test_multiple_horizons_produce_long_format(self) -> None:
        ticks = [tick(0, 1.0), tick(60, 1.1), tick(90, 1.05), tick(120, 1.2)]
        rows = build_labels(ticks, config(horizons_seconds=(60, 90, 120, 180)))

        self.assertEqual(len(rows), len(ticks) * 4)
        self.assertEqual(
            [row["horizon_seconds"] for row in rows[:4]], [60, 90, 120, 180]
        )

    def test_missing_exit_is_not_mapped_to_put(self) -> None:
        ticks = [tick(0, 1.0), tick(10, 1.1)]
        row = build_labels(ticks, config())[1]

        self.assertEqual(row["label"], "missing")
        self.assertIsNone(row["exit_price"])
        self.assertEqual(row["usable"], 0)


if __name__ == "__main__":
    unittest.main()
