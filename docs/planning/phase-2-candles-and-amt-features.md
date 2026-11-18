# Phase 2 — 1-Minute Candles, AMT Features, and Labels

Status: Planning

> **Objective:** Build the analytical layer: 1-minute candles from ticks, the macro/fast/forming context windows, rolling TPO/Value Area profiles, `amt-v2` features, tick-horizon labels, and a rule-based baseline.

---

## Scope

- Build the 1-minute candle builder.
- Define asset metadata.
- Add durable storage for candles and features.
- Implement TPO/Value Area.
- Implement the `amt-v2` feature set.
- Implement tick-horizon labels.
- Build a rule-based AMT baseline.
- Build a backtesting harness.
- Evaluate weekday vs weekend behaviour.

Out of scope: ML training, execution.

---

## Status

The offline library in `amt/` already covers the profile, features, and labels. Live integration and the baseline are still open.

| Component | Status |
|-----------|--------|
| Candle bucketing | Offline (`amt/timeframes.py`) |
| TPO profile and Value Area | Offline (`amt/profile.py`) |
| `amt-v2` features | Offline (`amt/features.py`) |
| Tick-horizon labels | Offline (`amt/labels.py`) |
| Tick loader and CSV output | Offline (`amt/data.py`, `amt/build.py`) |
| Live receiver integration | Not started |
| Rule-based baseline | Not started |
| Backtest harness | Not started |

---

## Tasks

### Candles

- [x] Implement whole-minute OHLCV aggregation.
- [x] Define duplicate policy: drop exact `(timestamp, price)` pairs.
- [x] Define forming vs completed candles.
- [x] Detect gaps in the macro window.
- [ ] Emit gap markers for missing minutes in storage.
- [ ] Add candle rebuild from raw JSONL.
- [ ] Validate OHLC invariants in the candle builder.

### Metadata

- [ ] Define the active-instrument configuration contract.
- [ ] Add pip size, tick size, asset type, payout, and expiry options.
- [ ] Validate metadata at startup.
- [ ] Add tests for invalid metadata.
- [ ] Defer multi-instrument metadata until multi-instrument support exists.

### Storage

- [ ] Add raw tick JSONL persistence.
- [ ] Add SQLite for candles and features.
- [ ] Record feature, label, candle, and dataset versions.
- [ ] Add retention and backup rules.

### TPO / Value Area

- [x] Implement binning with float-edge correction.
- [x] Implement POC with deterministic tie-breaks.
- [x] Implement 70% pair expansion over non-empty bins.
- [x] Compute VAH/VAL from bin edges.
- [x] Validate against the worked example.
- [x] Add profile tests for flat, gapped, and low-tick windows.
- [x] Return a null profile below the minimum tick count.

### AMT features

- [x] Implement macro 7 / fast 3 / forming layers.
- [x] Implement `z_poc`, `z_vah`, `z_val` on `sigma_7`.
- [x] Implement value-area width and position features.
- [x] Implement tail-specific excess features.
- [x] Implement tick rate, price speed, range, and range speed per layer.
- [x] Implement layer ratios.
- [x] Implement context features.
- [x] Enforce causal windows; add a prefix-equality test.
- [x] Version the feature set as `amt-v2`.
- [ ] Add worked-example fixtures for every feature family.
- [ ] Measure build time on a realistic tick volume.

### Labels

- [x] Implement 60/90/120/180-second tick labels.
- [x] Implement first-tick-at-or-after-horizon exit with tolerance.
- [x] Keep ties and missing exits explicit.
- [x] Emit long-format labels keyed by `tick_id` and horizon.
- [ ] Add a candle-close research label variant.
- [ ] Add a dataset join between features and labels.

### Baseline and backtest

- [ ] Implement the rule-based AMT baseline.
- [ ] Build a payout-aware backtest harness with one open position.
- [ ] Report win rate, breakeven, EV, trade count, independent windows, and drawdown.
- [ ] Compare weekday and weekend subsets.
- [ ] Record baseline results in `reports/`.

---

## Deliverables

- 1-minute candle builder with forming/completed semantics.
- Active-instrument configuration and validation.
- SQLite/Parquet storage.
- TPO/Value Area engine.
- `amt-v2` feature engine.
- Tick-horizon label builder.
- Rule-based baseline.
- Backtest harness.
- Phase 2 report.

---

## Acceptance Criteria

- [ ] Candles pass all OHLC and boundary tests.
- [x] TPO/Value Area matches the documented worked example.
- [x] Feature rows are causal and reproducible.
- [x] Feature version is recorded on every row.
- [x] Labels never map ties or missing exits to a direction.
- [ ] Baseline backtest reports EV against payout breakeven.
- [ ] Weekday and weekend results are reported separately.
- [ ] A replay from raw ticks reproduces the dataset.
- [ ] Feature build time is measured and documented.

---

## Dependencies

- Phase 1 accepted: verified tick contract, persistence, replay, quality metrics.

---

## Related Documentation

- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [Data Pipeline](../system/07_DATA_PIPELINE.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-18*
