# ML Runtime and Signal Selection

Status: Planning

> This document tracks the remaining learned-selector and readiness work. Candle-close inference, a deterministic EV router, and paper-only runtime decisions are implemented; none of that establishes an edge or authorizes broker execution.

## Purpose

Define how the existing capture and offline ML work could grow into a market-running IQ Option system that loads trained models for inference and uses ML in signal selection. Pocket Auto v3 is a design reference only; it is not the target repository and its current behavior is not evidence that the IQ Option hypothesis works.

## Current state versus target

| Area | IQ Option Bot today | Intended direction |
|---|---|---|
| Data | Browser capture, streaming event/candle store, plus offline file-to-dataset build | Preserve the causal data contract; harden and observe capture quality on real sessions |
| Features | Stateless `amt-v4` feature table; fixed `core16-v2` classifier inputs, plus diagnostics | Keep feature calculators explicit and versioned. Treat their output as model inputs/building blocks, not as signals by themselves |
| Training | Four calibrated binary classifiers, one per horizon, trained offline | Continue offline training and compare candidate model/selector designs against fixed baselines |
| Persistence | `runner.py train` writes timestamped `.joblib` suites with manifest sidecars; legacy pickle remains readable for analysis/backtest | Keep compatibility metadata, artifact integrity checks, and explicit local artifact selection |
| Inference | Candle-close `RuntimeEngine` uses the shared feature function and a manifest-validated `.joblib` suite | Validate causal feature parity and runtime behavior on independent captures |
| Signal selection | Deterministic EV router chooses among per-horizon probabilities | Evaluate a learned selector for direction, horizon, or abstention; retain deterministic payout, risk, and execution constraints as hard gates |
| Evaluation | Held-out probabilities replayed offline; runtime writes paper decisions and trade outcomes | Compare offline and runtime results chronologically, then gather shadow and sustained paper evidence before any separate demo/live decision |
| Trading readiness | No broker order execution, complete risk manager, or kill switch | Separate readiness gates; passing code/tests or backtests alone never authorizes market execution |

The IQ model suite is ML-based at the probability-estimation layer. Runtime inference and paper decision wiring now exist, but the final router remains deterministic. The learned selector and sustained evidence remain future work.

## Intended component boundaries

```text
Capture and quality checks
    -> sequence-preserving streaming store and candle-close decisions
    -> versioned feature calculators
    -> offline labels and training data
    -> trainer + time-aware evaluation
    -> versioned .joblib artifact + manifest
    -> runtime loader + compatibility validation
    -> ML predictions / deterministic EV baseline
    -> future learned candidate selector (not implemented)
    -> deterministic payout, risk, and execution gates
    -> explicit proposal or abstention
    -> shadow / paper evaluation
    -> separately gated demo/live work
```

### Features are inputs, not signals

The 16 `core16-v2` values describe the market at a candle-close decision point. They are not independent trade instructions and do not imply that a signal exists. A future design may also have feature or setup components that define candidate opportunities; the learned selector would score or choose among those candidates using a precisely specified target. Keep the responsibilities separate:

- **Feature calculation:** produce causal, versioned values from data available at decision time.
- **Candidate/setup definition:** if used, describe possible directions and expiries without seeing the outcome.
- **Prediction/selection:** estimate outcomes or rank candidates using a trained model.
- **Policy gates:** enforce configured payout availability, exposure/risk limits, market/session permission, and execution constraints.
- **Abstention:** return an explicit reason when model, data, payout, or safety requirements are not met.

No candidate-generation design or selector training target is implemented or settled yet.

## ML selector recommendation

The target is to evaluate a learned selector for direction, horizon, and no-trade, rather than describing the current EV router as ML. Keep the current per-horizon probability models and deterministic EV router as a baseline. Compare a learned selector against that baseline on the same chronological, untouched evaluation periods.

The learned part must not override hard safety policy. A model may rank or reject candidates, but deterministic checks should still block an invalid payout, disallowed instrument/session, exceeded risk limit, incompatible artifact, or unavailable execution path. The current minimum-EV rule may remain as a hard gate, or be revised only through a documented, validated decision; never change it just to create more trades.

Training a selector requires a target that reflects actual payouts and outcomes and avoids using future information. Candidate scope, target definition, and whether selection is trained jointly across horizons remain open design decisions.

## Artifact and runtime contract

The implemented runtime artifact is a timestamped `.joblib` suite with a `.manifest.json` sidecar. Joblib serialization is Python object serialization; artifacts must be trusted, versioned, and loaded only after compatibility checks.

