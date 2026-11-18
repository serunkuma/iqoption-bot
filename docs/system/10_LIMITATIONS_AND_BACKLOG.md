# Limitations and Improvement Backlog

Status: Current

> This document records what the proof of concept does not do yet and the prioritised work required to turn it into a trustworthy ingestion and trading system. It is intentionally blunt.

---

## Current Limitations

| Area | Limitation | Impact |
|------|------------|--------|
| Capture scope | The extension forwards only frames whose outer `name` is `"candle-generated"` | Other price-bearing message types may be missed; feed changes can silently break capture |
| Frame semantics | It is not verified whether a frame is a tick, a partial-candle update, or a completed candle | The tick/candle model is provisional |
| Timestamps | `msg.at` semantics are unknown; receipt time is not recorded | Ordering, gaps, and causal features cannot be trusted yet |
| Buffer | 500 raw messages per `active_id`, in memory only | Restart loses data; history depth may be seconds, not minutes |
| Persistence | No raw tick store, no candle store, no replay | AMT features and backtests are not reproducible |
| Aggregation | No 1-minute candle builder | Labels, charting, and context features are blocked |
| Data quality | No duplicate, gap, out-of-order, stale, or rate checks | Tick density can be inflated or biased |
| Configuration | Host, port, buffer size, and paths are hard-coded | Multi-asset and deployment changes require code edits |
| Logging | Plain text logs; no metrics or structured fields | Failures are hard to aggregate or alert on |
| Tests | Three unit tests; no integration or load tests | Reconnect and malformed-frame behaviour is under-tested |
| Packaging | Flat files; `requirements.txt` only | No installable package or reproducible dev workflow |
| Security | Localhost binding only; no authentication | Acceptable for local PoC; must be revisited before remote deployment |
| Execution | No order placement, risk controls, or kill switch | Live trading is not possible and must not be attempted |
| Analytics | No AMT, signals, backtesting, or ML | The core trading hypothesis is unvalidated |
| Documentation | README overstates the buffer as "candle history" | Misleads future work and agents |

---

## Backlog

### P0 — Make the PoC trustworthy

| ID | Improvement | Rationale | Acceptance Criteria |
|----|-------------|-----------|---------------------|
| P0-1 | Define and verify the tick-event contract | AMT depends on knowing exactly what one message represents | Documented schema; sample traffic inspected; `at` semantics recorded |
| P0-2 | Record `received_at` for every accepted frame | Establishes local ordering independent of broker timestamps | Every stored tick has `received_at` in UTC |
| P0-3 | Persist raw frames as JSONL | Restart-safe capture and replay | Append-only file; rotation policy; replay script reads it |
| P0-4 | Add data-quality counters | Tick density is only valid on a clean stream | Counts for received, accepted, rejected, malformed, duplicate, stale, late |
| P0-5 | Add gap and reconnect tracking | Missing data must be visible in features and backtests | Session and gap records; candles can be flagged |
| P0-6 | Replace hard-coded constants with configuration | Enables multi-asset and deployment changes without code edits | Config file plus environment overrides; validation errors are clear |
| P0-7 | Fix documentation terminology | Prevents future work from assuming candles already exist | Docs consistently say "raw tick buffer" and "planned 1-minute candles" |
| P0-8 | Add structured logging | Makes failures diagnosable and alertable | Key-value or JSON logs with session, active_id, frame type, outcome |
| P0-9 | Expand tests | Reconnect, malformed frames, duplicates, buffer eviction, and asset-map validation need coverage | Tests pass locally and in CI |
| P0-10 | Document extension queue-loss behaviour | The extension drops the oldest message when its 500-message queue is full | Limit documented; metric or warning added |

### P1 — Analytics foundation

| ID | Improvement | Rationale | Acceptance Criteria |
|----|-------------|-----------|---------------------|
| P1-1 | Build 1-minute OHLCV aggregation | Needed for labels, charting, and context | Candle builder passes OHLC and boundary tests |
| P1-2 | Add instrument metadata | Pip size and payout drive bins and expected value | `assets.json` with validation |
| P1-3 | Add durable storage | In-memory deque is insufficient for research | SQLite for candles/trades; Parquet for bulk research |
| P1-4 | Build TPO/Value Area engine | Core AMT representation | POC/VAH/VAL match worked examples; causal windows enforced |
| P1-5 | Build AMT feature engine | Converts AMT theory into model inputs | Feature vector documented and reproducible |
| P1-6 | Build a rule-based AMT baseline | Establishes a benchmark before ML | Baseline signals and backtest results recorded |
| P1-7 | Build a backtesting harness | Measures edge after payout | Walk-forward, payout-aware metrics, no leakage |
| P1-8 | Add weekday/weekend regime analysis | OTC pricing may change on weekends | Separate metrics and a documented filter decision |

### P2 — ML, execution, and operations

| ID | Improvement | Rationale | Acceptance Criteria |
|----|-------------|-----------|---------------------|
| P2-1 | Build labels and payout-aware EV | Accuracy alone is not sufficient | Labels, breakeven win rate, and EV documented and tested |
| P2-2 | Build the two-stage ML pipeline | Approach A is the primary design | Regime gate plus conditional models; reproducible training |
| P2-3 | Add calibration and drift monitoring | Probabilities must be trustworthy over time | Reliability curve, Brier score, drift metrics |
| P2-4 | Build paper/demo execution | Safe path before real money | Order lifecycle, idempotency, journal |
| P2-5 | Add risk controls and kill switch | Limits losses and stops runaway behaviour | Daily loss limit, max stake, consecutive-loss limit, manual kill |
| P2-6 | Add monitoring and alerts | Unattended operation needs visibility | Health check, metrics, alert rules |
| P2-7 | Complete the operational runbook | Operators need repeatable procedures | Tested start/stop/troubleshoot procedures |
| P2-8 | Review legal and platform terms | Real-money automation carries account and jurisdiction risk | Documented risk acceptance and constraints |

---

## Phase Mapping

| Phase | Backlog focus |
|-------|---------------|
| Phase 1 — Tick capture hardening | P0-1 through P0-10 |
| Phase 2 — Candles and AMT features | P1-1 through P1-8 |
| Phase 3 — ML pipeline and validation | P2-1 through P2-3 |
| Phase 4 — Execution and operations | P2-4 through P2-8 |

---

## Related Documentation

- [System overview](01_OVERVIEW.md)
- [Tick stream contract](../data/01_TICK_STREAM.md)
- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [Planning](../planning.md)
- [Phase 1: Tick capture hardening](../planning/phase-1-tick-capture-hardening.md)

---

*Last updated: 2026-11-18*
