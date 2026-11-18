# Model Validation

Status: Planning

> This document defines how the AMT/ML hypothesis is tested. The goal is not a good-looking backtest; it is evidence that survives time, regime changes, and payout costs.

---

## Principles

1. **Time-based splits only.** Never random-split time series data.
2. **No leakage.** Features at `t` use only data available at `t`.
3. **Payout-aware.** Evaluate expected value, not just accuracy.
4. **Regime-aware.** Report balance and imbalance results separately.
5. **Weekday/weekend-aware.** OTC pricing may change by session.
6. **Baseline-aware.** Beat random and rule-based baselines.
7. **Reproducible.** Every result records data, feature, label, model, and config versions.
8. **Fail closed.** No execution if validation is inconclusive.

---

## Splits

```text
|------------ train ------------|-- purge --|-- validation --|-- purge --|-- test --|
                                                                              ^
                                                                         out-of-sample
```

Rules:

- Chronological order only.
- Purge rows whose label window crosses the next split. The purge length is the longest horizon plus exit tolerance: 180 seconds + 5 seconds by default.
- Embargo a configurable period after each split.
- The test set is touched once per candidate model, not tuned against repeatedly.
- Walk-forward evaluation is required for the final candidate.
- Report metrics per horizon. A model that works only at 180s is a different claim from one that works at 60s.

### Walk-Forward

```text
fold 1: train [t0, t1) -> validate [t1, t2)
fold 2: train [t0, t2) -> validate [t2, t3)
fold 3: train [t0, t3) -> validate [t3, t4)
...
```

Report per-fold and aggregate metrics. A model that works in only one fold is not validated.

---

## Overlapping Tick Labels

Rows are ticks, so observations are not independent:

- Adjacent ticks share almost all of their feature window.
- Label windows overlap: a 180-second label covers 180 seconds of other rows.
- A raw row count overstates the number of independent outcomes.

Required handling:

1. Purge and embargo by time, not by row count.
2. Report the number of independent expiry windows as well as the row count.
3. Report results per horizon; longer horizons overlap more.
4. Simulate trades with at most one open position per instrument, using the same entry and expiry rules.
5. Do not compare row-level win rates directly across horizons without stating the overlap.

Optional but recommended: cluster standard errors by time bucket, or report block-bootstrap confidence intervals over contiguous time blocks.

---

## Trade Simulation

The backtest must not assume every labelled row is tradeable.

| Rule | Requirement |
|------|-------------|
| Position limit | At most one open trade per active instrument |
| Entry | Signal tick plus configured execution latency |
| Expiry | The same horizon used for the label |
| Payout | The payout available at entry, not a global average |
| Overlap | A new signal is skipped while a trade is open |
| Reporting | Count skipped signals and overlapping labels separately |

A strategy that only looks profitable because it takes every overlapping signal is not validated.

---

## Baselines

| Baseline | Purpose |
|----------|---------|
| Random direction | Lower bound |
| Always Call | Detects directional bias in the sample |
| Always Put | Detects directional bias in the sample |
| Rule-based AMT | Feature sanity check and performance floor |
| Majority class | Detects class-imbalance artefacts |

The ML model must beat the rule-based AMT baseline and the random baseline on out-of-sample EV.

---

## Metrics

### Classification

| Metric | Why |
|--------|-----|
| Accuracy | Intuitive, but insufficient alone |
| Precision / recall | Quality of actionable signals |
| AUC | Ranking quality |
| Log loss | Probability quality |
| Brier score | Calibration and accuracy combined |
| Confusion matrix | Error structure |

### Calibration

| Metric | Why |
|--------|-----|
| Reliability curve | Visual calibration |
| Expected calibration error | Summary calibration |
| Brier decomposition | Resolution vs reliability |

### Trading

| Metric | Why |
|--------|-----|
| Win rate | Compare to payout breakeven |
| EV per trade | Primary profitability measure |
| Trade count | Statistical significance |
| Coverage | Share of rows that produce a trade |
| Independent expiry windows | Honest measure of sample size |
| Skipped overlapping signals | Shows how much the position limit removes |
| Average payout | Correct cost assumption |
| Max drawdown | Risk |
| Consecutive losses | Risk-limit design |
| PnL distribution | Tail risk |

### Regime and Session

Report separately for:

- Balance vs imbalance.
- Weekday vs weekend.
- Each instrument.
- Each session (Asia, London, New York, overlap).
- High vs low volatility.

---

## OTC vs Live Spot

If a live spot FX feed is available:

1. Compute the same AMT features on both feeds.
2. Compare feature distributions.
3. Compare predictive performance.
4. Test whether the OTC feed behaves like a lagged, smoothed, or distorted version of spot.
5. Test weekday vs weekend separately.

If AMT has no edge on live spot and no stable relationship to the OTC feed, the OTC result is suspect.

---

## Drift Monitoring

| Drift type | Measure | Action |
|------------|---------|--------|
| Feature drift | Population stability index or distribution tests | Investigate; retrain if persistent |
| Prediction drift | Distribution of predicted probabilities | Check calibration |
| Performance drift | Rolling EV, win rate, calibration | Reduce size or stop trading |
| Data drift | Tick rate, gaps, message mix | Check ingestion and broker behaviour |
| Regime drift | Share of balance/imbalance/ambiguous | Re-evaluate model mix |

Monitoring thresholds are configuration values with documented defaults.

---

## Go/No-Go Gate

Execution work may begin only when all conditions hold:

- [ ] Out-of-sample EV per trade is positive after using the actual payout, for at least one horizon.
- [ ] Win rate exceeds `1 / (1 + payout)` by the configured margin for that horizon.
- [ ] Calibration error is within tolerance.
- [ ] Results are stable across walk-forward folds.
- [ ] Results survive the one-open-position trade simulation.
- [ ] Results are stable across weekday/weekend splits.
- [ ] The rule-based AMT baseline and random baseline are beaten.
- [ ] Independent expiry windows, not just row counts, are large enough.
- [ ] Feature and label versions are recorded and reproducible.
- [ ] A paper-trading run confirms the live pipeline matches offline results.

If the gate fails, do not proceed to live execution. Return to feature research or document the hypothesis as unsupported.

---

## Reporting

Every validation report includes:

- Dataset and feature versions.
- Label definition and payout assumptions.
- Split boundaries and purge/embargo settings.
- All metrics by fold, regime, instrument, and session.
- Calibration plots and tables.
- Trade-count and coverage statistics.
- Known data-quality issues.
- A clear pass/fail decision against the gate.

Reports are stored under `reports/` and referenced in the decision log.

---

## Related Documentation

- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [ML Pipeline](08_ML_PIPELINE.md)
- [Data Pipeline](07_DATA_PIPELINE.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)
- [Security and Safety](06_SECURITY.md)

---

*Last updated: 2026-11-18*
