"""Streaming store: ticks in, closed candles out, hourly Parquet on disk.

The package keeps the event contract, candle construction, rolling window, and
persistence in separate modules. ``runner.py`` wires them together through
:class:`StreamStore`.
"""

from .candles import CandleBuilder, CandleUpdate, ClosedCandle
from .engine import IngestResult, StreamBufferError, StreamStore
from .events import EventError, TickEvent
from .parquet import HourlyParquetStore, StoreWriteError
from .window import RollingCandleWindow

__all__ = [
    "CandleBuilder",
    "CandleUpdate",
    "ClosedCandle",
    "EventError",
    "HourlyParquetStore",
    "IngestResult",
    "RollingCandleWindow",
    "StoreWriteError",
    "StreamBufferError",
    "StreamStore",
    "TickEvent",
]
