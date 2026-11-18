# Components

Status: Current

> This document lists the components that exist today and the components the target system will add. Current components are implemented; planned components are not.

---

## Current Components

| Component | Location | Responsibility |
|-----------|----------|----------------|
| Page WebSocket intercept | `chrome-extension/inject.js` | Patch `window.WebSocket`, observe incoming messages, filter `candle-generated`, post raw payload to the isolated world |
| Local forwarder | `chrome-extension/content.js` | Validate page messages, connect to `ws://localhost:8765`, reconnect every 2 seconds, queue up to 500 messages |
| Extension manifest | `chrome-extension/manifest.json` | Declare MV3 content scripts and host permissions |
| WebSocket receiver | `receiver.py` | Accept frames, validate envelope, buffer raw messages per `active_id`, log OHLCV fields |
| Asset-name map | `asset_names.json` | Map `active_id` to a display name |
| Receiver tests | `test_receiver.py` | Test identity formatting, buffering, logging, and asset-map loading |
| Dependency manifest | `requirements.txt` | Declare the `websockets` dependency |

### Current Data Flow

```text
IQ Option page WebSocket
    -> inject.js
    -> content.js
    -> receiver.py
    -> in-memory deque (500 raw messages per active_id)
    -> console log
```

There is no persistence, aggregation, analytics, or execution component today.

---

## Planned Components

| Component | Responsibility | Depends on |
|-----------|----------------|------------|
| Ingestion service | Validate, timestamp, deduplicate, and count frames | Tick stream contract |
| Raw tick store | Append-only JSONL; later SQLite/Parquet | Ingestion |
| Session and gap tracker | Record connection sessions, reconnects, and missing periods | Ingestion |
| 1-minute candle builder | Aggregate ticks into clock-aligned OHLCV candles | Raw tick store |
| Asset metadata registry | Pip size, asset type, payout, expiry, session | Asset identities |
| TPO/Value Area engine | Build rolling profiles and POC/VAH/VAL | Raw ticks |
| Feature engine | Compute AMT, velocity, context, and regime features | TPO engine, candles, metadata |
| Label builder | Build binary-option outcomes and payout-aware EV | Candles, metadata |
| Dataset builder | Join features, labels, and metadata into versioned datasets | Feature engine, label builder |
| Model service | Train, calibrate, version, and serve models | Dataset builder |
| Signal service | Convert model output into Call/Put/No-Trade | Model service, risk |
| Risk manager | Stake sizing, daily loss limit, exposure, kill switch | Signal service |
| Execution adapter | Paper, demo, or live order placement | Risk manager |
| Trade journal | Persist orders, fills, outcomes, and reasons | Execution adapter |
| Monitoring and alerts | Health, latency, data quality, model drift | All services |

---

## Component Boundaries

The target architecture separates:

1. **Capture** — browser extension and receiver.
2. **Data** — raw ticks, candles, features, labels.
3. **Research** — backtesting and model training.
4. **Decision** — signals and risk.
5. **Execution** — paper/demo/live adapters.
6. **Operations** — monitoring, alerts, runbook.

A component may read from an upstream store, but it must not reach into another component's internals.

---

## Related Documentation

- [System overview](01_OVERVIEW.md)
- [Interfaces](04_INTERFACES.md)
- [Data pipeline](07_DATA_PIPELINE.md)
- [ML pipeline](08_ML_PIPELINE.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-18*
