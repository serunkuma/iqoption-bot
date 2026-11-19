# Data Documentation — "What"

Status: Current

> Documents in this folder specify **data structures, fields, calculation formulas, pipeline stages, and validation rules** — the precise definition of what data flows through the system and how it transforms at each stage.

---

## What Goes Here

This category answers **"what are the data and how are they computed?"** — the unambiguous specification of every data element.

| Type | Examples in this project | When to Create |
|------|--------------------------|----------------|
| Data models / schemas | `TickEvent`, `Candle`, `FeatureSnapshot`, `Signal` | When domain models are defined |
| Calculation formulas | POC/VAH/VAL, `Z_POC`, tick velocity, expected value | When algorithms are specified |
| Pipeline stages | Tick ingestion → candles → AMT features → labels | When data flows are designed |
| Validation rules | OHLC invariants, causal windows, gap handling | When data quality matters |
| Output formats | JSONL ticks, SQLite candles, Parquet feature sets | When interfaces are defined |

---

## Numbering Convention

Pipeline stages should follow data flow order:

```
data/
├── README.md
├── 01_TICK_STREAM.md
├── 02_ASSET_IDENTITIES.md
├── 03_CANDLE_AGGREGATION.md
├── 04_TPO_VALUE_AREA.md
├── 05_AMT_FEATURE_SPEC.md
├── 06_LABELS_PAYOUTS_AND_EV.md
├── 07_TICK_STORE.md
├── 08_SNAPSHOTS_AND_CONTINUITY.md
└── 09_MODEL_INPUTS.md
```

The `DATA_CATALOG.md` pattern (a single-file reference of every field, its type, source, and description) is highly recommended for projects with many data elements.

---

## Population Process

1. **First pass** — Agent extracts data specifications from attached source documents
2. **During implementation** — When code reveals data shapes or edge cases not covered in sources
3. **During testing** — When validation rules are refined based on test findings

---

## Relationship to Other Categories

```
docs/concepts/  ──►  "Why" — philosophy, beliefs, rationale
docs/data/      ──►  "What" — data structures, formulas, pipelines  ← You are here
docs/system/    ──►  "How" — architecture, components, deployment
```

Data docs are the contract between concepts (what we want to achieve) and system (how we achieve it). Every data element should trace back to a concept in `docs/concepts/`.

---

## Key Principles

- **Precision over prose** — use tables, pseudocode, and schemas; minimise vague descriptions
- **Single source of truth** — every field is defined in exactly one place (cross-reference don't duplicate)
- **Examples required** — every calculation doc includes at least one worked example with inputs and expected output
- **Validation rules explicit** — don't say "validated" — say "must be > 0 and ≤ 1000"

---

## Doc Template (Data Layer)

When creating a new data layer doc, follow this structure:

```markdown
# Layer Name — Brief Description

## Overview
What this layer does, when it runs, what it consumes.

## Input
Table of input fields with types and sources.

## Output
Table of output fields with types, descriptions, and units.

## Calculation
Pseudocode or formula in fenced code block.

## Key Principles
Design constraints or invariants that shape this layer.

## Validation Rules
Assertions that must hold for output to be valid.

## Related Documentation
```

---

## Related

- `docs/concepts/README.md` — design philosophy behind the data
- `docs/system/README.md` — component architecture that processes this data
- `AGENTS.md` Section 6 (key concepts) draws from here

---

*Last updated: 2026-11-19*
