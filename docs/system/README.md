# System Documentation — "How"

Status: Current

> Documents in this folder define **the system's architecture, components, configuration, deployment, and operations** — how the pieces fit together to form a working whole.

---

## What Goes Here

This category answers **"how does the system work?"** — the architecture, component interactions, configuration schema, deployment topology, and operational runbooks.

| Type | Examples in this project | When to Create |
|------|--------------------------|----------------|
| Architecture overview | Browser extension → receiver → tick store → feature engine | First — establishes mental model |
| Component specs | Receiver, candle builder, TPO engine, model service | During implementation |
| Configuration reference | `config/default.toml`, environment variables | After config is stable |
| API / interface docs | Browser-to-receiver WebSocket, internal contracts | When interfaces are defined |
| Deployment guide | Local Windows service, data directories | Before launch |
| Runbook / operations | Health checks, logs, gap handling, recovery | Before launch |
| Testing strategy | Unit, replay, integration, model validation | During testing phase |

---

## Numbering Convention

Use a numbered series that mirrors the system's logical layers:

```
system/
├── README.md
├── 01_OVERVIEW.md                 ← Current system and target architecture
├── 02_COMPONENTS.md               ← Component responsibilities and wiring
├── 03_CONFIGURATION.md            ← TOML schema, defaults, validation
├── 04_INTERFACES.md               ← External and internal contracts
├── 05_TESTING.md                  ← Test strategy and coverage gaps
├── 06_SECURITY.md                 ← Security model and trading safety
├── 07_DATA_PIPELINE.md            ← Capture → store → snapshot → dataset
├── 08_ML_PIPELINE.md              ← Four-horizon calibrated classifiers
├── 09_MODEL_VALIDATION.md         ← Walk-forward gate and calibration
├── 10_LIMITATIONS_AND_BACKLOG.md  ← Gaps and prioritised improvements
├── 11_RUNTIME_AND_ENTRYPOINT.md   ← runner.py commands and wiring
├── 12_MODEL_SUITE.md              ← Training, calibration, evaluation table
├── 13_SIGNAL_ROUTER.md            ← EV hurdle and proposal selection
├── 14_EXECUTION_AND_RESOLUTION.md ← Paper broker and trade resolution
└── 15_REPORTS_AND_DIAGNOSTICS.md  ← diagnose, build, train, backtest output
```

Not every project needs every file. Add only what the project requires.

---

## Population Process

1. **First pass** — Agent extracts architecture from source documents and project code during kickstart
2. **During implementation** — As components are built, document their interfaces and dependencies
3. **During testing** — As edge cases are discovered, document error handling and recovery
4. **Before launch** — Create deployment and runbook docs

---

## Relationship to Other Categories

```
docs/concepts/  ──►  "Why" — philosophy, beliefs, rationale
docs/data/      ──►  "What" — data structures, formulas, pipelines
docs/system/    ──►  "How" — architecture, components, deployment  ← You are here
```

System docs implement the concepts and process the data. Every component should trace to a concept in `docs/concepts/` and consume/produce data specified in `docs/data/`.

---

## Key Principles

- **Diagrams required** — every architecture overview includes an ASCII or Mermaid flow diagram
- **Component boundaries explicit** — each component has defined responsibilities, inputs, and outputs
- **Configuration cross-referenced** — every config key links to its validation rules and default value
- **Error states documented** — every interface doc includes error responses and recovery steps
- **Runbook is testable** — a fresh operator should be able to follow the runbook without asking questions
- **Status labels mandatory** — every doc starts with `Status: Current`, `Status: Planning`, or `Status: Historical`
- **Operator-first for operators** — RUNBOOK.md and README.md start with "what to do" before "why it works"
- **Copy-paste ready** — every command and code example is complete, tested, uses full paths (not abbreviations)

---

## Operator-First Language Guide

For operator-focused docs (RUNBOOK.md, README.md "Running" section):

1. **Start with workflow** — describe the exact steps before explaining architecture
2. **Real-money warnings upfront** — if this is production/real-money code, say it in the first line
3. **Three clear modes** — distinguish between "signal-only", "demo/paper", and "live" modes
4. **Preflight validation required** — operators should verify dependencies before running
5. **Troubleshooting guide** — include common issues and exact fix steps
6. **Copy-paste ready commands** — use `.venv/bin/python`, not bare `python`; include all flags
7. **Numbered steps** — 1, 2, 3... numbered sequences are easier to follow than bullet points

Example structure:
```
# RUNBOOK: Operating [Project]

## Core Rules (what's immutable)

## Daily Workflow
1. Step 1
   ```bash
   exact command here
   ```
2. Step 2
   ...

## Troubleshooting
### Issue: [Problem]
- Diagnosis: [how to check]
- Solution: [exact steps]
```

---

## Doc Template (System)

When creating a new system doc, follow this structure:

```markdown
# Document Title

## Overview
What this document covers, who it's for.

## Content
Main body — tables, diagrams, code blocks.

## Key Files
- `src/path/to/file.py` — what this file does

## Related Documentation
- `docs/concepts/xx_*.md`
- `docs/data/xx_*.md`

---

*Last updated: 2026-11-18*
```

---

## Related

- `docs/concepts/README.md` — design philosophy behind the architecture
- `docs/data/README.md` — data specifications consumed by components
- `AGENTS.md` Section 4 (architecture) and Section 5 (configuration) live here

---

*Last updated: 2026-11-19*
