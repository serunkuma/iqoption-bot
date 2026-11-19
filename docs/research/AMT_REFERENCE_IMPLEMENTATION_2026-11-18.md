# AMT Reference Implementation Review — 2026-11-18

Status: Historical

> Records how an external AMT feature-engineering sample was reviewed, what was adopted, and what was deliberately changed before the first offline feature package was written.
>
> **Note:** this note predates the `engine/` package. Paths and version names in the "What Was Adopted" table have been updated to the current equivalents; the reasoning is unchanged.

---

## Context

An external AI-assisted conversation produced a Python sample that built a rolling TPO profile, tick velocity features, a two-stage balance/imbalance model, and a simple backtest. It used only `timestamp` and `price`, and it mixed feature engineering with labels, training, and evaluation.

The sample was treated as a **reference prototype**, not as a specification and not as code to copy. The canonical implementation is `engine/` in this repository.

---

## What Was Adopted

| Idea | Where it landed |
|------|-----------------|
| Tick density as the volume proxy | [TPO and Value Area](../data/04_TPO_VALUE_AREA.md) |
| Rolling POC, VAH, VAL | `engine/domain/profile.py` |
| Normalising distance by volatility | `engine/features.py` |
| Separating balance from imbalance | [ML Pipeline](../system/08_ML_PIPELINE.md) |
| Payout breakeven instead of raw accuracy | [Labels and EV](../data/06_LABELS_PAYOUTS_AND_EV.md) |
| Some embargo between train and test | [Model Validation](../system/09_MODEL_VALIDATION.md) |

---

## What Was Changed

| Area | Reference behaviour | Project decision |
|------|---------------------|------------------|
| Instrument scope | One unnamed series | One configured active instrument; multi-instrument is a future item |
| Timestamp | Naive timestamp | One local receipt timestamp, ISO 8601 with offset |
| Decision unit | A label for every tick at 60s | Tick entries with 60/90/120/180s horizons; candles are context only |
| Tie handling | `future_price > price` else Put, so ties became Put | Ties and missing exits stay explicit and are excluded from directional training |
| Expiry match | `merge_asof` forward within 5s | First tick at or after the horizon within a 5s tolerance, with delay recorded |
| Volatility | 15-minute tick log-return std × price | `sigma_7`: sample std of tick price changes over the last 7 completed candles |
| Profile bins | Rounded to bin centres, observed bins only | `floor(price / bin_size)` with float-edge correction; contiguous bins; VAH/VAL from edges |
| VA expansion | One bin at a time | Pair expansion over non-empty bins |
| POC tie-break | `argmax`, lowest index | Highest count, then nearest to current price, then lower bin |
| Insufficient data | POC/VAH/VAL set to current price | Null profile with `profile_missing = 1`; no synthetic values |
| Excess | Global single-tick-bin ratio | Tail-specific `excess_high`, `excess_low`, `excess_asymmetry` |
| Velocity | Fixed 5s/30s windows | Macro 7 / fast 3 / forming layer comparisons; no fixed short windows |
| Regime gate | Balance means "not imbalance" | Balance, imbalance, and ambiguous; ambiguous excluded from directional training |
| Guardrail | Probability overwritten to 0.5 | Explicit no-trade with a reason code |
| Validation | One chronological split, win rate only | Walk-forward, purge/embargo, calibration, EV per trade, baselines, one open position |
| Performance | Per-tick loop with per-window `np.unique` | Offline batch build now; incremental or vectorised engine is a backlog item |

---

## What Was Rejected

- Copying the sample's label construction. It produced heavily overlapping outcomes and mislabelled ties.
- Using the sample's fallback profile. Fabricated POC/VAH/VAL values create false "inside value" observations.
- Reporting win rate alone. A result can look strong and still lose money after payout.
- Treating the sample as production code. It had no configuration, no null handling, no deduplication, and no per-instrument separation.

---

## Decision

The external sample is historical context. The canonical definitions are the data and system specifications; the canonical implementation is `engine/` with `amt-v3` features, the `core16-v1` model vector, and `snapshot-horizon-v1` labels. Any future change must be justified against the specs and the validation gate, not against the sample.

The raw discussion input was removed from the working tree after its useful content was absorbed. It remains available in git history.

---

## Related Documentation

- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [ML Pipeline](../system/08_ML_PIPELINE.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [AMT on OTC](AMT_ON_OTC.md)

---

*Last updated: 2026-11-19*
