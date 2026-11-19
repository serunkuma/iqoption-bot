# Phase 1 — Tick Capture Hardening

Status: Current

> **Objective:** Turn the live tick-capture proof of concept into a trustworthy ingestion layer with a verified contract, persistence, quality metrics, and configuration.

> **State:** Persistence, dedupe, ordering, parsing validation, and engine configuration are implemented. Frame semantics and receiver-level quality counters remain open.

---

## Scope

- Verify what one intercepted frame actually represents.
- Record receipt time and event time.
- Persist raw frames.
- Add data-quality checks and counters.
- Replace hard-coded constants with configuration.
- Expand tests.
- Correct documentation terminology.

Out of scope: candle aggregation, AMT features, ML, execution.

---

## Tasks

### Contract and timestamps

- [ ] Capture a representative raw sample of frames.
- [ ] Document every field that appears.
- [x] Decide the timestamp: one local receipt time per tick.
- [x] Stamp `received_at` on every accepted frame.
- [x] Document the timestamp decision in [Tick Stream Contract](../data/01_TICK_STREAM.md).
- [ ] Confirm that `at` can stay ignored without losing information.
- [ ] Confirm whether a frame is a tick or a partial candle by comparing `close` with subsequent prices.

### Persistence

- [x] Add append-only JSONL capture with daily rotation.
- [x] Record `received_at`, `active_id`, `price`, and the raw payload.
- [ ] Record `session_id` and `connection_id`.
- [x] Add a replay path: `build --input <jsonl>`.
- [ ] Add retention and disk-usage policy.

### Data quality

- [x] Count duplicates and out-of-order rows at build time.
- [x] Reject naive timestamps, non-numeric prices, and non-positive prices.
- [ ] Count received, accepted, rejected, malformed, and late frames at the receiver.
- [x] Add duplicate detection.
- [x] Add out-of-order detection.
- [ ] Add gap and reconnect records.
- [ ] Add per-`active_id` message-rate tracking.
- [ ] Expose counts in logs or a metrics endpoint.

### Configuration

- [x] Add `config/default.toml`.
- [x] Validate configuration at startup.
- [ ] Support environment overrides.
- [ ] Move host, port, buffer size, data directory, log level, and asset-map path out of the receiver module.
- [x] Add `.env` and local data paths to `.gitignore`.

### Code quality

- [ ] Add structured logging.
- [x] Add tests for malformed frames, missing fields, duplicates, and invalid asset maps.
- [ ] Add an integration test that starts the receiver and sends multiple frames.
- [ ] Add a basic health check.
- [x] Document extension queue-loss behaviour.

### Documentation

- [x] Correct the README wording from "candle history" to "raw tick buffer".
- [x] Update the system overview with verified findings.
- [ ] Record the sample session in `docs/research/`.
- [x] Update `AGENTS.md` with decisions made.

---

## Deliverables

- Verified tick contract (partial).
- JSONL raw tick log (done).
- Replay path via `build --input` (done).
- Quality counters (build-time done, capture-time open).
- `config/default.toml` and validation (done).
- Expanded tests (done).
- Updated docs (done).

---

## Acceptance Criteria

- [ ] The meaning of one frame is documented and agreed.
- [ ] `at` semantics are documented.
- [x] A receiver restart does not lose previously captured ticks.
- [ ] A JSONL capture can be replayed to produce the same accepted/rejected counts.
- [ ] Duplicate, gap, and late-tick counts are visible at capture time.
- [ ] Configuration changes do not require code edits.
- [x] Tests cover malformed and edge-case frames.
- [x] Documentation no longer implies candles already exist.

---

## Dependencies

- None. This is the foundation phase.

---

## Related Documentation

- [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)
- [Tick stream contract](../data/01_TICK_STREAM.md)
- [Runtime and entry point](../system/11_RUNTIME_AND_ENTRYPOINT.md)
- [System overview](../system/01_OVERVIEW.md)
- [Testing strategy](../system/05_TESTING.md)

---

*Last updated: 2026-11-19*
