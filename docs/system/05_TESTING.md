# Testing Strategy

Status: Current

> This document describes the tests that exist today, how to run them, and the test layers required before the system can be trusted with trading logic.

---

## Current Tests

### Receiver

`test_receiver.py` uses `unittest` and covers:

1. Identity formatting when no local asset name is mapped.
2. Buffering and logging when a valid candle-shaped frame arrives.
3. Loading a valid `asset_names.json` file.

### AMT pipeline

`tests/` uses `unittest` and covers the offline `amt` package:

| File | Coverage |
|------|----------|
| `test_config.py` | Default config, unknown keys, window validation, horizon ordering |
| `test_data.py` | Sorting, exact dedupe, offset requirement, `active_id` mismatch, missing columns |
| `test_timeframes.py` | Minute bucketing, forming-candle exclusion, gap detection, sorted input |
| `test_profile.py` | Worked example, POC tie-breaks, bin edges, single bin, internal gap, insufficient ticks |
| `test_features.py` | One row per tick, null context, layer ratios, forming candle exclusion, causal prefix equality |
| `test_labels.py` | Exit selection, tolerance, ties, missing exits, multi-horizon output |

### Run

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_receiver
.\.venv\Scripts\python.exe -m unittest discover -s tests -t . -v
.\.venv\Scripts\python.exe -m amt.build --input data\ticks.csv
```

### Current Gaps

- No test for malformed JSON.
- No test for a frame without `msg`.
- No test for a frame without `active_id`.
- No test for buffer eviction at 500 entries.
- No test for reconnect behaviour in `content.js`.
- No test for the extension queue dropping the oldest message.
- No test for `load_asset_names` rejecting invalid files.
- No integration test that starts the receiver and sends multiple frames.
- No end-to-end test from live receiver to feature rows.
- No load or soak test.

---

## Documentation Checks

The previous `scripts/validate_scaffold.*` validators were scaffolding. Until CI is added, run this manual checklist after structural documentation changes:

1. Every `.md` file under `docs/` starts with a status label: `Status: Current`, `Status: Planning`, or `Status: Historical`.
2. Every link in `docs/index.md` resolves to an existing file.
3. No document links to `sources/` or `scripts/`.
4. `AGENTS.md`, `README.md`, and `RUNBOOK.md` agree on layout and commands.
5. Commands use the virtual environment path, not bare `python`.
6. Feature and label versions referenced in docs match `amt/config.py`.

Automate this with `tests/test_docs.py` when CI exists.

---

## Planned Test Layers

| Layer | Scope | Examples |
|-------|-------|----------|
| Unit | Pure functions and models | Asset validation, identity formatting, binning, POC, Value Area, labels, EV |
| Contract | Message schemas | Tick envelope, candle record, feature snapshot, signal |
| Integration | Receiver plus sender | Start receiver, send valid and invalid frames, assert counts and storage |
| Replay | Stored raw ticks | Rebuild candles and features from a fixed JSONL fixture |
| Property-based | Invariants | OHLC invariants, Value Area containment, no-lookahead windows |
| Load | Throughput and backpressure | Sustained message rate, queue behaviour, memory growth |
| Model validation | Offline research | Walk-forward splits, calibration, drift checks |
| End-to-end | Paper mode | Tick replay to signal to paper order to journal |

---

## Required Invariants

### Tick ingestion

- A malformed frame never reaches storage.
- A frame without `active_id` is rejected.
- Accepted frames always have `received_at`.
- Duplicate policy is deterministic.

### Candles

- `low <= open <= high`.
- `low <= close <= high`.
- `tick_count >= 1`.
- Bucket boundaries are 60 seconds.
- A finalized candle is not silently rewritten.

### TPO / Value Area

- `VAL <= POC <= VAH`.
- The value area contains at least the target share unless all bins are included.
- A profile with fewer than the minimum ticks is null, never synthesised.
- A feature snapshot uses no tick with a timestamp later than the decision tick.

### Labels and EV

- A label never appears in its own feature row.
- Train/validation/test splits are chronological.
- Payout breakeven matches the formula.
- A tie is never mapped to a directional label.
- A missing exit is never mapped to a directional label.
- Purge length covers the longest horizon plus tolerance.

### Execution

- Paper mode never calls a live endpoint.
- Live mode requires an explicit configuration flag.
- Every order has an idempotency key.
- The kill switch prevents new orders.

---

## Test Data

- Keep small, anonymised fixtures under `tests/fixtures/`.
- Include at least one session with gaps, duplicates, and out-of-order ticks.
- Never commit real account identifiers or credentials.
- Multi-instrument fixtures are deferred until multi-instrument support exists.

---

## Continuous Integration

Planned CI pipeline:

1. Install Python dependencies.
2. Run unit and contract tests.
3. Run replay tests on fixtures.
4. Run lint and type checks.
5. Upload coverage (target to be defined).
6. Fail on missing doc status labels or broken index links.

---

## Related Documentation

- [Tick stream contract](../data/01_TICK_STREAM.md)
- [1-minute candle aggregation](../data/03_CANDLE_AGGREGATION.md)
- [Model validation](09_MODEL_VALIDATION.md)
- [Limitations and backlog](10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-18*
