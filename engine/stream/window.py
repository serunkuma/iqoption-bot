"""Bounded rolling window of closed candles."""

from __future__ import annotations

from collections import deque

from .candles import ClosedCandle


class RollingCandleWindow:
    """Keep the most recent closed candles and report readiness.

    A window is ready only when it holds ``size`` candles with contiguous bucket
    keys. A gap resets readiness until enough new candles arrive.
    """

    def __init__(self, size: int = 7) -> None:
        if size < 1:
            raise ValueError("size must be at least 1")
        self.size = size
        self._candles: deque[ClosedCandle] = deque(maxlen=size)

    def append(self, candle: ClosedCandle) -> None:
        if self._candles and candle.bucket_key <= self._candles[-1].bucket_key:
            raise ValueError("candles must be appended in ascending bucket order")
        self._candles.append(candle)

    def reset(self) -> None:
        self._candles.clear()

    @property
    def candles(self) -> tuple[ClosedCandle, ...]:
        return tuple(self._candles)

    @property
    def ready(self) -> bool:
        return len(self._candles) == self.size and self.contiguous

    @property
    def contiguous(self) -> bool:
        if not self._candles:
            return False
        keys = [candle.bucket_key for candle in self._candles]
        return keys[-1] - keys[0] + 1 == len(keys)

    def __len__(self) -> int:
        return len(self._candles)
