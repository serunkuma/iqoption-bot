import tempfile
import unittest
from pathlib import Path

from amt.config import ConfigError, load_config


class ConfigTests(unittest.TestCase):
    def test_default_config_loads(self) -> None:
        config = load_config()

        self.assertEqual(config.instrument.symbol, "EURUSD")
        self.assertEqual(config.context.macro_candles, 7)
        self.assertEqual(config.context.fast_candles, 3)
        self.assertEqual(config.labels.horizons_seconds, (60, 90, 120, 180))
        self.assertEqual(config.feature_version, "amt-v2")

    def test_unknown_key_is_rejected(self) -> None:
        content = '[context]\nmacro_candles = 7\ntypo_key = 1\n'
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.toml"
            path.write_text(content, encoding="utf-8")
            with self.assertRaises(ConfigError):
                load_config(path)

    def test_fast_window_cannot_exceed_macro(self) -> None:
        content = '[context]\nmacro_candles = 3\nfast_candles = 5\n'
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


if __name__ == "__main__":
    unittest.main()
