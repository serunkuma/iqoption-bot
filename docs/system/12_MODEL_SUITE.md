# Model Suite

Status: Current

> One calibrated binary classifier per expiry horizon. Each model answers a single question: *what is the probability that the exit price at this horizon is above the entry price?* Everything else — direction, payout, hurdle — belongs to the router.

---

## Why Four Models Instead of One

The four horizons have different payoff structures (`payout` differs by horizon) and different noise levels. A single multi-class model would force a shared decision boundary across 60s and 180s outcomes. Four independent binary models let each horizon be calibrated and validated on its own, and let the router reject one horizon while accepting another.

| Horizon | Positive class | Negative class |
|---------|----------------|----------------|
| 60s | `call` | `put` |
| 90s | `call` | `put` |
| 120s | `call` | `put` |
| 180s | `call` | `put` |

A `put` probability is the complement of the `call` probability. Ties and missing exits are excluded by the label layer, so they never enter training.

---

## Input Features

Each model consumes exactly the 16 `core16-v1` features in fixed order:

```text
z_poc, z_vah, z_val, inside_va, va_width_norm, poc_position,
edge_proximity, excess_high, excess_low, excess_asymmetry,
tick_rate_3_7, tick_rate_forming_3, price_speed_3_7,
price_speed_forming_3, range_forming_3, price_change_forming
```

The wider `amt-v3` table (POC/VAH/VAL levels, raw tick rates, time features, quality flags) is stored for diagnostics only. Feeding raw price levels to the model would make it instrument- and price-scale-dependent.

The feature engine is stateless, so the training matrix and a live vector are produced by the same function. See [Model Inputs](../data/09_MODEL_INPUTS.md).

---

## Estimator

| Setting | Default | Notes |
|---------|---------|-------|
| `models.engine` | `lightgbm` | `sklearn` selects `HistGradientBoostingClassifier` |
| `models.n_estimators` | `300` | `max_iter` for sklearn |
| `models.learning_rate` | `0.03` | |
| `models.num_leaves` | `15` | `max_leaf_nodes` for sklearn |
| `models.min_child_samples` | `50` | `min_samples_leaf` for sklearn |
| `models.random_seed` | `7` | |
| `models.min_train_rows` | `500` | Below this the horizon is skipped |

LightGBM runs with `subsample=0.9`, `colsample_bytree=0.9`, `reg_lambda=1.0`, and `n_jobs=1`. The models are deliberately shallow and regularised: with a few thousand overlapping rows there is not enough independent signal for a deep model.

Missing feature values stay `NaN` and are handled natively by both estimators. They are never imputed with a future value or with the current price.

---

## Purged Walk-Forward Validation

Random splits are forbidden: adjacent snapshots share overlapping label windows and nearly identical features.

The training set is sorted by snapshot time and divided into `n_splits + 1` equal folds. For each fold `1..n_splits`:

1. Train on every row strictly earlier than the fold start minus `models.purge_seconds` (default 180s, the longest horizon).
2. Predict the fold.
3. Collect the fold's predictions as out-of-sample.

`models.embargo_seconds` is subtracted as well and defaults to `0`; it is available for future session-boundary work.

A fold is skipped when its training slice has fewer than `models.min_train_rows` rows or only one class.

### Overlap Weights

A snapshot every 30 seconds with a 180-second horizon means roughly six rows share any given expiry window. Each row carries about `30 / 180` of independent information.

```text
spacing  = median difference between snapshot epochs
overlap  = max(1, horizon_seconds / spacing)
weight   = clamp(1 / overlap, 0.01, 1.0)
```

The weight is passed to `fit(..., sample_weight=...)`. It reduces the influence of duplicated information without discarding rows.

---

## Calibration

Calibration is mandatory before probabilities reach the router. The suite supports:

| Method | When | Behaviour |
|--------|------|-----------|
| `isotonic` | `auto` and at least 500 calibration rows | Monotone step fit |
| `platt` | `auto` and fewer than 500 calibration rows | Logistic fit on the logit of the raw probability |
| `none` | `calibration = "none"` or a rejected fit | Identity with clipping to `[1e-6, 1 - 1e-6]` |

