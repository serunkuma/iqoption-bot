"""Multi-horizon model suite.

Four shallow, regularised binary classifiers — one per expiry bucket — each
wrapped in a probability calibrator. Training uses purged walk-forward splits
so the calibrated probability reflects honest out-of-sample performance.

The suite never fabricates a model. If a horizon has too few rows, one class
only, or no usable out-of-sample predictions, it records the reason and is
skipped. The router then has no probability for that horizon.
"""

from __future__ import annotations

import pickle
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

# LightGBM's Windows DLL must be loaded before pandas/pyarrow. When pandas is
# imported first, LightGBM raises "access violation reading 0x0" inside
# LGBM_DatasetSetField on the first fit. Importing it here, before pandas,
# makes the order deterministic for every entry point that imports `engine`.
try:  # pragma: no cover - environment dependent
    import lightgbm as _lightgbm  # noqa: F401

    LIGHTGBM_AVAILABLE = True
except ImportError:  # pragma: no cover - environment dependent
    _lightgbm = None
    LIGHTGBM_AVAILABLE = False

import pandas as pd

from .config import Config
from .features import CORE_FEATURES

EPS = 1e-6


def _clip(probability: np.ndarray) -> np.ndarray:
    return np.clip(probability, EPS, 1.0 - EPS)


def _logit(probability: np.ndarray) -> np.ndarray:
    probability = _clip(probability)
    return np.log(probability / (1.0 - probability))


@dataclass
class Calibrator:
    """Platt or isotonic probability calibration with a shared interface."""

    method: str = "none"
    model: Any = None

    def fit(self, probabilities: np.ndarray, labels: np.ndarray) -> "Calibrator":
        if self.method == "isotonic":
            from sklearn.isotonic import IsotonicRegression

            model = IsotonicRegression(out_of_bounds="clip", y_min=0.0, y_max=1.0)
            model.fit(probabilities, labels)
            self.model = model
        elif self.method == "platt":
            from sklearn.linear_model import LogisticRegression

            model = LogisticRegression(C=1.0, solver="lbfgs")
            model.fit(_logit(probabilities).reshape(-1, 1), labels)
            self.model = model
        else:
            self.model = None
        return self

    def transform(self, probabilities: np.ndarray) -> np.ndarray:
        if self.method == "isotonic" and self.model is not None:
            return _clip(np.asarray(self.model.predict(probabilities), dtype=float))
        if self.method == "platt" and self.model is not None:
            return _clip(
                np.asarray(
                    self.model.predict_proba(_logit(probabilities).reshape(-1, 1))[:, 1],
                    dtype=float,
                )
            )
        return _clip(np.asarray(probabilities, dtype=float))

    def is_increasing(self) -> bool:
        """True when the calibration map cannot invert the model's direction.

        Isotonic regression is monotone by construction. Platt is a logistic
        fit and may end up with a negative slope on a noisy slice, which would
        turn a weak signal into a systematically inverted one. The trainer
        rejects that fit instead of shipping it.
        """

        if self.method == "platt" and self.model is not None:
            return float(self.model.coef_[0][0]) > 0.0
        return True


@dataclass
class HorizonMetrics:
    horizon_seconds: int
    rows: int = 0
    positives: int = 0
    oos_rows: int = 0
    evaluation_rows: int = 0
    log_loss: float | None = None
    brier: float | None = None
    auc: float | None = None
    calibration: str = "none"
    calibration_note: str | None = None
    skipped_reason: str | None = None

    def as_dict(self) -> dict:
        return {
            "horizon_seconds": self.horizon_seconds,
            "rows": self.rows,
            "positives": self.positives,
            "oos_rows": self.oos_rows,
            "evaluation_rows": self.evaluation_rows,
            "log_loss": self.log_loss,
            "brier": self.brier,
            "auc": self.auc,
            "calibration": self.calibration,
            "calibration_note": self.calibration_note,
            "skipped_reason": self.skipped_reason,
        }


@dataclass
class HorizonModel:
    horizon_seconds: int
    estimator: Any
    calibrator: Calibrator
    feature_names: tuple[str, ...]
    metrics: HorizonMetrics

    def predict_raw(self, matrix: np.ndarray) -> np.ndarray:
        return np.asarray(self.estimator.predict_proba(matrix)[:, 1], dtype=float)

    def predict(self, matrix: np.ndarray) -> np.ndarray:
        return self.calibrator.transform(self.predict_raw(matrix))


#: Columns of the held-out evaluation table stored on the suite. These are the
#: only probabilities the backtest may replay; they were never used to fit an
#: estimator or a calibrator.
EVALUATION_COLUMNS = ("snapshot_id", "horizon_seconds", "probability", "label")


