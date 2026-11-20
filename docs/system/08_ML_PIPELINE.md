# ML Pipeline

Status: Current

> The implemented architecture is four shallow calibrated binary classifiers, one per expiry horizon, trained on purged walk-forward splits. The earlier two-stage regime design is retained as research, not as the shipped path.

> **Boundary:** This is the current offline training and evaluation path. `predict_vector` is not wired to live features, and the current EV router is deterministic. The planned runtime loader and learned signal selector are described in [ML Runtime and Signal Selection](../planning/ml-runtime-and-signal-selection.md).

---

## Implemented Architecture

```text
dataset (one row per snapshot per horizon)
        |
        +--> 60s  classifier --> calibrator --> p(call)
        +--> 90s  classifier --> calibrator --> p(call)
        +--> 120s classifier --> calibrator --> p(call)
        +--> 180s classifier --> calibrator --> p(call)
                                                   |
                                                   v
                                            signal router
```

Each classifier answers one question: *is the exit price above the entry price at this horizon?* The label `put` is the complement. The router, not the model, decides whether the probability is high enough to trade after payout.

### Why Not One Multi-Class Model

The horizons have different payouts and different signal-to-noise. A shared multi-class model couples them: a bad 180s boundary can degrade the 60s decision. Independent binaries also let a horizon be skipped cleanly when it has too few rows or one class.

### Why Not the Two-Stage Regime Model First

The two-stage design — a balance/imbalance gate, then conditional models — needs a validated regime rule and enough rows per regime to train two models. Neither exists. Building it first would mean training on an unvalidated label with a fraction of the data.

The rule-based gate remains a sensible next research step, and the diagnostics already carry the inputs it would need (`inside_va`, `edge_proximity`, `excess_*`, activity ratios). See [Approach A as research](#approach-a-as-research).

---

## Training Flow

1. Filter to rows where `horizon_seconds == h` and `usable == 1`.
2. Drop rows without a label.
3. Encode `label == "call"` as `1`, everything else as `0`.
4. Build the 16-column matrix in `CORE_FEATURES` order.
5. Compute overlap weights from snapshot spacing and horizon.
6. Run purged walk-forward, collecting out-of-sample predictions.
7. Split those predictions chronologically 70/30.
8. Fit the calibrator on the earlier 70%.
9. Score and store the later 30% as the evaluation table.
10. Refit the shipped estimator on all usable rows.

Full detail is in [Model suite](12_MODEL_SUITE.md).

---

## Split Discipline

```text
time ----------------------------------------------------------->

fold 1: |-- train --|-- purge --|-- test --|
fold 2: |------ train ------|-- purge --|-- test --|
...
```

- Training rows must end at least `purge_seconds` (180s) before the test fold.
- No row is ever in both a training slice and its own test fold.
- The evaluation slice is later in time than the calibration slice.
- No random shuffling anywhere.

Overlapping label windows are handled by the purge and by down-weighting, not by pretending rows are independent.

---

## Calibration

`auto` chooses isotonic with at least 500 calibration rows, otherwise Platt. A Platt fit with a non-positive slope is rejected and identity calibration is shipped, with a recorded note.

A negative-slope Platt fit means the raw score is anti-correlated with the outcome on that slice. Shipping it would invert every decision, so the trainer refuses it. This is a real failure mode on noisy, small samples and it is not hidden.

---

## Hurdle, Not Threshold Clamping

The router computes `EV = q * (1 + payout) - 1` and requires `EV >= min_ev`. It never rescales `q` to clear the hurdle. If the model's honest probability does not produce enough expected value, the correct output is no trade.

---

## Evaluation Contract

| Data | Used for |
|------|----------|
| Walk-forward training slices | Fitting estimators |
| Earlier 70% of OOS | Fitting the calibrator |
| Later 30% of OOS | Metrics, calibration report, backtest replay |
| All usable rows | Final shipped estimator refit |

The backtest may only call `evaluate_snapshot`, which reads the later 30%. It cannot call `predict_vector`. This prevents the in-sample replay bug that produced 254 losing trades in an earlier iteration.

---

## Metrics

| Metric | Use |
|--------|-----|
| Brier | Primary probability score |
| Log loss | Penalises confident errors |
| AUC | Ranking quality, not profitability |
| ECE and reliability curve | Calibration shape |
| EV per trade | The decision-relevant number |
| Win rate vs breakeven | Sanity check against payout |

A model with 0.55 AUC and Brier 0.25 is not distinguishable from noise at these sample sizes. Reporting it as an edge would be dishonest.

---

## Reproducibility

| Recorded | Where |
|----------|-------|
| Feature, core feature, label versions | Dataset rows, suite |
| Config hash | Build summary, suite |
| Random seed | Config |
| Held-out evaluation rows | Suite |
| Calibration notes and skip reasons | Suite metrics |

Given the same dataset and config, training is deterministic for a fixed LightGBM build and thread count (`n_jobs=1`).

---

## Approach A as Research

The original two-stage design remains documented because it is still the leading hypothesis for improving the model:

1. Classify the market state at the snapshot as balance, imbalance, or ambiguous using a rule-based gate on value-area position and activity.
2. Train separate directional models per state, or add the state as a feature.

Preconditions before implementing it:

- The regime rule must be defined with explicit thresholds and validated on held-out data.
- Each regime must have enough usable rows to train and calibrate.
- The regime must improve held-out EV, not just AUC.

Until then, the four-horizon suite remains the current offline model path.

---

## What Is Not Implemented

- Regime gating.
- Drift monitoring.
- Online or incremental learning.
- Live inference (the vector function exists; the loop does not).
- Runtime loading of a validated `.joblib` artifact. The current model suite is saved as `suite.pkl` using Python `pickle`.
- A learned selector for direction, expiry, and no-trade. The current router applies deterministic payout-aware EV and tie-break rules to model probabilities.
- Ensembling, stacking, or hyperparameter search.
- Payout forecasting: payouts are configured.

---

## Related Documentation

- [Model suite](12_MODEL_SUITE.md)
- [Model inputs](../data/09_MODEL_INPUTS.md)
- [Signal router](13_SIGNAL_ROUTER.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Labels, payouts, and EV](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [ML Runtime and Signal Selection](../planning/ml-runtime-and-signal-selection.md)

---

*Last updated: 2026-11-20*
