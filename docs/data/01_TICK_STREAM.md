# Tick Stream Contract

Status: Current

> This document defines what the project means by a **tick event**, what the receiver currently accepts, and what must be validated before the stream is used for candles, AMT features, or models.

---

## Definition

In this project, a **tick event** is one live price update forwarded by the Chrome extension and accepted by `components/receiver.py`.

A tick event is **not** an exchange trade print. It is a broker-originated price update observed through the browser's WebSocket connection. The payload does not contain true traded volume or Level 2 depth.

The IQ Option message envelope currently uses the name `candle-generated`. That name is an implementation detail of the feed and must not be confused with the project's own 1-minute candle layer. The project's candles are built later from tick events.

---

## Current Envelope

The extension forwards the original JSON string. `components/receiver.py` parses it and expects:

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

`components/receiver.py` currently performs these steps:

1. Parse the raw frame as JSON. Malformed JSON is logged and ignored.
2. Require a JSON object with `name == "candle-generated"`.
3. Require `msg` to be an object.
4. Require `msg.active_id` to be present.
5. Copy `msg` into a dictionary and stamp `received_at` if absent.
6. Append the dictionary to `history_by_active_id[active_id]`.
7. Call `process_tick`, which logs OHLCV values and the current buffer length.
8. Call the optional tick sink, which `runner.py serve` wires to the JSONL writer.

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
| Receipt time | Receiver clock, captured when the frame is accepted | Implemented: stamped as `received_at` |
| Payload `at` | `msg.at` | Stored inside the raw payload; never promoted |

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
- Every accepted frame is stamped with `received_at`.
- Accepted ticks can be appended to a daily JSONL capture.
- Asset-name files must map string keys to non-empty string values.
- The tick store rejects naive timestamps, non-numeric prices, non-positive prices, and `active_id` mismatches.
- Exact `(timestamp, price)` duplicates are dropped when the store is built.
- Out-of-order rows are counted and sorted.

### Planned

| Rule | Purpose |
|------|---------|
| Reject non-numeric `close` at the receiver | Fail earlier than the build |
| Detect duplicate frames at capture time | Avoid writing duplicates to disk |
| Detect gaps and reconnects | Mark periods with missing data explicitly |
| Track message rate per `active_id` | Detect stale or stalled instruments |
| Flag unknown/renamed message types | Detect feed schema drift |
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

## Persistence

`runner.py serve` persists accepted ticks as JSONL, one file per UTC day under `data/raw/`:

```json
{"received_at":"2026-11-18T13:00:00.123+01:00","active_id":42,"price":1.25,"payload":{"close":1.25,"at":123}}
```

JSONL is chosen first because it is append-only, easy to inspect, and replayable. `build` reads it into the Parquet tick store. The payload `at` value stays inside `payload` and is never promoted to a timestamp column.

Passing `--raw-dir ''` disables persistence for a capture-only session.

### Duplicate Rule

The tick store drops exact `(timestamp, price)` duplicates before snapshots are built. This prevents repeated frames from inflating tick density. Near-duplicates and genuinely repeated prices are still an open question.

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
- [Tick store](07_TICK_STORE.md)
- [1-minute candle aggregation](03_CANDLE_AGGREGATION.md)
- [Asset identities](02_ASSET_IDENTITIES.md)
- [Limitations and improvement backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)
- [Data pipeline](../system/07_DATA_PIPELINE.md)

---

*Last updated: 2026-11-19*
