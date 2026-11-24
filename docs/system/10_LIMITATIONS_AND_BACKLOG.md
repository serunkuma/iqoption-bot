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
| Repeated events | Exact duplicate `(timestamp, price)` events are preserved | Repeated frames can inflate tick density; impact is unvalidated |
| Multi-instrument | The sampler filters to one `active_id` | Cross-instrument work is blocked |

### Pipeline

| Area | Limitation | Impact |
|------|------------|--------|
| Live feature path | `serve` computes candle-close features only with a validated artifact | No sustained shadow/paper parity evidence exists |
| Incremental build | `build` reads a whole file and rewrites all artefacts | Long captures mean long rebuilds |
| Snapshot storage | `store.snapshots_path` is reserved but unused | Snapshot metadata is rebuilt, not persisted |
| Candle storage | Stream candles are persisted in immutable hourly parts; offline build also groups candles in memory | No compaction or retention policy; build can now read the stream event directory directly |
| Performance | Features are computed per snapshot in Python loops | Slow on multi-day captures |

### Models

| Area | Limitation | Impact |
|------|------------|--------|
| Evidence | No real capture has shown an edge | The core hypothesis is unvalidated |
| Sample size | Held-out evaluation uses the later 30% of walk-forward OOS rows | Metrics are noisy |
| Effective sample | Overlap weights are computed but not reported | Row counts overstate information |
| Regime | No balance/imbalance gate | The primary AMT hypothesis is only partly tested |
| Calibration | Small calibration slices often reject Platt and ship identity | Probabilities may be uncalibrated |
| Drift | No monitoring | A stale model would go unnoticed |
| Selection | One configuration per run; no seed or fold sweep | Fragility is unmeasured |
| Time features | Excluded from the model | Session effects are untested |
| Signal selection | Current router is deterministic EV selection; no learned selector | The target ML signal decision layer has not been evaluated |

### Execution and operations

| Area | Limitation | Impact |
|------|------------|--------|
| Execution | Paper only; `demo` and `live` raise | No real order path |
| Risk | Fixed stake, one open trade, cooldown, and a daily realized-loss stop | No complete risk manager, consecutive-loss policy, sizing policy, or kill switch |
| Journals | Runtime writes decision and trade JSONL journals and restores paper state from them | Retention and external audit workflows are unvalidated |
| Monitoring | Console logs and offline reports | No metrics or alerts |
| Config | Receiver host/port remain module defaults with CLI overrides; receiver history buffer remains a constant | Some capture settings still require code changes |
| Packaging | `requirements.txt` only; no installable package | Reproducibility depends on the venv |
| Documentation freshness | `docs-check` validates labels, links, and index coverage only; the pre-commit hook runs it, but it can be bypassed | Prose can still describe behaviour that changed |

---

## Backlog

### P0 — Trust the data

| ID | Improvement | Acceptance criteria |
|----|-------------|---------------------|
| P0-1 | Verify frame semantics against the platform | Documented whether a frame is a tick or a partial candle, with evidence |
| P0-2 | Measure real tick cadence per instrument | Per-minute tick distribution recorded; `min_ticks_per_bar` set from data |
| P0-3 | Record sessions, reconnects, and gaps | Session table or flags; gaps visible without inference |
| P0-4 | Study repeated/near-duplicate feed events | Real-capture evidence and a documented policy |
| P0-5 | Move receiver constants into configuration | `[server]` section; validation errors are clear |
| P0-6 | Add structured logging | Key-value or JSON logs with `active_id`, frame outcome, counters |
| P0-7 | Persist snapshots | `snapshots.parquet` written and reloadable |
| P0-8 | Run `docs-check` automatically | **Done 2026-11-20** — `.githooks/pre-commit` runs `tools/check_docs.py`; `tools/install_hooks.py` installs it |

### P1 — Make research efficient

| ID | Improvement | Acceptance criteria |
|----|-------------|---------------------|
| P1-1 | Incremental tick store append | New captures merge without a full rebuild |
| P1-2 | Vectorise the feature engine | Documented speed-up on a multi-day capture |
| P1-3 | Report effective sample size | Overlap-adjusted count in reports |
| P1-4 | Validate and operationalize candle-part persistence | Recovery/replay evidence, retention, and compaction policy |
| P1-5 | Add a rule-based AMT baseline | Baseline signals and EV recorded for comparison |
| P1-6 | Add seed and offset sensitivity sweeps | Result variance reported |
| P1-7 | Define journal retention and audit/reconciliation workflow | Reproducible decision-to-outcome audit |
| P1-8 | Report per-regime metrics | Balance/imbalance split using diagnostics |

### P2 — Model and execution

| ID | Improvement | Acceptance criteria |
|----|-------------|---------------------|
| P2-1 | Implement the two-stage regime model | Regime rule validated; held-out EV improves |
| P2-2 | Add drift monitoring | Rolling Brier/ECE with alert threshold |
| P2-3 | Complete the risk manager | Beyond current paper gates: exposure limits, loss streak policy, and documented limits |
| P2-4 | Add a kill switch | Manual and automatic stop, tested |
| P2-5 | Implement a demo adapter | Order lifecycle, idempotency, reconciliation |
| P2-6 | Complete the operational runbook | Tested start/stop/troubleshoot for every command |
| P2-7 | Review legal and platform terms | Documented constraints before any live use |
| P2-8 | Evaluate a learned direction/horizon/no-trade selector | Predefined target; compared with current EV-router baseline on untouched chronological data and independent captures |
| P2-9 | Validate runtime artifact and replay behavior on independent captures | Sustained evidence, operational activation/rollback, and runtime/offline parity |

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
- [ML Runtime and Signal Selection](../planning/ml-runtime-and-signal-selection.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-21*