The current manifest identifies:

- artifact format and artifact/model version;
- estimator and calibration components, if applicable;
- ordered feature names and feature-version identifier;
- label/target definition and version;
- model scope (instrument, horizon, or shared scope);
- training-data cutoff/fingerprint, configuration fingerprint, and training timestamp;
- Python and relevant model-library versions;
- sample counts, chronological split description, validation metrics, and skipped/rejected reasons.

Runtime guarantees and remaining expectations:

1. Select the artifact through `models.runtime_path` or `serve --model`; do not rely on an implicit fallback for runtime inference.
2. Verify artifact hash and format, ordered features, feature/decision/candle/label versions, configured instrument, and configured horizons before inference.
3. Use the same feature contract at training and inference; reject missing, reordered, stale, or incompatible inputs.
4. Do not retrain, overwrite, or promote the active artifact implicitly during a trading session.
5. If an artifact is missing or incompatible, `serve` exits with a visible error; it never falls back to pickle.
6. The runtime journals artifact id and feature/decision metadata with each decision. Sustained-session observability and operational recovery still need validation.

Artifact signing, promotion/rollback, and per-instrument versus shared model layout still need a separate design decision.

## Validation and release progression

1. **Research baseline:** preserve the existing purged walk-forward and held-out evaluation discipline. Compare the learned selector with the current EV router, random/no-signal baselines, and a rule-based baseline.
2. **Evidence review:** report per-horizon and per-selector payout-adjusted EV, calibration, uncertainty, sample sufficiency, independent expiry windows, session/weekend behavior, and sensitivity. Repeat on independent real captures. Synthetic data can test plumbing but cannot establish edge.
3. **Shadow inference:** run the existing runtime without allowing paper opens, or add an explicit shadow policy; verify feature parity, latency, abstentions, and failure handling.
4. **Sustained paper:** simulate orders from the live feed; reconcile decisions and outcomes with offline replay; exercise risk limits and stop conditions.
5. **Demo/live readiness:** only after model validation, risk controls, audit journal, monitoring, broker reconciliation, operational procedures, and platform/legal review have their own acceptance gates. A positive backtest is necessary evidence, not sufficient authorization.

If evidence is weak or inconclusive, remain in research or paper mode. Do not lower a hurdle or repeatedly tune on the held-out evaluation slice.

## Pocket Auto v3 reference notes

Potentially useful patterns include explicit proposal contracts, metadata registries, offline artifact creation, versioned model archives, and separation between trainer output and runtime activation.

Important distinctions:

- Pocket Auto v3's live signal engines are primarily rule/gate-based; their existence does not make the IQ Option target ML-based.
- Its optimizer's ML ranks configurations or predicts optimizer outcomes. That task differs from predicting market outcomes or choosing a trade.
- Some Pocket Auto artifacts are serialized with joblib despite `.pkl` filenames; the target IQ Option naming convention is explicitly `.joblib`.
- A historical/experimental signal-level model is not proof of an actively integrated, validated production signal model.

Reference locations in the Pocket Auto v3 repository: `docs/system/09_SIGNAL_MODELS.md`, `engines/signal/registry.py`, `tools/optimizer/ml/model_archive.py`, `tools/optimizer/ml/feature_schema.py`, and `tools/optimizer/ml/signal_model.py`. Re-check each source before adopting a pattern.

## Decisions still needed before selector promotion

- Selector target: realized directional outcome, payout-adjusted utility, or another explicitly defined target.
- Candidate source: raw market feature vector, candidates emitted by future setup components, or a staged combination.
- Model scope: per horizon/instrument, joint, or shared with supported context features.
- Artifact manifest, trust/integrity policy, path layout, activation and rollback procedure.
- Minimum independent sample, repeated-capture evidence, confidence/uncertainty criteria, and promotion thresholds for shadow, paper, and demo/live.
- Exact policy gates that remain deterministic outside the model.

## Related documentation

- [System overview](../system/01_OVERVIEW.md)
- [ML pipeline](../system/08_ML_PIPELINE.md)
- [Model suite](../system/12_MODEL_SUITE.md)
- [Signal router](../system/13_SIGNAL_ROUTER.md)
- [Model validation](../system/09_MODEL_VALIDATION.md)
- [Phase 3: ML pipeline and validation](phase-3-ml-pipeline-and-validation.md)
- [Phase 4: ML runtime, execution, and operations](phase-4-execution-and-operations.md)

*Last updated: 2026-11-21*
