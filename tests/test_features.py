import unittest

from engine.features import (
    CORE_FEATURES,
    build_diagnostic_table,
    build_feature_table,
    compute_features,
)
from engine.sampler import build_snapshots
from engine.store import TickStore

from .helpers import make_config, synthetic_ticks


def snapshots(config, ticks):
    return build_snapshots(TickStore.from_ticks(ticks), config).snapshots


class FeatureTests(unittest.TestCase):
    def test_core_vector_has_exactly_sixteen_ordered_features(self) -> None:
        self.assertEqual(len(CORE_FEATURES), 16)
        self.assertEqual(len(set(CORE_FEATURES)), 16)
        self.assertEqual(CORE_FEATURES[0], "z_poc")
        self.assertEqual(CORE_FEATURES[-1], "price_change_forming")

    def test_snapshot_features_are_complete_with_full_history(self) -> None:
        config = make_config()
        first = snapshots(config, synthetic_ticks(minutes=12))[0]
        vector = compute_features(first, config)

        self.assertTrue(vector.complete())
        self.assertEqual(vector.diagnostics["window_bars"], 3)
        self.assertEqual(vector.diagnostics["profile_missing"], 0)
        self.assertEqual(vector.diagnostics["volatility_missing"], 0)
        self.assertEqual(vector.diagnostics["gap_in_window"], 0)
        self.assertEqual(len(vector.values()), 16)

    def test_profile_uses_completed_bars_only(self) -> None:
        config = make_config()
        first = snapshots(config, synthetic_ticks(minutes=12))[0]
        vector = compute_features(first, config)

        self.assertEqual(
            vector.diagnostics["profile_ticks"], first.window_ticks
        )
        self.assertEqual(
            vector.diagnostics["profile_ticks"],
            sum(bar.tick_count for bar in first.completed_bars),
        )

    def test_future_ticks_cannot_change_the_feature_vector(self) -> None:
        config = make_config()
        ticks = synthetic_ticks(minutes=12)
        baseline = compute_features(snapshots(config, ticks)[0], config)

        first = snapshots(config, ticks)[0]
        cutoff = first.snapshot_time.timestamp()
        mutated = [
            type(tick)(tick.timestamp, tick.price * 2.0, tick.active_id)
            if tick.timestamp.timestamp() > cutoff
            else tick
            for tick in ticks
        ]
        changed = compute_features(snapshots(config, mutated)[0], config)

        self.assertEqual(baseline.core, changed.core)
        self.assertEqual(baseline.diagnostics["poc"], changed.diagnostics["poc"])
        self.assertEqual(baseline.diagnostics["sigma_7"], changed.diagnostics["sigma_7"])

    def test_missing_profile_is_explicit(self) -> None:
        config = make_config(context={"profile_min_ticks": 500})
        first = snapshots(config, synthetic_ticks(minutes=12))[0]
        vector = compute_features(first, config)

        self.assertEqual(vector.diagnostics["profile_missing"], 1)
        self.assertIsNone(vector.core["z_poc"])
        self.assertIsNone(vector.core["inside_va"])

    def test_flat_prices_mark_volatility_missing(self) -> None:
        config = make_config()
        ticks = [
            type(tick)(tick.timestamp, 1.0, 0)
            for tick in synthetic_ticks(minutes=12)
        ]
        first = snapshots(config, ticks)[0]
        vector = compute_features(first, config)

        self.assertEqual(vector.diagnostics["volatility_missing"], 1)
        self.assertIsNone(vector.core["z_poc"])

    def test_feature_table_has_one_row_per_snapshot(self) -> None:
        config = make_config()
        found = snapshots(config, synthetic_ticks(minutes=12))
        rows = build_feature_table(found, config)

        self.assertEqual(len(rows), len(found))
        self.assertEqual([row["snapshot_id"] for row in rows], list(range(len(found))))
        for name in CORE_FEATURES:
            self.assertIn(name, rows[0])
        self.assertEqual(rows[0]["feature_version"], "amt-v3")
        self.assertEqual(rows[0]["core_feature_version"], "core16-v1")

    def test_diagnostic_table_has_one_row_per_tick(self) -> None:
        config = make_config()
        ticks = synthetic_ticks(minutes=5, per_minute=10)
        rows = build_diagnostic_table(ticks, config)

        self.assertEqual(len(rows), len(ticks))
        self.assertEqual([row["tick_id"] for row in rows], list(range(len(ticks))))

    def test_time_features_follow_the_local_offset(self) -> None:
        from datetime import timedelta, timezone

        config = make_config()
        first = snapshots(config, synthetic_ticks(minutes=12))[0]
        shifted = type(first)(
            **{
                **first.__dict__,
                "utc_offset_seconds": int(timedelta(hours=2).total_seconds()),
            }
        )
        local = compute_features(shifted, config)
        utc = compute_features(first, config)

        self.assertNotAlmostEqual(
            local.diagnostics["time_sin"], utc.diagnostics["time_sin"]
        )


if __name__ == "__main__":
    unittest.main()
