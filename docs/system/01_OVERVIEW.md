# System Overview — Tick Capture and Target Architecture

Status: Current

> This document describes what exists today, what has been manually verified, and the target architecture. It separates the current proof of concept from planned trading functionality.

---

## Current State

The repository currently implements a **live tick-capture proof of concept**:

1. A Chrome Manifest V3 extension runs on `*.iqoption.com`.
2. `inject.js` patches the page's `WebSocket` constructor and observes incoming messages.
3. Messages whose outer payload has `name === "candle-generated"` are posted to the extension's isolated world.
4. `content.js` forwards the raw JSON string to `ws://localhost:8765`.
5. `receiver.py` validates the frame, stores it in an in-memory buffer per `active_id`, and logs the OHLCV fields.

The receiver console was manually observed to show live, correct prices from the platform.

### Current Architecture

```text
IQ Option Traderoom (browser)
        │
        │ page WebSocket messages
        ▼
chrome-extension/inject.js  (MAIN world)
        │  window.postMessage({ source: "IQ_TICK_BRIDGE", payload })
        ▼
chrome-extension/content.js  (isolated world)
        │  WebSocket ws://localhost:8765
        │  reconnect every 2 s; queue up to 500 messages
        ▼
receiver.py
        │  JSON validation
        │  require name == "candle-generated"
        │  require msg.active_id
        │  deque(maxlen=500) per active_id
        ▼
console log
```

### Verified

- The extension can intercept and forward IQ Option WebSocket messages.
- The local receiver accepts and logs the forwarded frames.
- `active_id`, OHLCV fields, and the `at` field are visible in the logs.
- Asset-name mapping works for display labels.
- Malformed JSON and frames without `active_id` are ignored.
- The receiver binds only to localhost.

### Not Verified

- Whether the intercepted frame represents a raw tick, a partial-candle update, or a completed candle.
- The exact meaning of `at` and whether it is a candle start, a price timestamp, or another server timestamp. It is currently ignored.
- Long-running stability under a full market session.
- Behaviour across reconnects, broker disconnects, and weekends.
- Data completeness and ordering guarantees.
- Whether the payload `volume` field has any relationship to traded volume.
- Whether the stream is sufficient for the planned AMT/TPO features at scale.

---

## Target Architecture

```text
Tick stream
    │
    ▼
[Ingestion and validation]
    │  schema checks, dedupe, ordering, gaps, receipt timestamps
    ▼
[Raw tick store]
    │  JSONL first; SQLite/Parquet later
    ▼
[1-minute candle builder]
    │  whole-minute OHLCV; volume = tick count
    ▼
[Feature engine]
    │  macro 7 / fast 3 / forming layers, TPO value area,
    │  normalized distance, excess, tick rate, price speed, range
    ▼
[Label builder]
    │  tick-horizon direction labels at 60/90/120/180s; payout-aware EV
    ▼
[Model and signal layer]
    │  two-stage regime architecture; calibration; no-trade output
    ▼
[Risk and execution]
    │  stake sizing, daily loss limit, kill switch, demo first
    ▼
[Trade journal and monitoring]
```

The target architecture is deliberately staged. The current PoC is only the first box: ingestion.

---

## Scope Boundaries

| Layer | Status | Notes |
|-------|--------|-------|
| Browser tick capture | Current | Proven manually |
| Receiver validation and logging | Current | Basic checks only |
| Raw tick persistence | Planned | No durable store yet |
| 1-minute candle aggregation | Planned | Candles are not generated today |
| TPO/Value Area features | Planned | Requires tick history |
| Labels and payout math | Planned | Depends on instrument metadata |
| ML pipeline | Planned | Approach A is the primary design |
| Paper/demo execution | Planned | Must follow validation gate |
| Live execution | Not approved | Requires separate safety review |
| Monitoring and runbooks | Partial | Operational runbook exists for the PoC |

---

## Key Files

| File | Purpose |
|------|---------|
| `chrome-extension/inject.js` | Patches `window.WebSocket` and filters incoming messages |
| `chrome-extension/content.js` | Forwards messages to the local receiver with reconnect and queueing |
| `chrome-extension/manifest.json` | Extension manifest and host permissions |
| `receiver.py` | Local WebSocket receiver and in-memory buffer |
| `test_receiver.py` | Unit tests for receiver formatting, buffering, and asset mapping |
| `asset_names.json` | Display-name mapping for `active_id` values |
| `requirements.txt` | Python dependency declaration |

---

## Related Documentation

- [Tick stream contract](../data/01_TICK_STREAM.md)
- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [Limitations and improvement backlog](10_LIMITATIONS_AND_BACKLOG.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [ML pipeline](08_ML_PIPELINE.md)
- [AMT concepts](../concepts/05_AUCTION_MARKET_THEORY.md)

---

*Last updated: 2026-11-18*