@dataclass
class ModelSuite:
    models: dict[int, HorizonModel] = field(default_factory=dict)
    feature_names: tuple[str, ...] = CORE_FEATURES
    feature_version: str = ""
    core_feature_version: str = ""
    label_version: str = ""
    config_hash: str = ""
    trained_at: str = ""
    skipped: dict[int, str] = field(default_factory=dict)
    evaluation: pd.DataFrame = field(default_factory=lambda: pd.DataFrame(
        columns=list(EVALUATION_COLUMNS)
    ))

    def predict_vector(self, values: list[float | None]) -> dict[int, float]:
        """Return calibrated Call probabilities keyed by horizon (live path)."""

        matrix = np.asarray(
            [[np.nan if value is None else float(value) for value in values]],
            dtype=float,
        )
        return {
            horizon: float(model.predict(matrix)[0])
            for horizon, model in sorted(self.models.items())
        }

    def evaluate_snapshot(self, snapshot_id: int) -> dict[int, float]:
        """Return held-out calibrated probabilities for one snapshot.

        Snapshots that were not in any evaluation slice return an empty
        mapping, which the router treats as no model. This is what keeps the
        backtest from replaying in-sample predictions.
        """

        if self.evaluation.empty:
            return {}
        rows = self.evaluation.loc[
            self.evaluation["snapshot_id"] == snapshot_id
        ]
        return {
            int(row.horizon_seconds): float(row.probability)
            for row in rows.itertuples(index=False)
        }

    def save(self, path: str | Path) -> Path:
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("wb") as handle:
            pickle.dump(self, handle)
        return destination

    @classmethod
    def load(cls, path: str | Path) -> "ModelSuite":
        with Path(path).open("rb") as handle:
            suite = pickle.load(handle)
        if not isinstance(suite, cls):
            raise TypeError(f"{path} does not contain a ModelSuite")
        return suite


# -- training --------------------------------------------------------------


def _make_estimator(config: Config) -> tuple[Any, str]:
    if config.models.engine == "lightgbm":
        if not LIGHTGBM_AVAILABLE:
            raise RuntimeError(
                "models.engine='lightgbm' but lightgbm is not installed; "
                "install it or set models.engine='sklearn'"
            )
        from lightgbm import LGBMClassifier

        return (
            LGBMClassifier(
                n_estimators=config.models.n_estimators,
                learning_rate=config.models.learning_rate,
                num_leaves=config.models.num_leaves,
                min_child_samples=config.models.min_child_samples,
                subsample=0.9,
                colsample_bytree=0.9,
                reg_lambda=1.0,
                random_state=config.models.random_seed,
                n_jobs=1,
                verbose=-1,
            ),
            "lightgbm",
        )

    from sklearn.ensemble import HistGradientBoostingClassifier

    return (
        HistGradientBoostingClassifier(
            max_iter=config.models.n_estimators,
            learning_rate=config.models.learning_rate,
            max_leaf_nodes=config.models.num_leaves,
            min_samples_leaf=config.models.min_child_samples,
            random_state=config.models.random_seed,
        ),
        "sklearn",
    )


def _overlap_weights(epochs: np.ndarray, horizon_seconds: int) -> np.ndarray:
    """Down-weight rows whose label windows overlap their neighbours.

    A snapshot every ``spacing`` seconds means roughly ``horizon / spacing``
    rows share any given expiry window, so each row carries about
    ``spacing / horizon`` of independent information.
    """

    if epochs.size < 2:
        return np.ones(epochs.size, dtype=float)
    spacing = float(np.median(np.diff(epochs)))
    if spacing <= 0:
        return np.ones(epochs.size, dtype=float)
    overlap = max(1.0, horizon_seconds / spacing)
    weight = 1.0 / overlap
    return np.full(epochs.size, min(1.0, max(0.01, weight)), dtype=float)


