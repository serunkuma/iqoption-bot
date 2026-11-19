# Auction Market Theory — Design Philosophy

Status: Current

> This document explains why the project is pursuing Auction Market Theory (AMT), what AMT concepts mean here, and why AMT on an OTC binary-option feed must be treated as a hypothesis rather than an established edge.

---

## Why AMT

A naive price-pattern model asks, "What did price do last time?" An AMT-informed model asks a more structural question:

- Is the market **balanced** or **imbalanced**?
- Is price being **accepted** at a level, or **rejected** from it?
- Is activity **initiative** (breaking out with conviction) or **responsive** (fading an extension back toward value)?

That framing is useful because it separates market context from direction. The same candle pattern can mean different things inside a value area and outside it.

---

## Core Hypothesis

The project's working hypothesis has three context layers:

| Layer | Window | Role |
|-------|--------|------|
| Macro value | Last 7 completed 1-minute candles | Defines POC, VAH, VAL, and the volatility used to normalise distance |
| Fast context | Last 3 completed 1-minute candles | Shows whether recent activity is faster or slower than the macro window |
| Forming candle | Ticks in the current minute | Current price, tick rate, price speed, and range |

In one sentence: **time-at-price defines value, and the rate at which price leaves value separates initiative from responsive behaviour.**

Two consequences shape the whole design:

1. **Predictions are per tick.** Binary options allow entry at any moment, so every accepted tick is a potential decision point. The 60/90/120/180-second horizons are measured from that tick.
2. **Candles are context, not decisions.** Candles bucket the stream so the macro, fast, and forming layers can be compared. The forming candle contributes current activity but never enters the profile until it completes.

Activity is compared across the three layers rather than through fixed short windows: tick rate, price speed, and range for each layer, plus ratios between them.

---

## Core Concepts

| Concept | Meaning in this project |
|---------|-------------------------|
| Auction | The market's ongoing process of discovering a fair price |
| Value Area | The price range containing approximately 70% of recent activity |
| POC | Point of Control: the price bin with the most activity |
| VAH | Value Area High: upper edge of the value area |
| VAL | Value Area Low: lower edge of the value area |
| Balance | Rotational, two-sided trade inside the value area |
| Imbalance | Directional trade outside the value area |
| Acceptance | Price spends time and activity at a level |
| Rejection / excess | Price moves quickly through a level with little activity and leaves a tail |
| Initiative activity | Aggressive activity that breaks value and continues |
| Responsive activity | Activity that fades an extension and returns toward value |

---

## The Data Constraint

AMT was developed for auction markets with observable volume and order-book depth. This project does not have those inputs.

The feed provides:

- Price updates with one timestamp: the receiver's local receipt time.
- OHLCV-shaped payload fields.
- No trusted traded volume.
- No Level 2 depth.
- No guarantee that the broker's prices come from a real auction.

Therefore:

1. **Tick density is the volume proxy.** We count price updates per price bin, following Time-Price Opportunity (TPO) logic.
2. **The payload `volume` field is not used as traded volume.** It may be synthetic.
3. **The AMT model is a microstructure hypothesis**, not a claim that the broker is running a real auction.
4. **The OTC feed may change behaviour** between weekdays and weekends, or when the broker switches pricing modes.

---

## Mapping AMT to Features

The project translates AMT into measurable features:

| AMT idea | Feature family |
|----------|----------------|
| Where is value? | Rolling POC, VAH, VAL, value-area width |
| How far is price from value? | `Z_POC`, `Z_VAH`, `Z_VAL`, normalized by volatility |
| Was a level accepted or rejected? | Excess ratio, single-print tail count, tail length |
| Is activity initiative or responsive? | Tick rate, price speed, and range across macro, fast, and forming layers |
| Is the market balanced or imbalanced? | Regime gate from price position and layer activity |

Exact definitions live in [TPO and Value Area](../data/04_TPO_VALUE_AREA.md) and [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md).

---

## Regime-First Design (Research)

The leading hypothesis for improving on the shipped model splits the problem:

1. **Stage 1:** Determine whether the market is balanced or imbalanced.
2. **Stage 2:** Apply a conditional directional model:
   - Balance model: mean reversion toward POC.
   - Imbalance model: continuation with the breakout.

This is preferable in principle to a single model that mixes incompatible market states, but it is not implemented. It needs a validated regime rule and enough rows per regime to train and calibrate two models. The shipped pipeline is four independent horizon classifiers that already carry AMT features; a regime-gated version must beat it out of sample before it replaces it.

See [ML pipeline](../system/08_ML_PIPELINE.md) for the current architecture and the preconditions.

---

## OTC Reality Check

| AMT component | Real exchange | OTC binary-option feed |
|---------------|---------------|------------------------|
| Price discovery | Real buyers and sellers negotiate fair value | Broker's internal pricing algorithm |
| Volume / POC | True contracts or lots at each price | Tick-count proxy only |
| Liquidity gaps | Real thin books create genuine jumps | Artificial jumps or flat lines may be injected |
| Edge sustainability | Institutions genuinely defend value areas | Broker engines have no real inventory to balance |

Because the feed may be synthetic, an AMT model on OTC data is testing whether the broker's algorithm behaves like a real auction. That can be a real, exploitable pattern, but it is fragile and regime-dependent.

The project therefore requires:

- A rule-based AMT baseline before ML.
- Time-based, out-of-sample validation.
- Separate weekday and weekend evaluation.
- A go/no-go gate before any execution work.

See [AMT on OTC](../research/AMT_ON_OTC.md).

---

## Design Principles

1. **Causal by construction.** Every feature uses only data available at the decision time.
2. **Ticks first, candles second.** TPO/Value Area is computed from the macro tick window; candles provide context layers, not decision points.
3. **One definition per feature.** No duplicate formulas in code and docs.
4. **Payout-aware evaluation.** A model that is accurate but below the payout breakeven loses money.
5. **No silent data loss.** Gaps, duplicates, and reconnects are recorded, not hidden.
6. **No-trade is a valid output.** The system must be able to abstain.

---

## Related Documentation

- [TPO and Value Area](../data/04_TPO_VALUE_AREA.md)
- [AMT Feature Specification](../data/05_AMT_FEATURE_SPEC.md)
- [Labels, Payouts, and Expected Value](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [Model Inputs](../data/09_MODEL_INPUTS.md)
- [Data Pipeline](../system/07_DATA_PIPELINE.md)
- [ML Pipeline](../system/08_ML_PIPELINE.md)
- [AMT on OTC](../research/AMT_ON_OTC.md)

---

*Last updated: 2026-11-19*
