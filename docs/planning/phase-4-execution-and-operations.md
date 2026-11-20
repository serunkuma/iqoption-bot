# Phase 4 — ML Runtime, Execution, and Operations

Status: Planning

> **Objective:** Add validated runtime ML inference and signal selection, then paper execution, hard risk controls, monitoring, and operational procedures. Demo/live execution is a separate, explicit decision.

> **State:** An in-process paper broker and offline backtest replay exist. There is no runtime feature/model loop, learned signal selector, live paper loop, demo adapter, complete risk layer, or kill switch.

---

## Scope

- Paper trading first.
- Runtime model loading and inference, using a versioned `.joblib` artifact.
- Evaluate a learned direction/horizon/no-trade selector against the existing deterministic EV router.
- Shadow predictions before any paper orders; retain deterministic payout/risk/execution hard gates.
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

### Runtime inference and selection

- [ ] Define the selector's outcome target, candidate inputs, and model scope.
- [ ] Define a versioned `.joblib` artifact and compatibility manifest, including ordered feature and target versions.
- [ ] Load only an explicitly selected, trusted artifact; verify compatibility before inference.
- [ ] Fail closed for ML proposals when the configured artifact is missing or incompatible; report an explicit diagnostic.
- [ ] Build live feature values from the same causal, versioned contract used for training.
- [ ] Run the learned selector in shadow mode and compare decisions with the current EV router on the same incoming snapshots.
- [ ] Promote to live paper only after a predeclared validation gate passes; do not train or replace the active model silently during a session.
- [ ] Log model/artifact version, feature version, selector output, deterministic gates, and abstention reasons.

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
- Versioned runtime model loader and learned-selector evaluation.
- Live feature/inference shadow and paper loop.
- Demo execution adapter.
- Risk manager and kill switch.
- Trade journal.
- Monitoring and alerts.
- Tested runbook.
- Live readiness decision.

---

## Acceptance Criteria

- [ ] Paper mode runs for a sustained period without manual intervention.
- [ ] Runtime rejects incompatible artifacts and fails closed with a visible diagnostic.
- [ ] Runtime feature vectors match the training schema and feature order.
- [ ] Learned selector beats or is rejected against the current EV-router baseline on untouched chronological data and independent captures.
- [ ] Shadow and paper outcomes are auditable and consistent with offline replay within predeclared tolerances.
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
- [ML Runtime and Signal Selection](ml-runtime-and-signal-selection.md)
- [RUNBOOK](../../RUNBOOK.md)
- [Limitations and backlog](../system/10_LIMITATIONS_AND_BACKLOG.md)

---

*Last updated: 2026-11-20*
