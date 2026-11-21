# Phase 2 — Analytical Layer

Status: Current

> **Objective:** Build the analytical layer: whole-minute bucketing, candle-close decisions, rolling TPO/Value Area profiles, `amt-v4` diagnostics with a `core16-v2` model vector, `snapshot-horizon-v1` labels, and a rule-based baseline.

---

## Scope

- Build whole-minute bucketing and the continuity gate.
- Define the active-instrument configuration.
- Add durable storage for ticks, features, labels, and datasets.
- Implement TPO/Value Area.
- Implement the `amt-v4` feature table and the `core16-v2` model vector.
- Implement snapshot-horizon labels with delayed entry.
- Build a rule-based AMT baseline.
- Evaluate weekday vs weekend behaviour.

Out of scope: model training, execution.

---

## Status

The candle-close offline path and streaming candle persistence are implemented and tested. Snapshots are not persisted separately, and the rule-based baseline is still open. See [Streaming Runtime and Store](../system/16_STREAMING_RUNTIME_AND_STORE.md) for the current runtime contract.

| Component | Status | Location |
|-----------|--------|----------|
| Minute bucketing | Done | `engine/domain/timeframes.py` |
| TPO profile and Value Area | Done | `engine/domain/profile.py` |
| Candle-close snapshot gate | Done | `engine/sampler.py` |
| Feature table and core vector (`amt-v4` / `core16-v2`) | Done | `engine/features.py` |
| Snapshot-horizon labels | Done | `engine/domain/labels.py` |
| Dataset assembly | Done | `engine/build.py` |
| Tick store | Done | `engine/store.py` |
| Rule-based baseline | Not started | — |
| Weekday/weekend analysis | Partial (diagnostics only) | `is_weekend` column |
| Stream candle persistence | Done | `engine/stream/` |
| Dedicated snapshot persistence | Not started | — |

---

## Tasks

### Candles and continuity

- [x] Implement whole-minute bucketing from `received_at`.
- [x] Preserve accepted duplicate events and count exact `(timestamp, price)` pairs in diagnostics.
- [x] Separate forming and completed bars.
- [x] Require a contiguous macro window.
- [x] Require `min_ticks_per_bar` ticks per completed bar.
- [ ] Emit gap markers into storage.
- [x] Persist finalized streaming candles in hourly Parquet parts.
- [ ] Persist offline snapshots separately.
- [ ] Validate OHLC invariants in a stored candle table.

### Configuration and metadata

- [x] Define the active-instrument configuration contract.
- [x] Add pip size and bin size.
- [x] Add payout per horizon.
- [x] Validate configuration at startup.
- [x] Add tests for invalid configuration.
- [ ] Discover payouts and expiries from the platform.
- [ ] Add asset type and session metadata.

### Storage

- [x] Persist streaming events as hourly Parquet parts.
- [x] Persist the tick store as Parquet.
- [x] Persist features, labels, and the dataset as Parquet.
- [x] Record feature, core feature, label, and candle versions.
- [ ] Persist snapshots.
- [ ] Add retention and backup rules.

### TPO / Value Area

- [x] Implement binning with float-edge correction.
- [x] Implement POC with deterministic tie-breaks.
- [x] Implement pair expansion over non-empty bins.
- [x] Compute VAH/VAL from bin edges.
- [x] Validate against the worked example.
- [x] Add tests for flat, gapped, and low-tick windows.
- [x] Return a null profile below the minimum tick count.

### Features

- [x] Implement macro / fast / forming layers.
- [x] Implement `z_poc`, `z_vah`, `z_val` on `sigma_7`.
- [x] Implement value-area width and position features.
- [x] Implement tail-specific excess features.
- [x] Implement tick rate, price speed, range, and range speed per layer.
- [x] Implement layer ratios.
- [x] Implement context and quality diagnostics.
- [x] Freeze the causal slice at the snapshot time.
- [x] Version the table `amt-v4` and the model vector `core16-v2`.
- [ ] Add worked-example fixtures for every feature family.
- [ ] Measure build time on a realistic tick volume.

### Labels

- [x] Implement 60/90/120/180-second snapshot labels.
- [x] Implement first-tick-at-or-after-horizon exit with tolerance.
- [x] Measure exits from the actual delayed entry.
- [x] Keep ties and missing exits explicit.
- [x] Emit long-format labels keyed by `snapshot_id` and horizon.
- [x] Join features and labels into one dataset.
- [x] Use candle-close decisions in the current snapshot-horizon label path.

### Baseline

- [ ] Implement the rule-based AMT baseline.
- [x] Build a payout-aware replay with one open position.
- [x] Report win rate, EV, trade count, and concurrency.
- [ ] Compare weekday and weekend subsets.
- [ ] Record baseline results in `reports/`.

---

## Deliverables

- Continuity-gated snapshots with delayed entry and horizon exits.
- TPO/Value Area engine.
- `amt-v4` feature table and `core16-v2` vector.
- `snapshot-horizon-v1` labels.
- Joined Parquet dataset.
- Rule-based baseline (open).

---

## Acceptance Criteria

- [x] Bucketing and continuity are tested.
- [x] TPO/Value Area matches the documented worked example.
- [x] Feature rows are causal and reproducible.
- [x] Feature and core feature versions are recorded on every row.
- [x] Labels never map ties or missing exits to a direction.
- [x] Exits are measured from the actual entry time.
- [x] The dataset join is keyed by `snapshot_id`.
- [ ] Baseline backtest reports EV against payout breakeven.
- [ ] Weekday and weekend results are reported separately.
- [ ] A replay from raw JSONL reproduces the dataset byte for byte.
- [ ] Feature build time is measured and documented.

---

## Dependencies

- Phase 1: capture and persistence (done).
- A real multi-hour capture for density checks (open).

---

## Related Documentation

- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)
- [Model inputs](../data/09_MODEL_INPUTS.md)
- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-21*
