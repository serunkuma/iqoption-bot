import tempfile
import unittest
from pathlib import Path

from engine.config import (
    CANDLE_VERSION,
    CORE_FEATURE_VERSION,
    DECISION_VERSION,
    FEATURE_VERSION,
    LABEL_VERSION,
    MODEL_FORMAT_VERSION,
    ConfigError,
    load_config,
)


class ConfigTests(unittest.TestCase):
    def test_default_config_loads(self) -> None:
        config = load_config()

        self.assertEqual(config.instrument.symbol, "EURUSD")
        self.assertEqual(config.context.macro_candles, 7)
        self.assertEqual(config.context.fast_candles, 3)
        self.assertEqual(config.labels.horizons_seconds, (60, 90, 120, 180))
        self.assertEqual(config.snapshot.entry_delay_ms, 250)
        self.assertEqual(config.feature_version, FEATURE_VERSION)
        self.assertEqual(config.core_feature_version, CORE_FEATURE_VERSION)
        self.assertEqual(config.label_version, LABEL_VERSION)
        self.assertEqual(config.candle_version, CANDLE_VERSION)
        self.assertEqual(config.decision_version, DECISION_VERSION)
        self.assertEqual(config.model_format_version, MODEL_FORMAT_VERSION)
        self.assertEqual(config.stream.root, "data/stream")
        self.assertEqual(config.execution.max_open_trades, 1)

    def test_default_versions_track_the_package_constants(self) -> None:
        self.assertEqual(FEATURE_VERSION, "amt-v4")
        self.assertEqual(CORE_FEATURE_VERSION, "core16-v2")
        self.assertEqual(LABEL_VERSION, "snapshot-horizon-v1")
        self.assertEqual(CANDLE_VERSION, "1m-clock-v1")
        self.assertEqual(DECISION_VERSION, "candle-close-v1")
        self.assertEqual(MODEL_FORMAT_VERSION, "joblib-v1")

    def test_legacy_intra_minute_offset_is_rejected(self) -> None:
        content = "[snapshot]\noffsets_seconds = [30]\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_stream_rotation_must_align_with_the_candle(self) -> None:
        content = "[stream]\nrotation_seconds = 90\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_daily_loss_limit_must_be_positive_or_null(self) -> None:
        content = "[execution]\ndaily_loss_limit = 0.0\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_unknown_key_is_rejected(self) -> None:
        content = "[context]\nmacro_candles = 7\ntypo_key = 1\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_fast_window_cannot_exceed_macro(self) -> None:
        content = "[context]\nmacro_candles = 3\nfast_candles = 5\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_horizons_must_be_ascending(self) -> None:
        content = "[labels]\nhorizons_seconds = [120, 60]\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_every_horizon_needs_a_payout(self) -> None:
        content = (
            "[labels]\nhorizons_seconds = [60, 90]\n"
            "[router.payouts]\n60 = 0.80\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_payouts_are_parsed_into_pairs(self) -> None:
        config = load_config()
        self.assertEqual(config.router.payout(60), 0.80)
        self.assertEqual(config.router.payout(180), 0.86)

    def test_live_execution_is_valid_but_not_implemented(self) -> None:
        content = "[execution]\nmode = 'live'\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            config = load_config(path)
        self.assertEqual(config.execution.mode, "live")

    def test_invalid_execution_mode_is_rejected(self) -> None:
        content = "[execution]\nmode = 'yolo'\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)


if __name__ == "__main__":
    unittest.main()
