# System Overview

Status: Current

> The repository is a working offline prediction engine fed by a live tick capture, plus a paper-only backtest. It does not place orders. This document separates what runs today from what is still planned.

---

## Current State

| Layer | State |
|-------|-------|
| Tick capture | Live, Chrome MV3 extension plus `components/receiver.py` |
| Durable capture | JSONL per UTC day under `data/raw/` when `serve` runs |
| Tick store | Parquet, validated, ordered, deduplicated |
| Snapshots | Continuity-gated evaluation points at configurable minute offsets |
| Features | Stateless `amt-v3` table with a 16-feature `core16-v1` model vector |
| Labels | `snapshot-horizon-v1` at 60/90/120/180s, ties and misses explicit |
| Models | Four calibrated LightGBM classifiers, purged walk-forward, held-out evaluation slice |
| Router | Payout-aware EV hurdle, single best horizon/direction, explicit no-trade |
| Backtest | Held-out replay through the router and a paper broker |
| Execution | Paper only; demo and live are rejected |
| Risk | Fixed stake and one open trade; no daily limit, no kill switch |

The capture path has been observed live. Everything downstream runs end to end on captured or synthetic data and is unit-tested. None of it has been validated as profitable, and no result to date shows an edge.

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
        |  JsonlTickSink
        v
data/raw/ticks-YYYY-MM-DD.jsonl
        |  runner.py build
        v
engine.store.TickStore         ordered, deduplicated, point-in-time
        |
        v
engine.sampler                 continuity gate, delayed entry, exits
        |
        v
engine.features                core16-v1 + amt-v3 diagnostics
        |
        v
data/dataset.parquet           features joined to labels
        |
        v
engine.models                  four calibrated horizon classifiers
        |
        v
engine.router                  EV hurdle, one proposal or no-trade
        |
        v
engine.backtest + execution    paper trades, held-out replay
        |
        v
reports/backtest.{json,md}
```

`runner.py` is the only entry point. It wires the components; no component imports another component's internals.

---

## Verified

- The extension intercepts and forwards IQ Option WebSocket frames.
- The receiver validates the envelope, stamps `received_at`, and can persist every accepted tick as JSONL.
- CSV, JSONL, and Parquet ingestion enforce the tick contract; exact duplicates are dropped; ordering is restored.
- Snapshot sampling rejects missing history, gaps, sparse bars, and missing entry ticks with specific counters.
- The 16 core features are computed from one snapshot with no lookahead.
- Training produces one calibrated model per horizon, or records why a horizon was skipped.
- The backtest replays only held-out probabilities, enforces the open-trade limit, and writes JSON and Markdown reports.
- 111 unit tests pass across config, store, timeframes, profile, sampler, features, labels, models, router, execution, reports, backtest, and receiver.

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
| Durable tick capture | Current | JSONL, daily rotation, append-only |
| Tick store and replay | Current | Parquet, deterministic rebuild |
| Snapshot sampling | Current | Batch only, one instrument |
| Feature engine | Current | Stateless, snapshot-based |
| Labels and payout math | Current | Ties and missing exits explicit |
| Model suite | Current | Four horizons, calibrated, walk-forward |
| Signal router | Current | EV hurdle, reason codes |
| Paper backtest | Current | Held-out slice only |
| Live features and signals | Not implemented | `serve` captures only |
| Demo/live execution | Not implemented | Mode names validated, then rejected |
| Risk manager and kill switch | Not implemented | Fixed stake only |
| Multi-instrument | Not implemented | Filtered to one `active_id` |
| Monitoring and alerts | Not implemented | Console logs and reports only |

---

## Key Files

| Path | Purpose |
|------|---------|
| `runner.py` | Entry point: `serve`, `build`, `train`, `backtest`, `diagnose` |
| `components/receiver.py` | WebSocket capture, receipt stamping, tick sink |
| `engine/config.py` | TOML schema, validation, version constants, config hash |
| `engine/store.py` | Tick ingestion, ordering, dedupe, point-in-time lookup |
| `engine/sampler.py` | Snapshot gate, continuity, entry/exit timing |
| `engine/features.py` | `core16-v1` vector and `amt-v3` diagnostics |
| `engine/domain/` | Candles, profile, labels |
| `engine/models.py` | Calibration, walk-forward, model suite |
| `engine/router.py` | EV hurdle and proposal selection |
| `engine/execution.py` | Paper broker and trade journal |
| `engine/backtest.py` | Held-out replay |
| `engine/reports.py` | Calibration, importance, report bundle |
| `engine/build.py` | Pipeline assembly and artifact writing |
| `config/default.toml` | Active configuration |
| `chrome-extension/` | Browser capture extension |
| `tests/` | Unit tests for every component |

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [ML pipeline](08_ML_PIPELINE.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-19*
