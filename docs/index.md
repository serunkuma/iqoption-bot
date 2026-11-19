# Documentation Index

Status: Current

> File finder for the project. Every link below resolves to a file that exists.

---

## Concepts — Why We Built It This Way

- [Concepts guide](concepts/README.md) — What belongs in this category
- [Auction Market Theory](concepts/05_AUCTION_MARKET_THEORY.md) — Balance/imbalance, acceptance/rejection, tick-density proxy, OTC caveat

Planned: domain primitives, market-data bridge rationale, trading philosophy, open questions.

**Use when:** You need the reasoning behind the design.

---

## Data — What Flows Through the System

- [Data guide](data/README.md) — What belongs in this category
- [Tick Stream Contract](data/01_TICK_STREAM.md) — Tick envelope, fields, buffering, `received_at`, JSONL capture
- [Asset Identities](data/02_ASSET_IDENTITIES.md) — `active_id`, `asset_names.json`, configured metadata
- [1-Minute Candle Aggregation](data/03_CANDLE_AGGREGATION.md) — Whole-minute bucketing and forming bars
- [TPO and Value Area](data/04_TPO_VALUE_AREA.md) — POC/VAH/VAL rules and worked example
- [AMT Feature Specification](data/05_AMT_FEATURE_SPEC.md) — Feature families, formulas, causality, versioning
- [Labels, Payouts, and Expected Value](data/06_LABELS_PAYOUTS_AND_EV.md) — Snapshot labels, breakeven, EV, no-trade
- [Tick Store](data/07_TICK_STORE.md) — Schema, ingestion rules, dedupe, point-in-time lookup
- [Snapshots and Continuity](data/08_SNAPSHOTS_AND_CONTINUITY.md) — Continuity gate, delayed entry, exits
- [Model Inputs](data/09_MODEL_INPUTS.md) — `core16-v1` vector and `amt-v3` diagnostics

**Use when:** You need exact data contracts, formulas, or schemas.

---

## System — How We Built It

- [System guide](system/README.md) — What belongs in this category
- [System Overview](system/01_OVERVIEW.md) — Current architecture, verified vs unverified, scope
- [Components](system/02_COMPONENTS.md) — Component map, boundaries, tests
- [Configuration](system/03_CONFIGURATION.md) — Full TOML schema, defaults, validation
- [Interfaces](system/04_INTERFACES.md) — External protocols and internal contracts
- [Testing Strategy](system/05_TESTING.md) — Test coverage, helpers, known gaps
- [Security and Safety](system/06_SECURITY.md) — Threats, secrets, live-trading safety, legal notes
- [Data Pipeline](system/07_DATA_PIPELINE.md) — Capture to store to dataset
- [ML Pipeline](system/08_ML_PIPELINE.md) — Four-horizon calibrated classifiers
- [Model Validation](system/09_MODEL_VALIDATION.md) — Walk-forward, calibration, go/no-go gate
- [Limitations and Backlog](system/10_LIMITATIONS_AND_BACKLOG.md) — Gaps and prioritised improvements
- [Runtime and Entry Point](system/11_RUNTIME_AND_ENTRYPOINT.md) — `runner.py` commands and wiring
- [Model Suite](system/12_MODEL_SUITE.md) — Training, calibration, evaluation table, persistence
- [Signal Router](system/13_SIGNAL_ROUTER.md) — EV hurdle, candidate selection, reason codes
- [Execution and Resolution](system/14_EXECUTION_AND_RESOLUTION.md) — Paper broker, resolution, journal
- [Reports and Diagnostics](system/15_REPORTS_AND_DIAGNOSTICS.md) — Command output and report fields

**Use when:** You need to implement, operate, or debug the system.

---

## Planning — How We’re Building It

- [Roadmap](planning.md) — Vision, phases, milestones, risks, decision points
- [Phase 1: Tick Capture Hardening](planning/phase-1-tick-capture-hardening.md)
- [Phase 2: Analytical Layer](planning/phase-2-candles-and-amt-features.md)
- [Phase 3: ML Pipeline and Validation](planning/phase-3-ml-pipeline-and-validation.md)
- [Phase 4: Execution and Operations](planning/phase-4-execution-and-operations.md)

**Use when:** You need to know what comes next or what “done” means.

---

## Research and Historical

- [Research guide](research/README.md) — Convention for historical notes
- [AMT on OTC — Reality Check](research/AMT_ON_OTC.md) — Why AMT on OTC is a hypothesis and what to test
- [PoC Validation — 2026-11-18](research/POC_VALIDATION_2026-11-18.md) — What the first live capture proved and did not prove
- [AMT Reference Implementation Review — 2026-11-18](research/AMT_REFERENCE_IMPLEMENTATION_2026-11-18.md) — Review of the external reference implementation

**Use when:** You are investigating why a decision was made or what failed.

---

## Operations and Project Entry Points

- [README](../README.md) — Project overview and quick start
- [AGENTS.md](../AGENTS.md) — Single source of truth for agents and developers
- [RUNBOOK.md](../RUNBOOK.md) — Operating the capture, build, train, and backtest commands

**Use when:** You are setting up, running, or operating the system.

---

## Status Legend

- **Status: Current** — Authoritative and usable now.
- **Status: Planning** — Designed or scheduled, not implemented.
- **Status: Historical** — Kept for context; do not follow as current.

If a doc lacks a status label, treat it as incomplete.

---

## Quick Find

| Topic | Doc |
|-------|-----|
| What exists today | [system/01_OVERVIEW.md](system/01_OVERVIEW.md) |
| How to run each command | [system/11_RUNTIME_AND_ENTRYPOINT.md](system/11_RUNTIME_AND_ENTRYPOINT.md) |
| Every config key | [system/03_CONFIGURATION.md](system/03_CONFIGURATION.md) |
| What one tick means | [data/01_TICK_STREAM.md](data/01_TICK_STREAM.md) |
| Tick table and dedupe | [data/07_TICK_STORE.md](data/07_TICK_STORE.md) |
| When a snapshot is valid | [data/08_SNAPSHOTS_AND_CONTINUITY.md](data/08_SNAPSHOTS_AND_CONTINUITY.md) |
| The 16 model inputs | [data/09_MODEL_INPUTS.md](data/09_MODEL_INPUTS.md) |
| How POC/VAH/VAL are computed | [data/04_TPO_VALUE_AREA.md](data/04_TPO_VALUE_AREA.md) |
| Payout breakeven and EV | [data/06_LABELS_PAYOUTS_AND_EV.md](data/06_LABELS_PAYOUTS_AND_EV.md) |
| How models are trained | [system/12_MODEL_SUITE.md](system/12_MODEL_SUITE.md) |
| How a trade is chosen | [system/13_SIGNAL_ROUTER.md](system/13_SIGNAL_ROUTER.md) |
| How a trade resolves | [system/14_EXECUTION_AND_RESOLUTION.md](system/14_EXECUTION_AND_RESOLUTION.md) |
| What the reports contain | [system/15_REPORTS_AND_DIAGNOSTICS.md](system/15_REPORTS_AND_DIAGNOSTICS.md) |
| Validation gate | [system/09_MODEL_VALIDATION.md](system/09_MODEL_VALIDATION.md) |
| What to improve first | [system/10_LIMITATIONS_AND_BACKLOG.md](system/10_LIMITATIONS_AND_BACKLOG.md) |
| Roadmap | [planning.md](planning.md) |
| Operating the system | [../RUNBOOK.md](../RUNBOOK.md) |

---

*Last updated: 2026-11-19*
