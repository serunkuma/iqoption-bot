import unittest
from datetime import datetime, timedelta, timezone

from amt.config import CandleConfig, Config, ContextConfig, InstrumentConfig, LabelConfig
from amt.features import build_features
from amt.timeframes import Tick

BASE = datetime(2026, 11, 18, 12, 0, 0, tzinfo=timezone.utc)


def tick(seconds: float, price: float, active_id: int = 0) -> Tick:
    return Tick(BASE + timedelta(seconds=seconds), price, active_id)


def base_config(**context_overrides) -> Config:
    context = {
        "macro_candles": 2,
        "fast_candles": 1,
        "profile_min_ticks": 1,
        "value_area_target": 0.70,
        "tail_bins": 2,
        "single_print_max_ticks": 1,
        "volatility_min_changes": 1,
    }
    context.update(context_overrides)
    return Config(
        instrument=InstrumentConfig(
            symbol="EURUSD", active_id=0, pip_size=0.0001, bin_size=0.001
        ),
        candles=CandleConfig(interval_seconds=60),
        context=ContextConfig(**context),
        labels=LabelConfig(horizons_seconds=(60,), exit_tolerance_seconds=5.0),
    )


def sample_ticks() -> list[Tick]:
    return [
        tick(0, 1.000),
        tick(10, 1.001),
        tick(20, 1.002),
        tick(30, 1.001),
        tick(60, 1.003),
        tick(70, 1.004),
        tick(120, 1.005),
    ]


class FeatureTests(unittest.TestCase):
    def test_one_row_per_tick(self) -> None:
        features = build_features(sample_ticks(), base_config())
        self.assertEqual(len(features), 7)
        self.assertEqual([row["tick_id"] for row in features], list(range(7)))

    def test_first_candle_has_no_completed_context(self) -> None:
        row = build_features(sample_ticks(), base_config())[0]

        self.assertEqual(row["profile_missing"], 1)
        self.assertEqual(row["volatility_missing"], 1)
        self.assertIsNone(row["poc"])
        self.assertIsNone(row["sigma_7"])
        self.assertIsNone(row["tick_rate_7"])
        self.assertIsNone(row["z_poc"])
        self.assertAlmostEqual(row["tick_rate_forming"], 1.0)

    def test_completed_context_uses_previous_candles(self) -> None:
        row = build_features(sample_ticks(), base_config())[-1]

        self.assertEqual(row["profile_ticks"], 6)
        self.assertAlmostEqual(row["poc"], 1.0015)
        self.assertAlmostEqual(row["val"], 1.001)
        self.assertAlmostEqual(row["vah"], 1.005)
        self.assertAlmostEqual(row["tick_rate_7"], 6 / 120)
        self.assertAlmostEqual(row["price_change_7"], 0.004)
        self.assertAlmostEqual(row["range_7"], 0.004)
        self.assertAlmostEqual(row["sigma_7"], 0.0010954451150103838, places=12)
        self.assertAlmostEqual(row["z_poc"], (1.005 - 1.0015) / row["sigma_7"])
        self.assertEqual(row["inside_va"], 1)

    def test_layer_ratios_compare_fast_to_macro(self) -> None:
        row = build_features(sample_ticks(), base_config())[-1]

        self.assertAlmostEqual(row["tick_rate_3"], 2 / 60)
        self.assertAlmostEqual(row["tick_rate_3_7"], (2 / 60) / (6 / 120))
        self.assertAlmostEqual(row["price_speed_3_7"], 0.5)
        self.assertAlmostEqual(row["range_3_7"], 0.25)

    def test_forming_candle_does_not_enter_profile(self) -> None:
        ticks = sample_ticks() + [tick(130, 1.050), tick(140, 1.051)]
        row = build_features(ticks, base_config())[-2]

        self.assertEqual(row["price"], 1.050)
        self.assertEqual(row["profile_ticks"], 6)
        self.assertAlmostEqual(row["vah"], 1.005)
        self.assertAlmostEqual(row["range_forming"], 1.050 - 1.005)

    def test_constant_prices_mark_volatility_missing(self) -> None:
        ticks = [tick(0, 1.0), tick(10, 1.0), tick(60, 1.0), tick(70, 1.0)]
        row = build_features(ticks, base_config())[-1]

        self.assertIsNone(row["sigma_7"])
        self.assertEqual(row["volatility_missing"], 1)
        self.assertIsNone(row["z_poc"])

    def test_insufficient_ticks_is_flagged(self) -> None:
        ticks = sample_ticks()
        row = build_features(ticks, base_config(profile_min_ticks=30))[-1]

        self.assertEqual(row["profile_missing"], 1)
        self.assertEqual(row["insufficient_ticks"], 1)

    def test_features_are_causal(self) -> None:
        ticks = sample_ticks()
        prefix = build_features(ticks[:6], base_config())
        full = build_features(ticks, base_config())

        for earlier, later in zip(prefix, full[: len(prefix)]):
            self.assertEqual(earlier, later)


if __name__ == "__main__":
    unittest.main()
