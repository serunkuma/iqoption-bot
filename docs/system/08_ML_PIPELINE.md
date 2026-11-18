# ML Pipeline

Status: Planning

> This document specifies the primary machine-learning architecture. It follows the two-stage regime design (Approach A). Approach B is retained as a research alternative.

---

## Primary Design — Approach A: Two-Stage Regime Architecture

### Stage 1 — Market State Gate

Classify each tick at entry time `t` as:

| State | Rule-based definition |
|-------|-----------------------|
| Balance | Price inside `[VAL, VAH]` and forming activity is not elevated |
| Imbalance | Price outside `[VAL, VAH]` with elevated forming activity in the breakout direction |
| Ambiguous | Neither condition is clear |

Initial implementation:

- Rule-based gate using the features in [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md).
- No ML required for Stage 1 at first.
- A predictive classifier may be added later to forecast the next-state regime.

Worked rule:

```text
forming_activity = mean(price_speed_forming_3, tick_rate_forming_3, range_forming_3)
elevated         = forming_activity >= forming_activity_threshold

balance    = inside_va == 1 and not elevated
imbalance  = inside_va == 0 and elevated
              and sign(price - POC) == sign(price_change_forming)
ambiguous  = otherwise
```

`forming_activity_threshold` is a configuration value, initially a fixed quantile of the training window. It must not be tuned on the test set.

The gate must be causal. It may not use any later tick or the outcome.

### Stage 2 — Conditional Directional Models

| Model | Training rows | Intended behaviour |
|-------|---------------|--------------------|
| Balance model | Rows labelled `balance` | Mean reversion: Put near VAH, Call near VAL, target POC |
| Imbalance model | Rows labelled `imbalance` | Continuation in the breakout direction |
| No-trade | Ambiguous, missing data, or low confidence | Abstain |

The initial version trains a separate model per horizon (60, 90, 120, 180 seconds) for each regime. A shared model with the horizon as a feature is a later experiment and must beat the per-horizon baseline to replace it.

Each model outputs a calibrated probability for the chosen direction, or a no-trade decision.

### Architecture

```text
Tick + completed candles + forming candle + metadata
        │
        ▼
Feature snapshot (amt-v2, one row per tick)
        │
        ▼
Stage 1: regime gate
   ├── balance ──► Balance model per horizon ──┐
   ├── imbalance ─► Imbalance model per horizon ─┤
   └── ambiguous ────────────────────────────────┤
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
3. Purge rows whose label window crosses a split boundary; embargo a configurable period after each split.
4. Train the balance and imbalance models separately for each horizon.
5. Calibrate probabilities on a held-out calibration set.
6. Evaluate with the metrics in [Model Validation](09_MODEL_VALIDATION.md).
7. Register the model artifact with feature and label versions.
8. Only deploy if the validation gate passes.

Rows are ticks, so adjacent rows are highly correlated and label windows overlap. Training must not treat row count as independent sample size. Purging, embargo, and per-fold reporting are mandatory.

### Empty or One-Class Regimes

A regime subset can be empty or contain a single class. In that case:

- Skip the model and record the reason.
- Never fabricate a probability.
- Never silently train on the other regime's rows.

The validation report must state which regime/horizon models were skipped.

---

## Inference Workflow

1. Receive a complete feature snapshot for an accepted tick.
2. Check feature version and model version compatibility.
3. Run the Stage 1 gate.
4. Run the appropriate Stage 2 model for the chosen horizon.
5. Calibrate or verify calibration.
6. Compute EV using the current payout for that horizon.
7. Apply the no-trade threshold and risk checks.
8. Emit a signal with model version, horizon, and reason.

If any step fails, emit no-trade. A structural guardrail must produce an explicit no-trade reason code, not overwrite the probability.

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
