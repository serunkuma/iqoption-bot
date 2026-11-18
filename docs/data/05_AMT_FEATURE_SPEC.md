# AMT Feature Specification

Status: Planning

> This document defines the exact feature families and formulas for the AMT model. Every feature must be computable causally at the decision timestamp. It is not implemented yet.

---

## Notation

| Symbol | Meaning |
|--------|---------|
| `P_t` | Current tick price at decision time `t` |
| `POC` | Point of Control from the rolling profile |
| `VAH` | Value Area High |
| `VAL` | Value Area Low |
| `sigma_t` | Rolling volatility in price units |
| `W` | Profile/volatility window, e.g. 15 or 30 minutes |
| `V` | Short velocity window, e.g. 30 seconds |

### Volatility Definition

```text
sigma_t = standard_deviation(P_i - P_{i-1} for the last N completed 1-minute candles)
```

Requirements:

- Use completed 1-minute candles only.
- Minimum of 10 candles; otherwise emit `null`.
- Do not annualise.
- The same `sigma_t` is used for all normalised distance features at time `t`.

An ATR-based alternative may be added later, but it must be a separate feature version.

---

## Feature Family 1 — Normalised Distance to Value

```text
Z_POC = (P_t - POC) / sigma_t
Z_VAH = (P_t - VAH) / sigma_t
Z_VAL = (P_t - VAL) / sigma_t
```

Interpretation:

| Feature | Positive value means | Negative value means |
|---------|----------------------|----------------------|
| `Z_POC` | Price above value centre | Price below value centre |
| `Z_VAH` | Price above value area | Price inside/below VAH |
| `Z_VAL` | Price above VAL | Price below value area |

Related features:

```text
inside_va        = 1 if VAL <= P_t <= VAH else 0
va_width         = VAH - VAL
va_width_norm    = va_width / sigma_t
poc_position     = (POC - VAL) / (VAH - VAL)
edge_proximity   = min(P_t - VAL, VAH - P_t) / sigma_t
```

`poc_position` is in `[0, 1]` because POC lies inside the value area.

---

## Feature Family 2 — Excess and Single Prints

A single print is a price bin at the extreme of the profile with very few ticks and a much denser neighbouring bin. It represents rejection: price moved through the level quickly rather than accepting it.

### Definitions

```text
single_print_max_ticks = 1        # configurable
acceptance_min_ticks   = 3        # configurable
tail_bins              = 3        # number of extreme bins inspected
```

For the top tail:

```text
high_tail = the highest `tail_bins` non-empty bins in the profile
high_single_prints = count of high_tail bins with count <= single_print_max_ticks
high_tail_ticks = sum of counts in high_tail
excess_high = high_single_prints / max(high_tail_ticks, 1)
```

For the bottom tail:

```text
low_tail = the lowest `tail_bins` non-empty bins in the profile
low_single_prints = count of low_tail bins with count <= single_print_max_ticks
low_tail_ticks = sum of counts in low_tail
excess_low = low_single_prints / max(low_tail_ticks, 1)
```

Additional features:

```text
tail_length_high = (highest_included_bin - VAH_bin) / 1
tail_length_low  = (VAL_bin - lowest_included_bin) / 1
excess_asymmetry = excess_high - excess_low
```

`tail_length_*` is measured in bins, not price units, so it is comparable across instruments with different pip sizes.

---

## Feature Family 3 — Tick Velocity and Initiative

### Tick rate

```text
tick_rate_short = ticks in [t - 30s, t] / 30
tick_rate_long  = ticks in [t - 300s, t] / 300
tick_accel      = tick_rate_short / max(tick_rate_long, epsilon)
median_dt       = median inter-tick interval in [t - 60s, t]
```

### Boundary crossing

A boundary crossing is detected when price moves from inside the value area to outside it:

```text
crossed_vah_up   = previous_price < VAH and P_t > VAH
crossed_val_down = previous_price > VAL and P_t < VAL
```

At the crossing, record:

```text
cross_velocity = tick_rate_short at the crossing
cross_distance = abs(P_t - boundary) / sigma_t
```

### Regime features

```text
initiative = 1 if outside_va and tick_rate_short > rolling_80pct(tick_rate_short)
                 and cross_distance >= 0.5 * sigma_t
responsive = 1 if boundary_touched and price_returned_inside_within_N_ticks
```

