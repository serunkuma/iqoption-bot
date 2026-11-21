# Model Validation

Status: Current

> Validation exists to answer one question: does the engine have positive expected value after payout, out of sample, on data it has never seen? Everything below is designed to make a false positive hard.

The current validation path evaluates the four horizon probability models and deterministic EV router. Candle-close runtime inference and `.joblib` compatibility checks are implemented, but a learned selector must be evaluated separately against that baseline. Runtime wiring is not evidence of a validated edge.

---

## Principles

1. **Time-based splits only.** Random splitting of overlapping time-series rows leaks the future.
2. **No leakage.** Features at `t` use only ticks at or before `t`.
3. **Payout-aware.** Accuracy is not the objective; EV is.
4. **Held-out replay.** The backtest may only consume probabilities the model was not fit on.
5. **Explicit exclusions.** Ties, missing exits, and gaps are counted, not repaired.
6. **Reproducible.** Versions and config hash travel with every artefact.
7. **Fail closed.** Inconclusive evidence means no trade.
8. **Small samples are named as such.** A metric computed on dozens of trades is not a result.

---

## Split Structure

```text
|------------ train ------------|-- purge 180s --|-- test fold --|
```

Purged walk-forward with `n_splits = 5`. Each fold trains only on rows at least 180 seconds older than the first test row, so a training row whose 180-second label window overlaps the test period is excluded.

Then, within the walk-forward out-of-sample predictions:

```text
|------ calibration 70% ------|------ evaluation 30% ------|
```

The evaluation slice is later in time than the calibration slice and is never used to fit anything. It is the only slice the backtest may replay.

Why two layers? Walk-forward alone still lets a calibrator see the same rows whose scores it later transforms. Layering the chronological calibration/evaluation split removes that too.

---

## Coverage

| Split | Rows | Purpose |
|-------|------|---------|
| Training | All usable rows for the horizon | Final estimator |
| Purged walk-forward | Rolling earlier folds | OOS probability generation |
| Calibration | Earlier 70% of OOS | Fit isotonic/Platt |
| Evaluation | Later 30% of OOS | Metrics, backtest |

With one snapshot per minute, overlapping labels still reduce effective sample size. The evaluation slice is later than the calibration slice; its actual size depends on usable rows and the walk-forward splits.

---

## Required Metrics

| Metric | Threshold for "interesting" |
|--------|------------------------------|
| EV per trade | Positive after the 3% hurdle |
| Win rate | Above `1 / (1 + payout)` |
| Brier | Below 0.25 (a 50/50 constant scores about 0.25) |
| AUC | Above 0.55, and stable across folds |
| ECE | Below the configured tolerance |
| Trade count | Enough independent expiry windows to matter |

These are sanity thresholds, not acceptance criteria. A single capture that clears them proves little.

---

## Overlapping Windows

A 180-second horizon sampled once per minute creates overlapping label windows. Two consequences:

1. Row counts overstate independent information. The effective sample is roughly `rows * spacing / horizon`.
2. Any split that ignores time will place near-duplicate rows on both sides.

The implementation addresses (1) with overlap weights `1 / max(1, horizon / spacing)` and (2) with purging and chronological splits. Reports do not currently print an effective sample size; that is a gap.

---

## Backtest Honesty

The backtest iterates every snapshot in the dataset, but only snapshots present in the evaluation table produce probabilities. Everything else is `skipped_no_model`.

It never calls `predict_vector`, and it never refits. The estimators used to produce the evaluation probabilities saw only earlier data; the calibrators saw only earlier out-of-sample data.

An earlier iteration replayed in-sample predictions and produced 254 trades with zero wins. That output was invalid and is not cited anywhere. The current design makes that class of mistake structurally difficult: there is no code path from the backtest to an in-sample probability.

---

## Payout Gate

At payout `p`, breakeven is `1 / (1 + p)`. Configured payouts are `0.80 / 0.82 / 0.84 / 0.86` for 60/90/120/180 seconds.

| Horizon | Payout | Breakeven win rate |
|---------|--------|--------------------|
| 60s | 0.80 | 55.56% |
| 90s | 0.82 | 54.95% |
| 120s | 0.84 | 54.35% |
| 180s | 0.86 | 53.76% |

