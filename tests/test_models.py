import unittest

import numpy as np

from engine.build import build_from_ticks
from engine.models import (
    Calibrator,
    ModelSuite,
    _overlap_weights,
    train_suite,
)

from .helpers import make_config, synthetic_walk_ticks


def training_dataset(config, minutes: int = 120):
    return build_from_ticks(synthetic_walk_ticks(minutes=minutes), config).dataset


class OverlapWeightTests(unittest.TestCase):
    def test_weights_shrink_when_horizon_spans_many_snapshots(self) -> None:
        epochs = np.arange(0, 600, 30, dtype=float)  # 30s spacing
        weights = _overlap_weights(epochs, 60)
        self.assertTrue(np.allclose(weights, 0.5))

    def test_single_row_keeps_full_weight(self) -> None:
        weights = _overlap_weights(np.array([0.0]), 60)
        self.assertEqual(weights.tolist(), [1.0])

    def test_short_horizon_is_not_upweighted_above_one(self) -> None:
        epochs = np.arange(0, 600, 30, dtype=float)
        weights = _overlap_weights(epochs, 10)
        self.assertTrue(np.allclose(weights, 1.0))


class CalibratorTests(unittest.TestCase):
    def test_isotonic_is_monotone_and_bounded(self) -> None:
        raw = np.linspace(0.05, 0.95, 50)
        labels = (raw > 0.5).astype(int)

        calibrator = Calibrator(method="isotonic").fit(raw, labels)
        calibrated = calibrator.transform(raw)

        self.assertTrue(calibrator.is_increasing())
        self.assertTrue(np.all(np.diff(calibrated) >= -1e-12))
        self.assertTrue(np.all((calibrated > 0) & (calibrated < 1)))

    def test_platt_with_negative_slope_is_rejected(self) -> None:
        raw = np.linspace(0.05, 0.95, 100)
        labels = (raw < 0.5).astype(int)  # inverted relationship

        calibrator = Calibrator(method="platt").fit(raw, labels)

        self.assertFalse(calibrator.is_increasing())

    def test_identity_calibration_returns_clipped_probabilities(self) -> None:
        calibrator = Calibrator(method="none")
        calibrated = calibrator.transform(np.array([-0.5, 0.5, 1.5]))

        self.assertAlmostEqual(float(calibrated[0]), 1e-6)
        self.assertAlmostEqual(float(calibrated[1]), 0.5)
        self.assertAlmostEqual(float(calibrated[2]), 1 - 1e-6)


class TrainSuiteTests(unittest.TestCase):
    def test_every_horizon_trains_and_records_held_out_rows(self) -> None:
        config = make_config()
        dataset = training_dataset(config)
        suite = train_suite(dataset, config, config_hash="test-hash")

        self.assertEqual(sorted(suite.models), [60, 90])
        self.assertFalse(suite.evaluation.empty)
        self.assertEqual(
            list(suite.evaluation.columns),
            ["snapshot_id", "horizon_seconds", "probability", "label"],
        )
        self.assertTrue(
            suite.evaluation["probability"].between(0.0, 1.0).all()
        )
        self.assertEqual(suite.config_hash, "test-hash")
        self.assertEqual(suite.core_feature_version, "core16-v2")

    def test_evaluation_snapshots_come_from_the_dataset(self) -> None:
        config = make_config()
        dataset = training_dataset(config)
        suite = train_suite(dataset, config)

        known = set(dataset["snapshot_id"].tolist())
        evaluated = set(suite.evaluation["snapshot_id"].tolist())
        self.assertTrue(evaluated)
        self.assertTrue(evaluated <= known)

    def test_evaluation_slice_never_overlaps_the_calibration_slice(self) -> None:
        config = make_config()
        dataset = training_dataset(config)
        suite = train_suite(dataset, config)

        for horizon, model in suite.models.items():
            evaluated = suite.evaluation[
                suite.evaluation["horizon_seconds"] == horizon
            ]
            self.assertEqual(len(evaluated), model.metrics.evaluation_rows)
            self.assertLessEqual(len(evaluated), model.metrics.oos_rows)

    def test_unknown_snapshot_has_no_evaluation_probability(self) -> None:
        config = make_config()
        suite = train_suite(training_dataset(config), config)

        self.assertEqual(suite.evaluate_snapshot(-1), {})

    def test_too_few_rows_skips_the_horizon_with_a_reason(self) -> None:
        config = make_config(models={"min_train_rows": 100000})
        suite = train_suite(training_dataset(config), config)

        self.assertEqual(suite.models, {})
        self.assertEqual(sorted(suite.skipped), [60, 90])
        self.assertIn("usable rows", suite.skipped[60])
        self.assertTrue(suite.evaluation.empty)

    def test_empty_dataset_skips_every_horizon(self) -> None:
        import pandas as pd

        config = make_config()
        suite = train_suite(pd.DataFrame(), config)

        self.assertEqual(
            suite.skipped,
            {60: "empty dataset", 90: "empty dataset"},
        )

    def test_suite_round_trips_through_pickle(self) -> None:
        import tempfile
        from pathlib import Path

        config = make_config()
        suite = train_suite(training_dataset(config), config)

        with tempfile.TemporaryDirectory() as directory:
            path = suite.save(Path(directory) / "suite.pkl")
            reloaded = ModelSuite.load(path)

        self.assertEqual(sorted(reloaded.models), sorted(suite.models))
        self.assertEqual(len(reloaded.evaluation), len(suite.evaluation))

    def test_joblib_artifact_round_trips_with_a_manifest(self) -> None:
        import json
        import tempfile
        from pathlib import Path

        config = make_config()
        suite = train_suite(training_dataset(config), config)

        with tempfile.TemporaryDirectory() as directory:
            path = suite.save(Path(directory) / "suite.joblib")
            manifest_path = ModelSuite.manifest_path(path)
            self.assertTrue(manifest_path.is_file())
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["format_version"], "joblib-v1")
            self.assertEqual(manifest["artifact_id"], suite.artifact_id)

            reloaded = ModelSuite.load(path, require_manifest=True)

        self.assertEqual(reloaded.artifact_id, suite.artifact_id)
        self.assertEqual(sorted(reloaded.models), sorted(suite.models))
        self.assertEqual(reloaded.validate(config), [])

    def test_artifact_hash_mismatch_is_rejected(self) -> None:
        import tempfile
        from pathlib import Path

        from engine.models import ModelArtifactError

        config = make_config()
        suite = train_suite(training_dataset(config), config)

        with tempfile.TemporaryDirectory() as directory:
            path = suite.save(Path(directory) / "suite.joblib")
            path.write_bytes(path.read_bytes() + b"\x00")
            with self.assertRaises(ModelArtifactError):
                ModelSuite.load(path, require_manifest=True)

    def test_runtime_load_refuses_a_pickle(self) -> None:
        import tempfile
        from pathlib import Path

        from engine.models import ModelArtifactError

        config = make_config()
        suite = train_suite(training_dataset(config), config)

        with tempfile.TemporaryDirectory() as directory:
            path = suite.save(Path(directory) / "suite.pkl")
            with self.assertRaises(ModelArtifactError):
                ModelSuite.load(path, require_manifest=True)


if __name__ == "__main__":
    unittest.main()