Default `N = 5` ticks.

### Regime label

```text
regime = "balance"    if inside_va and not initiative
       = "imbalance"  if outside_va and initiative
       = "ambiguous"  otherwise
```

`ambiguous` rows are excluded from directional training by default, but retained for diagnostics.

---

## Feature Family 4 — Context

| Feature | Definition |
|---------|------------|
| `time_sin` | `sin(2 * pi * seconds_since_midnight / 86400)` |
| `time_cos` | `cos(2 * pi * seconds_since_midnight / 86400)` |
| `day_of_week` | `0`–`6`, Monday = 0 |
| `is_weekend` | `1` if Saturday or Sunday in the configured session timezone |
| `asset_type` | Categorical: forex, forex_otc, crypto, index, commodity, stock |
| `session` | Categorical: asia, london, newyork, overlap, off_hours |
| `tick_rate_short` | From Family 3 |
| `volatility_regime` | Low/normal/high from `sigma_t` quantiles |

Time must be computed in the configured session timezone, not the machine's local timezone.

---

## Full Feature Vector

| Name | Type | Formula / source |
|------|------|------------------|
| `Z_POC` | float | `(P_t - POC) / sigma_t` |
| `Z_VAH` | float | `(P_t - VAH) / sigma_t` |
| `Z_VAL` | float | `(P_t - VAL) / sigma_t` |
| `inside_va` | int | `VAL <= P_t <= VAH` |
| `va_width_norm` | float | `(VAH - VAL) / sigma_t` |
| `poc_position` | float | `(POC - VAL) / (VAH - VAL)` |
| `edge_proximity` | float | `min(P_t - VAL, VAH - P_t) / sigma_t` |
| `excess_high` | float | Top-tail single-print ratio |
| `excess_low` | float | Bottom-tail single-print ratio |
| `excess_asymmetry` | float | `excess_high - excess_low` |
| `tail_length_high` | float | Bins above VAH |
| `tail_length_low` | float | Bins below VAL |
| `tick_rate_short` | float | Ticks per second, 30-second window |
| `tick_rate_long` | float | Ticks per second, 5-minute window |
| `tick_accel` | float | Short rate / long rate |
| `median_dt` | float | Median seconds between ticks |
| `initiative` | int | Rule-based flag |
| `responsive` | int | Rule-based flag |
| `regime` | category | `balance`, `imbalance`, `ambiguous` |
| `time_sin` | float | Cyclical time encoding |
| `time_cos` | float | Cyclical time encoding |
| `day_of_week` | int | Session timezone |
| `is_weekend` | int | Session timezone |
| `asset_type` | category | Metadata |
| `session` | category | Session classifier |

---

## Causal Rules

1. A feature snapshot at time `t` may use only ticks with `received_at <= t`.
2. The profile window is `[t - W, t]`.
3. Velocity windows end at `t`.
4. `sigma_t` uses completed candles ending at or before `t`.
5. No feature may use the outcome candle or any later tick.
6. Feature computation for training and inference must share the same code path and version.

---

## Missing Data

| Situation | Output |
|-----------|--------|
| Fewer than minimum profile ticks | All profile features `null`; `profile_missing = 1` |
| Fewer than minimum volatility candles | `sigma_t = null`; all `Z_*` features `null` |
| No ticks in velocity window | `tick_rate_short = 0`; `median_dt = null` |
| Unknown asset metadata | `asset_type = "unknown"`; flag `metadata_missing = 1` |
| Gap in window | Compute with available ticks; set `gap_in_window = 1` |

Do not impute missing values with future data. Models must handle nulls explicitly or rows must be excluded.

---

## Feature Versioning

The feature set is versioned, for example `amt-v1`.

A new version is required when:

- Bin size or window length changes.
- `sigma_t` definition changes.
- Value-area expansion changes.
- A feature is added, removed, or redefined.
- Session timezone changes.

Every stored feature row must record `feature_version`.

---

## Related Documentation

- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [Tick stream contract](01_TICK_STREAM.md)
- [Labels, payouts, and expected value](06_LABELS_PAYOUTS_AND_EV.md)
- [Auction Market Theory](../concepts/05_AUCTION_MARKET_THEORY.md)
- [ML pipeline](../system/08_ML_PIPELINE.md)

---

*Last updated: 2026-11-18*
