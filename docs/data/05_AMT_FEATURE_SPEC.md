# AMT Feature Specification

Status: Current

> This document defines the exact AMT feature families and formulas. `engine/features.py` implements `amt-v3`: one row per validated snapshot, with a 16-feature `core16-v1` model vector and the remaining columns kept as diagnostics. Every feature is computable causally from one snapshot time.

---

## Notation

| Symbol | Meaning |
|--------|---------|
| `P_t` | Price at the snapshot time `t` — the last tick at or before `t` |
| `k` | Number of completed 1-minute candles since capture start |
| `POC` | Point of Control from the macro profile |
| `VAH` | Value Area High |
| `VAL` | Value Area Low |
| `sigma_7` | Rolling volatility in price units over the macro window |

---

## Context Windows

Ticks carry one timestamp: the receiver's local receipt time, stored as ISO 8601 with an offset. All windows are measured in absolute time, so whole-minute buckets coincide with whole local minutes.

| Window | Definition | Role |
|--------|------------|------|
| Macro | Last `macro_candles` completed candles (default 7) | Profile, `sigma_7`, slow activity |
| Fast | Last `fast_candles` completed candles (default 3) | Recent activity |
| Forming | Ticks in the current, incomplete candle | Current price, immediate activity |

The forming candle **never** enters the profile. It contributes current price, tick rate, price speed, and range only.

For each layer `L`, with `duration_L` measured from the start of the oldest candle in the layer to the start of the forming candle:

```text
tick_rate_L     = ticks_L / duration_L
price_change_L  = last_price_L - first_price_L
price_speed_L   = abs(price_change_L) / duration_L
range_L         = max_price_L - min_price_L
range_speed_L   = range_L / duration_L
```

For the forming layer:

```text
duration_forming = max(t - start_of_current_candle, 1 second)
```

---

## Volatility Definition

```text
sigma_7 = sample_standard_deviation(
    consecutive tick price differences over the macro window
)
```

Requirements:

- The macro window contains ticks from completed candles only.
- At least `volatility_min_changes` price differences are required (default 10).
- `sigma_7` must be finite and greater than zero; otherwise it is null.
- Do not annualise and do not use candle closes.

At the start of capture, before enough history exists, `sigma_7` is null. All normalised distance features are then null.

---

## Feature Family 1 — Normalised Distance to Value

```text
z_poc = (P_t - POC) / sigma_7
z_vah = (P_t - VAH) / sigma_7
z_val = (P_t - VAL) / sigma_7
```

| Feature | Positive value means | Negative value means |
|---------|----------------------|----------------------|
| `z_poc` | Price above value centre | Price below value centre |
| `z_vah` | Price above value area | Price inside or below VAH |
| `z_val` | Price above VAL | Price below value area |

Related features:

```text
inside_va      = 1 if VAL <= P_t <= VAH else 0
va_width_norm  = (VAH - VAL) / sigma_7
poc_position   = (POC - VAL) / (VAH - VAL)
edge_proximity = min(P_t - VAL, VAH - P_t) / sigma_7
```

`poc_position` is in `[0, 1]`. `edge_proximity` is negative outside the value area, which is intentional.

---

## Feature Family 2 — Excess and Tails

A single print is a price bin at the extreme of the profile with very few ticks. It represents rejection: price moved through the level quickly instead of accepting it.

```text
single_print_max_ticks = 1
tail_bins              = 3
```

For the top tail:

```text
high_tail          = highest `tail_bins` non-empty bins
high_single_prints = count of high_tail bins with count <= single_print_max_ticks
high_tail_ticks    = sum of counts in high_tail
excess_high        = high_single_prints / max(high_tail_ticks, 1)
```

For the bottom tail:

```text
low_tail          = lowest `tail_bins` non-empty bins
low_single_prints = count of low_tail bins with count <= single_print_max_ticks
low_tail_ticks    = sum of counts in low_tail
excess_low        = low_single_prints / max(low_tail_ticks, 1)
```

