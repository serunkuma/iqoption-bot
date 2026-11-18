# Testing Strategy

Status: Current

> This document describes the tests that exist today, how to run them, and the test layers required before the system can be trusted with trading logic.

---

## Current Tests

`test_receiver.py` uses `unittest` and covers:

1. Identity formatting when no local asset name is mapped.
2. Buffering and logging when a valid candle-shaped frame arrives.
3. Loading a valid `asset_names.json` file.

### Run

```powershell
.\.venv\Scripts\python.exe -m unittest -v test_receiver
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
- No load or soak test.

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
- A feature snapshot uses no tick with `received_at > decision_at`.

### Labels and EV

- A label never appears in its own feature row.
- Train/validation/test splits are chronological.
- Payout breakeven matches the formula.
- Ties are handled according to the configured policy.

### Execution

- Paper mode never calls a live endpoint.
- Live mode requires an explicit configuration flag.
- Every order has an idempotency key.
- The kill switch prevents new orders.

---

## Test Data

- Keep small, anonymised JSONL fixtures under `tests/fixtures/`.
- Include at least one session with gaps, duplicates, and out-of-order ticks.
- Include a fixture with multiple `active_id` values.
- Never commit real account identifiers or credentials.

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
