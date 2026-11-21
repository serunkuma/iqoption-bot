# Interfaces

Status: Current

> External interfaces: browser extension to receiver, receiver to sink, and file formats. Internal interfaces: tick store, snapshot, feature vector, signal proposal, and trade.

---

## Browser Extension to Receiver

### Transport

| Property | Value |
|----------|-------|
| Protocol | WebSocket |
| URL | `ws://localhost:8765` |
| Direction | Extension to receiver |
| Authentication | None; localhost only |
| Max frame size | 1 MiB |
| Ping interval / timeout | 20 s / 20 s |

### Frame

The extension forwards the page's original JSON string.

```json
{
  "name": "candle-generated",
  "msg": {
    "active_id": 42,
    "open": 1.2,
    "close": 1.25,
    "min": 1.1,
    "max": 1.3,
    "volume": 7,
    "at": 123,
    "interval": 60,
    "symbol": "EURUSD"
  }
}
```

### Acceptance Rules

The receiver accepts a frame only when:

- it parses as JSON,
- it is a JSON object,
- `name == "candle-generated"`,
- `msg` is a JSON object,
- `msg.active_id` is present.

Accepted frames get `received_at` (ISO 8601 with offset) if absent. Rejected frames are logged and dropped. The receiver does not validate `close` as a positive numeric value; the streaming or batch store validates it before accepting a tick, with an explicit diagnostic on failure.

`msg.at` and `msg.volume` are stored but never promoted or trusted.

---

## Receiver to Stream Store

The receiver validates the envelope, stamps `received_at`, and forwards accepted events to the stream store. The stream store assigns an acceptance sequence and persists events and candles in hourly Parquet parts. Storage failures are surfaced and block runtime decisions; see [Streaming Runtime and Store](16_STREAMING_RUNTIME_AND_STORE.md).

---

## File Formats

| File | Written by | Consumed by |
|------|------------|-------------|
| `data/stream/events/YYYY-MM-DD/HH/part-*.parquet` | `serve` | `replay` |
| `data/stream/candles/YYYY-MM-DD/HH/part-*.parquet` | `serve` | `replay` |
| `data/ticks.parquet` | `build` | `build --input` |
| `data/features.parquet` | `build` | research |
| `data/labels.parquet` | `build` | research |
| `data/dataset.parquet` | `build` | `train`, `backtest` |
| `data/models/suite-<timestamp>.joblib` + manifest | `train` | `serve`, `model-check`, `backtest` |
| `reports/backtest.json` | `backtest` | humans, tooling |
| `reports/backtest.md` | `backtest` | humans |

CSV import is an operator convenience: `timestamp,price[,active_id]`, ISO 8601 with offset. `build` and `diagnose` also accept JSONL and Parquet tick files. Legacy pickle suites can be read for analysis/backtest, but runtime inference requires a validated `.joblib` artifact.

---

## Tick Store Interface

| Member | Contract |
|--------|----------|
| `timestamp` | UTC, never null |
| `price` | Positive float, never null |
| `active_id` | Nullable integer |
| `utc_offset_seconds` | Original offset |
| `tick_id` | Store-assigned row id |
| `.frame` | Read-only view; callers must not mutate |
| `.last_price_at(t)` | Last price at or before `t`; null before the first tick |
| `.price_at(ts)` | Backward as-of merge, one row per query |

Batch loading preserves duplicate observations and stable-sorts by timestamp and sequence. The store guarantees that no lookup returns a future price.

---

## Snapshot Interface

A snapshot is the only object a feature function may consume.

| Field | Contract |
|-------|----------|
| `snapshot_id` | Unique within one build |
| `snapshot_time` | Candle-close decision time |
| `completed_bars` | Exactly `macro_candles` contiguous completed candles |
| `forming_bar` | Not included in the decision feature vector |
| `entry_timestamp` / `entry_price` | Resolved delayed entry |
| `outcomes[horizon]` | Exit timestamp, price, delay, label |

Downstream code must not read ticks directly; otherwise the causality slice can be bypassed.

---

## Feature Interface

```python
FeatureVector.core       -> dict[str, float | None]   # 16 keys, fixed order
FeatureVector.values()   -> tuple[float | None, ...]
FeatureVector.complete() -> bool
snapshot_feature_row()   -> flat dict for Parquet
```

The core dict must contain exactly `CORE_FEATURES` in the declared order. `ModelSuite` stores that order and trains on it, so a reordering is a breaking change requiring a version bump.

---

## Proposal Interface

| Field | Contract |
|-------|----------|
| `horizon_seconds` | One configured horizon, or the best rejected one |
| `direction` | `call`, `put`, or `no_trade` |
| `probability` | Probability of the chosen direction |
| `payout` | Payout used for EV |
| `expected_value` | EV per unit stake |
| `reason` | One of the four reason codes |
| `actionable` | True only for `selected` with a direction |

---

## Trade Interface

| Field | Contract |
|-------|----------|
| `entry_timestamp` / `entry_price` | Actual entry tick |
| `expiry_timestamp` | `entry_timestamp + horizon_seconds` |
| `status` | `open`, `won`, `lost`, `void` |
| `pnl` | `+stake * payout`, `-stake`, or `0` |
| `resolve(exit_price)` | Exactly once |

---

## Versioning

Every artefact records the versions that produced it:

| Version | Where stored |
|---------|--------------|
| `feature_version` | Feature rows, dataset, manifest |
| `core_feature_version` | Feature rows, dataset, manifest |
| `label_version` | Label rows, dataset, manifest |
| `decision_version` / `candle_version` | Runtime manifest |
| `config_hash` | Build summary, model suite/manifest |
| `trained_at` | Model suite/manifest |

A consumer that does not recognise a version must refuse the artefact rather than guess.

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Configuration](03_CONFIGURATION.md)
- [Tick store](../data/07_TICK_STORE.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)

---

*Last updated: 2026-11-21*
