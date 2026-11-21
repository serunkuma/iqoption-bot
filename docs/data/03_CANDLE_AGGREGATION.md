# 1-Minute Candle Aggregation

Status: Current

> This document specifies clock-aligned 1-minute OHLC candles built from accepted price-update events. Payload `volume` is not aggregated or treated as traded volume. Offline candles are grouped during `build`; the streaming path uses `engine/stream/CandleBuilder` and persists finalized candle parts.

---

## Purpose

Candles provide a stable, lower-frequency representation of the tick stream. They are used for:

- Macro, fast, and last-completed-candle context windows.
- Profile and volatility windows.
- Charting and inspection.
- Backtest reporting.

The profile and activity features use ticks contained in completed candles. Candle close is the decision cadence; labels still price entries and exits from accepted ticks.

---

## Definitions

| Term | Definition |
|------|------------|
| Tick event | One accepted price update from the receiver |
| Bucket | A half-open 60-second interval `[start, start + 60s)` |
| Bucket start | Whole-minute boundary in absolute time |
| Tick price | The `close` value of the tick event |
| Complete candle | A candle whose bucket has ended and whose final state is stored |
| Forming candle | The current, incomplete bucket that receives incoming ticks |
| Tick count | Number of accepted tick events assigned to the bucket |

### Boundary Rule

Buckets are whole minutes in absolute time:

```text
bucket_start = floor(received_at / 60) * 60
```

Whole-minute UTC boundaries coincide with whole local minutes for every real UTC offset. Using absolute time keeps two ticks with the same local wall-clock time but different offsets, as during a daylight-saving change, in separate buckets.

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
| `symbol` | Tick payload or asset map | Optional | Display and metadata |
| `interval` | Tick payload | Optional | Feed context; not used for bucket size |

---

## Output

| Field | Type | Description |
|-------|------|-------------|
| `bucket_key` | int64 | Integer minute key |
| `bucket_start`, `bucket_end` | UTC timestamps | Half-open bucket bounds |
| `active_id` | int64 | Instrument key |
| `open`, `high`, `low`, `close` | float64 | OHLC from accepted prices |
| `tick_count` | int64 | Number of accepted events |
| `first_sequence`, `last_sequence` | int64 | Sequence range of events in the candle |
| `finalized_at` | UTC timestamp | Receipt time of the event that caused finalization |

---

## Algorithm

```text
on accepted tick(active_id, price, received_at):
    bucket_start = floor(received_at / 60) * 60
    candle = open_candles[active_id].get(bucket_start)

    if candle is None:
        start_forming_candle(event, bucket_start)
        return

on first accepted event in a later bucket:
    finalize the previous non-empty candle
    persist it
    start_forming_candle(event, bucket_start)

otherwise:
    update OHLC, tick_count, last_sequence, and event-price history
```

### Late and Out-of-Order Ticks

Streaming policy:

- If a tick's bucket has already been finalized, do **not** rewrite the candle.
- Reject the event and increment `late_rejected`; it is not persisted as an accepted event.
- Batch input is stably sorted by `(timestamp, sequence)` before offline sampling; it does not apply the streaming late-reject rule.

This keeps live candles deterministic and prevents silent history changes. An offline rebuild can choose a different policy if the data justifies it.

### Empty Buckets

If no ticks arrive during a minute:

- Do not synthesize a candle with a fabricated price.
- Count the skipped minute(s) as gaps in the stream store; the rolling feature window cannot be ready across a gap.

### Duplicate Ticks

Repeated events, including exact `(timestamp, price)` duplicates, are preserved and each has a distinct sequence. Their effect on tick density must be evaluated against real traffic.

---

## Worked Example

Input ticks for `active_id = 42` during `12:00:00`–`12:00:59`:

| Receipt time | Price | Payload volume |
|--------------|-------|----------------|
| 12:00:02.100 | 1.2500 | 2 |
| 12:00:15.400 | 1.2505 | 1 |
| 12:00:31.900 | 1.2492 | 3 |
| 12:00:58.700 | 1.2510 | 2 |

Output candle (the stored table also includes the bucket end, sequence bounds, and finalization time):

```json
{
  "bucket_key": 29916720,
  "bucket_start": "2026-11-18T12:00:00Z",
  "bucket_end": "2026-11-18T12:01:00Z",
  "active_id": 42,
  "open": 1.25,
  "high": 1.251,
  "low": 1.2492,
  "close": 1.251,
  "tick_count": 4,
  "tick_count": 4,
  "first_sequence": 101,
  "last_sequence": 104,
  "finalized_at": "2026-11-18T12:01:00.010Z"
}
```

The payload `volume` field is not included in the candle.

---

## Validation Rules

A stored candle is valid only if:

- `low <= open <= high`
- `low <= close <= high`
- `low <= high`
- `tick_count >= 1`
- `bucket_start` is aligned to a 60-second boundary
- `close` equals the price of the last accepted tick in the bucket
- `bucket_end` is exactly one interval after `bucket_start`
- `first_sequence <= last_sequence`

Additional checks:

- No overlapping buckets for the same `active_id`.
- No duplicate `(active_id, bucket_start)` records.
- Missing buckets are counted as gaps; no gap candles are fabricated.
- A rejected late event is counted but is not written as an accepted event.

---

## Storage

The offline sampler groups ticks into minute buckets during `build`. The streaming path persists immutable event and candle Parquet parts under `data/stream/events/YYYY-MM-DD/HH/` and `data/stream/candles/YYYY-MM-DD/HH/`. `state.json` records recovery state, including the forming candle. See [Streaming Runtime and Store](../system/16_STREAMING_RUNTIME_AND_STORE.md).

Not implemented:

| Store | Content |
|-------|---------|
| Session/gap history | Explicit reconnect/session records; gaps are currently counters and absent buckets |
| Candle compaction | Compaction/retention policy for immutable hourly parts |
| Build input | Direct directory ingestion from the streaming event parts |

The aggregation version is `CANDLE_VERSION = "1m-clock-v1"`.

---

## Open Questions

- Confirm whether non-identical repeated prices should count as TPO observations.
- Confirm behaviour for very low-liquidity instruments with long gaps.
- Confirm retention: how much raw tick and candle history is required for backtests.
- Decide whether a candle store is worth adding, given that features read ticks directly.

---

## Related Documentation

- [Tick stream contract](01_TICK_STREAM.md)
- [Tick store](07_TICK_STORE.md)
- [Snapshots and continuity](08_SNAPSHOTS_AND_CONTINUITY.md)
- [TPO and Value Area](04_TPO_VALUE_AREA.md)
- [Labels, payouts, and expected value](06_LABELS_PAYOUTS_AND_EV.md)
- [Data pipeline](../system/07_DATA_PIPELINE.md)
- [Limitations and improvement backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-19*
