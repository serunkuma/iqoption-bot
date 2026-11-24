# Streaming Runtime and Store Migration

Status: Historical

> This document records the migration from file-first, `:30` snapshots to a
> candle-close streaming runtime. The implementation is current; this plan is
> kept for context. The authoritative behaviour is in
> [Streaming Runtime and Store](../system/16_STREAMING_RUNTIME_AND_STORE.md).

---

## What was replaced

| Before | After |
|---|---|
| `serve` appended daily raw JSONL captures | `serve` writes hourly Parquet event and candle parts under `data/stream/` |
| Snapshots at a configurable minute offset, default `:30` | One decision at every closed 1-minute candle |
| The four forming-bar model inputs | The four last-completed-candle inputs (`core16-v2`) |
| Diagnostics `amt-v3` | Diagnostics `amt-v4` |
| Exact duplicate `(timestamp, price)` rows dropped | Every accepted event preserved with a monotonic `sequence` |
| Pickle `suite.pkl` was the runtime artifact | Manifest-bearing `.joblib` is required at runtime; pickle remains readable for analysis and backtest |
| No runtime risk gates | Paper-only gates: one open trade, cooldown, daily realized-loss stop, store health |

The old `suite.pkl` files were trained on `:30` observations. They are not
candle-close compatible and must not drive runtime inference.

## What shipped

- `engine/stream/`: sequenced events, one-minute candles, a seven-candle rolling
  window, hourly Parquet parts, atomic writes, state recovery, late-event
  rejection, and a bounded ingestion buffer.
- `engine/runtime.py`: candle-close warm-up, per-horizon inference, deterministic
  EV routing, paper gates, decision journal, and shadow mode.
- `engine/replay.py` and `runner.py replay`: rebuild candles from stored events
  and compare OHLC, tick counts, sequences, and the 16 core features.
- `TickStore.from_stream_events`: build and diagnose can read the streaming
  store's event parts directly.
- Runtime paper state is reloaded from `trades.jsonl`, so the open-trade gate,
  cooldown, and daily loss stop survive a restart.
- Tests: store, candle, window, Parquet, runtime, replay, and CLI coverage.

## Deviations from the original plan

| Planned | Actual |
|---|---|
| New `docs/planning/streaming-runtime-and-store.md` as a planning doc | This historical record plus `docs/system/16_STREAMING_RUNTIME_AND_STORE.md` as the current implementation doc |
| `[stream].state_file` and `[stream].decisions_dir` config keys | Fixed paths under `[stream].root`; `rotation_seconds` is validated but partitioning is always hourly |
| Shadow mode described only as a validation step | Implemented as `serve --shadow` |
| Build input limited to files | `build` and `diagnose` also accept a stream events directory |
| Runtime state only in `state.json` | Candles and events in `state.json`; paper trades reloaded from `trades.jsonl` |
| Learned selector in Phase 4 | Still unimplemented; the router remains deterministic |

## What remains

- Real-capture retraining and a regenerated backtest. Checked-in `data/*.parquet`
  and `reports/backtest.*` may predate the candle-close contract until re-run.
- Real-feed replay parity, a sustained shadow session, and a sustained paper
  session with audited gates.
- Stream retention and compaction policy.
- A broker-reported payout source; payouts are configuration only.
- A learned direction/horizon/no-trade selector evaluated against the EV router.
- A complete risk manager, kill switch, monitoring, and any demo/live adapter.

No edge has been established. The runtime exists; it is not a validated trading
bot.

---

## Related Documentation

- [Streaming Runtime and Store](../system/16_STREAMING_RUNTIME_AND_STORE.md)
- [Runtime and Entry Point](../system/11_RUNTIME_AND_ENTRYPOINT.md)
- [Tick Store](../data/07_TICK_STORE.md)
- [Snapshots and Continuity](../data/08_SNAPSHOTS_AND_CONTINUITY.md)
- [Model Inputs](../data/09_MODEL_INPUTS.md)
- [ML Runtime and Signal Selection](ml-runtime-and-signal-selection.md)
- [Roadmap](../planning.md)

---

*Last updated: 2026-11-22*
