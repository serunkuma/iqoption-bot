# Phase 4 — Execution and Operations

Status: Planning

> **Objective:** Add paper/demo execution, hard risk controls, monitoring, and operational procedures. Live execution is a separate, explicit decision.

> **State:** An in-process paper broker and backtest replay exist. There is no live paper loop, no demo adapter, no risk layer, and no kill switch.

---

## Scope

- Paper trading first.
- Demo-account execution second.
- Risk manager and kill switch.
- Trade journal.
- Monitoring and alerts.
- Operational runbook.
- Live readiness review.

---

## Tasks

### Paper trading

- [x] Implement an in-process paper broker.
- [x] Simulate entry, expiry, outcome, and PnL.
- [x] Enforce a one-open-trade limit.
- [x] Void ties instead of mapping them to a direction.
- [x] Replay the paper broker over held-out probabilities.
- [ ] Implement a live paper loop that consumes new snapshots.
- [ ] Persist every paper trade and its reason from the live loop.
- [ ] Compare live paper results with offline backtest results.

### Demo execution

- [ ] Implement the demo execution adapter.
- [ ] Add order idempotency keys.
- [ ] Handle rejection, timeout, and partial states.
- [ ] Record the broker's response.
- [ ] Reconcile expected and actual outcomes.

### Risk

- [x] Implement a fixed stake.
- [x] Implement a maximum open-trade count.
- [ ] Implement a maximum stake policy beyond a single value.
- [ ] Implement a daily loss limit.
- [ ] Implement a maximum consecutive-loss limit.
- [ ] Implement exposure limits.
- [ ] Implement a manual kill switch.
- [ ] Fail closed on data-quality or model-version problems.
- [ ] Reject martingale or loss-doubling strategies unless explicitly configured with limits.

### Journal and audit

- [x] Provide a JSONL trade journal writer.
- [ ] Wire the journal into the backtest and the live loop.
- [ ] Persist signals, risk decisions, orders, fills, outcomes, and PnL.
- [ ] Record model and feature versions per trade.
- [ ] Record payout and expiry per trade.
- [ ] Support audit and replay.

### Monitoring

- [ ] Add a health check.
- [ ] Add metrics for tick rate, gaps, rejects, latency, signals, orders, and PnL.
- [ ] Add alerts for data loss, model drift, and loss limits.
- [ ] Add a dashboard or log summary.

### Operations

- [ ] Complete the RUNBOOK with start, stop, restart, and troubleshooting for every command.
- [ ] Test the runbook end to end.
- [ ] Define backup and retention.
- [ ] Define incident response.
- [ ] Conduct a live readiness review.
- [ ] Document legal and platform-term review.

---

## Deliverables

- Paper execution adapter.
- Demo execution adapter.
- Risk manager and kill switch.
- Trade journal.
- Monitoring and alerts.
- Tested runbook.
- Live readiness decision.

---

## Acceptance Criteria

- [ ] Paper mode runs for a sustained period without manual intervention.
- [ ] Paper results are consistent with offline backtests.
- [ ] Demo mode handles wins, losses, ties, rejections, and timeouts.
- [ ] Risk limits stop trading at the configured thresholds.
- [ ] The kill switch stops new orders immediately.
- [ ] Every trade is auditable.
- [ ] Monitoring detects a simulated data gap and a simulated loss-limit breach.
- [ ] The runbook is tested by someone other than the author.
- [ ] Live execution is explicitly approved or explicitly deferred.

---

## Dependencies

- Phase 3 go/no-go gate passed.
- Demo account and execution access, if demo mode is pursued.
- Documented risk limits.

---

## Related Documentation

- [Execution and resolution](../system/14_EXECUTION_AND_RESOLUTION.md)
- [Security and Safety](../system/06_SECURITY.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [RUNBOOK](../../RUNBOOK.md)
- [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-19*
