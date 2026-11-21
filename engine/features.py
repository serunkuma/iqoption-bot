"""Stateless feature engine.

The canonical entry point is :func:`compute_features`, which takes one validated
candle-close :class:`~engine.sampler.Snapshot` and returns the model input vector
plus diagnostic fields. The function has no state and no I/O, so the exact same
code runs in research and in live inference.

``core16-v2`` uses only completed candles. The four former forming-bar inputs now
read the last completed candle, so the runtime and the offline build share one
definition with no partial-bar state.

``build_diagnostic_table`` reproduces the older one-row-per-tick table for
exploratory work. It routes through ``compute_features`` so the two paths cannot
drift apart.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import numpy as np

from .config import Config
from .domain.profile import Profile, build_profile
from .domain.timeframes import Candle, Tick, group_candles
from .sampler import BarSlice, Snapshot

#: The sixteen inputs the horizon models consume, in fixed order.
CORE_FEATURES: tuple[str, ...] = (
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
    "tick_rate_3_7",
    "tick_rate_last_3",
    "price_speed_3_7",
    "price_speed_last_3",
    "range_last_3",
    "price_change_last",
)

DIAGNOSTIC_FEATURES: tuple[str, ...] = (
    "poc",
    "vah",
    "val",
    "profile_ticks",
    "sigma_7",
    "window_bars",
    "tail_length_high",
    "tail_length_low",
    "tick_rate_7",
    "tick_rate_3",
    "tick_rate_last",
    "price_change_7",
    "price_change_3",
    "price_change_last",
    "price_speed_7",
    "price_speed_3",
    "price_speed_last",
    "range_7",
    "range_3",
    "range_last",
    "range_speed_7",
    "range_speed_3",
    "range_speed_last",
    "range_3_7",
    "time_sin",
    "time_cos",
    "day_of_week",
    "is_weekend",
    "profile_missing",
    "volatility_missing",
    "insufficient_ticks",
    "gap_in_window",
)

FEATURE_COLUMNS: tuple[str, ...] = (
    "snapshot_id",
    "timestamp",
    "active_id",
    "price",
    "feature_version",
    "core_feature_version",
    "decision_version",
    *CORE_FEATURES,
    *DIAGNOSTIC_FEATURES,
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
class FeatureVector:
    """One model-ready observation plus its diagnostic fields."""

    core: dict[str, float | None]
    diagnostics: dict[str, float | None]

    def values(self) -> tuple[float | None, ...]:
        return tuple(self.core[name] for name in CORE_FEATURES)

    def as_list(self) -> list[float | None]:
        return list(self.values())

    def complete(self) -> bool:
        return all(value is not None for value in self.core.values())

    def row(
        self,
        *,
        snapshot_id: int,
        timestamp: datetime,
        active_id: int,
        price: float,
        config: Config,
    ) -> dict:
        row: dict = {
            "snapshot_id": snapshot_id,
            "timestamp": timestamp.isoformat(),
            "active_id": active_id,
            "price": price,
            "feature_version": config.feature_version,
            "core_feature_version": config.core_feature_version,
            "decision_version": config.decision_version,
        }
        row.update(self.core)
        row.update(self.diagnostics)
        return row


def _safe_div(numerator: float | None, denominator: float | None) -> float | None:
    if numerator is None or denominator is None or denominator <= 0:
        return None
    return numerator / denominator


def _layer_stats(prices: tuple[float, ...], duration: float) -> LayerStats | None:
    if not prices:
        return None
    values = np.asarray(prices, dtype=float)
    return LayerStats(
        tick_count=len(prices),
        duration_seconds=max(duration, 1e-9),
        first_price=float(values[0]),
        last_price=float(values[-1]),
        high=float(values.max()),
        low=float(values.min()),
    )


def _sigma(prices: np.ndarray, min_changes: int) -> float | None:
    if prices.size < min_changes + 1:
        return None
    changes = np.diff(prices)
    if changes.size < min_changes:
        return None
    sigma = float(changes.std(ddof=1))
    if not math.isfinite(sigma) or sigma <= 0:
        return None
    return sigma


def _time_features(
    timestamp: datetime, utc_offset_seconds: int = 0
) -> tuple[float, float, int, int]:
    local = timestamp.astimezone(timezone(timedelta(seconds=utc_offset_seconds)))
    seconds = (
        local.hour * 3600
        + local.minute * 60
        + local.second
        + local.microsecond / 1_000_000
    )
    angle = 2 * math.pi * seconds / 86400
    day_of_week = local.weekday()
    return math.sin(angle), math.cos(angle), day_of_week, int(day_of_week >= 5)


def _prices(bars: tuple[BarSlice, ...]) -> np.ndarray:
    return np.asarray(
        [price for bar in bars for price in bar.prices], dtype=float
    )


def compute_features(snapshot: Snapshot, config: Config) -> FeatureVector:
    """Compute the core vector and diagnostics for one candle-close snapshot."""

    interval = float(config.candles.interval_seconds)
    bars = snapshot.completed_bars
    macro_prices = _prices(bars)
    fast_bars = bars[-config.context.fast_candles :]
    fast_prices = _prices(fast_bars)

    last_bar = bars[-1] if bars else None
    last_prices = np.asarray(last_bar.prices, dtype=float) if last_bar else np.array([])

    macro_duration = (
        (bars[-1].start_epoch + interval) - bars[0].start_epoch if bars else 0.0
    )
    fast_duration = (
        (fast_bars[-1].start_epoch + interval) - fast_bars[0].start_epoch
        if fast_bars
        else 0.0
    )

    macro = _layer_stats(tuple(macro_prices.tolist()), macro_duration)
    fast = _layer_stats(tuple(fast_prices.tolist()), fast_duration)
    last = _layer_stats(tuple(last_prices.tolist()), interval)

    price = snapshot.price

    profile: Profile | None = (
        build_profile(
            macro_prices,
            bin_size=config.instrument.bin_size,
            value_area_target=config.context.value_area_target,
            tail_bins=config.context.tail_bins,
            single_print_max_ticks=config.context.single_print_max_ticks,
            min_ticks=config.context.profile_min_ticks,
            current_price=price,
        )
        if macro_prices.size
        else None
    )
    sigma = _sigma(macro_prices, config.context.volatility_min_changes)

    poc = profile.poc_price if profile else None
    vah = profile.vah if profile else None
    val = profile.val if profile else None

    z_poc = _safe_div(price - poc, sigma) if poc is not None and sigma else None
    z_vah = _safe_div(price - vah, sigma) if vah is not None and sigma else None
    z_val = _safe_div(price - val, sigma) if val is not None and sigma else None

    if profile is None:
        inside_va = None
        va_width_norm = None
        poc_position = None
        edge_proximity = None
    else:
        inside_va = int(profile.val <= price <= profile.vah)
        va_width_norm = _safe_div(profile.vah - profile.val, sigma)
        poc_position = _safe_div(
            profile.poc_price - profile.val, profile.vah - profile.val
        )
        edge_proximity = _safe_div(
            min(price - profile.val, profile.vah - price), sigma
        )

    macro_tick_rate = macro.tick_rate if macro else None
    fast_tick_rate = fast.tick_rate if fast else None
    last_tick_rate = last.tick_rate if last else None
    macro_price_speed = macro.price_speed if macro else None
    fast_price_speed = fast.price_speed if fast else None
    last_price_speed = last.price_speed if last else None

    time_sin, time_cos, day_of_week, is_weekend = _time_features(
        snapshot.snapshot_time, snapshot.utc_offset_seconds
    )

    core: dict[str, float | None] = {
        "z_poc": z_poc,
        "z_vah": z_vah,
        "z_val": z_val,
        "inside_va": inside_va,
        "va_width_norm": va_width_norm,
        "poc_position": poc_position,
        "edge_proximity": edge_proximity,
        "excess_high": profile.excess_high if profile else None,
        "excess_low": profile.excess_low if profile else None,
        "excess_asymmetry": profile.excess_asymmetry if profile else None,
        "tick_rate_3_7": _safe_div(fast_tick_rate, macro_tick_rate),
        "tick_rate_last_3": _safe_div(last_tick_rate, fast_tick_rate),
        "price_speed_3_7": _safe_div(fast_price_speed, macro_price_speed),
        "price_speed_last_3": _safe_div(last_price_speed, fast_price_speed),
        "range_last_3": _safe_div(
            last.price_range if last else None, fast.price_range if fast else None
        ),
        "price_change_last": last.price_change if last else None,
    }

    diagnostics: dict[str, float | None] = {
        "poc": poc,
        "vah": vah,
        "val": val,
        "profile_ticks": int(macro_prices.size),
        "sigma_7": sigma,
        "window_bars": len(bars),
        "tail_length_high": profile.tail_length_high if profile else None,
        "tail_length_low": profile.tail_length_low if profile else None,
        "tick_rate_7": macro_tick_rate,
        "tick_rate_3": fast_tick_rate,
        "tick_rate_last": last_tick_rate,
        "price_change_7": macro.price_change if macro else None,
        "price_change_3": fast.price_change if fast else None,
        "price_change_last": last.price_change if last else None,
        "price_speed_7": macro_price_speed,
        "price_speed_3": fast_price_speed,
        "price_speed_last": last_price_speed,
        "range_7": macro.price_range if macro else None,
        "range_3": fast.price_range if fast else None,
        "range_last": last.price_range if last else None,
        "range_speed_7": macro.range_speed if macro else None,
        "range_speed_3": fast.range_speed if fast else None,
        "range_speed_last": last.range_speed if last else None,
        "range_3_7": _safe_div(
            fast.price_range if fast else None, macro.price_range if macro else None
        ),
        "time_sin": time_sin,
        "time_cos": time_cos,
        "day_of_week": day_of_week,
        "is_weekend": is_weekend,
        "profile_missing": int(profile is None),
        "volatility_missing": int(sigma is None),
        "insufficient_ticks": int(
            0 < macro_prices.size < config.context.profile_min_ticks
        ),
        "gap_in_window": int(not _bars_contiguous(bars)),
    }

    return FeatureVector(core=core, diagnostics=diagnostics)


def _bars_contiguous(bars: tuple[BarSlice, ...]) -> bool:
    if len(bars) < 2:
        return True
    keys = [bar.bucket_key for bar in bars]
    return keys[-1] - keys[0] + 1 == len(keys)


def snapshot_feature_row(snapshot: Snapshot, config: Config) -> dict:
    """Convenience wrapper returning a flat, CSV/Parquet-friendly row."""

    vector = compute_features(snapshot, config)
    return vector.row(
        snapshot_id=snapshot.snapshot_id,
        timestamp=snapshot.snapshot_time,
        active_id=snapshot.active_id,
        price=snapshot.price,
        config=config,
    )


def build_feature_table(snapshots: list[Snapshot], config: Config) -> list[dict]:
    """Build one row per snapshot. This is the model-ready table."""

    return [snapshot_feature_row(snapshot, config) for snapshot in snapshots]


def build_diagnostic_table(ticks: list[Tick], config: Config) -> list[dict]:
    """One row per tick, for exploratory research and regression checks.

    The rows are not the model input. They exist so that tick-level and
    snapshot-level research can be compared without maintaining two feature
    implementations. The current partial candle is treated as the last bar.
    """

    if not ticks:
        return []

    candles: list[Candle] = group_candles(ticks, config.candles.interval_seconds)
    interval = config.candles.interval_seconds
    macro = config.context.macro_candles

    bar_cache: dict[int, BarSlice] = {}
    for index, candle in enumerate(candles):
        bar_cache[index] = BarSlice(
            bucket_key=candle.bucket_key,
            start_epoch=candle.start_epoch,
            epochs=tuple(ticks[i].epoch for i in candle.tick_indices),
            prices=tuple(ticks[i].price for i in candle.tick_indices),
        )

    rows: list[dict] = []
    tick_id = 0

    for candle_index, candle in enumerate(candles):
        start = max(0, candle_index - macro + 1)
        previous = tuple(bar_cache[i] for i in range(start, candle_index))
        current = bar_cache[candle_index]

        for position, tick_index in enumerate(candle.tick_indices):
            tick = ticks[tick_index]
            partial = BarSlice(
                bucket_key=current.bucket_key,
                start_epoch=current.start_epoch,
                epochs=current.epochs[: position + 1],
                prices=current.prices[: position + 1],
            )
            completed = (*previous[-macro + 1 :], partial) if macro > 1 else (partial,)
            snapshot = Snapshot(
                snapshot_id=tick_id,
                active_id=tick.active_id if tick.active_id is not None else 0,
                snapshot_time=tick.timestamp,
                completed_bars=completed,
                price=tick.price,
                window_ticks=sum(bar.tick_count for bar in completed),
                entry_timestamp=None,
                entry_price=None,
                entry_delay_seconds=None,
                outcomes={},
                utc_offset_seconds=int(tick.timestamp.utcoffset().total_seconds()),
            )
            # The diagnostic row keeps the historical tick-based identifiers.
            rows.append(
                {
                    **compute_features(snapshot, config).row(
                        snapshot_id=tick_id,
                        timestamp=tick.timestamp,
                        active_id=tick.active_id if tick.active_id is not None else 0,
                        price=tick.price,
                        config=config,
                    ),
                    "tick_id": tick_id,
                    "interval_seconds": interval,
                }
            )
            tick_id += 1

    return rows
