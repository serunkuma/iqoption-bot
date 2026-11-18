# Phase 4 — Execution and Operations

Status: Planning

> **Objective:** Add paper/demo execution, hard risk controls, monitoring, and operational procedures. Live execution is a separate, explicit decision.

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

- [ ] Implement a paper execution adapter.
- [ ] Simulate entry, expiry, outcome, and PnL.
- [ ] Persist every paper trade and its reason.
- [ ] Compare paper results with offline backtest results.

### Demo execution

- [ ] Implement the demo execution adapter.
- [ ] Add order idempotency keys.
- [ ] Handle rejection, timeout, and partial states.
- [ ] Record the broker's response.
- [ ] Reconcile expected and actual outcomes.

### Risk

- [ ] Implement maximum stake.
- [ ] Implement daily loss limit.
- [ ] Implement maximum consecutive losses.
- [ ] Implement exposure limits.
- [ ] Implement a manual kill switch.
- [ ] Fail closed on data-quality or model-version problems.
- [ ] Reject martingale or loss-doubling strategies unless explicitly configured with limits.

### Journal and audit

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

- [ ] Complete the RUNBOOK with start, stop, restart, and troubleshooting.
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

- [Security and Safety](../system/06_SECURITY.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [RUNBOOK](../../RUNBOOK.md)
- [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-18*
