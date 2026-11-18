# Labels, Payouts, and Expected Value

Status: Planning

> This document defines the prediction target, binary-option payoff math, and the evaluation gate. It is the contract between the data pipeline and the ML pipeline.

---

## Binary Option Mechanics

A binary option pays a fixed profit if the chosen direction wins and loses the stake if it loses.

| Outcome | Profit / loss per unit stake |
|---------|-----------------------------|
| Win | `+payout` |
| Loss | `-1` |
| Tie / refund | Configured; typically `0` or `-1` depending on platform rules |

Where `payout` is the broker's profit rate, for example `0.80` for an 80% payout.

### Breakeven Win Rate

With no tie and no fees:

```text
E[V] = q * payout - (1 - q)
```

Setting `E[V] = 0`:

```text
q_breakeven = 1 / (1 + payout)
```

| Payout | Breakeven win rate |
|--------|--------------------|
| 0.70 | 58.82% |
| 0.80 | 55.56% |
| 0.85 | 54.05% |
| 0.90 | 52.63% |

A model with 54% accuracy is profitable at 90% payout and unprofitable at 70% payout. Accuracy alone is not a sufficient metric.

---

## Prediction Target

Predictions are tick-based. A model scores each accepted tick as a potential entry point.

| Element | Definition |
|---------|------------|
| Decision time | Timestamp of one accepted tick |
| Entry price | That tick's price |
| Horizons | 60, 90, 120, 180 seconds (configurable) |
| Exit | First tick at or after `entry + horizon` within the tolerance window |
| Tie | Exit price exactly equals entry price |

Label for one tick and one horizon `h`:

```text
exit_price_h = price of the first tick with timestamp >= t + h
               and timestamp <= t + h + exit_tolerance

label_h = call    if exit_price_h > entry_price
        = put     if exit_price_h < entry_price
        = tie     if exit_price_h == entry_price
        = missing if no tick satisfies the exit window
```

Defaults: `exit_tolerance = 5 seconds`, `tie_policy = exclude`.

Ties are never mapped to Put. A missing exit is never mapped to a directional label. Both stay explicit, and rows that are not `call` or `put` are marked unusable for directional training.

### Why tick-based labels

Binary options let the trader enter at an arbitrary moment, including mid-candle. Tick-based labels match that mechanic and allow every horizon to be evaluated from the same entry.

The cost is overlapping observations: adjacent ticks have nearly identical features and outcomes that overlap in time. This is handled at validation time, not by pretending the rows are independent. See [Model Validation](../system/09_MODEL_VALIDATION.md).

### Candles are context, not decisions

1-minute candles provide the macro, fast, and forming context windows. They define value, volatility, and activity baselines. They do not create decision points or labels.

---

## Alternative Labels

These are documented for future research, not the default:

| Label type | Definition | Trade-off |
|------------|------------|-----------|
| Tick fixed-offset (default) | Sign of price change at a fixed second offset | Matches arbitrary entry; overlapping observations |
| Candle close | Exit at the close of a later completed candle | Cleaner for 60/120/180; cannot express 90s exactly |
| Touch / barrier | Whether price touches a barrier before expiry | Closer to some platform mechanics; path-dependent |
| Triple barrier | Profit target, stop, and time barrier | More realistic risk modelling; more complex |

A candle-close variant is a research label, not the default. It must carry its own `label_version`.

Any change to the label definition requires a dataset version bump.

---

## Expected Value and Trade Decision

For a predicted win probability `q_hat`:

```text
EV_per_unit = q_hat * payout - (1 - q_hat)
            = q_hat * (1 + payout) - 1
```

Trade only if:

```text
q_hat > q_breakeven + margin
```

Where `margin` covers calibration error, model drift, and execution uncertainty. The default margin is a configuration value, not a hard-coded constant.

### No-Trade Output

The system must support three outputs:

1. Call
2. Put
3. No trade

No-trade is required when:

- The calibrated probability is below the threshold.
- The regime is `ambiguous`.
- Features are missing.
- The data stream has a gap or quality flag.
- Risk limits block a new trade.

---

## Calibration

Probabilities must be calibrated before they are used for trade decisions.

Required metrics:

| Metric | Purpose |
|--------|---------|
| Brier score | Overall probability accuracy |
| Log loss | Penalises confident wrong predictions |
| Reliability curve | Visual calibration check |
| Expected calibration error | Summary calibration error |
| Precision at threshold | Quality of actionable signals |
| Coverage | Share of rows that produce a trade |

A model can have good AUC and poor calibration. Calibration is mandatory.

---

## Dataset Construction

One row per:

- `active_id`
- Tick timestamp
- Expiry horizon
- Feature version
- Label version

The feature table has one row per tick. The label table is long format: one row per tick per horizon. Joining them on `tick_id` gives the training dataset.

Required columns:

| Column | Meaning |
|--------|---------|
| `tick_id` | Row ordinal in the sorted tick stream |
| `timestamp` | Tick receipt time, ISO 8601 with offset |
| `active_id` | Instrument |
| `entry_price` | Tick price at entry |
| `horizon_seconds` | 60, 90, 120, or 180 |
| `exit_timestamp` | Receipt time of the exit tick, or null |
| `exit_price` | Exit tick price, or null |
| `exit_delay_seconds` | Delay beyond the exact horizon, or null |
| `label` | `call`, `put`, `tie`, or `missing` |
| `usable` | `1` when the row may be used for directional training |
| `payout` | Payout used for EV |
| `feature_version` | Feature set version, for example `amt-v2` |
| `label_version` | Label definition version, for example `tick-horizon-v1` |
| `quality_flags` | Gaps, stale data, missing profile |

### Exclusion Rules

Exclude rows when:

- `label` is `tie` and `tie_policy = "exclude"`.
- `label` is `missing`.
- The profile or volatility is missing and the model requires them.
- `active_id` metadata is missing for payout or pip size.
- The row falls outside the configured session.
- The tick is a duplicate or flagged out of order.

Exclusions must be counted and reported, not silently dropped.

---

## Leakage Rules

1. Features at time `t` may use only data up to `t`.
2. The label uses data after `t`; it must never enter the feature vector.
3. Train, validation, and test splits are chronological.
4. Purge rows whose label window crosses a split boundary; the purge length is the longest horizon plus tolerance.
5. Do not use future payout or future instrument metadata in historical labels unless the value was known at the time.
6. Overlapping label windows are expected. They reduce effective sample size and must be handled by purging and by reporting the number of independent windows, not just the row count.

---

## Evaluation Gate

Before any execution work:

1. Out-of-sample, walk-forward EV per trade is positive after using the actual payout.
2. Win rate exceeds the payout breakeven by the configured margin.
3. Calibration error is within the configured tolerance.
4. Results are stable across instruments and weekday/weekend splits.
5. Trade count is large enough to be statistically meaningful.
6. A rule-based AMT baseline and a random baseline are both beaten.

If the gate fails, the project returns to feature research or declares the hypothesis unsupported.

---

## Related Documentation

- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](05_AMT_FEATURE_SPEC.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [ML Pipeline](../system/08_ML_PIPELINE.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-18*
