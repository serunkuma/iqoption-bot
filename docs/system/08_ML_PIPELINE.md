# ML Pipeline

Status: Planning

> This document specifies the primary machine-learning architecture. It follows the two-stage regime design (Approach A). Approach B is retained as a research alternative.

---

## Primary Design — Approach A: Two-Stage Regime Architecture

### Stage 1 — Market State Gate

Classify the market at decision time `t` as:

| State | Rule-based definition |
|-------|-----------------------|
| Balance | Price inside `[VAL, VAH]` and not initiative |
| Imbalance | Price outside `[VAL, VAH]` with initiative velocity |
| Ambiguous | Neither condition is clear |

Initial implementation:

- Rule-based gate using the features in [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md).
- No ML required for Stage 1 at first.
- A predictive classifier may be added later to forecast the next-state regime.

The gate must be causal. It may not use the outcome candle.

### Stage 2 — Conditional Directional Models

| Model | Training rows | Intended behaviour |
|-------|---------------|--------------------|
| Balance model | Rows labelled `balance` | Mean reversion: Put near VAH, Call near VAL, target POC |
| Imbalance model | Rows labelled `imbalance` | Continuation in the breakout direction |
| No-trade | Ambiguous, missing data, or low confidence | Abstain |

Each model outputs a calibrated probability for the chosen direction, or a no-trade decision.

### Architecture

```text
Tick + candle + metadata
        │
        ▼
Feature snapshot (amt-v1)
        │
        ▼
Stage 1: regime gate
   ├── balance ──► Balance model ──┐
   ├── imbalance ─► Imbalance model ─┤
   └── ambiguous ────────────────────┤
                                     ▼
                          Calibrated probability
                                     │
                                     ▼
                          EV threshold + risk check
                                     │
                                     ▼
                          Call / Put / No-Trade
```

---

## Why Two Stages

A single model trained on all rows mixes two incompatible behaviours:

- Inside value, extensions tend to revert.
- Outside value with initiative, moves tend to continue.

Splitting the data before training prevents one regime from diluting the other. It also makes failures diagnosable: a bad balance model is a different problem from a bad imbalance model.

---

## Approach B — AMT-Penalised Loss (Research)

A single model can be trained with an added structural penalty:

```text
L_total = L_BCE(y, p_hat) + lambda * Penalty_AMT(p_hat, Z_VAH, Z_VAL, velocity)
```

Example penalty behaviour:

- At VAH with low velocity (rejection context), a high Call probability increases loss.
- At VAL with low velocity, a high Put probability increases loss.
- A breakout with high initiative velocity should not be penalised in the breakout direction.

Requirements before this is considered:

1. A precise, differentiable penalty definition.
2. A baseline comparison against Approach A.
3. Evidence that the penalty improves out-of-sample EV, not just training loss.

Approach B is not the default and must not block the primary pipeline.

---

## Baseline Before ML

Before training any model, build a rule-based AMT baseline:

| Setup | Signal |
|-------|--------|
| Balance, price near VAH, rejection signs | Put toward POC |
| Balance, price near VAL, rejection signs | Call toward POC |
| Imbalance, price outside VAH with initiative | Call continuation |
| Imbalance, price outside VAL with initiative | Put continuation |
| Ambiguous | No trade |

The baseline provides:

- A sanity check for the features.
- A performance floor the ML model must beat.
- A fallback if the model is unavailable.

---

## Training Workflow

1. Build a versioned dataset: features, labels, metadata, quality flags.
2. Split chronologically into train, validation, and test.
3. Purge and embargo rows near split boundaries to prevent label overlap.
4. Train the balance and imbalance models separately.
5. Calibrate probabilities on a held-out calibration set.
6. Evaluate with the metrics in [Model Validation](09_MODEL_VALIDATION.md).
7. Register the model artifact with feature and label versions.
8. Only deploy if the validation gate passes.

---

## Inference Workflow

1. Receive a complete feature snapshot at decision time.
2. Check feature version and model version compatibility.
3. Run the Stage 1 gate.
4. Run the appropriate Stage 2 model.
5. Calibrate or verify calibration.
6. Compute EV using the current payout.
7. Apply the no-trade threshold and risk checks.
8. Emit a signal with model version and reason.

If any step fails, emit no-trade.

---

## Model Registry

Each model artifact records:

| Field | Purpose |
|-------|---------|
| `model_id` | Unique identifier |
| `model_version` | Human-readable version |
| `feature_version` | Required feature set |
| `label_version` | Training label definition |
| `training_range` | Start and end timestamps |
| `validation_metrics` | Out-of-sample metrics |
| `calibration` | Calibration method and metrics |
| `library` | Library and version |
| `artifact_path` | Local path or hash |
| `created_at` | Creation timestamp |
| `status` | Candidate, active, retired |

The active model is a pointer, not a hard-coded path.

---

## Library Choice

Recommended starting point: **LightGBM** for tabular features.

Reasons:

- Strong performance on tabular data.
- Fast training and inference.
- Handles missing values.
- Easy feature-importance inspection.

Alternatives:

- XGBoost: comparable; choose based on team familiarity.
- PyTorch: only if a sequence model or custom loss is justified by evidence.

The library is not a final decision. Document the choice when the first model is built.

---

## Related Documentation

- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [Model Validation](09_MODEL_VALIDATION.md)
- [Data Pipeline](07_DATA_PIPELINE.md)
- [Auction Market Theory](../concepts/05_AUCTION_MARKET_THEORY.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-18*
