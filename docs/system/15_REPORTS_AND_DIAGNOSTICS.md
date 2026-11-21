# Reports and Diagnostics

Status: Current

> Reports audit the engine; they never change a model, a trade, or a dataset. `diagnose` reports data quality, `build` reports exclusions, `train` reports held-out metrics, and `backtest` writes a JSON/Markdown pair.

---

## Design Rules

1. Every report is derived from stored artefacts, not from recomputation.
2. Calibration and per-horizon metrics come from the held-out evaluation slice only.
3. Missing values are reported as missing, never as zero.
4. Exclusions are counted, never silently dropped.
5. Markdown rendering uses a local table writer, so `tabulate` is not a dependency.

---

## `diagnose`

```powershell
.\.venv\Scripts\python.exe runner.py diagnose --input data\raw\ticks-2026-11-18.jsonl
```

```text
tick store
  rows                        : 28800
  duplicate (timestamp, price): 0
  out-of-order rows           : 0
  first tick                  : 2026-11-18 12:00:00+00:00
  last tick                   : 2026-11-18 14:59:59+00:00
  span seconds                : 10799
  minutes with ticks          : 180
```

Use it before a build: `minutes with ticks` is the hard ceiling on candidate snapshots, and the duplicate counter shows repeated timestamp/price pairs. Events are preserved; the counter does not mean they were removed.

`out-of-order rows` counts adjacent timestamp inversions in the file order, measured before sorting.

---

## `build` Summary

The build summary combines store statistics, sampler exclusions, and artefact sizes:

| Key | Meaning |
|-----|---------|
| `ticks` | Rows in the canonical store |
| `duplicate_rows` | Exact `(timestamp, price)` duplicate pairs observed and preserved |
| `out_of_order` | Timestamp inversions seen on load |
| `candidate_minutes` | Whole minutes containing at least one tick |
| `snapshots` | Validated snapshots |
| `feature_rows` / `label_rows` | One per snapshot / one per snapshot per horizon |
| `dataset_rows` | Features joined to labels |
| `usable_rows` | Rows where `usable == 1` |
| `config_hash` | Short hash of the resolved configuration |
| `skipped_insufficient_history` | Fewer than `macro_candles` earlier minutes |
| `skipped_gap` | Macro window is not contiguous |
| `skipped_sparse_bar` | A completed bar has fewer than `min_ticks_per_bar` ticks |
| `skipped_no_entry_tick` | No tick within the entry delay plus tolerance |
| `snapshots_with_missing_exits` | At least one horizon had no exit tick |

`dataset_rows / snapshots` should equal the number of configured horizons. A smaller ratio means labels were lost, which points at missing exits.

---

## `train` Output

One line per horizon:

```text
horizon   60s  rows=770 oos=258 eval=77 brier=0.2513 auc=0.5542 cal=none
                calibration: rejected platt fit with a negative slope; using identity
```

| Field | Meaning |
|-------|---------|
| `rows` | Usable rows for the horizon |
| `oos` | Walk-forward out-of-sample rows |
| `eval` | Held-out evaluation rows (the later 30% of OOS) |
| `brier` | Brier score on the evaluation rows |
| `auc` | ROC AUC on the evaluation rows |
| `cal` | Calibrator shipped: `isotonic`, `platt`, or `none` |

A skipped horizon prints its reason instead of a metric line. A model that is trained but has fewer than 10 evaluation rows shows `eval=<10` and carries the `too few held-out evaluation rows` note.

These numbers are small-sample estimates. `eval` in the dozens is enough to sanity-check the pipeline, not enough to claim an edge.

---

## `backtest` Report

`reports/backtest.json` contains four sections:

| Section | Content |
|---------|---------|
| `calibration` | Per-horizon reliability summary on the evaluation slice: rows, positives, Brier, log loss, AUC, ECE |
| `horizons` | Per-horizon training metrics, including calibrator notes and skipped reasons |
| `importance` | Top-16 feature importance per horizon |
| `execution` | Trade counts, PnL, win rate, concurrency, skip counters, skipped horizons |

`reports/backtest.md` contains the per-horizon table and the execution block. It does not repeat calibration or importance; use the JSON when those are needed.

### Execution Section

| Key | Meaning |
|-----|---------|
| `snapshots` | Snapshots that were routed; the result's `routed` counter is printed under this name |
| `trades`, `closed`, `open` | Trade counts |
| `wins`, `losses`, `voids`, `win_rate` | Closed-trade outcomes |
| `pnl` | Sum of realised PnL at fixed stake |
| `concurrency` | Max/mean concurrent trades and overlapping pairs (JSON only) |
| `skipped_overlap` | Blocked by the open-trade limit |
| `skipped_no_model` | Snapshot outside the held-out evaluation slice, or no model for that horizon |
| `skipped_below_hurdle` | Routed snapshot whose best EV failed `router.min_ev` |
| `skipped_horizons` | Horizon to skip reason (JSON only) |

High `skipped_no_model` is expected: only the held-out evaluation slice is replayable.

### Concurrency

`concurrency` sweeps entry and expiry events to report the peak number of simultaneous live trades, the mean concurrency, and how many trade pairs overlap. With `max_open_trades = 1` the peak should be 1; a higher value indicates a broker or replay bug.

---

## Feature Importance

`feature_importance` prefers SHAP values from `TreeExplainer` and falls back to `feature_importances_` when SHAP is unavailable or raises. It explains the shipped estimator on an all-zero sample, which is only a directional ranking aid, not a causal explanation.

If SHAP is missing and the estimator exposes no native importance, the section is empty. It is never filled with placeholder values.

---

## Reliability Curve

`reliability_curve(labels, probabilities, bins=10)` returns, per bin: bin index, lower and upper edge, count, mean predicted probability, and observed rate.

`calibration_summary(labels, probabilities)` returns rows, positives, Brier, log loss, AUC, and expected calibration error. AUC is `0.0` when only one class is present; the function does not raise.

---

## Reading Results Honestly

| Observation | Interpretation |
|-------------|----------------|
| Brier near 0.25 and AUC near 0.5 | The model is no better than a constant 50% guess |
| AUC well above 0.5 but EV negative | Calibration or payout is insufficient |
| Many trades, near-zero wins | The direction is inverted or the labels are wrong; investigate before anything else |
| Very few trades | The EV hurdle is high relative to model confidence, or the evaluation slice is small |
| Large `skipped_no_model` | Normal for honest replay; do not "fix" it by widening the evaluation slice |
| `open` trades at the end | Missing exit ticks at the end of the capture |

A negative result is a valid research outcome. The reports exist to make that visible early.

---

## Related Documentation

- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Model suite](12_MODEL_SUITE.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Testing strategy](05_TESTING.md)

---

*Last updated: 2026-11-21*
