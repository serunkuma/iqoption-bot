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

Default target:

- **Horizon:** 1 minute.
- **Decision time:** close of a completed 1-minute candle.
- **Entry price:** close of that completed candle.
- **Expiry:** 1 minute after entry.
- **Exit price:** close of the next completed 1-minute candle.

Label:

```text
call_wins = 1 if exit_price > entry_price else 0
put_wins  = 1 if exit_price < entry_price else 0
tie       = 1 if exit_price == entry_price else 0
```

Default tie policy: ties are excluded from directional training and counted separately. The execution policy must define whether ties are refunded or lost.

### Why the next completed candle

Using the next completed candle gives a clean, reproducible label. It avoids intrabar path ambiguity in the first version. Path-aware labels can be added later.

---

## Alternative Labels

These are documented for future research, not the default:

| Label type | Definition | Trade-off |
|------------|------------|-----------|
| Next-close (default) | Exit at the close of the next 1-minute candle | Simple, reproducible, ignores intrabar path |
| Touch / barrier | Whether price touches a barrier before expiry | Closer to some platform mechanics; path-dependent |
| Triple barrier | Profit target, stop, and time barrier | More realistic risk modelling; more complex |
| Direction at fixed offset | Sign of price change at a fixed second offset | Fine-grained but sensitive to timing |

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
- Decision timestamp
- Expiry horizon
- Feature version
- Label version

Required columns:

| Column | Meaning |
|--------|---------|
| `decision_at` | Timestamp of the completed candle close |
| `active_id` | Instrument |
| `entry_price` | Close of the decision candle |
| `exit_price` | Close of the expiry candle |
| `label_call` | Whether Call won |
| `label_put` | Whether Put won |
| `tie` | Whether the outcome was a tie |
| `payout` | Payout used for EV |
| `feature_version` | Feature set version |
| `label_version` | Label definition version |
| `quality_flags` | Gaps, late ticks, stale data |

### Exclusion Rules

Exclude rows when:

- The decision candle or expiry candle is incomplete.
- There is a gap in either candle.
- The expiry candle is missing.
- `active_id` metadata is missing for payout or pip size.
- The row falls outside the configured session.

Exclusions must be counted and reported, not silently dropped.

---

## Leakage Rules

1. Features at time `t` may use only data up to `t`.
2. The label uses data after `t`; it must never enter the feature vector.
3. Train, validation, and test splits are chronological.
4. Purge rows near split boundaries to prevent overlapping label horizons.
5. Do not use future payout or future instrument metadata in historical labels unless the value was known at the time.

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
