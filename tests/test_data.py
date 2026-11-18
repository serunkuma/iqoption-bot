import tempfile
import unittest
from pathlib import Path

from amt.data import TickDataError, load_ticks


def write_csv(directory: str, content: str) -> Path:
    path = Path(directory) / "ticks.csv"
    path.write_text(content, encoding="utf-8")
    return path


class DataTests(unittest.TestCase):
    def test_loads_and_sorts_ticks(self) -> None:
        content = (
            "timestamp,price,active_id\n"
            "2026-11-18T12:01:00+00:00,1.2,0\n"
            "2026-11-18T12:00:00+00:00,1.1,0\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = load_ticks(write_csv(directory, content))

        self.assertEqual([tick.price for tick in result.ticks], [1.1, 1.2])
        self.assertEqual(result.out_of_order, 1)

    def test_exact_duplicates_are_dropped(self) -> None:
        content = (
            "timestamp,price\n"
            "2026-11-18T12:00:00+00:00,1.1\n"
            "2026-11-18T12:00:00+00:00,1.1\n"
            "2026-11-18T12:00:00+00:00,1.2\n"
        )
        with tempfile.TemporaryDirectory() as directory:
            result = load_ticks(write_csv(directory, content))

        self.assertEqual(len(result.ticks), 2)
        self.assertEqual(result.duplicates_dropped, 1)

    def test_naive_timestamp_is_rejected(self) -> None:
        content = "timestamp,price\n2026-11-18T12:00:00,1.1\n"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TickDataError):
                load_ticks(write_csv(directory, content))

    def test_active_id_mismatch_is_rejected(self) -> None:
        content = "timestamp,price,active_id\n2026-11-18T12:00:00+00:00,1.1,7\n"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TickDataError):
                load_ticks(write_csv(directory, content), active_id=0)

    def test_missing_columns_are_rejected(self) -> None:
        content = "timestamp,close\n2026-11-18T12:00:00+00:00,1.1\n"
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(TickDataError):
                load_ticks(write_csv(directory, content))


if __name__ == "__main__":
    unittest.main()
