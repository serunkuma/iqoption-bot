# PoC Validation — 2026-11-18

Status: Historical
Date: 2026-11-18

> Research note. This records what was observed while validating the tick-capture proof of concept and what remains unproven. It is not current system documentation.

---

## What Was Tested

A manual end-to-end run of the current capture path:

```text
IQ Option Traderoom (browser)
    -> chrome-extension/inject.js
    -> chrome-extension/content.js
    -> ws://localhost:8765
    -> receiver.py console output
```

The receiver was started locally, the unpacked extension was loaded in Chrome, and an IQ Option page was opened and left running.

---

## Observations

| Observation | Result |
|-------------|--------|
| Extension connects to the local receiver | Passed — the receiver logged the client connection |
| Frames arrive continuously while the page is open | Passed |
| Prices in the console track the platform | Passed — manually compared against the Traderoom chart |
| Multiple instruments appear | Passed — separate `active_id` values appeared |
| OHLCV-shaped fields are present | Passed — `open`, `close`, `min`, `max`, `volume`, `at`, `interval` observed |
| Asset names resolve from `asset_names.json` | Partially — unmapped `active_id` values showed as `unmapped` |
| Malformed frames are ignored | Passed — no crash on unexpected frames |

---

## What Was Not Tested

- Long-running stability across a full session.
- Behaviour across broker disconnects, browser sleep, and reconnects.
- Whether the extension queue dropped messages during a disconnect.
- Whether `at` is a tick time, a candle start, or another server timestamp.
- Whether the intercepted frame is a raw tick, a partial-candle update, or a completed candle.
- Whether repeated identical prices represent genuine observations.
- Message rate per `active_id` under different volatility conditions.
- Weekend OTC behaviour versus weekday behaviour.

---

## Interpretation

The PoC proves the capture path works: browser WebSocket messages can be intercepted, forwarded locally, validated, and logged.

It does **not** prove that:

- The stream is complete or correctly ordered.
- The stream can be turned into clean 1-minute candles yet.
- Tick density is a valid TPO proxy for these instruments.
- Any AMT or ML edge exists.

The next step is Phase 1 hardening, not modelling. See [Phase 1](../planning/phase-1-tick-capture-hardening.md).

---

## Follow-Ups

1. Capture a raw sample and document every field that appears.
2. Verify `at` semantics and units.
3. Add `received_at` and persist raw frames.
4. Add quality counters and gap tracking.
5. Fix the README wording that described the in-memory buffer as candle history.

---

## Related Documentation

- [Tick stream contract](../data/01_TICK_STREAM.md)
- [System overview](../system/01_OVERVIEW.md)
- [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)
- [Interview transcript](../../sources/INTERVIEW_TRANSCRIPT.md)

---

*Last updated: 2026-11-18*