Platt scaling can fit a negative slope on a noisy slice, which would systematically invert a weak signal. The trainer checks the slope and rejects the fit, recording the note `rejected platt fit with a negative slope; using identity` and shipping identity calibration instead. Isotonic is monotone by construction.

A calibrator is fit only when it has at least 50 rows and both classes present.

### Chronological Calibration/Evaluation Split

Walk-forward out-of-sample predictions are split chronologically, not randomly:

```text
|------ earlier 70%: fit calibrator ------|------ later 30%: evaluation ------|
```

`CALIBRATION_SHARE = 0.70`. The earlier share fits the calibrator. The later share is stored untouched on the suite as the evaluation table.

This is what makes the backtest honest: the evaluation probabilities are produced by estimators that never saw those rows *and* by calibrators that never saw those rows. A random split would leak — the same period would inform both the calibrator and the reported score.

---

## Evaluation Table

`ModelSuite.evaluation` is a DataFrame with exactly four columns:

| Column | Meaning |
|--------|---------|
| `snapshot_id` | Snapshot the row belongs to |
| `horizon_seconds` | 60, 90, 120, or 180 |
| `probability` | Calibrated out-of-sample Call probability |
| `label` | Realised outcome, `1` for call |

A horizon contributes rows only when it has at least 10 held-out evaluation rows. Below that, the model is still trained and stored, but `metrics.skipped_reason` records `too few held-out evaluation rows` and the horizon is not replayable.

`ModelSuite.evaluate_snapshot(snapshot_id)` returns the stored probabilities for that snapshot, or `{}` when it is not in the table. The backtest may use nothing else.

---

## Metrics

Computed on the held-out evaluation rows only:

| Metric | Meaning |
|--------|---------|
| `rows` | Usable rows for the horizon |
| `positives` | Count of `call` labels |
| `oos_rows` | Walk-forward out-of-sample rows |
| `evaluation_rows` | Rows in the later 30% |
| `brier` | Brier score, lower is better |
| `log_loss` | Log loss, lower is better |
| `auc` | ROC AUC |
| `calibration` | Calibrator shipped, or `none` |
| `calibration_note` | Why a fit was rejected |
| `skipped_reason` | Why a horizon is not usable |

AUC is recorded only when the evaluation slice contains both classes.

---

## Final Refit

After the walk-forward and calibration steps, the shipped estimator is refit on **all** usable rows for that horizon, not only the walk-forward training slices. The metrics still describe the honest held-out slice; the refit only improves the live model. The calibrator is not refit on the full set, because that would undo the chronological separation.

---

## Persistence

`ModelSuite` is pickled with its estimators, calibrators, metrics, skipped reasons, evaluation table, and version metadata:

| Field | Value |
|-------|-------|
| `feature_names` | `core16-v1` names |
| `feature_version` | `amt-v3` |
| `core_feature_version` | `core16-v1` |
| `label_version` | `snapshot-horizon-v1` |
| `config_hash` | First 16 hex characters of a SHA-256 over the resolved config |
| `trained_at` | UTC ISO 8601 timestamp |

`ModelSuite.load` rejects a pickle that is not a `ModelSuite`.

---

## Failure Behaviour

| Situation | Result |
|-----------|--------|
| Empty dataset | Every horizon skipped with `empty dataset` |
| Fewer than `min_train_rows` usable rows | Horizon skipped with the required row count |
| Single class | Horizon skipped |
| No walk-forward folds | No out-of-sample rows; horizon not replayable |
| Fewer than 10 evaluation rows | Model stored, horizon not replayable |
| Calibrator slope not increasing | Identity calibration with a recorded note |
| LightGBM missing | `RuntimeError` telling the operator to install it or use `models.engine = "sklearn"` |

The suite never fabricates a model and never reports a metric it cannot compute.

---

## Related Documentation

- [Model inputs](../data/09_MODEL_INPUTS.md)
- [Labels, payouts, and EV](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [Signal router](13_SIGNAL_ROUTER.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [ML pipeline](08_ML_PIPELINE.md)

---

*Last updated: 2026-11-19*
