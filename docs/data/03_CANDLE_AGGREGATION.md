# 1-Minute Candle Aggregation

Status: Planning

> This document specifies how the project will build its own 1-minute OHLCV candles from tick events. Candle generation does not exist yet. The current receiver stores raw messages only.

---

## Purpose

Candles provide a stable, lower-frequency representation of the tick stream. They are used for:

- Labels and expiry outcomes.
- Charting and inspection.
- Context features.
- Backtest reporting.
- Fallback strategies that operate on completed candles.

AMT/TPO features are computed from ticks, not from candles. Candles do not replace the tick stream.

---

## Definitions

| Term | Definition |
|------|------------|
| Tick event | One accepted price update from the receiver |
| Bucket | A half-open 60-second interval `[start, start + 60s)` |
| Bucket start | UTC minute boundary aligned to the Unix epoch |
| Tick price | The `close` value of the tick event |
| Complete candle | A candle whose bucket has ended and whose final state is stored |
| Tick count | Number of accepted tick events assigned to the bucket |

### Boundary Rule

Buckets are clock-aligned to UTC minute boundaries:

```text
bucket_start = floor(event_time / 60) * 60
```

Examples:

| Event time (UTC) | Bucket start | Bucket end |
|------------------|--------------|------------|
| 12:00:00.000 | 12:00:00 | 12:01:00 |
| 12:00:59.999 | 12:00:00 | 12:01:00 |
| 12:01:00.000 | 12:01:00 | 12:02:00 |

The project does not use rolling 60-second windows starting from the first tick.

---

## Input

| Field | Source | Required | Use |
|-------|--------|----------|-----|
| `active_id` | Tick envelope | Yes | Candle key |
| `close` | Tick payload | Yes | Tick price |
| `received_at` | Receiver | Yes | Ordering and bucket assignment |
| `event_at` | Tick payload `at` | Optional | Secondary timestamp after verification |
| `symbol` | Tick payload or asset map | Optional | Display and metadata |
| `interval` | Tick payload | Optional | Feed context; not used for bucket size |

---

## Output

| Field | Type | Description |
|-------|------|-------------|
| `active_id` | string or number | Instrument key |
| `symbol` | string or null | Human-readable symbol |
| `interval` | integer | Always `60` |
| `bucket_start` | timestamp | UTC start of the minute |
| `open` | number | First tick price in the bucket |
| `high` | number | Maximum tick price in the bucket |
| `low` | number | Minimum tick price in the bucket |
| `close` | number | Last tick price in the bucket |
| `tick_count` | integer | Number of accepted ticks in the bucket |
| `payload_volume_sum` | number or null | Sum of untrusted payload `volume`; diagnostic only |
| `first_tick_at` | timestamp | Receipt time of the first tick |
| `last_tick_at` | timestamp | Receipt time of the last tick |
| `is_complete` | boolean | Whether the bucket has ended |
| `quality_flags` | array of strings | Gap, late tick, duplicate, stale, or similar |

---

## Algorithm

```text
on accepted tick(active_id, price, received_at):
    bucket_start = floor(received_at / 60) * 60
    candle = open_candles[active_id].get(bucket_start)

    if candle is None:
        candle = new Candle(
            active_id=active_id,
            bucket_start=bucket_start,
            open=price,
            high=price,
            low=price,
            close=price,
            tick_count=1,
            first_tick_at=received_at,
            last_tick_at=received_at,
            is_complete=False
        )
        open_candles[active_id][bucket_start] = candle
        return

    candle.high = max(candle.high, price)
    candle.low = min(candle.low, price)
    candle.close = price
    candle.tick_count += 1
    candle.last_tick_at = received_at

on clock advance:
    for each open candle whose bucket has ended:
        candle.is_complete = True
        persist(candle)
        remove from open_candles
```

### Late and Out-of-Order Ticks

Default policy:

- If a tick's bucket has already been finalized, do **not** rewrite the candle.
- Count the tick as late.
- Store the late tick in the raw tick store with a `late` quality flag.
- Recompute candles offline during backtests if late arrivals matter.

This keeps live candles deterministic and prevents silent history changes. An offline rebuild can choose a different policy if the data justifies it.

### Empty Buckets

If no ticks arrive during a minute:

- Do not synthesize a candle with a fabricated price.
- Optionally emit a gap marker for that `active_id`.
- Mark the next candle's `quality_flags` with `gap_before`.

### Duplicate Ticks

Exact duplicates must not increment `tick_count` unless the duplicate is known to represent a genuine repeated price observation. The default policy is:

- Hash the raw payload and receipt window.
- Drop exact duplicates that arrive within a short configurable window.
- Count the drop in metrics.

The final dedupe rule must be confirmed after inspecting real traffic.

---

## Worked Example

Input ticks for `active_id = 42` during `12:00:00`–`12:00:59`:

| Receipt time | Price | Payload volume |
|--------------|-------|----------------|
| 12:00:02.100 | 1.2500 | 2 |
| 12:00:15.400 | 1.2505 | 1 |
| 12:00:31.900 | 1.2492 | 3 |
| 12:00:58.700 | 1.2510 | 2 |

Output candle:

```json
{
  "active_id": 42,
  "symbol": "EURUSD",
  "interval": 60,
  "bucket_start": "2026-11-18T12:00:00Z",
  "open": 1.25,
  "high": 1.251,
  "low": 1.2492,
  "close": 1.251,
  "tick_count": 4,
  "payload_volume_sum": 8,
  "first_tick_at": "2026-11-18T12:00:02.100Z",
  "last_tick_at": "2026-11-18T12:00:58.700Z",
  "is_complete": true,
  "quality_flags": []
}
```

`payload_volume_sum` is diagnostic only. It is not treated as traded volume.

---

## Validation Rules

A stored candle is valid only if:

- `low <= open <= high`
- `low <= close <= high`
- `low <= high`
- `tick_count >= 1`
- `bucket_start` is aligned to a 60-second boundary
- `close` equals the price of the last accepted tick in the bucket
- `first_tick_at <= last_tick_at`
- `is_complete` is true before the candle is used in a label

Additional checks:

- No overlapping buckets for the same `active_id`.
- No duplicate `(active_id, bucket_start)` records.
- Gap markers are explicit, not inferred from missing rows.
- Late ticks are visible in the raw store even when they do not modify the candle.

---

## Storage

Planned tables or files:

| Store | Content |
|-------|---------|
| Raw ticks | JSONL append log; later SQLite/Parquet |
| Candles | SQLite table keyed by `(active_id, interval, bucket_start)` |
| Gaps | Table or flags recording missing minutes |
| Rebuild metadata | Source tick range and aggregation version |

---

## Open Questions

- Confirm that `received_at` should drive bucket assignment until `at` is verified.
- Confirm whether exact duplicate prices should count as TPO observations.
- Confirm behaviour for very low-liquidity instruments with long gaps.
- Confirm whether candles are needed for every `active_id` or only a selected universe.
- Confirm retention: how much raw tick and candle history is required for backtests.

---

## Related Documentation

- [Tick stream contract](01_TICK_STREAM.md)
- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [Labels, payouts, and expected value](06_LABELS_PAYOUTS_AND_EV.md)
- [Data pipeline](../system/07_DATA_PIPELINE.md)
- [Limitations and improvement backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-18*
