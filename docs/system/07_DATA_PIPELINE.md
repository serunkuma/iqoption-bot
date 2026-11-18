# Data Pipeline

Status: Planning

> This document specifies the path from a browser tick to a versioned training row. Only the first stage exists today.

---

## Pipeline Stages

| Stage | Input | Output | Status |
|-------|-------|--------|--------|
| Capture | Browser WebSocket frame | Raw JSON frame | Current |
| Validate | Raw frame | Accepted or rejected tick event | Partial |
| Persist | Accepted tick event | JSONL raw log; later SQLite/Parquet | Planned |
| Aggregate | Tick events | 1-minute OHLCV candles | Planned |
| Profile | Tick events | POC, VAH, VAL, value-area metrics | Planned |
| Feature | Profile, ticks, candles, metadata | Feature snapshot | Planned |
| Label | Candles, metadata | Binary outcome and payout-aware EV | Planned |
| Dataset | Features + labels + metadata | Versioned dataset | Planned |
| Train | Dataset | Model artifact | Planned |
| Infer | Live features + model | Signal | Planned |
| Execute | Signal + risk decision | Paper/demo/live order | Planned |
| Journal | Order and outcome | Trade record | Planned |

---

## Data Flow

```text
Browser WebSocket
    │
    ▼
[Capture] extension inject.js + content.js
    │
    ▼
[Validate] receiver.py
    │  JSON, envelope, active_id, numeric price
    ▼
[Persist] raw ticks (JSONL)
    │
    ├──────────────► [Profile] TPO/Value Area from ticks
    │                       │
    │                       ▼
    │                [Feature engine] ──┐
    │                                   │
    ▼                                   │
[Aggregate] 1-minute candles ──► [Label builder]
    │                                   │
    └──────────────► [Dataset builder] ◄┘
                            │
                            ▼
                     [Train / validate]
                            │
                            ▼
                     [Model registry]
                            │
                            ▼
                     [Inference] → [Signal] → [Risk] → [Execution]
```

---

## Offline First

Build and validate the pipeline offline before running it live:

1. Capture raw ticks to JSONL.
2. Replay the JSONL through the same validation and aggregation code.
3. Build candles and features from the replay.
4. Compare live and replay outputs on the same time range.
5. Only then enable online feature computation.

This avoids train/serve skew and makes failures reproducible.

---

## Storage Layout

```text
data/
├── raw/
│   └── ticks-2026-11-18.jsonl
├── candles/
│   └── candles.sqlite
├── features/
│   └── amt-v1/
│       └── features-2026-11-18.parquet
├── labels/
│   └── next-close-v1/
├── datasets/
│   └── amt-v1_next-close-v1_2026-11-18.parquet
├── models/
│   └── model-2026-11-18/
└── journals/
    └── paper-2026-11-18.jsonl
```

Only `data/` is local and gitignored. Small anonymised fixtures live under `tests/fixtures/`.

---

## Versioning

Every derived artifact records:

| Field | Example |
|-------|---------|
| `feature_version` | `amt-v1` |
| `label_version` | `next-close-v1` |
| `candle_version` | `1m-clock-v1` |
| `dataset_version` | `2026-11-18.1` |
| `model_version` | `model-2026-11-18` |
| `code_commit` | Git commit hash |
| `config_hash` | Hash of the resolved configuration |

A change to bin size, window length, sigma, label definition, or session timezone requires a version bump.

---

## Failure Handling

| Failure | Behaviour |
|---------|-----------|
| Malformed frame | Reject, count, sample in logs |
| Receiver restart | New session ID; gap recorded |
| Extension disconnect | Reconnect; gap recorded; queue-loss counted |
| Late tick | Store raw; do not rewrite finalized candle |
| Missing minute | Emit gap marker; do not synthesize prices |
| Insufficient ticks | Emit null profile/features; do not impute |
| Model missing | No trade |
| Feature version mismatch | No trade |
| Storage write failure | Stop the pipeline; fail closed |

---

## Scheduling

Offline batch jobs:

- Raw-to-candle rebuild: daily or on demand.
- Feature rebuild: after any feature-version change.
- Dataset build: after labels or features change.
- Model retraining: scheduled and event-driven.
- Backtest: per candidate model.

Online jobs:

- Tick validation and persistence: continuous.
- Candle finalization: every minute.
- Feature snapshot: at decision times.
- Inference: at decision times.
- Monitoring: continuous.

---

## Related Documentation

- [Tick stream contract](../data/01_TICK_STREAM.md)
- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [ML Pipeline](08_ML_PIPELINE.md)
- [Model Validation](09_MODEL_VALIDATION.md)

---

*Last updated: 2026-11-18*