def _walk_forward_oos(
    X: np.ndarray,
    y: np.ndarray,
    epochs: np.ndarray,
    weights: np.ndarray,
    config: Config,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Return out-of-sample row positions, probabilities, and labels.

    Positions index the input arrays, so callers can map predictions back to
    snapshot ids without relying on row order.
    """

    order = np.argsort(epochs, kind="mergesort")
    X, y, epochs, weights = X[order], y[order], epochs[order], weights[order]

    n_splits = config.models.n_splits
    fold_size = len(X) // (n_splits + 1)
    if fold_size < 1:
        return np.array([], dtype=int), np.array([]), np.array([])

    positions: list[np.ndarray] = []
    oos_probability: list[np.ndarray] = []
    oos_label: list[np.ndarray] = []

    for fold in range(1, n_splits + 1):
        start = fold * fold_size
        end = len(X) if fold == n_splits else (fold + 1) * fold_size
        if start >= len(X):
            break
        train_mask = epochs < (epochs[start] - config.models.purge_seconds)
        train_mask &= epochs < (epochs[start] - config.models.embargo_seconds)
        if train_mask.sum() < config.models.min_train_rows:
            continue
        if len(np.unique(y[train_mask])) < 2:
            continue

        estimator, _ = _make_estimator(config)
        estimator.fit(X[train_mask], y[train_mask], sample_weight=weights[train_mask])
        probability = estimator.predict_proba(X[start:end])[:, 1]
        positions.append(order[start:end])
        oos_probability.append(probability)
        oos_label.append(y[start:end])

    if not oos_probability:
        return np.array([], dtype=int), np.array([]), np.array([])
    return (
        np.concatenate(positions),
        np.concatenate(oos_probability),
        np.concatenate(oos_label),
    )


CALIBRATION_SHARE = 0.70


def _calibration_choice(config: Config, oos_rows: int) -> str:
    if config.models.calibration != "auto":
        return config.models.calibration
    return "isotonic" if oos_rows >= 500 else "platt"


def train_suite(dataset: pd.DataFrame, config: Config, config_hash: str = "") -> ModelSuite:
    """Train one calibrated model per horizon using purged walk-forward splits.

    The walk-forward predictions are split chronologically. The earlier share
    fits the probability calibrator; the later share is the untouched
    evaluation slice stored on the suite. The backtest only replays that slice,
    so neither the estimators nor the calibrators have seen it.
    """

    suite = ModelSuite(
        feature_names=CORE_FEATURES,
        feature_version=config.feature_version,
        core_feature_version=config.core_feature_version,
        label_version=config.label_version,
        config_hash=config_hash,
        trained_at=datetime.now(timezone.utc).isoformat(),
    )

    if dataset.empty:
        for horizon in config.labels.horizons_seconds:
            suite.skipped[horizon] = "empty dataset"
        return suite

    evaluation_frames: list[pd.DataFrame] = []

    for horizon in config.labels.horizons_seconds:
        metrics = HorizonMetrics(horizon_seconds=horizon)
        subset = dataset[
            (dataset["horizon_seconds"] == horizon) & (dataset["usable"] == 1)
        ].dropna(subset=["label"])

        metrics.rows = len(subset)
        if metrics.rows < config.models.min_train_rows:
            metrics.skipped_reason = (
                f"only {metrics.rows} usable rows, need {config.models.min_train_rows}"
            )
            suite.skipped[horizon] = metrics.skipped_reason
            continue

        labels = (subset["label"] == "call").to_numpy(dtype=int)
        metrics.positives = int(labels.sum())
        if len(np.unique(labels)) < 2:
            metrics.skipped_reason = "single class in horizon subset"
            suite.skipped[horizon] = metrics.skipped_reason
            continue

        X = subset.loc[:, list(CORE_FEATURES)].to_numpy(dtype=float)
        epochs = pd.to_datetime(subset["timestamp"], utc=True).astype("int64").to_numpy(
            dtype=float
        ) / 1e9
        weights = _overlap_weights(epochs, horizon)

        positions, oos_probability, oos_label = _walk_forward_oos(
            X, labels, epochs, weights, config
        )
        metrics.oos_rows = int(oos_probability.size)

        # Chronological split: fit the calibrator on the earlier share, keep the
        # later share untouched for evaluation.
        cut = int(round(metrics.oos_rows * CALIBRATION_SHARE))
        calibration_probability = oos_probability[:cut]
        calibration_label = oos_label[:cut]
        evaluation_probability = oos_probability[cut:]
        evaluation_label = oos_label[cut:]
        evaluation_positions = positions[cut:]
        metrics.evaluation_rows = int(evaluation_probability.size)

        calibrator = Calibrator(method="none")
        if calibration_probability.size >= 50 and len(np.unique(calibration_label)) == 2:
            method = _calibration_choice(config, int(calibration_probability.size))
            candidate = Calibrator(method=method).fit(
                calibration_probability, calibration_label
            )
            if candidate.is_increasing():
                calibrator = candidate
                metrics.calibration = method
            else:
                metrics.calibration_note = (
                    f"rejected {method} fit with a negative slope; using identity"
                )

        calibrated_evaluation = (
            calibrator.transform(evaluation_probability)
            if evaluation_probability.size
            else np.array([], dtype=float)
        )

        if metrics.evaluation_rows >= 10:
            from sklearn.metrics import brier_score_loss, log_loss, roc_auc_score

            metrics.brier = float(
                brier_score_loss(evaluation_label, calibrated_evaluation)
            )
            metrics.log_loss = float(
                log_loss(evaluation_label, _clip(calibrated_evaluation))
            )
            if len(np.unique(evaluation_label)) == 2:
                metrics.auc = float(
                    roc_auc_score(evaluation_label, calibrated_evaluation)
                )
            evaluation_frames.append(
                pd.DataFrame(
                    {
                        "snapshot_id": subset["snapshot_id"].to_numpy()[
                            evaluation_positions
                        ],
                        "horizon_seconds": horizon,
                        "probability": calibrated_evaluation,
                        "label": evaluation_label,
                    }
                )
            )
        else:
            metrics.skipped_reason = "too few held-out evaluation rows"

        estimator, _ = _make_estimator(config)
        estimator.fit(X, labels, sample_weight=weights)

        suite.models[horizon] = HorizonModel(
            horizon_seconds=horizon,
            estimator=estimator,
            calibrator=calibrator,
            feature_names=CORE_FEATURES,
            metrics=metrics,
        )

    if evaluation_frames:
        suite.evaluation = pd.concat(evaluation_frames, ignore_index=True).loc[
            :, list(EVALUATION_COLUMNS)
        ]
    return suite
