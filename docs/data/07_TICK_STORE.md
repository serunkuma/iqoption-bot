# Tick Store

Status: Current

> The tick store is the canonical tick table for the engine. It enforces the tick contract, orders and deduplicates rows, and exposes point-in-time lookups so nothing downstream can read the future.

---

## Position in the Pipeline

```text
extension -> components/receiver.py -> data/raw/ticks-YYYY-MM-DD.jsonl
                                              |
                                    TickStore.from_jsonl
                                              v
                                       TickStore
                                              v
                                   snapshot sampler
```

The store is built in memory during `build` and written to `data/ticks.parquet`. It is not a live database; there is no append-in-place path yet.

---

## Schema

| Column | Type | Meaning |
|--------|------|---------|
| `tick_id` | int64 | Row ordinal after sorting and deduplication |
| `timestamp` | `datetime64[ns, UTC]` | `received_at`, the local receipt time |
| `utc_offset_seconds` | int64 | Original UTC offset, retained for local-time features |
| `price` | float64 | Tick price, from the payload `close` |
| `active_id` | Int64 (nullable) | Instrument key |

`tick_id` is assigned by the store. It is never trusted from an input file, and it is rebuilt on every load so a Parquet round-trip cannot duplicate or reorder ids.

The row order is always ascending `timestamp`, with a stable mergesort so ties keep their input order.

---

## Ingestion Rules

| Rule | Behaviour |
|------|-----------|
| Timestamp present | Required |
| Timestamp timezone-aware | Required; a naive timestamp is rejected |
| Price numeric | Required |
| Price positive | Required; zero and negatives are rejected |
| `active_id` optional | Nullable; CSV/JSONL may omit it |
| `active_id` mismatch | Rejected when a configured `instrument.active_id` disagrees |
| Exact duplicate `(timestamp, price)` | Dropped, first occurrence kept |
| Out-of-order rows | Sorted, with a count recorded |

Every violation raises `TickStoreError` with the line number. Bad input fails loudly; it is never repaired silently.

### CSV

Required columns are `timestamp` and `price`; `active_id` is optional. Timestamps must be ISO 8601 with an offset, for example `2026-11-18T12:00:02.100+01:00`.

```csv
timestamp,price,active_id
2026-11-18T12:00:02.100+01:00,1.2500,42
2026-11-18T12:00:15.400+01:00,1.2505,42
```

### JSONL

Each line is a receiver record:

```json
{"received_at": "2026-11-18T12:00:02.100000+01:00", "active_id": 42, "price": 1.25, "payload": {"close": 1.25, "at": 123}}
```

Only `received_at`, `active_id`, and `price` are promoted. `payload` stays on disk as evidence; it is not stored in the tick table.

### Parquet

Parquet is treated as an already-validated store. The schema is still checked for `timestamp` and `price`, but row-level validation is not repeated.

---

## Deduplication

Duplicate detection is exact on `(timestamp, price)`.

This removes frames the extension repeated or that arrived twice across a reconnect. It does not merge genuinely repeated prices at different timestamps: a market resting at one price still accrues TPO time, which is the intended behaviour.

Near-duplicate detection is an open question, not an implemented rule.

---

## Access API

| Member | Purpose |
|--------|---------|
| `TickStore.from_ticks(ticks)` | Build from `Tick` objects |
| `TickStore.from_csv(path, active_id=...)` | Load and validate a CSV |
| `TickStore.from_jsonl(path, active_id=...)` | Load a raw capture |
| `TickStore.from_parquet(path)` | Reload a store |
| `TickStore.empty()` | Empty store |
| `.is_empty` | True when there are no rows |
| `.frame` | The underlying DataFrame |
| `.as_ticks()` | Convert back to `Tick` objects |
| `.between(start, end)` | Inclusive time slice |
| `.last_price_at(timestamp)` | Last price at or before a time |
| `.price_at(timestamps)` | Vectorised point-in-time merge |
| `.appended(ticks)` | New store with ticks merged and re-deduplicated |
| `.write_parquet(path)` | Persist the store |

`last_price_at` and `price_at` use a backward `merge_asof`, so a query never sees a future price. A query before the first tick returns null rather than the first price.

---

## Load Statistics

| Statistic | Meaning |
|-----------|---------|
| `total_rows` | Rows read from the source |
| `duplicates_dropped` | Exact duplicates removed |
| `out_of_order` | Adjacent timestamp inversions before sorting |

`diagnose` prints these, and `build` includes them in its summary. They are the first signal of a broken capture.

---

## Versioning

The store does not currently carry a version column. The tick contract itself is unversioned. When the capture format changes — for example if a second price field is promoted — add a version and migrate rather than guessing which rows follow which rule.

---

## Known Gaps

| Gap | Consequence |
|-----|-------------|
| No live append path | Capture and build are separate runs |
| No session table | Reconnects and gaps are only visible as missing minutes |
| No near-duplicate rule | Repeated prices at different timestamps inflate tick counts |
| No per-instrument partitioning | Multi-instrument is filtered, not stored separately |
| CSV/JSONL import only | No streaming ingestion |

See [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md).

---

## Related Documentation

- [Tick stream contract](01_TICK_STREAM.md)
- [Snapshots and continuity](08_SNAPSHOTS_AND_CONTINUITY.md)
- [1-minute candle aggregation](03_CANDLE_AGGREGATION.md)
- [Runtime and entry point](../system/11_RUNTIME_AND_ENTRYPOINT.md)

---

*Last updated: 2026-11-19*