A 54% model is profitable at 180s and loses at 60s. Validation must therefore be per horizon, and a blended win rate is misleading.

If the broker changes payouts, the hurdle changes. Configured payouts must be refreshed before any result is believed.

---

## Go/No-Go Gate

Before any demo or live work:

- [ ] Held-out EV per trade is positive after the actual payout and the 3% hurdle.
- [ ] Win rate exceeds breakeven by a margin larger than the confidence interval.
- [ ] Calibration error is within tolerance and the reliability curve is not degenerate.
- [ ] Results hold across at least two independent captures or instruments.
- [ ] Weekday and weekend subsets are reported separately.
- [ ] A rule-based AMT baseline and a random baseline are both beaten.
- [ ] Trade count is large enough for the observed effect to be distinguishable from noise.
- [ ] The result is robust to a changed random seed and holds on independent captures at the fixed candle-close cadence.

If the gate fails, the correct action is to return to feature research or declare the hypothesis unsupported on OTC data. It is not to lower the hurdle.

## Future Learned-Selector Gate

Before any learned direction/horizon/no-trade selector is promoted beyond shadow evaluation:

- Define its training target, candidate inputs, model scope, and no-trade label before examining its evaluation period.
- Compare it with the existing horizon-classifier-plus-EV-router path on the same untouched chronological periods and report payout-adjusted outcomes.
- Include independent captures, uncertainty/sample sufficiency, calibration where probabilities are used, and robustness across relevant sessions/instruments.
- Keep payout, configured risk limits, execution permission, and artifact compatibility as deterministic hard gates.
- Fail closed for ML proposals when the configured artifact is missing or incompatible; surface a diagnostic rather than silently using a fallback.
- Do not tune the selector against the held-out evaluation slice or treat synthetic data as market evidence.

The selector promotion principles remain planning work. The runtime loader and fail-closed artifact compatibility checks exist, but sustained shadow/paper evidence is not established. See [ML Runtime and Signal Selection](../planning/ml-runtime-and-signal-selection.md).

---

## Current Evidence

| Question | Answer |
|----------|--------|
| Has the pipeline run end to end? | Yes, on synthetic and small captures |
| Has any horizon shown an edge? | No |
| Are current results distinguishable from noise? | No |
| Has a real multi-day capture been validated? | No |
| Is live execution safe? | No |

### Historical synthetic run (pre-candle-close contract)

The following checked-in report predates the candle-close contract and used the former `:30` snapshot cadence, `core16-v1`, and `amt-v3`. Its metrics do not describe the current runtime/model versions. The checked-in synthetic capture (48,000 ticks over 800 minutes, one instrument) built 793 snapshots and 3,172 dataset rows. Training produced all four horizons with 77–79 evaluation rows each; every Platt fit was rejected as non-increasing, so identity calibration shipped. Held-out AUC ranged from 0.501 to 0.605 and Brier from 0.250 to 0.270.

That historical backtest routed 81 snapshots, opened 55 trades, and closed 25 winners against 30 losers: win rate 0.455, PnL `-9.8` at unit stake. At the 60s payout of 0.80 the breakeven win rate is 0.556, so that run lost, as expected.

That is a correct and useful result. It shows the harness measures a losing system honestly instead of manufacturing trades. It says nothing about real AMT behaviour, because synthetic ticks have no auction structure.

Synthetic data has no auction participants and no real payout behaviour. It can prove plumbing; it cannot prove edge.

---

## Anti-Patterns

- Lowering `min_ev` until trades appear.
- Widening the evaluation slice until the sample looks large.
- Reporting AUC as profitability.
- Reporting a blended win rate across horizons with different payouts.
- Fitting a calibrator on the evaluation slice.
- Using `predict_vector` in a backtest.
- Treating synthetic smoke-test output as evidence.
- Adding features after seeing the evaluation result, then re-reporting the same slice.

---

## Related Documentation

- [Model suite](12_MODEL_SUITE.md)
- [Signal router](13_SIGNAL_ROUTER.md)
- [Reports and diagnostics](15_REPORTS_AND_DIAGNOSTICS.md)
- [Labels, payouts, and EV](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)
- [ML Runtime and Signal Selection](../planning/ml-runtime-and-signal-selection.md)

---

*Last updated: 2026-11-21*
