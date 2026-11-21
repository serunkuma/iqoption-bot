# Phase 1 — Tick Capture Hardening

Status: Current

> **Objective:** Turn the live tick-capture proof of concept into a trustworthy ingestion layer with a verified contract, persistence, quality metrics, and configuration.

> **State:** The stream store persists sequenced events and finalized candles in hourly Parquet parts, with state recovery and replay checks. Frame semantics and real-feed quality remain open. The earlier daily JSONL design below is historical; current stream behavior is specified in [Streaming Runtime and Store](../system/16_STREAMING_RUNTIME_AND_STORE.md).

---

## Scope

- Verify what one intercepted frame actually represents.
- Record receipt time and event time.
- Persist accepted event records and finalized candles.
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

- [x] Persist sequenced events in hourly Parquet parts.
- [x] Record `received_at`, `active_id`, `price`, sequence, and the raw payload.
- [x] Persist finalized candles and recover stream state.
- [ ] Record `session_id` and `connection_id`.
- [x] Add file-based build/diagnose and persisted-stream candle replay.
- [ ] Add retention and disk-usage policy.

### Data quality

- [x] Count duplicate timestamp/price pairs and out-of-order rows in file diagnostics; preserve events.
- [x] Reject naive timestamps, non-numeric prices, and non-positive prices.
- [ ] Count received, accepted, rejected, malformed, and late frames at the receiver.
- [x] Add duplicate counting without deduplication.
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
- Hourly event/candle Parquet parts with state recovery (implemented).
- File-based offline build plus streaming-event candle replay (implemented).
- Duplicate/file diagnostics and streaming gap/late-event counters are implemented; richer receiver-level metrics remain open.
- `config/default.toml` and validation (done).
- Expanded tests (done).
- Updated docs (done).

---

## Acceptance Criteria

- [ ] The meaning of one frame is documented and agreed.
- [ ] `at` semantics are documented.
- [x] A stream-store restart recovers persisted sequence/state; rolling features warm up again.
- [x] Persisted events can be replayed to compare rebuilt and recorded candles.
- [ ] Duplicate, gap, and late-tick counts are visible at capture time.
- [ ] Configuration changes do not require code edits.
- [x] Tests cover malformed and edge-case frames.
- [x] Documentation distinguishes persisted streaming candles from offline rebuilt snapshots.

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

*Last updated: 2026-11-21*
