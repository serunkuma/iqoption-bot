# Data Pipeline

Status: Current

> The system has a live streaming store/runtime path and an offline file-to-dataset research path. `build`, `train`, and `backtest` remain batch commands; `serve` can make paper decisions from streaming candle closes.

---

## Stages

| # | Stage | Input | Output | Where |
|---|-------|-------|--------|-------|
| 1 | Intercept | Page WebSocket message | Raw JSON payload | `chrome-extension/inject.js` |
| 2 | Forward | Raw payload | WebSocket frame | `chrome-extension/content.js` |
| 3 | Accept | Frame | Validated tick with `received_at` | `components/receiver.py` |
| 4 | Persist stream | Accepted event | Hourly event/candle parts and state | `engine/stream/` |
| 5 | Runtime decision | Closed candle + rolling window | Paper decision or abstention | `engine/runtime.py` |
| 6 | Load offline file | JSONL / CSV / Parquet | `TickStore` | `engine/store.py` |
| 7 | Sample | Tick store | Candle-close `Snapshot` list + exclusion report | `engine/sampler.py` |
| 8 | Feature | Snapshot | `core16-v2` + `amt-v4` row | `engine/features.py` |
| 9 | Label | Snapshot | Long-format label rows | `engine/domain/labels.py` |
| 10 | Join | Feature + label rows | `dataset.parquet` | `engine/build.py` |
| 11 | Train | Dataset | Calibrated `.joblib` suite + manifest | `engine/models.py` |
| 12 | Backtest | Dataset + suite | Held-out paper trades + reports | `engine/backtest.py` |

Steps 1–5 are live process work when `serve` is running. Offline steps 6–12 run when commanded. `serve` does not write the former daily raw JSONL capture.

---

## Stage Detail

### 1–4. Capture

The extension forwards only frames whose outer `name` is `"candle-generated"`. The receiver validates the envelope, stamps `received_at` with a local offset, buffers the last 500 payloads per `active_id` in memory, and calls the configured sink. `runner.py serve` connects it to `StreamStore`.

The broker's `at` and `volume` fields stay inside `payload`. They are evidence, not data. `received_at` is the project's only tick timestamp.

### 6. Offline Tick Store

`TickStore` enforces aware timestamps and positive numeric prices, records duplicate timestamp/price pairs without removing them, and stably sorts by `(timestamp, sequence)`. Live ingestion instead preserves arrival order and rejects events too late to update the forming candle.

### 7. Sample

The sampler creates one decision snapshot per eligible minute. Its window includes `macro_candles` contiguous completed candles through the decision candle; each must meet the density gate. It then finds a delayed entry tick and resolves one exit per horizon from the actual entry time.

### 8. Feature

One row per snapshot. The model vector is the 16 `core16-v2` features; the rest of the row is `amt-v4` diagnostics. The stateless function receives completed bars only.

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
| `feature_version` | Feature | `amt-v4` |
| `core_feature_version` | Feature | `core16-v2` |
| `decision_version` | Feature | `candle-close-v1` |
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

- `build` does not read the streaming directory directly; it reads a file.
- It does not create candles for empty minutes or accept late stream updates into finalized candles.
- It does not append incrementally to an existing store.
- It does not select multiple instruments; the runtime and sampler use one configured `active_id`.
- It does not place demo/live orders or use a learned signal selector.

---

## Related Documentation

- [Tick store](../data/07_TICK_STORE.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)
- [Model inputs](../data/09_MODEL_INPUTS.md)
- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)

---

*Last updated: 2026-11-21*
