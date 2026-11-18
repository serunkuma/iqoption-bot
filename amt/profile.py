"""TPO profile, Point of Control, and Value Area computation.

Canonical rules:

- Bin index is ``floor(price / bin_size)``; bins are contiguous integers.
- VAH and VAL are the upper and lower edges of the included bins.
- The Value Area expands from the POC in pairs of non-empty bins until the
  target share is reached. A pair may overshoot the target.
- POC ties are broken by proximity to the current price, then by lower bin.
- Below the minimum tick count the profile is ``None``; no synthetic values.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Profile:
    bin_size: float
    total_ticks: int
    poc_bin: int
    poc_price: float
    val_bin: int
    vah_bin: int
    val: float
    vah: float
    value_area_ticks: int
    value_area_share: float
    lowest_bin: int
    highest_bin: int
    excess_high: float
    excess_low: float
    excess_asymmetry: float
    tail_length_high: float
    tail_length_low: float

    def bin_lower(self, index: int) -> float:
        return index * self.bin_size

    def bin_upper(self, index: int) -> float:
        return (index + 1) * self.bin_size


def bin_index(price: float, bin_size: float) -> int:
    """Return ``floor(price / bin_size)`` without float boundary drift.

    Decimal prices and bin sizes are inexact binary floats, so a price sitting
    exactly on a bin edge can divide to just below an integer. The scaled
    epsilon restores the intended edge without moving any real price.
    """

    if bin_size <= 0:
        raise ValueError("bin_size must be positive")
    ratio = price / bin_size
    return math.floor(ratio + 1e-9 * max(1.0, abs(ratio)))


def _bin_counts(prices: Sequence[float], bin_size: float) -> tuple[int, list[int]]:
    """Return the lowest bin index and contiguous per-bin tick counts."""

    indices = [bin_index(price, bin_size) for price in prices]
    lowest = min(indices)
    highest = max(indices)
    counts = [0] * (highest - lowest + 1)
    for index in indices:
        counts[index - lowest] += 1
    return lowest, counts


def _poc_offset(counts: list[int], lowest: int, bin_size: float, current_price: float) -> int:
    def score(offset: int) -> tuple[int, float, int]:
        centre = (lowest + offset + 0.5) * bin_size
        return (counts[offset], -abs(centre - current_price), -offset)

    return max(range(len(counts)), key=score)


def _value_area(counts: list[int], poc_offset: int, target: float) -> tuple[set[int], int]:
    """Expand the Value Area in pairs of non-empty bins around the POC."""

    total = sum(counts)
    target_ticks = target * total
    included = {poc_offset}
    included_ticks = counts[poc_offset]

    lower_cursor = poc_offset - 1
    upper_cursor = poc_offset + 1

    while included_ticks < target_ticks:
        above: list[int] = []
        cursor = upper_cursor
        while cursor < len(counts) and len(above) < 2:
            if counts[cursor] > 0:
                above.append(cursor)
            cursor += 1

        below: list[int] = []
        cursor = lower_cursor
        while cursor >= 0 and len(below) < 2:
            if counts[cursor] > 0:
                below.append(cursor)
            cursor -= 1

        if not above and not below:
            break

        above_count = sum(counts[offset] for offset in above)
        below_count = sum(counts[offset] for offset in below)

        if above and (above_count >= below_count or not below):
            for offset in above:
                included.add(offset)
            included_ticks += above_count
            upper_cursor = above[-1] + 1
        else:
            for offset in below:
                included.add(offset)
            included_ticks += below_count
            lower_cursor = below[-1] - 1

    return included, included_ticks


def _tail_features(
    counts: list[int],
    lowest: int,
    vah_bin: int,
    val_bin: int,
    tail_bins: int,
    single_print_max_ticks: int,
) -> tuple[float, float, float, float, float]:
    non_empty = [offset for offset, count in enumerate(counts) if count > 0]

    high_tail = non_empty[-tail_bins:]
    low_tail = non_empty[:tail_bins]

    high_single = sum(1 for offset in high_tail if counts[offset] <= single_print_max_ticks)
    high_ticks = sum(counts[offset] for offset in high_tail)
    excess_high = high_single / max(high_ticks, 1)

    low_single = sum(1 for offset in low_tail if counts[offset] <= single_print_max_ticks)
    low_ticks = sum(counts[offset] for offset in low_tail)
    excess_low = low_single / max(low_ticks, 1)

    highest_bin = lowest + non_empty[-1]
    lowest_bin = lowest + non_empty[0]

    tail_length_high = float(highest_bin - vah_bin)
    tail_length_low = float(val_bin - lowest_bin)

    return excess_high, excess_low, excess_high - excess_low, tail_length_high, tail_length_low


def build_profile(
    prices: Sequence[float],
    *,
    bin_size: float,
    value_area_target: float,
    tail_bins: int,
    single_print_max_ticks: int,
    min_ticks: int,
    current_price: float,
) -> Profile | None:
    """Build a TPO profile or return ``None`` when data is insufficient."""

    if bin_size <= 0:
        raise ValueError("bin_size must be positive")
    if min_ticks < 1:
        raise ValueError("min_ticks must be at least 1")
    if len(prices) < min_ticks:
        return None

    lowest, counts = _bin_counts(prices, bin_size)
    total = len(prices)
    poc_offset = _poc_offset(counts, lowest, bin_size, current_price)
    poc_bin = lowest + poc_offset

    included, included_ticks = _value_area(counts, poc_offset, value_area_target)

    val_bin = lowest + min(included)
    vah_bin = lowest + max(included)

    excess_high, excess_low, asymmetry, tail_high, tail_low = _tail_features(
        counts,
        lowest,
        vah_bin,
        val_bin,
        tail_bins,
        single_print_max_ticks,
    )

    non_empty = [offset for offset, count in enumerate(counts) if count > 0]

    return Profile(
        bin_size=bin_size,
        total_ticks=total,
        poc_bin=poc_bin,
        poc_price=(poc_bin + 0.5) * bin_size,
        val_bin=val_bin,
        vah_bin=vah_bin,
        val=val_bin * bin_size,
        vah=(vah_bin + 1) * bin_size,
        value_area_ticks=included_ticks,
        value_area_share=included_ticks / total,
        lowest_bin=lowest + non_empty[0],
        highest_bin=lowest + non_empty[-1],
        excess_high=excess_high,
        excess_low=excess_low,
        excess_asymmetry=asymmetry,
        tail_length_high=tail_high,
        tail_length_low=tail_low,
    )
