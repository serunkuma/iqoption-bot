# Model Inputs

Status: Current

> The models consume sixteen features, versioned `core16-v2`, computed by one stateless function from one candle-close snapshot. The wider `amt-v4` table is stored for diagnostics and research, not fed to the models.

---

## Contract

```python
compute_features(snapshot: Snapshot, config: Config) -> FeatureVector
```

- No state, no I/O, no clock reads.
- The snapshot is the only input; the config supplies parameters.
- The same function produces training rows and runtime inference vectors.
- Missing values are `None`, stored as `NaN`; nothing is imputed.

Because the function is pure, offline rebuilds and runtime inference share the same calculation. Any change to feature definitions requires a new `CORE_FEATURE_VERSION`.

---

## Core Vector — `core16-v2`

Order is frozen; the model stores the names and validates the order.

| # | Feature | Family | Definition |
|---|---------|--------|------------|
| 1 | `z_poc` | Value distance | `(price - POC) / sigma_7` |
| 2 | `z_vah` | Value distance | `(price - VAH) / sigma_7` |
| 3 | `z_val` | Value distance | `(price - VAL) / sigma_7` |
| 4 | `inside_va` | Value distance | `1` when `VAL <= price <= VAH` |
| 5 | `va_width_norm` | Value shape | `(VAH - VAL) / sigma_7` |
| 6 | `poc_position` | Value shape | `(POC - VAL) / (VAH - VAL)` |
| 7 | `edge_proximity` | Value distance | `min(price - VAL, VAH - price) / sigma_7` |
| 8 | `excess_high` | Excess | Top-tail single-print ratio |
| 9 | `excess_low` | Excess | Bottom-tail single-print ratio |
| 10 | `excess_asymmetry` | Excess | `excess_high - excess_low` |
| 11 | `tick_rate_3_7` | Activity ratio | `tick_rate_3 / tick_rate_7` |
| 12 | `tick_rate_last_3` | Activity ratio | `tick_rate_last / tick_rate_3` |
| 13 | `price_speed_3_7` | Activity ratio | `price_speed_3 / price_speed_7` |
| 14 | `price_speed_last_3` | Activity ratio | `price_speed_last / price_speed_3` |
| 15 | `range_last_3` | Activity ratio | `range_last / range_3` |
| 16 | `price_change_last` | Last candle | `last - first` price in the last completed candle |

Notes:

- `poc_position` is in `[0, 1]` when the value area is non-degenerate.
- `edge_proximity` is negative outside the value area, which is intentional and informative.
- `price_change_last` is signed; the activity ratios are unsigned.
- Ratios are `None` when the denominator is `None`, zero, or negative. They are not clipped.

### Why These Sixteen

The model needs to know three things: where price sits relative to accepted value, whether the extremes show rejection, and whether current activity is accelerating relative to the recent baseline.

Raw levels (`poc`, `vah`, `val`) and raw rates are deliberately excluded: they encode absolute price scale and instrument volatility, which would not transfer and would invite overfitting. Normalising by `sigma_7` and by the macro baseline keeps the vector comparable across sessions and instruments.

---

## Diagnostic Table — `amt-v4`

Every feature row also carries diagnostics. They are written to `data/features.parquet` and `data/dataset.parquet`, and they are useful for debugging and research, but they are not model inputs.

| Group | Columns |
|-------|---------|
| Levels | `poc`, `vah`, `val` |
| Profile | `profile_ticks`, `sigma_7`, `window_bars`, `tail_length_high`, `tail_length_low` |
| Layer activity | `tick_rate_7`, `tick_rate_3`, `tick_rate_last`, `price_change_7`, `price_change_3`, `price_change_last`, `price_speed_7`, `price_speed_3`, `price_speed_last`, `range_7`, `range_3`, `range_last`, `range_speed_7`, `range_speed_3`, `range_speed_last`, `range_3_7` |
| Context | `time_sin`, `time_cos`, `day_of_week`, `is_weekend` |
| Quality | `profile_missing`, `volatility_missing`, `insufficient_ticks`, `gap_in_window` |

`gap_in_window` should be `0` for every snapshot that passed the continuity gate; a non-zero value indicates a sampler or feature regression and is worth investigating.

The tick-level diagnostic table (`build_diagnostic_table`) also exists for research. It builds one row per tick by calling the same `compute_features` function, so it cannot silently diverge from the snapshot path. It is not the training input.

---

## Feature Construction Details

### Layer Statistics

For each layer — macro (all completed bars), fast (last `fast_candles` completed bars), and last (most recent completed candle):

```text
tick_rate    = tick_count / duration_seconds
price_change = last_price - first_price
price_speed  = abs(price_change) / duration_seconds
range        = max_price - min_price
range_speed  = range / duration_seconds
```

Durations for the macro and fast layers span their covered completed minutes. The last-candle layer uses one full `interval_seconds`.

### Profile

The profile is built from the macro window only, with `bin_size` from the instrument config. POC, VAH, and VAL come from the labelled profile implementation; see [TPO and Value Area](04_TPO_VALUE_AREA.md).

Below `profile_min_ticks`, the profile is `None` and every dependent feature is `None` with `profile_missing = 1`.

### Volatility

```text
sigma_7 = sample standard deviation of consecutive price differences
          across the macro window
```

It requires at least `volatility_min_changes` differences (default 10), must be finite, and must be greater than zero. Otherwise it is `None` and every normalised feature is `None`.

`sigma_7` is in price units. It is not annualised and is not computed from candle closes.

### Time Features

`time_sin`, `time_cos`, `day_of_week`, and `is_weekend` use the snapshot's own UTC offset, which was captured with the tick. They are diagnostics; the model does not consume them, because a few weeks of data cannot support a time-of-day effect and adding them invites spurious splits.

---

## Missing-Value Policy

| Situation | Effect |
|-----------|--------|
| Profile is `None` | All profile-dependent core features `None` |
| `sigma_7` is `None` | All `z_*`, `va_width_norm`, `poc_position`, `edge_proximity` `None` |
| Zero denominator | That ratio `None` |
| Last completed candle has one tick | Speeds remain defined; `price_change_last = 0` |

LightGBM and the sklearn fallback both accept `NaN` natively, so missing values do not require imputation. The row stays in training with its missing pattern intact, which is the honest representation.

---

## Versioning

| Version | Scope |
|---------|-------|
| `amt-v4` | Full diagnostic table, one row per snapshot |
| `core16-v2` | The sixteen model inputs |
| `snapshot-horizon-v1` | Labels |
| `1m-clock-v1` | Minute bucketing |
| `candle-close-v1` | Decision cadence |

`amt-v2` was the previous tick-level table with a different column set. It is superseded and must not be referenced as current.

A version bump is required when a feature is added, removed, or redefined, or when the window, decision cadence, bin size, volatility, or value-area definition changes. The version strings live in `engine/config.py` and are recorded on every row and every suite.

---

## Related Documentation

- [Snapshots and continuity](08_SNAPSHOTS_AND_CONTINUITY.md)
- [AMT feature specification](05_AMT_FEATURE_SPEC.md)
- [TPO and value area](04_TPO_VALUE_AREA.md)
- [Model suite](../system/12_MODEL_SUITE.md)

---

*Last updated: 2026-11-21*
