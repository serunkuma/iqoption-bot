# Snapshots and Continuity

Status: Current

> A snapshot is the only evaluation point the engine recognises. The sampler verifies that the seven preceding 1-minute bars exist and are contiguous, freezes the feature slice at the snapshot time, and attaches a delayed entry price plus one exit outcome per horizon.

---

## Why Snapshots

Predicting every tick would create thousands of near-identical rows per minute, each with an overlapping outcome window. That inflates row counts without adding information and makes the training set dominated by whichever microsecond the engine happened to sample.

Snapshots instead define a small, fixed set of decision points:

| Setting | Default | Meaning |
|---------|---------|---------|
| `snapshot.offsets_seconds` | `[30]` | Offset inside each forming minute |
| `snapshot.entry_delay_ms` | `250` | Delay between decision and entry |
| `snapshot.entry_tolerance_seconds` | `1.0` | How late the entry tick may be |
| `snapshot.exit_tolerance_seconds` | `5.0` | How late the exit tick may be |
| `snapshot.min_ticks_per_bar` | `1` | Minimum ticks in each completed bar |

Offsets may be a list, so `[0, 20, 40]` produces three snapshots per minute. Each offset must be inside `[0, interval_seconds)` and the list must be unique.

---

## The Continuity Gate

For every whole minute that contains ticks, in ascending order, the sampler builds a snapshot only when all of the following hold:

1. At least `context.macro_candles` earlier minutes exist.
2. The last `macro_candles` minutes are exactly `key - macro ... key - 1` — no missing minute.
3. Every completed bar in that window has at least `min_ticks_per_bar` ticks.
4. At least one tick exists at or before the snapshot offset inside the forming minute.
5. An entry tick exists within `entry_delay + entry_tolerance`.

Failure at any step increments a specific counter and moves on. The engine never fills a gap, interpolates a bar, or synthesises a price.

### The Forming Minute

The forming minute is **never** part of the profile or volatility window. It contributes only:

- the current price — the last tick at or before the snapshot time,
- forming tick rate, price speed, range, and price change,
- the entry and exit lookups.

Completed bars are the `macro_candles` minutes before the forming minute. The fast window is the last `fast_candles` of those completed bars.

---

## Causality Slice

The forming bar is truncated at the snapshot time:

```text
limit = searchsorted(epochs, snapshot_epoch, side="right")
forming_bar = ticks[forming_start:limit]
```

`side="right"` includes a tick exactly at the snapshot time and excludes everything after it. This is the only place the feature slice is cut, and it happens before any feature is computed.

---

## Delayed Entry

```text
entry_target = snapshot_epoch + entry_delay
entry_index  = searchsorted(epochs, entry_target, side="left")   # first >= target
entry_tick   = epochs[entry_index]  if entry_tick <= entry_target + entry_tolerance
```

The entry price is that tick's price. `entry_delay_seconds` records the realised delay, which is normally a little above 250ms.

If no tick arrives inside the tolerance, the snapshot is discarded with `skipped_no_entry_tick`. The engine does not fall back to the snapshot price, because that would price the trade at a moment it could not have acted.

---

## Exits and Labels

For each configured horizon:

```text
target        = entry_epoch + horizon
exit_index    = searchsorted(epochs, target, side="left")
exit_tick     = epochs[exit_index]  if exit_tick <= target + exit_tolerance
```

The exit is measured from the **actual entry time**, not from the snapshot time. With a 250ms entry delay, a 60s horizon expires 60.25s after the snapshot.

| Outcome | Label |
|---------|-------|
| Exit price > entry price | `call` |
| Exit price < entry price | `put` |
| Exit price == entry price | `tie` |
| No exit tick within tolerance | `missing` |

Ties and missing exits are never mapped to a direction. `tie_policy = "exclude"` marks ties unusable; `keep` retains them as rows but they remain non-directional for training. Missing exits are always unusable.

If any horizon is missing, the snapshot is still emitted and counted in `snapshots_with_missing_exits`; only the affected horizon is marked unusable.

---

## Snapshot Object

| Field | Meaning |
|-------|---------|
| `snapshot_id` | Monotonic id in build order |
| `active_id` | Instrument |
| `snapshot_time` | Decision time `forming_start + offset` |
| `forming_start` | Start of the forming minute |
| `completed_bars` | The `macro_candles` completed bars |
| `forming_bar` | Truncated forming bar |
| `price` | Last price at or before the snapshot time |
| `window_ticks` | Ticks in the completed macro window |
| `entry_timestamp`, `entry_price` | Delayed entry |
| `entry_delay_seconds` | Realised delay |
| `outcomes` | Horizon to `HorizonOutcome` |
| `utc_offset_seconds` | Original capture offset for local-time features |

`contiguous` is a property of the completed bars plus the forming bar: the keys must form one unbroken run ending immediately before the forming minute.

---

## Exclusion Report

| Counter | Meaning |
|---------|---------|
| `candidate_minutes` | Whole minutes containing at least one tick |
| `snapshots` | Snapshots emitted |
| `skipped_insufficient_history` | Fewer than `macro_candles` earlier minutes |
| `skipped_gap` | A minute is missing inside the macro window |
| `skipped_sparse_bar` | A completed bar has fewer than `min_ticks_per_bar` ticks |
| `skipped_no_pre_offset_tick` | No tick at or before the offset |
| `skipped_no_entry_tick` | No entry tick inside the tolerance |
| `snapshots_with_missing_exits` | At least one horizon has no exit |

The counters are printed by `build` and should be checked against the data. A high `skipped_gap` usually means the capture has holes; a high `skipped_no_entry_tick` usually means the feed is sparse or the entry tolerance is too tight.

---

## Single Instrument

The sampler filters the store to `instrument.active_id` before doing anything else. When the config value is null, it uses the first `active_id` present and filters to that.

This is how single-instrument operation is enforced: feature windows can never mix two instruments. Multi-instrument sampling is a future item, not a hidden mode.

---

## Worked Example

Capture starts at `12:00`. `macro_candles = 7`, offset `30`, horizon `60`.

| Minute | Result |
|--------|--------|
| 12:00–12:06 | `skipped_insufficient_history` (7 needed before the forming minute) |
| 12:07 | Snapshot at `12:07:30`, if bars `12:00`–`12:06` are contiguous and dense enough |
| 12:08 | Snapshot at `12:08:30`, window `12:01`–`12:07` |

A snapshot at `12:07:30` with entry at `12:07:30.31` expires at `12:08:30.31`; the exit is the first tick at or after that time, within 5 seconds.

---

## Known Gaps

- The continuity gate checks presence, not tick density quality beyond `min_ticks_per_bar`.
- A bar with exactly `min_ticks_per_bar` ticks is accepted; there is no upper-level quality score.
- Entry and exit tolerances are global, not per instrument or session.
- Snapshot offsets are fixed per minute; there is no event-driven trigger.
- The sampler is batch-only; live snapshots are not produced.

---

## Related Documentation

- [Tick store](07_TICK_STORE.md)
- [Model inputs](09_MODEL_INPUTS.md)
- [Labels, payouts, and EV](06_LABELS_PAYOUTS_AND_EV.md)
- [Data pipeline](../system/07_DATA_PIPELINE.md)

---

*Last updated: 2026-11-19*
