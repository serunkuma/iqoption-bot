# Data Pipeline

Status: Current

> The pipeline runs end to end: browser frame to JSONL capture, Parquet tick store, gated snapshots, feature rows, labels, and a joined dataset. It is batch, offline from the perspective of `build`; only capture is live.

---

## Stages

| # | Stage | Input | Output | Where |
|---|-------|-------|--------|-------|
| 1 | Intercept | Page WebSocket message | Raw JSON payload | `chrome-extension/inject.js` |
| 2 | Forward | Raw payload | WebSocket frame | `chrome-extension/content.js` |
| 3 | Accept | Frame | Validated tick with `received_at` | `components/receiver.py` |
| 4 | Persist | Accepted tick | `data/raw/ticks-<date>.jsonl` | `runner.py serve` |
| 5 | Load | JSONL / CSV / Parquet | `TickStore` | `engine/store.py` |
| 6 | Sample | Tick store | `Snapshot` list + exclusion report | `engine/sampler.py` |
| 7 | Feature | Snapshot | `core16-v1` + `amt-v3` row | `engine/features.py` |
| 8 | Label | Snapshot | Long-format label rows | `engine/domain/labels.py` |
| 9 | Join | Feature + label rows | `dataset.parquet` | `engine/build.py` |
| 10 | Train | Dataset | Calibrated suite | `engine/models.py` |
| 11 | Backtest | Dataset + suite | Paper trades + reports | `engine/backtest.py` |

Steps 1–4 are live. Steps 5–11 run when commanded, on whatever capture exists.

---

## Stage Detail

### 1–4. Capture

The extension forwards only frames whose outer `name` is `"candle-generated"`. The receiver validates the envelope, stamps `received_at` with a local offset, buffers the last 500 payloads per `active_id` in memory, and calls the JSONL sink.

The broker's `at` and `volume` fields stay inside `payload`. They are evidence, not data. `received_at` is the project's only tick timestamp.

### 5. Store

`TickStore` enforces the tick contract: aware timestamp, positive numeric price, optional `active_id`, exact `(timestamp, price)` dedupe, ascending order, contiguous `tick_id`. Load statistics record duplicates and out-of-order rows.

### 6. Sample

For each whole minute with ticks, the sampler requires `macro_candles` contiguous earlier minutes, dense enough bars, a tick at or before the snapshot offset, and an entry tick inside the delay plus tolerance. It truncates the forming bar at the snapshot time and resolves one exit per horizon from the actual entry time.

### 7. Feature

One row per snapshot. The model vector is the 16 `core16-v1` features; the rest of the row is `amt-v3` diagnostics. The function is stateless and never reads past the snapshot.

### 8. Label

One row per snapshot per horizon: entry and exit prices and timestamps, exit delay, label (`call`/`put`/`tie`/`missing`), `usable`, and the label version.

### 9. Join

Features and labels are merged on `snapshot_id`. The label table's `timestamp` and `active_id` are dropped to avoid colliding with the feature table's own columns. Rows are sorted by `timestamp` then `horizon_seconds` with a stable sort.

---

## Dataset Schema

| Column | Source | Meaning |
|--------|--------|---------|
| `snapshot_id` | Feature | Join key |
| `timestamp` | Feature | Snapshot time, ISO 8601 with offset |
| `active_id` | Feature | Instrument |
| `price` | Feature | Price at the snapshot |
| `feature_version` | Feature | `amt-v3` |
| `core_feature_version` | Feature | `core16-v1` |
| 16 core columns | Feature | Model inputs |
| 31 diagnostic columns | Feature | Research and debugging |
| `entry_timestamp` | Label | Actual entry tick time |
| `entry_price` | Label | Actual entry price |
| `horizon_seconds` | Label | 60/90/120/180 |
| `exit_timestamp` | Label | Exit tick time, or null |
| `exit_price` | Label | Exit price, or null |
| `exit_delay_seconds` | Label | Delay beyond the exact horizon |
| `label` | Label | `call`, `put`, `tie`, or `missing` |
| `usable` | Label | `1` for directional rows |
| `label_version` | Label | `snapshot-horizon-v1` |

`dataset_rows` should equal `snapshots x horizons` when every exit is present. A shortfall means missing exits.

---

## Exclusions

Exclusions happen once, in the sampler and the label layer, and are counted:

| Reason | Accumulates in |
|--------|----------------|
| Too little history | `skipped_insufficient_history` |
| Gap in the macro window | `skipped_gap` |
| Sparse completed bar | `skipped_sparse_bar` |
| No tick at or before the offset | `skipped_no_pre_offset_tick` |
| No entry tick | `skipped_no_entry_tick` |
| Missing exit | `snapshots_with_missing_exits`, `usable = 0` |
| Tie with `exclude` | `usable = 0` |

Nothing is imputed, interpolated, or backfilled.

---

## Rebuilds and Determinism

Given the same capture file and the same configuration, `build` produces byte-comparable rows: sorting is stable, `tick_id` is reassigned deterministically, and no timestamp depends on the wall clock.

Changing any of the following requires a full rebuild and a version bump where applicable:

- `candles.interval_seconds`
- `context.*`
- `snapshot.*`
- `instrument.bin_size`
- feature definitions

---

## What the Pipeline Does Not Do

- It does not stream: `build` reads a file, not a live socket.
- It does not write candles to storage; minute buckets exist only inside the build.
- It does not append incrementally to an existing store.
- It does not handle multiple instruments; the sampler filters to one.
- It does not run live features or live signals.

---

## Related Documentation

- [Tick store](../data/07_TICK_STORE.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)
- [Model inputs](../data/09_MODEL_INPUTS.md)
- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)

---

*Last updated: 2026-11-19*
