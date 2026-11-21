# System Overview

Status: Current

> The repository is a local streaming and offline research system. A candle-close runtime can make paper decisions from a validated model artifact; it does not place broker orders. This document separates what runs today from what remains planned or unvalidated.

---

## Current State

| Layer | State |
|-------|-------|
| Tick capture | Live, Chrome MV3 extension plus `components/receiver.py` |
| Durable capture | Event and candle Parquet parts under `data/stream/`; legacy JSONL files remain valid build inputs |
| Tick store | Batch Parquet with sequence; exact duplicates preserved; stable timestamp/sequence ordering |
| Stream store | Sequence assignment, candle construction, late rejection, gap counters, persistence and state recovery |
| Snapshots | One candle-close decision point per eligible minute with contiguous completed candles |
| Features | Stateless `amt-v4` table with a 16-feature `core16-v2` model vector |
| Labels | `snapshot-horizon-v1` at 60/90/120/180s, ties and misses explicit |
| Models | Four calibrated LightGBM classifiers, purged walk-forward, held-out evaluation slice |
| Router | Payout-aware EV hurdle, single best horizon/direction, explicit no-trade |
| Model artifact | Timestamped `.joblib` plus compatibility manifest; legacy pickle remains for analysis/backtest |
| Backtest | Held-out replay through the router and a paper broker |
| Runtime | Candle-close inference, deterministic EV routing, paper decisions and journals |
| Execution | Paper only; demo and live are rejected |
| Runtime gates | One open paper trade, cooldown, configured daily loss stop; no complete risk manager or kill switch |

The capture path has been observed live. Everything downstream runs end to end on captured or synthetic data and is unit-tested. None of it has been validated as profitable, and no result to date shows an edge.

The classifiers supply probabilities to a deterministic EV router. The learned selector remains planning work. The runtime is not an order execution adapter, and neither tests nor synthetic metrics establish an edge.

---

## Current Architecture

```text
IQ Option Traderoom (browser)
        |
        v
chrome-extension/inject.js     MAIN world, filters name == "candle-generated"
        |  window.postMessage
        v
chrome-extension/content.js    isolated world, reconnect + queue
        |  ws://localhost:8765
        v
components/receiver.py         validate, stamp received_at, buffer, sink
        |  runner.py serve
        v
engine.stream.StreamStore      sequence, events, candles, state, hourly parts
        |                            \
        v                             v
engine.runtime.RuntimeEngine    paper decisions / JSONL journals
        | candle-close features
        v
core16-v2 -> .joblib -> EV router -> PaperBroker

Offline path:
CSV / JSONL / Parquet -> TickStore -> candle-close sampler
    -> core16-v2 / amt-v4 + labels -> dataset.parquet
    -> calibrated suite -> held-out backtest -> reports
```

`runner.py` is the only entry point. It wires the components; no component imports another component's internals.

---

## Verified

- The extension intercepts and forwards IQ Option WebSocket frames.
- The receiver validates the envelope and stamps `received_at`; `serve` sends accepted events to the stream store.
- Stream events preserve repeated prices and sequence order; late events are rejected and counted.
- CSV, JSONL, and Parquet file ingestion enforce the batch tick contract and stably sort by timestamp and sequence.
- Snapshot sampling rejects missing history, gaps, sparse bars, and missing entry ticks with specific counters.
- The 16 core features are computed from one snapshot with no lookahead.
- Training produces one calibrated model per horizon, or records why a horizon was skipped.
- The backtest replays only held-out probabilities and writes JSON and Markdown reports.
- Stream, runtime, artifact, replay, and offline behavior have focused unit tests.

## Not Verified

- Whether a captured frame is a raw tick, a partial-candle update, or a completed candle.
- Whether `msg.at` is a candle start, a price timestamp, or another server clock. It is stored but never promoted.
- Long-run stability across sessions, reconnects, weekends, and broker maintenance.
- Data completeness: gaps are detectable, but their cause is not.
- Whether the payload `volume` has any relationship to traded volume. It is not used.
- Whether AMT structure has predictive value on OTC synthetic pricing.
- Whether the model has any edge after payout. Current synthetic results are indistinguishable from noise.

---

## Scope Boundaries

| Layer | Status | Notes |
|-------|--------|-------|
| Browser tick capture | Current | Manually observed live |
| Durable tick capture | Current | Event/candle Parquet parts; legacy JSONL captures remain loadable |
| Tick store and replay | Current | Batch store plus streaming replay from hourly parts |
| Snapshot sampling | Current | Candle-close cadence, offline and runtime, one instrument |
| Feature engine | Current | Stateless `core16-v2` / `amt-v4` |
| Labels and payout math | Current | Ties and missing exits explicit |
| Model suite | Current | Four horizons, calibrated, walk-forward |
| Signal router | Current | Deterministic EV hurdle, tie-break, and reason codes; not ML-based |
| Runtime model loading | Current | Manifest-bearing `.joblib`, compatibility checks, fail-closed startup |
| Learned signal selection | Planning | Evaluate learned direction/horizon/no-trade selection against the current EV router |
| Paper backtest | Current | Held-out slice only |
| Runtime inference and paper decisions | Current | Candle-close feature loop and decision journal; paper only |
| Learned signal selection | Planning | Evaluate learned direction/horizon/no-trade selection against deterministic router |
| Demo/live execution | Not implemented | Mode names validated, then rejected |
| Risk manager and kill switch | Not implemented | Runtime has one-open-trade, cooldown, and daily loss gates, not a complete risk system |
| Multi-instrument | Not implemented | Filtered to one `active_id` |
| Monitoring and alerts | Not implemented | Console logs and reports only |

---

## Key Files

| Path | Purpose |
|------|---------|
| `runner.py` | Entry point: `serve`, `build`, `train`, `backtest`, `model-check`, `replay`, `diagnose`, `docs-check` |
| `components/receiver.py` | WebSocket capture, receipt stamping, tick sink |
| `engine/config.py` | TOML schema, validation, version constants, config hash |
| `engine/store.py` | Batch tick ingestion, sequence ordering, duplicate reporting, point-in-time lookup |
| `engine/stream/` | Streaming event/candle storage and state recovery |
| `engine/runtime.py` | Candle-close inference, deterministic gates, paper journals |
| `engine/sampler.py` | Snapshot gate, continuity, entry/exit timing |
| `engine/features.py` | `core16-v2` vector and `amt-v4` diagnostics |
| `engine/domain/` | Candles, profile, labels |
| `engine/models.py` | Calibration, walk-forward, model suite |
| `engine/router.py` | EV hurdle and proposal selection |
| `engine/execution.py` | Paper broker and trade journal |
| `engine/backtest.py` | Held-out replay |
| `engine/reports.py` | Calibration, importance, report bundle |
| `engine/build.py` | Pipeline assembly and artifact writing |
| `config/default.toml` | Active configuration |
| `chrome-extension/` | Browser capture extension |
| `tools/check_docs.py` | Documentation status, link, and index checker |
| `tools/install_hooks.py` | Installs the versioned git hooks |
| `.githooks/` | Pre-commit hook that runs the documentation checker |
| `tests/` | Unit tests for every component |

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [ML pipeline](08_ML_PIPELINE.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)
- [ML Runtime and Signal Selection](../planning/ml-runtime-and-signal-selection.md)

---

*Last updated: 2026-11-21*
