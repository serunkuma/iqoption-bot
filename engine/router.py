"""Confidence and expected-value router.

The router turns calibrated per-horizon probabilities into at most one
actionable proposal. It is deliberately conservative: below the EV hurdle it
returns an explicit no-trade with a reason code, never a clamped probability.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Mapping

from .config import Config

NO_MODEL = "no_trade_no_model"
MISSING_PAYOUT = "no_trade_missing_payout"
BELOW_HURDLE = "no_trade_below_hurdle"

#: Reason codes emitted by the router.
REASON_CODES = (NO_MODEL, MISSING_PAYOUT, BELOW_HURDLE, "selected")


@dataclass(frozen=True)
class Candidate:
    horizon_seconds: int
    direction: str
    probability: float
    payout: float
    expected_value: float


@dataclass(frozen=True)
class SignalProposal:
    horizon_seconds: int | None
    direction: str
    probability: float | None
    payout: float | None
    expected_value: float | None
    reason: str
    candidates: tuple[Candidate, ...] = field(default_factory=tuple)

    @property
    def actionable(self) -> bool:
        return self.direction in {"call", "put"} and self.reason == "selected"


def expected_value(probability: float, payout: float) -> float:
    """Expected profit per unit stake for a binary option."""

    return probability * (1.0 + payout) - 1.0


def breakeven_win_rate(payout: float) -> float:
    return 1.0 / (1.0 + payout)


def route(probabilities: Mapping[int, float], config: Config) -> SignalProposal:
    """Choose the single best (horizon, direction) or return no-trade.

    ``probabilities`` maps a horizon in seconds to the calibrated probability
    that the exit price will be above the entry price (a Call).
    """

    if not probabilities:
        return SignalProposal(None, "no_trade", None, None, None, NO_MODEL)

    horizon_set = set(config.labels.horizons_seconds)
    candidates: list[Candidate] = []

    for horizon in sorted(probabilities):
        probability = probabilities[horizon]
        if horizon not in horizon_set:
            continue
        if probability is None or not 0.0 <= probability <= 1.0:
            continue
        try:
            payout = config.router.payout(horizon)
        except Exception:
            continue
        candidates.append(
            Candidate(
                horizon_seconds=horizon,
                direction="call",
                probability=probability,
                payout=payout,
                expected_value=expected_value(probability, payout),
            )
        )
        candidates.append(
            Candidate(
                horizon_seconds=horizon,
                direction="put",
                probability=1.0 - probability,
                payout=payout,
                expected_value=expected_value(1.0 - probability, payout),
            )
        )

    if not candidates:
        return SignalProposal(None, "no_trade", None, None, None, MISSING_PAYOUT)

    eligible = [c for c in candidates if c.expected_value >= config.router.min_ev]
    if not eligible:
        best = max(candidates, key=lambda c: c.expected_value)
        return SignalProposal(
            best.horizon_seconds,
            "no_trade",
            best.probability,
            best.payout,
            best.expected_value,
            BELOW_HURDLE,
            tuple(candidates),
        )

    if config.router.tie_break == "earliest_horizon":
        # Prefer the shortest expiry once the EV hurdle is cleared. This keeps
        # capital free sooner and reduces overlap with later snapshots.
        best = min(
            eligible,
            key=lambda c: (c.horizon_seconds, -round(c.expected_value, 12)),
        )
    else:
        best = max(eligible, key=lambda c: (round(c.expected_value, 12), -c.horizon_seconds))

    return SignalProposal(
        best.horizon_seconds,
        best.direction,
        best.probability,
        best.payout,
        best.expected_value,
        "selected",
        tuple(candidates),
    )
