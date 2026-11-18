# Tick Stream Contract

Status: Current

> This document defines what the project means by a **tick event**, what the receiver currently accepts, and what must be validated before the stream is used for candles, AMT features, or models.

---

## Definition

In this project, a **tick event** is one live price update forwarded by the Chrome extension and accepted by `receiver.py`.

A tick event is **not** an exchange trade print. It is a broker-originated price update observed through the browser's WebSocket connection. The payload does not contain true traded volume or Level 2 depth.

The IQ Option message envelope currently uses the name `candle-generated`. That name is an implementation detail of the feed and must not be confused with the project's own 1-minute candle layer. The project's candles are built later from tick events.

---

## Current Envelope

The extension forwards the original JSON string. `receiver.py` parses it and expects:

```json
{
  "name": "candle-generated",
  "msg": {
    "active_id": 42,
    "close": 1.25,
    "open": 1.2,
    "min": 1.1,
    "max": 1.3,
    "volume": 7,
    "at": 123,
    "interval": 60,
    "symbol": "EURUSD"
  }
}
```

### Outer Fields

| Field | Type | Required by receiver | Notes |
|-------|------|----------------------|-------|
| `name` | string | Yes | Must currently equal `"candle-generated"` |
| `msg` | object | Yes | Payload must be a JSON object |

### Payload Fields

| Field | Type | Required by receiver | Trusted? | Notes |
|-------|------|----------------------|----------|-------|
| `active_id` | string or number | Yes | Yes | Primary instrument key |
| `close` | number | No | Treat as price | Last price in the update |
| `open` | number | No | Treat as price | Opening price of the feed's update window |
| `min` | number | No | Treat as price | Low of the update window |
| `max` | number | No | Treat as price | High of the update window |
| `volume` | number | No | **No** | Not treated as traded volume |
| `at` | number | No | **Unverified** | Timestamp semantics need confirmation |
| `interval` | number | No | Yes | Feed interval, if present |
| `symbol` | string | No | Informational | May be absent |
| `ticker` | string | No | Informational | May be absent |
| `asset` / `asset_name` | string | No | Informational | May be absent |
| `active_name` | string | No | Informational | May be absent |
| `instrument` / `instrument_name` | string | No | Informational | May be absent |
| `underlying` | string | No | Informational | May be absent |
| `name` | string | No | Informational | Payload-level name, if present |

The receiver recognises the identity fields above when formatting logs. They are not required for processing.

---

## Receiver Behaviour

`receiver.py` currently performs these steps:

1. Parse the raw frame as JSON. Malformed JSON is logged and ignored.
2. Require a JSON object with `name == "candle-generated"`.
3. Require `msg` to be an object.
4. Require `msg.active_id` to be present.
5. Copy `msg` into a dictionary.
6. Append the dictionary to `history_by_active_id[active_id]`.
7. Call `process_tick`, which logs OHLCV values and the current buffer length.

### Buffer Semantics

`history_by_active_id` is a `defaultdict` of `deque(maxlen=500)`.

- The buffer stores **raw message dictionaries**, not generated candles.
- The 500-entry limit is per `active_id`.
- Entries are dropped silently when the deque is full.
- The buffer is in memory only. A receiver restart loses all data.

---

## Timestamp Semantics

The project uses **one timestamp**: the receiver's local receipt time.

| Time | Source | Status |
|------|--------|--------|
| Receipt time | Receiver clock, captured when the frame is accepted | Decided; not recorded by the current receiver |
| Payload `at` | `msg.at` | Ignored for now |

`msg.at` is not used for ordering, bucketing, or labels. Its semantics remain unverified and it may be a candle start, a partial-candle marker, or a broker-specific value.

### Decided Timestamp Rules

- Record `received_at` for every accepted frame.
- Store it as an ISO 8601 string with an explicit UTC offset, for example `2026-11-18T13:42:36.123+01:00`.
- Bucket candles by absolute minute, which matches the local minute for every real UTC offset and keeps repeated local minutes distinct across a daylight-saving change.
- Order ticks by `received_at`.
- Use only one instrument at a time. Multi-instrument capture is a future item.

---

## Data Quality Rules

### Implemented Today

- Frame must be valid JSON.
- Frame must be a JSON object.
- Outer `name` must equal `"candle-generated"`.
- `msg` must be an object.
- `active_id` must be present.
- Asset-name files must map string keys to non-empty string values.

### Planned Before AMT Work

| Rule | Purpose |
|------|---------|
| Require numeric `close` | Reject frames without a usable price |
| Record `received_at` | Establish local ordering |
| Detect duplicate frames | Avoid inflating tick density |
| Detect out-of-order events | Protect causal feature windows |
| Detect gaps and reconnects | Mark periods with missing data |
| Track message rate per `active_id` | Detect stale or stalled instruments |
| Validate `active_id` type | Keep storage keys consistent |
| Flag unknown/renamed message types | Detect feed schema drift |
| Store the raw frame | Support replay and audits |
| Count dropped extension-queue messages | Make data loss visible |

### Invalid-Frame Policy

Invalid frames must be counted and sampled in logs, not silently discarded. The planned metrics are:

- `frames_received`
- `frames_accepted`
- `frames_rejected`
- `frames_malformed`
- `frames_stale`
- `frames_duplicate`

---

## Planned Persistence

The proof of concept does not persist ticks. The planned raw-capture format is JSONL:

```json
{"received_at":"2026-11-18T13:00:00.123+01:00","session_id":"...","connection_id":"...","active_id":42,"raw":{...}}
```

JSONL is chosen first because it is append-only, easy to inspect, and replayable. SQLite or Parquet can follow once query and volume requirements are clearer. The payload `at` value stays inside `raw` and is not promoted to a timestamp column.

### Duplicate Rule

The offline loader drops exact `(timestamp, price)` duplicates before building features. This prevents repeated frames from inflating tick density. Near-duplicates and genuinely repeated prices are still an open question.

---

## Open Questions

- Is the intercepted frame a raw tick, a partial-candle update, or a completed-candle event?
- Does the feed send repeated identical prices, and should non-identical repeats count as TPO ticks?
- Are there other message types that carry price updates and should be captured?
- What is the expected message rate per `active_id` during an active session?
- How should multi-instrument capture partition storage and features if it is added later?

---

## Related Documentation

- [System overview](../system/01_OVERVIEW.md)
- [1-minute candle aggregation](03_CANDLE_AGGREGATION.md)
- [Asset identities](02_ASSET_IDENTITIES.md)
- [Limitations and improvement backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)
- [Data pipeline](../system/07_DATA_PIPELINE.md)

---

*Last updated: 2026-11-18*
