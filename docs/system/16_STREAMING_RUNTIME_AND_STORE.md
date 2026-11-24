# Streaming Runtime and Store

Status: Current

> `runner.py serve` streams accepted price updates into an hourly-partitioned Parquet store. The runtime can make candle-close paper decisions when a compatible model artifact is provided. It does not place broker orders.

## Architecture

```text
Chrome extension
    -> components/receiver.py        envelope validation and received_at stamp
    -> engine.stream.StreamStore     sequence, event persistence, candle builder
        -> closed candle             first accepted event in a later minute
        -> rolling candle window    contiguous completed candles only
    -> engine.runtime.RuntimeEngine  candle-close features and paper decisions
        -> .joblib ModelSuite        manifest and compatibility validation
        -> deterministic EV router   payout-aware proposal or abstention
        -> PaperBroker               local paper outcome tracking
    -> hourly Parquet parts, state.json, decision/trade JSONL journals
```

`runner.py` owns wiring and lifecycle. `StreamStore` owns event and candle persistence; the runtime owns feature calculation, inference, gates, and decision journaling. `build`, `train`, and `backtest` remain offline commands.

## Event and Candle Contract

Each accepted input becomes a `TickEvent` containing:

| Field | Contract |
|---|---|
| `sequence` | Monotonic acceptance order; rejected input does not advance it |
| `received_at` | Receiver-local aware timestamp; canonical event time |
| `active_id` | Integer instrument key |
| `price` | Positive numeric `close` value |
| `utc_offset_seconds` | Offset of the receipt timestamp |
| `raw` | Original receiver payload, persisted as JSON |

The payload's `at` field remains untrusted and is not promoted to event time. Duplicate prices, including equal timestamp/price events, are preserved as distinct accepted events. Batch `TickStore` loading assigns or preserves a sequence, then stable-sorts by timestamp and sequence; live ingestion preserves accepted arrival order.

Minute buckets are half-open intervals `[K * interval, (K + 1) * interval)` in absolute time. The first accepted event in a later bucket finalizes the previous non-empty candle and opens the new forming candle. Empty minutes do not get synthetic candles; they are counted as gaps. A candle is never rewritten. Events from an already-finalized minute or older than the forming candle are rejected and counted as late.

The runtime decision is triggered by the candle-close notification, not by a wall-clock timer. If no later event arrives, finalization and the decision wait for that event. A gap does not create candles or decisions for empty minutes.

## Persistence and Recovery

The store root defaults to `data/stream`:

```text
data/stream/
  events/YYYY-MM-DD/HH/part-NNNN.parquet
  candles/YYYY-MM-DD/HH/part-NNNN.parquet
  decisions/YYYY-MM-DD/HH.jsonl
  trades.jsonl
  state.json
```

Event parts include sequence, UTC `received_at`, `active_id`, price, offset, and `raw_json`. Candle parts include bucket key/start/end, instrument, OHLC, tick count, first/last sequence, and finalization time. Parquet parts are written to a temporary path and renamed into place. Hour directories are based on the event or candle UTC timestamp; the `rotation_seconds` setting is validated but does not currently change this hourly partitioning.

`state.json` is written atomically and records the last flushed sequence, last finalized bucket, stream configuration metadata, and the forming candle state. On startup, the store reads state or recovers the last sequence/bucket from part files, and restores a saved forming candle when available. The runtime rolling feature window is not rebuilt from historical candle parts, so it warms up again with newly closed contiguous candles after restart.

The runtime reloads paper trades from `trades.jsonl` at startup. The one-open-trade gate, cooldown clock, and daily realized-loss stop therefore survive a restart, and an open trade still resolves on a later event. A malformed trade journal refuses startup instead of silently resetting the gates. Shadow mode starts with an empty book so prior paper positions cannot suppress predictions. The feature window still warms up from scratch.

The store flushes on candle close and when the pending event count reaches `stream.flush_events`. A write failure retains buffered rows and marks storage degraded; runtime decisions are blocked while degraded. If the pending-event limit is exceeded, ingestion fails explicitly. Shutdown flushes pending parts and saves state; it does not force-finalize the forming candle.

