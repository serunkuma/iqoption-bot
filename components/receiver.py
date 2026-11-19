"""WebSocket receiver: the tick-capture component.

Responsibilities are deliberately narrow:

1. Accept WebSocket frames from the browser extension.
2. Validate the envelope.
3. Stamp a local receipt time.
4. Buffer the raw payload and hand it to an optional sink.

It does not build candles, compute features, or make decisions.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import websockets
from websockets.exceptions import ConnectionClosed

HOST = "localhost"
PORT = 8765
HISTORY_LIMIT = 500
ASSET_NAMES_PATH = Path(__file__).resolve().parent.parent / "asset_names.json"

#: Key added to every stored payload. The broker's own ``at`` field is kept
#: but never promoted to a timestamp.
RECEIVED_AT_KEY = "received_at"

IDENTITY_FIELDS = (
    "symbol",
    "ticker",
    "asset",
    "asset_name",
    "active_name",
    "instrument",
    "instrument_name",
    "underlying",
    "name",
)

logger = logging.getLogger("iqoption_receiver")

asset_names_by_id: dict[str, str] = {}
history_by_active_id: defaultdict[Any, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=HISTORY_LIMIT)
)

#: Optional sink invoked with ``(active_id, payload)`` for every accepted tick.
_tick_sink: Callable[[Any, dict[str, Any]], None] | None = None


def set_tick_sink(sink: Callable[[Any, dict[str, Any]], None] | None) -> None:
    """Install a persistence or streaming sink for accepted ticks."""

    global _tick_sink
    _tick_sink = sink


def load_asset_names(path: Path = ASSET_NAMES_PATH) -> dict[str, str]:
    with path.open(encoding="utf-8") as file:
        names = json.load(file)

    if not isinstance(names, dict) or any(
        not isinstance(active_id, str)
        or not isinstance(name, str)
        or not name.strip()
        for active_id, name in names.items()
    ):
        raise ValueError(f"{path} must contain a JSON object of active_id-to-name strings.")
    return names


def format_asset_identity(
    active_id: Any,
    tick_data: dict[str, Any],
    asset_names: dict[str, str],
) -> str:
    payload_identity = [
        f"{field}={tick_data[field]}"
        for field in IDENTITY_FIELDS
        if field in tick_data and isinstance(tick_data[field], (str, int, float))
    ]
    label = asset_names.get(str(active_id))
    identity = label or (", ".join(payload_identity) if payload_identity else "unmapped")
    details = f" payload_identity=[{'; '.join(payload_identity)}]" if label and payload_identity else ""
    return f"asset={identity} active_id={active_id}{details}"


def process_tick(
    active_id: Any,
    tick_data: dict[str, Any],
    history_buffer: deque[dict[str, Any]],
) -> None:
    logger.info(
        "%s close=%s open=%s min=%s max=%s volume=%s at=%s received_at=%s history=%d",
        format_asset_identity(active_id, tick_data, asset_names_by_id),
        tick_data.get("close"),
        tick_data.get("open"),
        tick_data.get("min"),
        tick_data.get("max"),
        tick_data.get("volume"),
        tick_data.get("at"),
        tick_data.get(RECEIVED_AT_KEY),
        len(history_buffer),
    )


def accept_frame(raw_message: Any, now: datetime | None = None) -> bool:
    """Validate and store one raw frame. Returns True when it was accepted."""

    try:
        data = json.loads(raw_message)
    except (json.JSONDecodeError, TypeError):
        logger.warning("Ignoring malformed JSON frame.")
        return False

    if not isinstance(data, dict) or data.get("name") != "candle-generated":
        return False

    message = data.get("msg")
    if not isinstance(message, dict):
        logger.warning("Ignoring candle frame without a valid msg object.")
        return False

    active_id = message.get("active_id")
    if active_id is None:
        logger.warning("Ignoring candle frame without active_id.")
        return False

    tick_data = dict(message)
    stamp = now or datetime.now(timezone.utc).astimezone()
    tick_data.setdefault(RECEIVED_AT_KEY, stamp.isoformat())

    history_buffer = history_by_active_id[active_id]
    history_buffer.append(tick_data)
    process_tick(active_id, tick_data, history_buffer)

    if _tick_sink is not None:
        try:
            _tick_sink(active_id, tick_data)
        except Exception:  # pragma: no cover - sink failures must not kill capture
            logger.exception("Tick sink failed for active_id=%s", active_id)

    return True


async def handle_ticks(websocket: Any) -> None:
    logger.info("Extension connected.")
    try:
        async for raw_message in websocket:
            accept_frame(raw_message)
    except ConnectionClosed:
        logger.info("Extension disconnected.")


async def serve(host: str = HOST, port: int = PORT) -> None:
    """Start the receiver and block until cancelled."""

    try:
        asset_names_by_id.update(load_asset_names())
    except FileNotFoundError:
        logger.warning("asset_names.json not found; using payload identities.")
    except ValueError as exc:
        logger.warning("asset_names.json is invalid: %s", exc)

    async with websockets.serve(
        handle_ticks,
        host,
        port,
        ping_interval=20,
        ping_timeout=20,
        max_size=1_048_576,
    ):
        logger.info("Listening for tick data on ws://%s:%d", host, port)
        await asyncio.Future()


def run(host: str = HOST, port: int = PORT) -> None:
    try:
        asyncio.run(serve(host, port))
    except KeyboardInterrupt:
        logger.info("Receiver stopped.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    run()
