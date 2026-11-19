# Execution and Resolution

Status: Current

> Paper execution only. The broker turns a routed proposal into a trade, holds it to expiry, and resolves it against the recorded exit price. Demo and live modes are validated by configuration and then rejected.

---

## Mode Gate

`config.execution.mode` accepts `paper`, `demo`, or `live`.

`PaperBroker.__post_init__` raises `ExecutionError` for anything other than `paper`. This is deliberate: the configuration accepts the mode names so a future adapter can be specified, but no adapter exists, and the process fails instead of pretending to trade.

There is no order placement, no account authentication, and no network execution path in the repository.

---

## Trade Model

| Field | Meaning |
|-------|---------|
| `trade_id` | Monotonic id within one broker |
| `snapshot_id` | Snapshot that produced the signal |
| `active_id` | Instrument |
| `direction` | `call` or `put` |
| `horizon_seconds` | Expiry offset |
| `stake` | Fixed stake from `execution.stake` |
| `payout` | Payout used for EV and for the win amount |
| `entry_timestamp` | Actual entry tick time |
| `entry_price` | Actual entry tick price |
| `expiry_timestamp` | `entry_timestamp + horizon_seconds` |
| `expected_value` | Router EV at decision time |
| `status` | `open`, `won`, `lost`, or `void` |
| `exit_price` | Recorded exit price, or null |
| `resolved_at` | Time the trade was resolved |
| `pnl` | Realised profit or loss |
| `reason` | Router reason code |

Entry is never the snapshot time. It is the first tick at or after `snapshot_time + 250ms` within the entry tolerance, so the trade is priced at a moment the engine could actually have acted. See [Snapshots and continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md).

---

## Opening a Trade

`PaperBroker.open(proposal, snapshot)` returns a trade only when:

1. `proposal.actionable` is true.
2. The snapshot has an entry timestamp and price.
3. `can_open(entry_timestamp)` is true.

`can_open` counts only positions whose expiry is still in the future:

```python
live = [t for t in open_trades if t.expiry_timestamp > now]
return len(live) < max_open_trades
```

A trade that has passed expiry but has not been resolved yet carries no market risk, so it does not block a new entry. This matters because resolution requires the expiry tick to be present; a missing exit must not deadlock the broker.

With the default `max_open_trades = 1`, the engine can hold one genuinely live position at a time.

---

## Resolution

Resolution uses the outcome recorded by the sampler, not a fresh price lookup:

```text
register_outcomes(snapshot)      # store exit prices per horizon
resolve_due(now)                 # resolve open trades whose expiry <= now
```

A trade resolves only when its registered outcome has a non-null exit price. Missing exits leave the trade open; they are never guessed.

| Exit vs entry | Status | PnL |
|---------------|--------|-----|
| Exit > entry and direction `call` | `won` | `+stake * payout` |
| Exit < entry and direction `put` | `won` | `+stake * payout` |
| Opposite direction | `lost` | `-stake` |
| Exit exactly equals entry | `void` | `0` |

A tie is a void trade: the stake is returned and PnL is zero. The model never sees a tie as a directional label, so voiding keeps execution consistent with training.

`Trade.resolve` raises `ExecutionError` if called twice on the same trade.

---

## Broker Summary

| Key | Meaning |
|-----|---------|
| `trades` | Trades opened |
| `closed` | Trades with a non-open status |
| `open` | Still open after final resolution |
| `wins` / `losses` / `voids` | Status counts |
| `pnl` | Sum of realised PnL, rounded to 6 decimals |
| `win_rate` | Wins divided by closed trades |

Win rate is measured over closed trades only. A void is neither a win nor a loss but does count in `closed`, which pulls the win rate down; read PnL alongside it.

---

## Backtest Replay

`run_backtest` is the only place a trade is simulated. It walks snapshot groups in time order:

1. Advance the broker's clock: `resolve_due(snapshot.entry_timestamp)`.
2. Ask the suite for held-out probabilities: `evaluate_snapshot(snapshot_id)`.
3. Skip the snapshot as `skipped_no_model` when the suite has none.
4. Register the snapshot's outcomes.
5. Route the probabilities.
6. If actionable but no slot is free, count `skipped_overlap` and move on.
7. Otherwise open a trade.

At the end, `resolve_due(MAX_TIME)` closes everything whose exit is known. Trades with a missing exit stay open and are reported as `open`.

Snapshots without an entry tick are skipped before routing and are not counted in `routed`.

| Counter | Meaning |
|---------|---------|
| `snapshots` (routed) | Snapshots with a held-out probability |
| `skipped_no_model` | Snapshots outside the evaluation slice |
| `skipped_below_hurdle` | Routed snapshots that failed the EV hurdle |
| `skipped_overlap` | Actionable signals blocked by the open-trade limit |
| `trades` | Trades actually opened |

The replay never calls `predict_vector`, so an in-sample probability cannot enter the backtest.

---

## Trade Journal

`TradeJournal` writes one JSON object per trade to an append-only JSONL file, converting timestamps to ISO 8601. It is not wired into the backtest yet; the backtest reports are the current audit trail.

When live or demo execution is added, the journal becomes the audit log and must record the decision inputs alongside the trade.

---

## Risk Controls That Are Not Implemented

| Control | Status |
|---------|--------|
| Fixed stake | Implemented (`execution.stake`) |
| One open trade per instrument | Implemented (`execution.max_open_trades`) |
| Daily loss limit | Not implemented |
| Consecutive-loss limit | Not implemented |
| Stake sizing / Kelly | Not implemented |
| Kill switch | Not implemented |
| Account state reconciliation | Not implemented |
| Order idempotency | Not applicable yet |

No live execution may be attempted until every missing control exists and is tested.

---

## Related Documentation

- [Signal router](13_SIGNAL_ROUTER.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)
- [Labels, payouts, and EV](../data/06_LABELS_PAYOUTS_AND_EV.md)

---

*Last updated: 2026-11-19*
