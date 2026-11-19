# Signal Router

Status: Current

> The router converts calibrated horizon probabilities into at most one actionable proposal, or a no-trade decision with a reason code. It never clamps a probability to force a trade.

---

## Contract

```python
route(probabilities: Mapping[int, float], config: Config) -> SignalProposal
```

`probabilities` maps a horizon in seconds to the calibrated probability that the exit price will be above the entry price — a Call.

The router knows the payout per horizon and the EV hurdle. It does not know the price, the instrument, or the state of the broker.

---

## Expected Value

For probability `q` and payout `p` (for example `0.80`):

```text
EV = q * (1 + p) - 1
```

A unit-stake binary option pays `+p` on a win and `-1` on a loss, so `EV = q*p - (1 - q)` is the same expression. The breakeven win rate is:

```text
q_breakeven = 1 / (1 + p)
```

At 80% payout the breakeven win rate is 55.6%.

---

## Candidate Generation

For every horizon present in the probability mapping:

1. Skip horizons that are not in `labels.horizons_seconds`.
2. Skip probabilities that are missing, negative, or above 1.
3. Skip horizons without a configured payout.
4. Emit a `call` candidate with `EV(q)`.
5. Emit a `put` candidate with `EV(1 - q)`.

Because `EV` is linear in `q`, exactly one of the two directions can clear a positive hurdle for a given horizon. Both candidates are still evaluated so the proposal can record the best available EV when nothing clears.

---

## Selection

```text
eligible = candidates with EV >= router.min_ev
```

Default `min_ev = 0.03`, i.e. a 3% expected return per unit stake after payout. The hurdle exists to absorb calibration error and model drift; it is not a rounding margin.

| `router.tie_break` | Rule |
|--------------------|------|
| `earliest_horizon` (default) | Shortest eligible horizon, then highest EV within it |
| `highest_ev` | Highest eligible EV, then shortest horizon |

`earliest_horizon` is the default because shorter expiries free capital sooner and overlap fewer later snapshots. With `max_open_trades = 1`, that matters.

No candidates at all → `no_trade_missing_payout`.
No eligible candidate → `no_trade_below_hurdle`, carrying the best candidate's horizon, probability, payout, and EV for audit.
Otherwise → `selected`.

---

## Reason Codes

| Code | Meaning |
|------|---------|
| `selected` | Actionable call or put |
| `no_trade_no_model` | No probabilities supplied |
| `no_trade_missing_payout` | No usable horizon/payout pair |
| `no_trade_below_hurdle` | Best candidate EV is below the hurdle |

`SignalProposal.actionable` is true only when `reason == "selected"` and the direction is `call` or `put`.

The no-trade proposal is explicit, not an empty result: it carries the best candidate's numbers so a report can explain why the engine stood down.

---

## Proposal Shape

| Field | Meaning |
|-------|---------|
| `horizon_seconds` | Selected horizon, or the best rejected one |
| `direction` | `call`, `put`, or `no_trade` |
| `probability` | Probability of the selected direction |
| `payout` | Payout used for the EV computation |
| `expected_value` | EV per unit stake |
| `reason` | Reason code |
| `candidates` | Every candidate considered, in generation order |

For a `put`, the stored probability is `1 - q`, so it always describes the chosen direction.

---

## What the Router Does Not Do

- It does not size the stake. Sizing is fixed by `execution.stake`.
- It does not check whether a trade is already open. `PaperBroker.can_open` owns that.
- It does not read prices, features, or the tick store.
- It does not blend horizons into a single score.
- It does not trade a horizon the model suite skipped.

Keeping the router pure means the backtest and any future live path apply exactly the same decision rule.

---

## Worked Example

`q = 0.60` at 60s with payout `0.80`:

```text
call EV = 0.60 * 1.80 - 1 = +0.08
put  EV = 0.40 * 1.80 - 1 = -0.28
```

`+0.08 >= 0.03`, so the router selects `call` at 60s with EV `0.08`.

`q = 0.56` at 180s with payout `0.86`:

```text
call EV = 0.56 * 1.86 - 1 = +0.0416
```

If no other horizon clears the hurdle, the proposal is `selected` at 180s. If the hurdle were `0.05`, the same input would return `no_trade_below_hurdle` with EV `0.0416`.

---

## Related Documentation

- [Model suite](12_MODEL_SUITE.md)
- [Execution and resolution](14_EXECUTION_AND_RESOLUTION.md)
- [Labels, payouts, and EV](../data/06_LABELS_PAYOUTS_AND_EV.md)
- [Configuration](03_CONFIGURATION.md)

---

*Last updated: 2026-11-19*
