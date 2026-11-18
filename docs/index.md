# Documentation Index

Status: Current

> File finder for the project. Every link below resolves to a file that exists. Planned docs that are not written yet are listed as plain text, not links.

---

## Concepts — Why We Built It This Way

- [Concepts guide](concepts/README.md) — What belongs in this category
- [Auction Market Theory](concepts/05_AUCTION_MARKET_THEORY.md) — Balance/imbalance, acceptance/rejection, tick-density proxy, OTC caveat

Planned: domain primitives, market-data bridge rationale, trading philosophy, open questions.

**Use when:** You need the reasoning behind the design.

---

## Data — What Flows Through the System

- [Data guide](data/README.md) — What belongs in this category
- [Tick Stream Contract](data/01_TICK_STREAM.md) — Current tick envelope, fields, buffering, timestamp uncertainty
- [Asset Identities](data/02_ASSET_IDENTITIES.md) — `active_id`, `asset_names.json`, planned asset metadata
- [1-Minute Candle Aggregation](data/03_CANDLE_AGGREGATION.md) — Planned tick-to-OHLCV aggregation
- [TPO and Value Area](data/04_TPO_VALUE_AREA.md) — Rolling POC/VAH/VAL specification
- [AMT Feature Specification](data/05_AMT_FEATURE_SPEC.md) — Feature formulas, causality, versioning
- [Labels, Payouts, and Expected Value](data/06_LABELS_PAYOUTS_AND_EV.md) — Binary labels, breakeven, EV, no-trade

Planned: signal model, order/trade model, storage schema, validation rules.

**Use when:** You need exact data contracts, formulas, or schemas.

---

## System — How We Built It

- [System guide](system/README.md) — What belongs in this category
- [System Overview](system/01_OVERVIEW.md) — Current PoC architecture, verified vs unverified, target architecture
- [Components](system/02_COMPONENTS.md) — Current and planned components
- [Configuration](system/03_CONFIGURATION.md) — Current constants and planned config
- [Interfaces](system/04_INTERFACES.md) — Extension-to-receiver protocol and planned internal contracts
- [Testing Strategy](system/05_TESTING.md) — Current tests, gaps, planned layers
- [Security and Safety](system/06_SECURITY.md) — Threats, secrets, live-trading safety, legal notes
- [Data Pipeline](system/07_DATA_PIPELINE.md) — Tick to candle to feature to dataset
- [ML Pipeline](system/08_ML_PIPELINE.md) — Two-stage regime architecture
- [Model Validation](system/09_MODEL_VALIDATION.md) — Walk-forward, calibration, go/no-go gate
- [Limitations and Backlog](system/10_LIMITATIONS_AND_BACKLOG.md) — PoC gaps and prioritised improvements

**Use when:** You need to implement, operate, or debug the system.

---

## Planning — How We’re Building It

- [Roadmap](planning.md) — Vision, phases, milestones, risks
- [Phase 1: Tick Capture Hardening](planning/phase-1-tick-capture-hardening.md)
- [Phase 2: Candles and AMT Features](planning/phase-2-candles-and-amt-features.md)
- [Phase 3: ML Pipeline and Validation](planning/phase-3-ml-pipeline-and-validation.md)
- [Phase 4: Execution and Operations](planning/phase-4-execution-and-operations.md)

**Use when:** You need to know what comes next or what “done” means.

---

## Research and Historical

- [Research guide](research/README.md) — Convention for historical notes
- [AMT on OTC — Reality Check](research/AMT_ON_OTC.md) — Why AMT on OTC is a hypothesis and what to test
- [PoC Validation — 2026-11-18](research/POC_VALIDATION_2026-11-18.md) — What the live tick capture run proved and did not prove

Planned: removed features, incident reports.

**Use when:** You are investigating why a decision was made or what failed.

---

## Operations and Project Entry Points

- [README](../README.md) — Project overview and quick start
- [AGENTS.md](../AGENTS.md) — Single source of truth for agents and developers
- [RUNBOOK.md](../RUNBOOK.md) — Operating the current PoC

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
| What one tick means | [data/01_TICK_STREAM.md](data/01_TICK_STREAM.md) |
| How 1-minute candles will work | [data/03_CANDLE_AGGREGATION.md](data/03_CANDLE_AGGREGATION.md) |
| How POC/VAH/VAL are computed | [data/04_TPO_VALUE_AREA.md](data/04_TPO_VALUE_AREA.md) |
| AMT feature formulas | [data/05_AMT_FEATURE_SPEC.md](data/05_AMT_FEATURE_SPEC.md) |
| Payout breakeven and EV | [data/06_LABELS_PAYOUTS_AND_EV.md](data/06_LABELS_PAYOUTS_AND_EV.md) |
| What to improve first | [system/10_LIMITATIONS_AND_BACKLOG.md](system/10_LIMITATIONS_AND_BACKLOG.md) |
| ML architecture | [system/08_ML_PIPELINE.md](system/08_ML_PIPELINE.md) |
| Validation gate | [system/09_MODEL_VALIDATION.md](system/09_MODEL_VALIDATION.md) |
| Roadmap | [planning.md](planning.md) |
| Operating the PoC | [../RUNBOOK.md](../RUNBOOK.md) |
| AMT reference implementation review | [research/AMT_REFERENCE_IMPLEMENTATION_2026-11-18.md](research/AMT_REFERENCE_IMPLEMENTATION_2026-11-18.md) |

---

*Last updated: 2026-11-18*
