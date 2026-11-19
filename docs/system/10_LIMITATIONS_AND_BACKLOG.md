# Limitations and Improvement Backlog

Status: Current

> What the engine does not do, what it does not do well, and what to fix first. This document is deliberately blunt.

---

## Current Limitations

### Capture and data

| Area | Limitation | Impact |
|------|------------|--------|
| Frame semantics | It is not verified whether a frame is a raw tick, a partial candle, or a completed candle | Tick density may not mean what the model assumes |
| Timestamp | `msg.at` is unknown and unused; only local `received_at` is trusted | Network and browser delay are inside every timestamp |
| Completeness | Gaps are detectable as missing minutes but their cause is unknown | No session or reconnect record exists |
| Volume | Payload `volume` is unverified and unused | TPO relies on tick count |
| Cadence | Real tick cadence on the target instrument is unmeasured | `min_ticks_per_bar = 1` may be far too permissive |
| Near-duplicates | Only exact `(timestamp, price)` duplicates are dropped | Repeated prices at different times inflate density |
| Multi-instrument | The sampler filters to one `active_id` | Cross-instrument work is blocked |

### Pipeline

| Area | Limitation | Impact |
|------|------------|--------|
| Live features | `serve` captures only; no live snapshots or vectors | No live signal path exists |
| Incremental build | `build` reads a whole file and rewrites all artefacts | Long captures mean long rebuilds |
| Snapshot storage | `store.snapshots_path` is reserved but unused | Snapshots are rebuilt, not persisted |
| Candle storage | Minute buckets exist only inside a build | No candle store or candle replay |
| Performance | Features are computed per snapshot in Python loops | Slow on multi-day captures |
| Single run | No incremental append to the tick store | Two captures mean two files, not one store |

### Models

| Area | Limitation | Impact |
|------|------------|--------|
| Evidence | No real capture has shown an edge | The core hypothesis is unvalidated |
| Sample size | Held-out evaluation is roughly the last quarter of the capture | Metrics are noisy |
| Effective sample | Overlap weights are computed but not reported | Row counts overstate information |
| Regime | No balance/imbalance gate | The primary AMT hypothesis is only partly tested |
| Calibration | Small calibration slices often reject Platt and ship identity | Probabilities may be uncalibrated |
| Drift | No monitoring | A stale model would go unnoticed |
| Selection | One configuration per run; no seed or fold sweep | Fragility is unmeasured |
| Time features | Excluded from the model | Session effects are untested |

### Execution and operations

| Area | Limitation | Impact |
|------|------------|--------|
| Execution | Paper only; `demo` and `live` raise | No real order path |
| Risk | Fixed stake and one open trade only | No daily loss limit, consecutive-loss limit, or sizing |
| Kill switch | Not implemented | Unattended operation is unsafe |
| Journal | `TradeJournal` exists but is not wired into the backtest | No per-trade audit file yet |
| Monitoring | Console logs and offline reports | No metrics or alerts |
| Config | Receiver host/port/buffer live in code | Deployment changes need edits |
| Packaging | `requirements.txt` only; no installable package | Reproducibility depends on the venv |

---

## Backlog

### P0 — Trust the data

| ID | Improvement | Acceptance criteria |
|----|-------------|---------------------|
| P0-1 | Verify frame semantics against the platform | Documented whether a frame is a tick or a partial candle, with evidence |
| P0-2 | Measure real tick cadence per instrument | Per-minute tick distribution recorded; `min_ticks_per_bar` set from data |
| P0-3 | Record sessions, reconnects, and gaps | Session table or flags; gaps visible without inference |
| P0-4 | Add near-duplicate detection | Rule documented and counted |
| P0-5 | Move receiver constants into configuration | `[server]` section; validation errors are clear |
| P0-6 | Add structured logging | Key-value or JSON logs with `active_id`, frame outcome, counters |
| P0-7 | Persist snapshots | `snapshots.parquet` written and reloadable |

### P1 — Make research efficient

| ID | Improvement | Acceptance criteria |
|----|-------------|---------------------|
| P1-1 | Incremental tick store append | New captures merge without a full rebuild |
| P1-2 | Vectorise the feature engine | Documented speed-up on a multi-day capture |
| P1-3 | Report effective sample size | Overlap-adjusted count in reports |
| P1-4 | Persist a candle table | Candles written and used for charting/reporting |
| P1-5 | Add a rule-based AMT baseline | Baseline signals and EV recorded for comparison |
| P1-6 | Add seed and offset sensitivity sweeps | Result variance reported |
| P1-7 | Wire the trade journal into the backtest | One JSONL line per trade |
| P1-8 | Report per-regime metrics | Balance/imbalance split using diagnostics |

### P2 — Model and execution

| ID | Improvement | Acceptance criteria |
|----|-------------|---------------------|
| P2-1 | Implement the two-stage regime model | Regime rule validated; held-out EV improves |
| P2-2 | Add drift monitoring | Rolling Brier/ECE with alert threshold |
| P2-3 | Add a risk manager | Daily loss limit, consecutive-loss limit, stake sizing, tested |
| P2-4 | Add a kill switch | Manual and automatic stop, tested |
| P2-5 | Implement a demo adapter | Order lifecycle, idempotency, reconciliation |
| P2-6 | Complete the operational runbook | Tested start/stop/troubleshoot for every command |
| P2-7 | Review legal and platform terms | Documented constraints before any live use |

---

## Known Technical Traps

| Trap | Detail |
|------|--------|
| LightGBM import order | Importing pandas before LightGBM can crash on Windows inside `LGBM_DatasetSetField` |
| Bin edge drift | `bin_index` adds a scaled epsilon; removing it moves prices that sit exactly on a bin edge |
| In-sample replay | The backtest must never call `predict_vector`; only `evaluate_snapshot` |
| Tie handling | A tie is `void` in execution and non-directional in training; never map it to put |
| Missing exit | Leaves the trade open; never guess a price |
| Duplicate `tick_id` | Reassigned on every store construction; never trust an input column |

---

## Related Documentation

- [System overview](01_OVERVIEW.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Planning](../planning.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-19*
