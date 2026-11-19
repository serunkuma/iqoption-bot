# Labels, Payouts, and Expected Value

Status: Current

> This document defines the prediction target, binary-option payoff math, and the evaluation gate. It is the contract between the data pipeline and the ML pipeline. Labels are attached to snapshots, priced at a delayed entry tick, and versioned `snapshot-horizon-v1`.

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

Predictions are attached to **snapshots**, not to every tick. A snapshot is a validated decision point inside a forming minute, by default `:30`.

| Element | Definition |
|---------|------------|
| Decision time | `forming_start + snapshot offset` |
| Features | Ticks at or before the decision time |
| Entry time | First tick at or after `decision + 250ms` within 1s tolerance |
| Entry price | That tick's price |
| Horizons | 60, 90, 120, 180 seconds (configurable) |
| Exit | First tick at or after `entry + horizon` within the 5s tolerance |
| Tie | Exit price exactly equals entry price |

Label for one snapshot and one horizon `h`:

```text
target_h     = actual_entry_time + h
exit_price_h = price of the first tick with timestamp >= target_h
               and timestamp <= target_h + exit_tolerance

label_h = call    if exit_price_h > entry_price
        = put     if exit_price_h < entry_price
        = tie     if exit_price_h == entry_price
        = missing if no tick satisfies the exit window
```

Defaults: `entry_delay_ms = 250`, `entry_tolerance_seconds = 1.0`, `exit_tolerance_seconds = 5.0`, `tie_policy = exclude`.

The exit is measured from the **actual entry time**, not from the snapshot time. A 60s horizon from a snapshot at `:30` that entered at `:30.31` expires at `:31:30.31`.

Ties are never mapped to Put. A missing exit is never mapped to a directional label. Both stay explicit, and rows that are not `call` or `put` are marked unusable for directional training.

### Why snapshot labels

Binary options let the trader enter at an arbitrary moment, including mid-candle, so labels are priced from an actual tick. But evaluating every tick would create thousands of near-identical rows per minute with overlapping outcomes, dominated by whichever microsecond was sampled.

Fixed snapshot offsets give a small, reproducible set of decision points while keeping entry and exit priced from real ticks. The cost is still overlapping observations — a 180s horizon sampled every 30s overlaps six rows — which is handled at validation time with purge and overlap weights.

### Candles are context, not decisions

1-minute candles provide the macro, fast, and forming context windows. They define value, volatility, and activity baselines. They do not create decision points or labels.

---

## Alternative Labels

These are documented for future research, not the default:

| Label type | Definition | Trade-off |
|------------|------------|-----------|
| Snapshot fixed-offset (default) | Sign of price change at entry plus a fixed horizon | Matches arbitrary entry; overlapping observations |
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
EV_per_unit >= min_ev
```

`min_ev` defaults to `0.03` in `[router]`. It covers calibration error, model drift, and execution uncertainty. It is a configuration value, not a hard-coded constant.

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

- `snapshot_id`
- Expiry horizon

The feature table has one row per snapshot. The label table is long format: one row per snapshot per horizon. Joining them on `snapshot_id` gives the training dataset.

Required columns:

| Column | Meaning |
|--------|---------|
| `snapshot_id` | Snapshot ordinal within the build |
| `timestamp` | Snapshot time, ISO 8601 with offset |
| `active_id` | Instrument |
| `entry_timestamp` | Receipt time of the delayed entry tick |
| `entry_price` | Price of the delayed entry tick |
| `horizon_seconds` | 60, 90, 120, or 180 |
| `exit_timestamp` | Receipt time of the exit tick, or null |
| `exit_price` | Exit tick price, or null |
| `exit_delay_seconds` | Delay beyond the exact horizon, or null |
| `label` | `call`, `put`, `tie`, or `missing` |
| `usable` | `1` when the row may be used for directional training |
| `feature_version` | `amt-v3` |
| `core_feature_version` | `core16-v1` |
| `label_version` | `snapshot-horizon-v1` |

Payout is not stored per row; it is configured per horizon in `[router.payouts]`. Diagnostics such as `profile_missing` and `gap_in_window` are carried by the feature columns.

### Exclusion Rules

Exclude rows when:

- `label` is `tie` and `tie_policy = "exclude"`.
- `label` is `missing`.
- The snapshot failed the continuity gate (it is never built).
- The tick is an exact duplicate (it is dropped in the store).

Exclusions must be counted and reported, not silently dropped.

---

## Leakage Rules

1. Features at time `t` may use only data up to `t`.
2. The label uses data after `t`; it must never enter the feature vector.
3. Train, validation, and test splits are chronological.
4. Purge rows whose label window crosses a split boundary; the purge length is the longest horizon plus tolerance (`models.purge_seconds = 180`).
5. Do not use future payout or future instrument metadata in historical labels unless the value was known at the time.
6. Overlapping label windows are expected. They reduce effective sample size and are handled with purging and overlap weights, not by pretending rows are independent.

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

- [Snapshots and continuity](08_SNAPSHOTS_AND_CONTINUITY.md)
- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](05_AMT_FEATURE_SPEC.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [ML Pipeline](../system/08_ML_PIPELINE.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-19*
