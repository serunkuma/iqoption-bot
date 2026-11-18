# Phase 3 — ML Pipeline and Validation

Status: Planning

> **Objective:** Build a reproducible, payout-aware ML pipeline, validate the AMT hypothesis out of sample, and make an explicit go/no-go decision.

---

## Scope

- Build labels and expected-value math.
- Build versioned datasets.
- Implement the two-stage regime architecture.
- Calibrate probabilities.
- Run walk-forward validation.
- Compare against the rule-based baseline.
- Produce a go/no-go report.

Out of scope: live execution.

---

## Tasks

### Labels and EV

- [ ] Implement the next-close 1-minute label.
- [ ] Implement tie policy.
- [ ] Implement payout-aware EV.
- [ ] Implement breakeven win rate.
- [ ] Add exclusion rules for gaps and incomplete candles.
- [ ] Add label-version metadata.

### Dataset

- [ ] Build the dataset join across features, labels, metadata, and quality flags.
- [ ] Add chronological splits with purge and embargo.
- [ ] Record feature, label, and dataset versions.
- [ ] Add reproducibility checks.

### Models

- [ ] Implement the rule-based Stage 1 regime gate.
- [ ] Train a balance model.
- [ ] Train an imbalance model.
- [ ] Calibrate probabilities on a held-out calibration set.
- [ ] Add a no-trade threshold.
- [ ] Register model artifacts and versions.
- [ ] Document Approach B as research only.

### Validation

- [ ] Run walk-forward validation.
- [ ] Report metrics by fold, regime, instrument, and session.
- [ ] Report calibration curves and Brier score.
- [ ] Compare with random and rule-based baselines.
- [ ] Compare weekday and weekend results.
- [ ] Compare with live spot FX if available.
- [ ] Run drift checks.
- [ ] Apply the go/no-go gate.

### Documentation

- [ ] Record the model library choice.
- [ ] Record the feature and label versions.
- [ ] Publish the validation report under `reports/`.
- [ ] Update `AGENTS.md` with the decision.

---

## Deliverables

- Label builder.
- Versioned dataset.
- Two-stage model.
- Calibration report.
- Walk-forward validation report.
- Go/no-go decision record.

---

## Acceptance Criteria

- [ ] Labels cannot leak into features.
- [ ] Splits are chronological with purge and embargo.
- [ ] Walk-forward results are reported per fold.
- [ ] Calibration is measured, not assumed.
- [ ] EV uses the actual payout.
- [ ] The model beats the rule-based and random baselines out of sample, or the hypothesis is documented as unsupported.
- [ ] The go/no-go decision is recorded before any execution work.

---

## Dependencies

- Phase 2 accepted: candles, features, baseline, backtest harness.
- Payout data or a documented payout assumption.
- Sufficient historical tick/candle data.

---

## Related Documentation

- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [ML Pipeline](../system/08_ML_PIPELINE.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-18*
