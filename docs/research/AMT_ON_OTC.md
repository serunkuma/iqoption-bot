# AMT on OTC — Reality Check

Status: Planning

> Research note. This document records why AMT on an OTC binary-option feed is a hypothesis, not an established edge, and what must be tested before execution work.

---

## Context

Auction Market Theory was developed for markets with observable volume and order-book depth. This project receives broker-originated price updates from a browser WebSocket. It has no trusted volume and no Level 2 data.

The project uses tick density as a Time-Price Opportunity proxy. That is a reasonable approximation for market-profile analysis, but it does not recreate a real auction.

---

## Comparison

| AMT component | Real exchange (futures / spot ECN) | OTC binary-option feed |
|---------------|-------------------------------------|-------------------------|
| Price discovery | Real buyers and sellers negotiate fair value | Broker's internal pricing algorithm |
| Volume / POC | True contracts or lots traded at each price | Approximated by tick count only |
| Liquidity gaps | Real thin order books create genuine jumps | Artificial jumps or flat lines may be injected |
| Edge sustainability | Institutions genuinely trade around VAH/VAL/POC | Broker engines have no real inventory to balance |

---

## What This Means for Features

| Feature | Confidence on OTC | Caveat |
|---------|-------------------|--------|
| POC / VAH / VAL | Medium | Tick density is a proxy, not volume |
| Normalised distance to value | Medium | Depends on a stable volatility estimate |
| Excess / single prints | Low–medium | Broker price updates may not reflect rejection |
| Initiative vs responsive | Low–medium | Tick velocity may reflect feed behaviour, not aggression |
| Regime gating | Medium | Useful even if the underlying mechanism is synthetic |
| Payout-aware EV | High | Arithmetic, independent of the feed |

The features are still testable. The interpretation must remain cautious.

---

## Hypothesis

> The broker's synthetic price process may reproduce enough auction-like microstructure that tick-density value areas and initiative/responsive behaviour have out-of-sample predictive value for 1-minute binary outcomes.

This is a hypothesis about the broker's algorithm, not a claim about real market microstructure.

### Sub-hypotheses

1. Value-area boundaries act as short-horizon support/resistance in OTC data.
2. Tick-velocity breakouts have continuation probability above the payout breakeven.
3. Rejection tails at value-area edges have mean-reversion probability above the payout breakeven.
4. Weekday OTC behaviour differs from weekend behaviour.
5. The effect, if present, is stable enough to survive walk-forward validation.

---

## Validation Plan

1. Capture a clean tick dataset with verified timestamps.
2. Build 1-minute candles and AMT features.
3. Implement the rule-based AMT baseline.
4. Measure out-of-sample EV against payout breakeven.
5. Compare weekday and weekend subsets.
6. Compare with live spot FX if available.
7. Run walk-forward validation across multiple folds.
8. Check calibration and drift.
9. Apply the go/no-go gate in [Model Validation](../system/09_MODEL_VALIDATION.md).

---

## Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Overfitting to broker quirks | Model fails when the broker changes | Walk-forward validation; drift monitoring; small position sizes |
| Synthetic weekend regime | Weekday model fails on weekends | Weekend flag; separate evaluation; no weekend trading initially |
| Tick-density bias | POC/VA misestimated | Dedupe rules; compare multiple bin sizes; sensitivity analysis |
| Timestamp ambiguity | Causal features are wrong | Verify `at`; use receipt time; replay tests |
| Payout changes | EV gate invalid | Record payout with each trade; re-evaluate |
| Platform/legal restrictions | Account or legal risk | Review terms and jurisdiction before live trading |
| No real edge | Losses | Fail the gate and stop; do not force a model |

---

## Decision

- AMT is a research direction, not an approved trading strategy.
- Approach A is the primary architecture.
- A rule-based baseline is required before ML.
- No live execution until the validation gate passes.

---

## Related Documentation

- [Auction Market Theory](../concepts/05_AUCTION_MARKET_THEORY.md)
- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Model Validation](../system/09_MODEL_VALIDATION.md)
- [AMT reference implementation review](AMT_REFERENCE_IMPLEMENTATION_2026-11-18.md)

---

*Last updated: 2026-11-18*
