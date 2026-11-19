# Testing Strategy

Status: Current

> The engine is tested with `unittest` at the component boundary: each module is exercised with real objects, synthetic ticks, and explicit failure cases. There is no live-to-offline parity test yet, because there is no live inference path.

---

## Running the Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Import `engine` before pandas in any ad-hoc script; see the Windows LightGBM caveat below.

Expected tail:

```text
Ran 117 tests

OK
```

---

## Coverage by File

| File | Tests | Covers |
|------|-------|--------|
| `test_config.py` | 10 | Defaults, unknown keys, section types, offset uniqueness and range, horizon ordering, payout coverage, mode validation, config hash stability |
| `test_store.py` | 10 | CSV contract, naive timestamp rejection, non-positive price, `active_id` mismatch, dedupe, ordering, `tick_id` on reload, point-in-time lookups |
| `test_timeframes.py` | 7 | Bucket boundaries, forming vs completed, gap detection, unsorted input, tick counts |
| `test_profile.py` | 6 | Worked example, POC tie-breaks, bin edges, single bin, internal gap, insufficient ticks |
| `test_sampler.py` | 11 | Continuity gate, insufficient history, gaps, sparse bars, offset slicing, entry delay, exit tolerance, missing exits, single-instrument filtering |
| `test_features.py` | 9 | Exact core feature list and order, null propagation, layer ratios, forming truncation, profile/volatility missing flags, diagnostic table parity |
| `test_labels.py` | 7 | Call/put/tie classification, tie policy, missing exits, long-format rows, label version |
| `test_models.py` | 13 | Overlap weights, calibrator monotonicity, rejected Platt slope, identity clipping, per-horizon training, evaluation table shape, held-out slice disjoint from calibration, skipped horizons, pickle round-trip |
| `test_router.py` | 10 | EV math, breakeven, call/put candidate selection, hurdle rejection, reason codes, tie-break modes, malformed probabilities |
| `test_execution.py` | 11 | Mode rejection, open limits, expired-trade slot release, win/loss/void resolution, double resolve, summary, journal |
| `test_backtest.py` | 5 | Only held-out snapshots routed, trades reference evaluated snapshots, one-open-trade limit, no-model no-trade, horizon resolution |
| `test_reports.py` | 6 | Reliability bins, Brier/AUC/ECE, single-class safety, concurrency, JSON/Markdown writing without `tabulate` |
| `test_receiver.py` | 5 | Identity formatting, acceptance and buffering, rejection paths, asset-map loading |
| `test_docs.py` | 6 | Missing status, broken link, ignored external/anchor/mailto links, orphan doc, and a clean sweep of this repository |

---

## Test Helpers

`tests/helpers.py` provides:

| Helper | Purpose |
|--------|---------|
| `make_config(**sections)` | Build a validated `Config` with small, fast model settings |
| `synthetic_ticks(...)` | Deterministic rising ticks, one per second |
| `synthetic_walk_ticks(...)` | Seeded random walk that produces both call and put labels |

`make_config` lowers `min_train_rows`, `n_estimators`, and `num_leaves` so model tests finish in seconds while still exercising the real code path.

Synthetic data is only a plumbing test. It cannot validate the AMT hypothesis, because it has no auction structure.

---

## The Windows LightGBM Caveat

Importing pandas or pyarrow before `lightgbm` can make the first `LGBMClassifier.fit` crash with:

```text
OSError: exception: access violation reading 0x0000000000000000
```

inside `LGBM_DatasetSetField`.

`engine/models.py` imports LightGBM first and `engine/__init__.py` imports `.models` before anything else, so importing `engine` is always safe. A test or script that imports pandas at the top and lands in `engine.models` later can still trip it; import `engine` first.

If the crash appears in a new environment, check import order before suspecting the data.

---

## What Is Not Covered

| Gap | Risk |
|-----|------|
| Live-to-offline parity | Live inference does not exist, so there is nothing to compare |
| Long-run capture | Reconnects and multi-hour sessions are untested |
| Real tick density | Synthetic ticks are far denser and cleaner than a real feed |
| Calibration on real data | Only synthetic and small samples have been exercised |
| Statistical validity | Unit tests assert mechanics, not edge |
| Multi-instrument | Explicitly unsupported |
| Demo/live execution | Not implemented |

Passing tests mean the pipeline is internally consistent. They say nothing about profitability.

---

## Adding Tests

1. Put the test in the file matching the component.
2. Build inputs through helpers rather than hard-coding blobs.
3. Assert the failure mode as well as the success path.
4. For anything touching time, use explicit UTC-aware timestamps.
5. Do not assert a specific model score; assert structure, monotonicity, and invariants.
6. Run the full suite, not only the new file.

---

## Documentation Checklist

Three checks are automated by `tools/check_docs.py`, reachable as `runner.py docs-check`:

```powershell
.\.venv\Scripts\python.exe runner.py docs-check
```

| Check | Fails when |
|-------|------------|
| Status label | A doc under `docs/` has no `Status:` line |
| Link resolution | A relative markdown link targets a missing file |
| Index coverage | A doc under `docs/` is not linked from `docs/index.md` |

The remainder is still human work:

- [ ] No doc points at removed `sources/`, `scripts/`, `amt/`, or root `receiver.py`.
- [ ] Commands in `AGENTS.md`, `README.md`, and `RUNBOOK.md` match the real CLI.
- [ ] Version strings are `amt-v3`, `core16-v1`, `snapshot-horizon-v1`, `1m-clock-v1`.
- [ ] No doc claims live execution, live features, or multi-instrument support.
- [ ] Counts quoted in docs (test totals, column counts) match a fresh run.

The checker validates structure, not truth. A doc can pass every check and still describe behaviour that no longer exists.

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-19*