Additional features:

```text
excess_asymmetry = excess_high - excess_low
tail_length_high = highest_non_empty_bin - VAH_bin
tail_length_low  = VAL_bin - lowest_non_empty_bin
```

`tail_length_*` is measured in bins, not price units, so it is comparable across instruments with different pip sizes.

The global ratio of single-tick bins to all bins is a diagnostic only. It is not a tail feature and must not replace `excess_high` or `excess_low`.

---

## Feature Family 3 — Layer Activity

Every layer produces the same five metrics. Ratios compare fast to macro and forming to fast.

| Feature | Definition |
|---------|------------|
| `tick_rate_7` | Ticks per second over the macro window |
| `tick_rate_3` | Ticks per second over the fast window |
| `tick_rate_forming` | Ticks per second in the forming candle |
| `price_change_7` | Last minus first price in the macro window |
| `price_change_3` | Last minus first price in the fast window |
| `price_change_forming` | Current price minus first price in the forming candle |
| `price_speed_7` | `abs(price_change_7) / duration_7` |
| `price_speed_3` | `abs(price_change_3) / duration_3` |
| `price_speed_forming` | `abs(price_change_forming) / duration_forming` |
| `range_7` | High minus low in the macro window |
| `range_3` | High minus low in the fast window |
| `range_forming` | High minus low in the forming candle |
| `range_speed_7` | `range_7 / duration_7` |
| `range_speed_3` | `range_3 / duration_3` |
| `range_speed_forming` | `range_forming / duration_forming` |

Ratios:

```text
tick_rate_3_7          = tick_rate_3 / tick_rate_7
tick_rate_forming_3    = tick_rate_forming / tick_rate_3
price_speed_3_7        = price_speed_3 / price_speed_7
price_speed_forming_3  = price_speed_forming / price_speed_3
range_3_7              = range_3 / range_7
range_forming_3        = range_forming / range_3
```

A ratio is null when its denominator is null, zero, or negative. Ratios are not clipped.

There are no fixed 5-second, 30-second, or 300-second velocity windows. Activity is always compared across the macro, fast, and forming layers.

---

## Feature Family 4 — Context

| Feature | Definition |
|---------|------------|
| `time_sin` | `sin(2 * pi * seconds_since_local_midnight / 86400)` |
| `time_cos` | `cos(2 * pi * seconds_since_local_midnight / 86400)` |
| `day_of_week` | `0`–`6`, Monday = 0, from the tick's local timestamp |
| `is_weekend` | `1` if `day_of_week >= 5` |

Time features use the tick's own local timestamp. They do not convert to a session timezone.

---

## Full Feature Vector

| Name | Type | Formula / source |
|------|------|------------------|
| `snapshot_id` | int | Snapshot ordinal within the build |
| `timestamp` | string | Snapshot time, ISO 8601 with offset |
| `active_id` | int | Instrument key |
| `price` | float | `P_t` |
| `feature_version` | string | `amt-v3` |
| `core_feature_version` | string | `core16-v1` |
| `poc` | float or null | POC bin midpoint |
| `vah` | float or null | Upper edge of the highest included bin |
| `val` | float or null | Lower edge of the lowest included bin |
| `profile_ticks` | int | Ticks in the macro window |
| `sigma_7` | float or null | Rolling volatility |
| `z_poc` | float or null | `(P_t - POC) / sigma_7` |
| `z_vah` | float or null | `(P_t - VAH) / sigma_7` |
| `z_val` | float or null | `(P_t - VAL) / sigma_7` |
| `inside_va` | int or null | `VAL <= P_t <= VAH` |
| `va_width_norm` | float or null | `(VAH - VAL) / sigma_7` |
| `poc_position` | float or null | `(POC - VAL) / (VAH - VAL)` |
| `edge_proximity` | float or null | `min(P_t - VAL, VAH - P_t) / sigma_7` |
| `excess_high` | float or null | Top-tail single-print ratio |
| `excess_low` | float or null | Bottom-tail single-print ratio |
| `excess_asymmetry` | float or null | `excess_high - excess_low` |
| `tail_length_high` | float or null | Bins above VAH |
| `tail_length_low` | float or null | Bins below VAL |
| all `*_7`, `*_3`, `*_forming` | float or null | Layer activity metrics |
| all `*_3_7`, `*_forming_3` | float or null | Layer ratios |
| `time_sin` | float | Cyclical time encoding |
| `time_cos` | float | Cyclical time encoding |
| `day_of_week` | int | Local timestamp |
| `is_weekend` | int | Local timestamp |
| `profile_missing` | int | `1` when the profile is null |
| `volatility_missing` | int | `1` when `sigma_7` is null |
| `insufficient_ticks` | int | `1` when the window has ticks but fewer than `profile_min_ticks` |
| `gap_in_window` | int | `1` when the macro window skips a whole minute |