`runner.py serve` no longer writes daily `data/raw/*.jsonl` files. Existing CSV, JSONL, and Parquet tick files remain supported by `build` and `diagnose`.

## Candle-Close Decisions

The default window contains seven contiguous completed candles. The forming candle is excluded from features. Until the window is ready, each close is journaled as `warmup`. A ready window uses the same stateless `compute_features` function as offline builds, with the versioned `core16-v2` vector and `amt-v4` diagnostics.

The runtime loads and validates the `.joblib` artifact before starting unless `--capture-only` is selected. With `--shadow`, it loads the model and journals decisions but never opens a paper trade; the router and gate reasons are still recorded so shadow output can be compared with paper and offline results. Otherwise it:

1. Resolves any due paper trade using the accepted event price.
2. Computes features at the candle close and predicts per-horizon Call probabilities.
3. Applies the deterministic EV router and configured payout.
4. Applies runtime gates: storage health, at most one open paper trade, cooldown, and daily realized-loss limit.
5. Waits for the first event at or after the configured entry delay, within the entry tolerance.
6. Opens a paper trade or journals an explicit abstention; resolves it on a later event at or after expiry.

Decision records are append-only JSONL, partitioned by UTC day/hour, and include the candle-close time, sequence, artifact id, feature/decision versions, values, probabilities, proposal, reason, trade id, and measured latency. Trade outcomes are separately appended to `trades.jsonl`.

Runtime reason codes include warm-up, open trade, cooldown, daily stop, missing entry tick, store degradation, broker rejection, shutdown, no model, missing payout, and below hurdle. The exact record and counters are defined in `engine/runtime.py`.

## Model Artifact and Commands

`train` writes a timestamped `suite-<UTC timestamp>.joblib` and a matching `.manifest.json` sidecar. The manifest includes an artifact hash, ordered feature names, feature/decision/candle/label versions, instrument, configuration hash, horizons, metrics, split metadata, and training environment. Runtime loading requires the manifest, verifies the artifact hash/format/feature order, and checks configuration compatibility. A missing or incompatible artifact causes `serve` to exit with an error; there is no runtime fallback to pickle.

Legacy pickle suites can still be loaded for analysis and backtesting, but runtime inference requires `.joblib`. Joblib is executable serialization: load only trusted local artifacts.

```powershell
.\.venv\Scripts\python.exe runner.py serve --capture-only
.\.venv\Scripts\python.exe runner.py serve --shadow
.\.venv\Scripts\python.exe runner.py serve --model data\models\suite-YYYYMMDDTHHMMSSZ.joblib
.\.venv\Scripts\python.exe runner.py model-check --model data\models\suite-YYYYMMDDTHHMMSSZ.joblib
.\.venv\Scripts\python.exe runner.py replay --events data\stream\events --candles data\stream\candles
.\.venv\Scripts\python.exe runner.py build --input data\stream\events
```

`model-check` prints the manifest and compatibility result. `replay` rebuilds candles from stored event parts and compares them with recorded candles; it can also compare features when given `--dataset`.

## Boundaries and Limitations

- The router remains deterministic; a learned direction/horizon/no-trade selector is not implemented.
- `PaperBroker` is local simulation only. There is no demo/live order adapter or account integration.
- Daily loss stop and cooldown are runtime paper gates, not a complete risk manager or kill switch.
- The runtime has unit coverage, but sustained shadow/paper sessions and real-feed parity have not been established.
- Feed-frame meaning, real tick cadence, OTC suitability, and predictive edge remain unverified. A passing test suite or replay does not establish profitability.

## Related Documentation

- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [Tick stream contract](../data/01_TICK_STREAM.md)
- [Tick store](../data/07_TICK_STORE.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)
- [Model inputs](../data/09_MODEL_INPUTS.md)
- [Model suite](12_MODEL_SUITE.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-22*
