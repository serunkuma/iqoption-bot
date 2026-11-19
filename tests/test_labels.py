import unittest
from datetime import timedelta

from engine.domain.labels import LABEL_VERSION, classify_direction, snapshot_label_rows
from engine.sampler import HorizonOutcome, Snapshot

from .helpers import BASE


def snapshot(outcomes: dict[int, HorizonOutcome], snapshot_id: int = 0) -> Snapshot:
    return Snapshot(
        snapshot_id=snapshot_id,
        active_id=0,
        snapshot_time=BASE,
        forming_start=BASE,
        completed_bars=(),
        forming_bar=None,  # type: ignore[arg-type]
        price=1.0,
        window_ticks=0,
        entry_timestamp=BASE + timedelta(milliseconds=250),
        entry_price=1.0,
        entry_delay_seconds=0.25,
        outcomes=outcomes,
    )


def outcome(horizon: int, exit_price: float | None, label: str) -> HorizonOutcome:
    return HorizonOutcome(
        horizon_seconds=horizon,
        exit_timestamp=BASE + timedelta(seconds=horizon) if exit_price is not None else None,
        exit_price=exit_price,
        exit_delay_seconds=0.0 if exit_price is not None else None,
        label=label,
    )


class LabelTests(unittest.TestCase):
    def test_direction_classification_is_explicit(self) -> None:
        self.assertEqual(classify_direction(1.0, 1.1), "call")
        self.assertEqual(classify_direction(1.0, 0.9), "put")
        self.assertEqual(classify_direction(1.0, 1.0), "tie")

    def test_long_format_has_one_row_per_horizon(self) -> None:
        rows = snapshot_label_rows(
            [
                snapshot(
                    {
                        60: outcome(60, 1.1, "call"),
                        90: outcome(90, 0.9, "put"),
                    }
                )
            ],
            tie_policy="exclude",
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual([row["horizon_seconds"] for row in rows], [60, 90])
        self.assertEqual(rows[0]["label"], "call")
        self.assertEqual(rows[1]["label"], "put")
        self.assertEqual({row["usable"] for row in rows}, {1})

    def test_ties_are_unusable_by_default(self) -> None:
        rows = snapshot_label_rows(
            [snapshot({60: outcome(60, 1.0, "tie")})], tie_policy="exclude"
        )

        self.assertEqual(rows[0]["label"], "tie")
        self.assertEqual(rows[0]["usable"], 0)

    def test_ties_can_be_kept(self) -> None:
        rows = snapshot_label_rows(
            [snapshot({60: outcome(60, 1.0, "tie")})], tie_policy="keep"
        )
        self.assertEqual(rows[0]["usable"], 1)

    def test_missing_exit_is_unusable_and_has_no_price(self) -> None:
        rows = snapshot_label_rows(
            [snapshot({60: outcome(60, None, "missing")})], tie_policy="keep"
        )

        self.assertEqual(rows[0]["label"], "missing")
        self.assertEqual(rows[0]["usable"], 0)
        self.assertIsNone(rows[0]["exit_price"])
        self.assertIsNone(rows[0]["exit_timestamp"])

    def test_label_rows_carry_the_version(self) -> None:
        rows = snapshot_label_rows(
            [snapshot({60: outcome(60, 1.1, "call")})], tie_policy="exclude"
        )
        self.assertEqual(rows[0]["label_version"], LABEL_VERSION)
        self.assertEqual(LABEL_VERSION, "snapshot-horizon-v1")

    def test_entry_timestamp_is_recorded(self) -> None:
        rows = snapshot_label_rows(
            [snapshot({60: outcome(60, 1.1, "call")})], tie_policy="exclude"
        )
        self.assertIsNotNone(rows[0]["entry_timestamp"])
        self.assertEqual(rows[0]["entry_price"], 1.0)


if __name__ == "__main__":
    unittest.main()