---

## Causal Rules

1. A feature snapshot at time `t` may use only ticks with timestamp `<= t`.
2. The sampler truncates the forming bar at `t` before any feature is computed.
3. The profile and `sigma_7` use completed candles only.
4. The forming candle contributes only `P_t` and forming-layer activity.
5. No feature may use any tick after `t`.
6. Feature computation for training and inference must share the same code path and version.

---

## Missing Data

| Situation | Output |
|-----------|--------|
| No completed candles | All profile and macro/fast features null; `profile_missing = 1` |
| Fewer than `profile_min_ticks` | Profile features null; `profile_missing = 1`; `insufficient_ticks = 1` if ticks exist |
| Fewer than `volatility_min_changes` price changes | `sigma_7 = null`; `volatility_missing = 1`; all `z_*` and normalised width features null |
| `sigma_7 <= 0` | Treated as missing volatility |
| Zero denominator in a ratio | Ratio null |
| Gap in the macro window | Compute with available candles; `gap_in_window = 1` |

Missing values are never imputed from future data and never replaced with the current price.

---

## Feature Versioning

Two version strings matter:

| Version | Scope |
|---------|-------|
| `amt-v3` | The full snapshot table, including diagnostics |
| `core16-v1` | The sixteen model inputs |

A new version is required when:

- `macro_candles`, `fast_candles`, or the candle interval changes.
- Bin size, `sigma_7`, or value-area expansion changes.
- A feature is added, removed, or redefined.
- The definition of a layer or ratio changes.
- The snapshot offset, entry delay, or tolerance changes.

`amt-v1` was the pre-implementation draft with fixed velocity windows and candle-close `sigma_t`. `amt-v2` was the previous tick-level table. Both are superseded.

---

## Implementation Reference

| Item | Location |
|------|----------|
| Feature engine | `engine/features.py` |
| TPO profile | `engine/domain/profile.py` |
| Candle bucketing | `engine/domain/timeframes.py` |
| Snapshot gate | `engine/sampler.py` |
| Configuration | `config/default.toml`, `engine/config.py` |
| Tests | `tests/test_features.py`, `tests/test_profile.py`, `tests/test_timeframes.py`, `tests/test_sampler.py` |

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe runner.py build --input data\ticks.csv
```

The tick-level diagnostic table (`build_diagnostic_table`) still exists for research. It routes through `compute_features`, so it cannot drift from the snapshot path.

---

## Related Documentation

- [Model inputs](09_MODEL_INPUTS.md)
- [Snapshots and continuity](08_SNAPSHOTS_AND_CONTINUITY.md)
- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [Tick stream contract](01_TICK_STREAM.md)
- [Labels and expected value](06_LABELS_PAYOUTS_AND_EV.md)
- [Auction Market Theory](../concepts/05_AUCTION_MARKET_THEORY.md)

---

*Last updated: 2026-11-19*
