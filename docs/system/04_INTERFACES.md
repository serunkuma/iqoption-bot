# Interfaces

Status: Current

> This document defines the interfaces between the browser extension and the receiver, and the planned internal contracts between pipeline components.

---

## Browser Extension to Receiver

### Transport

| Property | Value |
|----------|-------|
| Protocol | WebSocket |
| URL | `ws://localhost:8765` |
| Direction | Extension to receiver |
| Authentication | None (localhost only) |
| Max frame size | 1 MiB in the receiver |

### Message

The extension forwards the original JSON string from the page WebSocket.

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

### Receiver Acceptance Rules

The receiver accepts a frame only when:

- It is valid JSON.
- It is a JSON object.
- `name == "candle-generated"`.
- `msg` is a JSON object.
- `msg.active_id` is present.

Everything else is ignored or logged as malformed.

### Connection Behaviour

- The extension reconnects every 2 seconds after a disconnect.
- While disconnected, it queues up to 500 messages.
- When the queue is full, it drops the oldest message and logs a warning.
- The receiver handles one or more client connections but keeps shared per-`active_id` state.

### Error Handling

| Condition | Current behaviour | Planned behaviour |
|-----------|-------------------|-------------------|
| Malformed JSON | Log and ignore | Count and sample |
| Missing `msg` | Log and ignore | Count and sample |
| Missing `active_id` | Log and ignore | Count and sample |
| Unknown message type | Ignore | Count; optionally capture for schema discovery |
| Receiver unavailable | Extension reconnects | Same, with queue metrics |
| Queue full | Drop oldest | Expose dropped count to the receiver or logs |

---

## Planned Internal Contracts

These contracts do not exist yet. They are defined here so components can be built against a stable shape.

### Tick Event

```json
{
  "active_id": 42,
  "symbol": "EURUSD",
  "price": 1.25,
  "timestamp": "2026-11-18T13:00:02.130+01:00",
  "session_id": "session-uuid",
  "connection_id": "connection-uuid",
  "quality_flags": []
}
```

`timestamp` is the receiver's local receipt time. There is no separate event timestamp in this contract.

### 1-Minute Candle

```json
{
  "active_id": 42,
  "interval": 60,
  "bucket_start": "2026-11-18T13:00:00+01:00",
  "open": 1.25,
  "high": 1.251,
  "low": 1.2492,
  "close": 1.251,
  "tick_count": 4,
  "is_complete": true,
  "quality_flags": []
}
```

### Feature Snapshot

```json
{
  "tick_id": 1284,
  "active_id": 42,
  "timestamp": "2026-11-18T13:01:07.412+01:00",
  "feature_version": "amt-v2",
  "features": {
    "price": 1.2505,
    "poc": 1.25025,
    "vah": 1.251,
    "val": 1.2495,
    "sigma_7": 0.00012,
    "z_poc": 2.08,
    "z_vah": -4.17,
    "z_val": 8.33,
    "inside_va": 1,
    "tick_rate_7": 1.4,
    "tick_rate_3": 2.1,
    "tick_rate_forming": 3.0,
    "tick_rate_3_7": 1.5,
    "tick_rate_forming_3": 1.43
  }
}
```

### Signal

```json
{
  "tick_id": 1284,
  "active_id": 42,
  "timestamp": "2026-11-18T13:01:07.412+01:00",
  "horizon_seconds": 60,
  "direction": "call",
  "probability": 0.57,
  "payout": 0.82,
  "expected_value": 0.0194,
  "model_version": "model-2026-11-18",
  "reason": "balance_model"
}
```

`direction` is one of `call`, `put`, or `no_trade`. A missing or ambiguous feature snapshot must produce `no_trade` with a reason code.

### Order and Trade Result

```json
{
  "order_id": "order-uuid",
  "mode": "paper",
  "active_id": 42,
  "direction": "call",
  "stake": 1.0,
  "entry_at": "2026-11-18T12:01:00Z",
  "expiry_at": "2026-11-18T12:02:00Z",
  "status": "filled",
  "outcome": "win",
  "pnl": 0.82
}
```

---

## Interface Rules

1. Every payload has a versioned schema.
2. Every timestamp is ISO 8601 with an explicit UTC offset.
3. Ticks carry exactly one timestamp: the receiver's local receipt time.
4. Optional fields are nullable, not omitted inconsistently.
5. Unknown fields are preserved in raw storage.
6. Schema changes require a version bump and a migration note.

---

## Related Documentation

- [Tick stream contract](../data/01_TICK_STREAM.md)
- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [Configuration](03_CONFIGURATION.md)
- [Data pipeline](07_DATA_PIPELINE.md)

---

*Last updated: 2026-11-18*
