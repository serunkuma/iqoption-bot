# Phase 3 — ML Pipeline and Validation

Status: Current

> **Objective:** Build a reproducible, payout-aware ML pipeline, validate the AMT hypothesis out of sample, and make an explicit go/no-go decision.

---

## Scope

- Build labels and expected-value math.
- Build versioned datasets.
- Train one calibrated classifier per horizon.
- Calibrate probabilities on data the model did not see.
- Run purged walk-forward validation.
- Compare against a rule-based baseline.
- Produce a go/no-go report.

Out of scope: live execution.

---

## Status

The pipeline is built and tested. Validation on real captures is the remaining gate.

Training and held-out offline evaluation are implemented. Timestamped `.joblib` suites with manifests are produced; runtime loading validates compatibility and fails closed. Candle-close inference and paper decisions exist, but real-capture validation, sustained runtime/offline parity, and a learned selector remain open. See [ML Runtime and Signal Selection](ml-runtime-and-signal-selection.md).

| Component | Status | Location |
|-----------|--------|----------|
| Snapshot labels and timed exits | Done | `engine/domain/labels.py`, `engine/sampler.py` |
| EV and breakeven | Done | `engine/router.py` |
| Purged walk-forward | Done | `engine/models.py` |
| Calibration (isotonic/Platt) | Done | `engine/models.py` |
| Held-out evaluation table | Done | `engine/models.py` |
| Router with reason codes | Done | `engine/router.py` |
| Paper backtest | Done | `engine/backtest.py` |
| JSON/Markdown reports | Done | `engine/reports.py` |
| Rule-based baseline | Not started | — |
| Two-stage regime model | Research only | [ML pipeline](../system/08_ML_PIPELINE.md) |
| Real-capture validation | Not started | — |
| Go/no-go decision | Not started | — |

---

## Tasks

### Labels and EV

- [x] Implement snapshot-horizon labels for 60/90/120/180 seconds.
- [x] Implement first-tick-at-or-after-horizon exit with tolerance.
- [x] Implement explicit tie and missing-exit handling.
- [x] Implement payout-aware EV per horizon.
- [x] Implement breakeven win rate per horizon.
- [x] Add exclusion rules for ties and missing exits.
- [x] Add label-version metadata to the dataset.

### Dataset

- [x] Build the dataset join across features, labels, and quality flags.
- [x] Add chronological splits with purge.
- [x] Record feature, label, and dataset versions.
- [x] Record the config hash.
- [x] Add a pickle round-trip test for the model suite.
- [ ] Add a byte-for-byte replay check from raw JSONL.

### Models

- [x] Train four binary classifiers, one per horizon.
- [x] Down-weight overlapping label windows.
- [x] Calibrate on a chronological share of out-of-sample rows.
- [x] Store the later share as the held-out evaluation table.
- [x] Reject a non-increasing calibration fit.
- [x] Skip empty or one-class horizons with a reason.
- [x] Register model artefacts with versions and a config hash.
- [x] Persist a timestamped `.joblib` suite with manifest for runtime compatibility checks.
- [ ] Define and validate a learned direction/horizon/no-trade selector against the existing deterministic EV router.
- [ ] Implement the rule-based Stage 1 regime gate.
- [ ] Train balance and imbalance models per horizon.
- [ ] Document Approach B as research only.

### Validation

- [x] Run purged walk-forward validation.
- [x] Report per-horizon metrics.
- [x] Report Brier, log loss, AUC, and reliability.
- [ ] Report metrics by fold and session.
- [ ] Report independent expiry windows alongside row counts.
- [x] Simulate trades with one open position at a time.
- [x] Replay only held-out probabilities.
- [ ] Compare with random and rule-based baselines.
- [ ] Compare weekday and weekend results.
- [ ] Run drift checks.
- [ ] Apply the go/no-go gate on a real capture.

### Documentation

- [x] Record the model library choice.
- [x] Record the feature and label versions.
- [x] Document training, routing, execution, and reporting.
- [ ] Publish a validation report on a real capture.
- [ ] Update `AGENTS.md` with the decision.

---

## Deliverables

- Snapshot label builder.
- Versioned dataset.
- Four calibrated horizon models.
- Held-out evaluation table.
- Paper backtest with JSON/Markdown reports.
- Rule-based baseline comparison (open).
- Go/no-go decision record (open).

---

## Acceptance Criteria

- [x] Labels cannot leak into features.
- [x] Splits are chronological with purge.
- [x] The evaluation slice is disjoint from calibration and training.
- [x] The backtest cannot access in-sample predictions.
- [x] Calibration is measured, not assumed.
- [x] EV uses the configured payout.
- [x] A rejected calibration fit is recorded, not hidden.
- [ ] Walk-forward results are reported per fold.
- [ ] The model beats the rule-based and random baselines out of sample, or the hypothesis is documented as unsupported.
- [ ] The go/no-go decision is recorded before any execution work.

---

## Dependencies

- Phase 2: features, labels, dataset (done).
- Payout data or a documented payout assumption (configured).
- Sufficient real capture data (open).

---

## Related Documentation

- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [Model Suite](../system/12_MODEL_SUITE.md)
- [Signal Router](../system/13_SIGNAL_ROUTER.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [ML Runtime and Signal Selection](ml-runtime-and-signal-selection.md)
- [Reports and Diagnostics](../system/15_REPORTS_AND_DIAGNOSTICS.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-21*
