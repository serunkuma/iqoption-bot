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

Accepted frames get `received_at` (ISO 8601 with offset) if absent. Rejected frames are logged and dropped. The receiver does not check `close` is numeric and positive; the tick store does that at build time, so a bad price is rejected in one place with a line number.

`msg.at` and `msg.volume` are stored but never promoted or trusted.

---

## Receiver to Sink

```python
set_tick_sink(sink: Callable[[Any, dict], None] | None)
```

The sink is called as `sink(active_id, tick_data)` after validation and buffering. Exceptions are logged and swallowed so capture cannot be killed by a disk error.

`JsonlTickSink` writes one record per accepted tick:

| Field | Type | Meaning |
|-------|------|---------|
| `received_at` | ISO 8601 string with offset | Local receipt time |
| `active_id` | int or string | Instrument key as received |
| `price` | float | `msg.close` |
| `payload` | object | Full original `msg`, unmodified |

Daily files are `data/raw/ticks-YYYY-MM-DD.jsonl`, named by the UTC date of `received_at`.

---

## File Formats

| File | Written by | Consumed by |
|------|------------|-------------|
| `data/raw/ticks-<date>.jsonl` | `serve` | `build --input`, `diagnose` |
| `data/ticks.parquet` | `build` | `build --input` |
| `data/features.parquet` | `build` | research |
| `data/labels.parquet` | `build` | research |
| `data/dataset.parquet` | `build` | `train`, `backtest` |
| `data/models/suite.pkl` | `train` | `backtest` |
| `reports/backtest.json` | `backtest` | humans, tooling |
| `reports/backtest.md` | `backtest` | humans |

CSV import is an operator convenience: `timestamp,price[,active_id]`, ISO 8601 with offset. Parquet is the durable format.

---

## Tick Store Interface

| Member | Contract |
|--------|----------|
| `timestamp` | UTC, never null |
| `price` | Positive float, never null |
| `active_id` | Nullable integer |
| `utc_offset_seconds` | Original offset |
| `tick_id` | Store-assigned, contiguous, ascending by time |
| `.frame` | Read-only view; callers must not mutate |
| `.last_price_at(t)` | Last price at or before `t`; null before the first tick |
| `.price_at(ts)` | Backward as-of merge, one row per query |

The store guarantees that no lookup returns a future price.

---

## Snapshot Interface

A snapshot is the only object a feature function may consume.

| Field | Contract |
|-------|----------|
| `snapshot_id` | Unique within one build |
| `snapshot_time` | Decision time; features may use ticks `<=` this |
| `completed_bars` | Exactly `macro_candles` contiguous bars |
| `forming_bar` | Truncated at `snapshot_time` |
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
| `feature_version` | Feature rows, dataset, suite |
| `core_feature_version` | Feature rows, dataset, suite |
| `label_version` | Label rows, dataset, suite |
| `config_hash` | Build summary, suite |
| `trained_at` | Suite |

A consumer that does not recognise a version must refuse the artefact rather than guess.

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Configuration](03_CONFIGURATION.md)
- [Tick store](../data/07_TICK_STORE.md)
- [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)

---

*Last updated: 2026-11-19*
