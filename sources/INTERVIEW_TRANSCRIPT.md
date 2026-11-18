# Interview Transcript — Documentation Migration

Status: Historical
Date: 2026-11-18
Source: Conversation between the project owner and the documentation agent.
Purpose: Preserve the decisions and open questions that shaped the initial docs.

> This is a structured transcript, not a verbatim token-by-token recording. The raw AMT input is preserved separately in [`AMT_ML_DISCUSSION.md`](AMT_ML_DISCUSSION.md).

---

## 1. Starting point

**Agent:** Read the existing repository and the `docs-driven/` scaffold.

**Owner:** The repository contains a proof of concept: a Chrome extension captures IQ Option browser WebSocket messages and a local Python receiver logs them. The goal is to grow this into a full IQ Option trading bot and make the repository documentation-driven.

**Decision:** Use `docs-driven/` as the staging scaffold. Fill it with project-specific documentation first, then merge the docs into the repository root, then delete `docs-driven/`.

---

## 2. Current capability

**Owner:** The receiver console showed live ticks that were correct. The current state is a proof of concept, not a candle-generation pipeline.

**Decision:** Document the current system as a **live tick-capture proof of concept**:

- The browser extension captures live price updates.
- `receiver.py` receives, buffers, and logs them.
- Candle aggregation, persistence, analytics, signals, risk, and execution are future work.

---

## 3. Candles

**Owner:** Candles are a future event. Candles are made from ticks. Our candles will be 1 minute.

**Decision:** Document three distinct layers:

1. Incoming tick/price-update stream (current).
2. 1-minute OHLCV candles built from ticks (planned).
3. AMT features and ML models built on top of ticks and candles (planned).

The current `candle-generated` message-name filter is a proof-of-concept implementation detail to verify. It must not be confused with the project's own candle layer.

---

## 4. Auction Market Theory input

**Owner:** Provided a written AMT/ML discussion from another AI conversation. The intent is to turn part of it into documentation, not to copy it verbatim into the main docs.

**Decision:** Preserve the raw input in `sources/AMT_ML_DISCUSSION.md` and synthesize project-specific docs:

- Concepts: AMT philosophy and the OTC feed caveat.
- Data: tick-density/TPO, Value Area, AMT features, labels/payouts.
- System: data pipeline, ML pipeline, model validation.
- Research: AMT-on-OTC reality check.
- Planning: phases and backlog.

---

## 5. Defaults accepted for the initial documentation

- A tick is a live price update received through the extension, not an exchange trade print.
- The payload `volume` field is not trusted as traded volume.
- 1-minute candles will be clock-aligned to UTC minute boundaries.
- Candle volume will be tick count, with untrusted payload volume stored separately if needed.
- TPO/Value Area features will be computed from ticks.
- Labels will be computed from 1-minute candles at the expiry horizon.
- AMT-on-OTC is a hypothesis with an explicit validation gate.
- Approach A (two-stage regime architecture) is the primary ML design.
- Approach B (AMT-penalized loss) is research-only until the baseline is proven.
- A rule-based AMT baseline should precede ML.
- The first execution work will be paper/demo only.

---

## 6. Open questions

- What are the exact semantics of the `at` field?
- Is the intercepted frame a raw tick, a partial-candle update, or a completed-candle event?
- Which instrument(s) and expiry durations are first?
- Is payout data available from the feed or platform?
- Is a live spot FX feed available for comparison?
- Which model library should be primary?
- What is the eventual order-execution route?
- What are the risk limits and kill-switch rules?

---

*Last updated: 2026-11-18*
