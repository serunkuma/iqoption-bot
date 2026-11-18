# Phase 1 — Tick Capture Hardening

Status: Planning

> **Objective:** Turn the live tick-capture proof of concept into a trustworthy ingestion layer with a verified contract, persistence, quality metrics, and configuration.

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
- [ ] Determine whether `at` is seconds or milliseconds.
- [ ] Determine whether `at` is a tick time, candle start, or server time.
- [ ] Decide whether `received_at` or `event_at` drives ordering.
- [ ] Document the timestamp decision in [Tick Stream Contract](../data/01_TICK_STREAM.md).

### Persistence

- [ ] Add append-only JSONL capture with rotation.
- [ ] Record `received_at`, `session_id`, `connection_id`, `active_id`, and raw frame.
- [ ] Add a replay script that reads JSONL and feeds the receiver logic.
- [ ] Add retention and disk-usage policy.

### Data quality

- [ ] Count received, accepted, rejected, malformed, duplicate, late, and stale frames.
- [ ] Add duplicate detection.
- [ ] Add out-of-order detection.
- [ ] Add gap and reconnect records.
- [ ] Add per-`active_id` message-rate tracking.
- [ ] Expose counts in logs or a metrics endpoint.

### Configuration

- [ ] Add `config/default.toml`.
- [ ] Support environment overrides.
- [ ] Validate configuration at startup.
- [ ] Move host, port, buffer size, data directory, log level, and asset-map path out of code.
- [ ] Add `.env` and local data paths to `.gitignore`.

### Code quality

- [ ] Add structured logging.
- [ ] Add tests for malformed frames, missing fields, duplicates, buffer eviction, and invalid asset maps.
- [ ] Add an integration test that starts the receiver and sends multiple frames.
- [ ] Add a basic health check.
- [ ] Document extension queue-loss behaviour.

### Documentation

- [ ] Correct the README wording from "candle history" to "raw tick buffer".
- [ ] Update the system overview with verified findings.
- [ ] Record the sample session in `docs/research/`.
- [ ] Update `AGENTS.md` with decisions made.

---

## Deliverables

- Verified tick contract.
- JSONL raw tick log.
- Replay script.
- Quality metrics and counters.
- `config/default.toml` and validation.
- Expanded tests.
- Updated docs.

---

## Acceptance Criteria

- [ ] The meaning of one frame is documented and agreed.
- [ ] `at` semantics are documented.
- [ ] A receiver restart does not lose previously captured ticks.
- [ ] A JSONL capture can be replayed to produce the same accepted/rejected counts.
- [ ] Duplicate, gap, and late-tick counts are visible.
- [ ] Configuration changes do not require code edits.
- [ ] Tests cover malformed and edge-case frames.
- [ ] Documentation no longer implies candles already exist.

---

## Dependencies

- None. This is the foundation phase.

---

## Related Documentation

- [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)
- [Tick stream contract](../data/01_TICK_STREAM.md)
- [System overview](../system/01_OVERVIEW.md)
- [Testing strategy](../system/05_TESTING.md)

---

*Last updated: 2026-11-18*
