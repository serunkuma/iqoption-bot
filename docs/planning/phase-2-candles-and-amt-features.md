# Phase 2 — 1-Minute Candles and AMT Features

Status: Planning

> **Objective:** Build the analytical layer: 1-minute OHLCV candles from ticks, rolling TPO/Value Area profiles, AMT features, and a rule-based baseline.

---

## Scope

- Build the 1-minute candle builder.
- Define asset metadata.
- Add durable storage for candles and features.
- Implement TPO/Value Area.
- Implement the AMT feature set.
- Build a rule-based AMT baseline.
- Build a backtesting harness.
- Evaluate weekday vs weekend behaviour.

Out of scope: ML training, execution.

---

## Tasks

### Candles

- [ ] Implement clock-aligned 1-minute OHLCV aggregation.
- [ ] Define late-tick and duplicate policies.
- [ ] Emit gap markers for missing minutes.
- [ ] Validate OHLC invariants.
- [ ] Add candle rebuild from raw ticks.
- [ ] Add tests for boundary, late, and empty-bucket cases.

### Metadata

- [ ] Define `assets.json` schema.
- [ ] Add pip size, tick size, asset type, payout, expiry, session.
- [ ] Validate metadata at startup.
- [ ] Add tests for invalid metadata.

### Storage

- [ ] Add SQLite for candles and features.
- [ ] Add Parquet export for research.
- [ ] Record feature, candle, and dataset versions.
- [ ] Add retention and backup rules.

### TPO / Value Area

- [ ] Implement binning.
- [ ] Implement POC with deterministic tie-breaks.
- [ ] Implement 70% value-area expansion.
- [ ] Compute VAH/VAL.
- [ ] Validate against the worked example.
- [ ] Add profile tests for flat, gapped, and low-tick windows.

### AMT features

- [ ] Implement `Z_POC`, `Z_VAH`, `Z_VAL`.
- [ ] Implement value-area width and position features.
- [ ] Implement excess and single-print features.
- [ ] Implement tick velocity, acceleration, and initiative/responsive flags.
- [ ] Implement regime labels.
- [ ] Implement context features.
- [ ] Enforce causal windows.
- [ ] Version the feature set as `amt-v1`.

### Baseline and backtest

- [ ] Implement the rule-based AMT baseline.
- [ ] Build a payout-aware backtest harness.
- [ ] Report win rate, breakeven, EV, trade count, and drawdown.
- [ ] Compare weekday and weekend subsets.
- [ ] Record baseline results in `reports/`.

---

## Deliverables

- 1-minute candle builder.
- `assets.json` and validation.
- SQLite/Parquet storage.
- TPO/Value Area engine.
- AMT feature engine.
- Rule-based baseline.
- Backtest harness.
- Phase 2 report.

---

## Acceptance Criteria

- [ ] Candles pass all OHLC and boundary tests.
- [ ] TPO/Value Area matches the documented worked example.
- [ ] Feature snapshots are causal and reproducible.
- [ ] Feature version is recorded on every row.
- [ ] Baseline backtest reports EV against payout breakeven.
- [ ] Weekday and weekend results are reported separately.
- [ ] No feature uses future data.
- [ ] A replay from raw ticks reproduces the dataset.

---

## Dependencies

- Phase 1 accepted: verified tick contract, persistence, replay, quality metrics.

---

## Related Documentation

- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Data Pipeline](../system/07_DATA_PIPELINE.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-18*
