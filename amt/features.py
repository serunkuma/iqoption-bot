"""Causal AMT feature construction, one row per accepted tick.

Design:

- The profile and ``sigma_7`` come from the last ``macro_candles`` completed
  candles. They are constant within the forming candle.
- The forming candle contributes current price, tick rate, price speed, and
  range, but never enters the profile until it completes.
- The ``fast_candles`` window provides the fast layer used for ratios.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import Config
from .profile import Profile, build_profile
from .timeframes import Candle, Tick, completed_window, group_candles, window_has_gap

FEATURE_COLUMNS = (
    "tick_id",
    "timestamp",
    "active_id",
    "price",
    "feature_version",
    "poc",
    "vah",
    "val",
    "profile_ticks",
    "sigma_7",
    "z_poc",
    "z_vah",
    "z_val",
    "inside_va",
    "va_width_norm",
    "poc_position",
    "edge_proximity",
    "excess_high",
    "excess_low",
    "excess_asymmetry",
    "tail_length_high",
    "tail_length_low",
    "tick_rate_7",
    "tick_rate_3",
    "tick_rate_forming",
    "price_change_7",
    "price_change_3",
    "price_change_forming",
    "price_speed_7",
    "price_speed_3",
    "price_speed_forming",
    "range_7",
    "range_3",
    "range_forming",
    "range_speed_7",
    "range_speed_3",
    "range_speed_forming",
    "tick_rate_3_7",
    "tick_rate_forming_3",
    "price_speed_3_7",
    "price_speed_forming_3",
    "range_3_7",
    "range_forming_3",
    "time_sin",
    "time_cos",
    "day_of_week",
    "is_weekend",
    "profile_missing",
    "volatility_missing",
    "insufficient_ticks",
    "gap_in_window",
)


@dataclass(frozen=True)
class LayerStats:
    tick_count: int
    duration_seconds: float
    first_price: float
    last_price: float
    high: float
    low: float

    @property
    def tick_rate(self) -> float | None:
        return _safe_div(self.tick_count, self.duration_seconds)

    @property
    def price_change(self) -> float:
        return self.last_price - self.first_price

    @property
    def price_speed(self) -> float | None:
        return _safe_div(abs(self.price_change), self.duration_seconds)

    @property
    def price_range(self) -> float:
        return self.high - self.low

    @property
    def range_speed(self) -> float | None:
        return _safe_div(self.price_range, self.duration_seconds)


@dataclass(frozen=True)
class CompletedContext:
    macro: LayerStats | None
    fast: LayerStats | None
    profile: Profile | None
    sigma: float | None
    window_ticks: int
    gap: int


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _layer_stats(
    ticks: list[Tick],
    candles: list[Candle],
    start: int,
    end: int,
    indices: list[int],
) -> LayerStats:
    duration = candles[end].start_epoch - candles[start].start_epoch
    prices = [ticks[index].price for index in indices]
    return LayerStats(
        tick_count=len(indices),
        duration_seconds=duration,
        first_price=prices[0],
        last_price=prices[-1],
        high=max(prices),
        low=min(prices),
    )


def _window_indices(candles: list[Candle], start: int, end: int) -> list[int]:
    indices: list[int] = []
    for index in range(start, end):
        indices.extend(candles[index].tick_indices)
    return indices


def _sigma(prices: list[float], min_changes: int) -> float | None:
    if len(prices) < min_changes + 1:
        return None
    values = np.asarray(prices, dtype=float)
    changes = np.diff(values)
    if changes.size < min_changes:
        return None
    sigma = float(changes.std(ddof=1)) if changes.size > 1 else 0.0
    if not math.isfinite(sigma) or sigma <= 0:
        return None
    return sigma


def _completed_context(
    ticks: list[Tick],
    candles: list[Candle],
    current_index: int,
    config: Config,
) -> CompletedContext:
    if current_index == 0:
        return CompletedContext(None, None, None, None, 0, 0)

    macro_start, macro_end = completed_window(
        candles, current_index, config.context.macro_candles
    )
    fast_start, fast_end = completed_window(
        candles, current_index, config.context.fast_candles
    )

    macro_indices = _window_indices(candles, macro_start, macro_end)
    fast_indices = _window_indices(candles, fast_start, fast_end)

    macro_stats = _layer_stats(ticks, candles, macro_start, macro_end, macro_indices)
    fast_stats = _layer_stats(ticks, candles, fast_start, fast_end, fast_indices)

    prices = [ticks[index].price for index in macro_indices]
    profile = build_profile(
        prices,
        bin_size=config.instrument.bin_size,
        value_area_target=config.context.value_area_target,
        tail_bins=config.context.tail_bins,
        single_print_max_ticks=config.context.single_print_max_ticks,
        min_ticks=config.context.profile_min_ticks,
        current_price=prices[-1],
    )

    sigma = _sigma(prices, config.context.volatility_min_changes)
    gap = int(window_has_gap(candles, macro_start, macro_end))

    return CompletedContext(
        macro=macro_stats,
        fast=fast_stats,
        profile=profile,
        sigma=sigma,
        window_ticks=len(prices),
        gap=gap,
    )


def _time_features(timestamp) -> tuple[float, float, int, int]:
    seconds = (
        timestamp.hour * 3600
        + timestamp.minute * 60
        + timestamp.second
        + timestamp.microsecond / 1_000_000
    )
    angle = 2 * math.pi * seconds / 86400
    day_of_week = timestamp.weekday()
    return math.sin(angle), math.cos(angle), day_of_week, int(day_of_week >= 5)


def _row(
    tick: Tick,
    tick_id: int,
    forming: LayerStats,
    context: CompletedContext,
    config: Config,
) -> dict:
    price = tick.price
    profile = context.profile
    sigma = context.sigma

    poc = profile.poc_price if profile is not None else None
    vah = profile.vah if profile is not None else None
    val = profile.val if profile is not None else None

    z_poc = _safe_div(price - poc, sigma) if poc is not None else None
    z_vah = _safe_div(price - vah, sigma) if vah is not None else None
    z_val = _safe_div(price - val, sigma) if val is not None else None

    if profile is None:
        inside_va = None
        va_width_norm = None
        poc_position = None
        edge_proximity = None
    else:
        inside_va = int(profile.val <= price <= profile.vah)
        va_width_norm = _safe_div(profile.vah - profile.val, sigma)
        poc_position = _safe_div(profile.poc_price - profile.val, profile.vah - profile.val)
        edge_proximity = _safe_div(
            min(price - profile.val, profile.vah - price), sigma
        )

    macro = context.macro
    fast = context.fast

    time_sin, time_cos, day_of_week, is_weekend = _time_features(tick.timestamp)

    min_ticks = config.context.profile_min_ticks

    return {
        "tick_id": tick_id,
        "timestamp": tick.timestamp.isoformat(),
        "active_id": tick.active_id,
        "price": price,
        "feature_version": config.feature_version,
        "poc": poc,
        "vah": vah,
        "val": val,
        "profile_ticks": context.window_ticks,
        "sigma_7": sigma,
        "z_poc": z_poc,
        "z_vah": z_vah,
        "z_val": z_val,
        "inside_va": inside_va,
        "va_width_norm": va_width_norm,
        "poc_position": poc_position,
        "edge_proximity": edge_proximity,
        "excess_high": profile.excess_high if profile is not None else None,
        "excess_low": profile.excess_low if profile is not None else None,
        "excess_asymmetry": profile.excess_asymmetry if profile is not None else None,
        "tail_length_high": profile.tail_length_high if profile is not None else None,
        "tail_length_low": profile.tail_length_low if profile is not None else None,
        "tick_rate_7": macro.tick_rate if macro is not None else None,
        "tick_rate_3": fast.tick_rate if fast is not None else None,
        "tick_rate_forming": forming.tick_rate,
        "price_change_7": macro.price_change if macro is not None else None,
        "price_change_3": fast.price_change if fast is not None else None,
        "price_change_forming": forming.price_change,
        "price_speed_7": macro.price_speed if macro is not None else None,
        "price_speed_3": fast.price_speed if fast is not None else None,
        "price_speed_forming": forming.price_speed,
        "range_7": macro.price_range if macro is not None else None,
        "range_3": fast.price_range if fast is not None else None,
        "range_forming": forming.price_range,
        "range_speed_7": macro.range_speed if macro is not None else None,
        "range_speed_3": fast.range_speed if fast is not None else None,
        "range_speed_forming": forming.range_speed,
        "tick_rate_3_7": _safe_div(
            fast.tick_rate if fast is not None else None,
            macro.tick_rate if macro is not None else None,
        ),
        "tick_rate_forming_3": _safe_div(
            forming.tick_rate,
            fast.tick_rate if fast is not None else None,
        ),
        "price_speed_3_7": _safe_div(
            fast.price_speed if fast is not None else None,
            macro.price_speed if macro is not None else None,
        ),
        "price_speed_forming_3": _safe_div(
            forming.price_speed,
            fast.price_speed if fast is not None else None,
        ),
        "range_3_7": _safe_div(
            fast.price_range if fast is not None else None,
            macro.price_range if macro is not None else None,
        ),
        "range_forming_3": _safe_div(
            forming.price_range,
            fast.price_range if fast is not None else None,
        ),
        "time_sin": time_sin,
        "time_cos": time_cos,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "profile_missing": int(profile is None),
        "volatility_missing": int(sigma is None),
        "insufficient_ticks": int(0 < context.window_ticks < min_ticks),
        "gap_in_window": context.gap,
    }


def build_features(
    ticks: list[Tick],
    config: Config,
    candles: list[Candle] | None = None,
) -> list[dict]:
    """Build one causal feature row per accepted tick."""

    if not ticks:
        return []

    if candles is None:
        candles = group_candles(ticks, config.candles.interval_seconds)

    rows: list[dict] = []
    tick_id = 0

    for candle_index, candle in enumerate(candles):
        context = _completed_context(ticks, candles, candle_index, config)

        forming_first: float | None = None
        forming_high = -math.inf
        forming_low = math.inf

        for position, tick_index in enumerate(candle.tick_indices):
            tick = ticks[tick_index]
            price = tick.price

            if forming_first is None:
                forming_first = price
            forming_high = max(forming_high, price)
            forming_low = min(forming_low, price)

            duration = max(tick.epoch - candle.start_epoch, 1.0)
            forming = LayerStats(
                tick_count=position + 1,
                duration_seconds=duration,
                first_price=forming_first,
                last_price=price,
                high=forming_high,
                low=forming_low,
            )

            rows.append(_row(tick, tick_id, forming, context, config))
            tick_id += 1

    return rows
