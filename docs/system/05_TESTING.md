# Testing Strategy

Status: Current

> The engine is tested with `unittest` across offline research, streaming persistence, candle-close runtime, artifact validation, and replay. Runtime/offline parity has unit coverage, but sustained real-feed parity and edge validation remain open.

---

## Running the Tests

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
```

Import `engine` before pandas in any ad-hoc script; see the Windows LightGBM caveat below.

The current suite includes 167 tests. Use the actual output from the current checkout as the source of truth when reporting the count.

---

## Coverage by File

| File | Tests | Covers |
|------|-------|--------|
| `test_config.py` | Configuration defaults, schema validation, runtime/stream settings |
| `test_store.py` | File contracts, duplicate preservation, stable ordering, point-in-time lookups |
| `test_timeframes.py`, `test_profile.py` | Candle boundaries, gaps, profile calculations |
| `test_sampler.py`, `test_features.py`, `test_labels.py` | Candle-close snapshots, feature causality/versioning, labels |
| `test_models.py`, `test_router.py`, `test_backtest.py`, `test_reports.py` | Training, calibration, deterministic routing, held-out replay, reports |
| `test_stream.py` | Sequencing, event/candle persistence, recovery, late events, storage failures |
| `test_runtime.py`, `test_replay.py` | Artifact validation, runtime decisions/gates/journals, replay parity |
| `test_execution.py`, `test_receiver.py` | Paper broker and receiver contracts |
| `test_docs.py`, `test_hooks.py` | Documentation checker and hook installation |

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
| Sustained live-to-offline parity | Runtime/replay tests cover mechanics; no sustained independent real-feed run has been validated |
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
- [ ] Version strings match the current contract: `amt-v4`, `core16-v2`, `snapshot-horizon-v1`, `1m-clock-v1`, `candle-close-v1`, `joblib-v1`.
- [ ] No doc claims broker execution, a learned selector, or multi-instrument support.
- [ ] Counts quoted in docs (test totals, column counts) match a fresh run.

The checker validates structure, not truth. A doc can pass every check and still describe behaviour that no longer exists.

### Pre-commit hook

The checker is wired into git through a versioned hook, so a stale doc cannot be committed by accident:

```powershell
.\.venv\Scripts\python.exe tools\install_hooks.py
.\.venv\Scripts\python.exe tools\install_hooks.py --status
```

| Piece | Location | Purpose |
|-------|----------|---------|
| Hook | `.githooks/pre-commit` | Runs `tools/check_docs.py` before every commit |
| Installer | `tools/install_hooks.py` | Points the repository-local `core.hooksPath` at `.githooks/` |
| Tests | `tests/test_hooks.py` | Hook contents and installer behaviour |

The hook calls the checker directly rather than `runner.py`, so it needs only the standard library and still works when LightGBM or the rest of the virtual environment is broken. It never modifies files. A failed check exits `1` and prints the offending paths; `git commit --no-verify` bypasses it once, which is meant for emergencies only.

Setting `IQBOT_PRECOMMIT_TESTS=1` makes the hook run the full unit suite after the documentation check. That is off by default because the suite takes several seconds and is better run deliberately.

The hook is not a CI replacement. It only runs on machines where `tools/install_hooks.py` has been executed, and it can be bypassed.

---

## Related Documentation

- [Components](02_COMPONENTS.md)
- [Runtime and entry point](11_RUNTIME_AND_ENTRYPOINT.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-21*
