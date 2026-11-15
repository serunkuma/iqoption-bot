import asyncio
import json
import logging
from collections import defaultdict, deque
from pathlib import Path
from typing import Any

import websockets
from websockets.exceptions import ConnectionClosed

HOST = "localhost"
PORT = 8765
HISTORY_LIMIT = 500
ASSET_NAMES_PATH = Path(__file__).with_name("asset_names.json")
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("iqoption_receiver")

asset_names_by_id: dict[str, str] = {}
history_by_active_id: defaultdict[Any, deque[dict[str, Any]]] = defaultdict(
    lambda: deque(maxlen=HISTORY_LIMIT)
)


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
    """Add real-time indicator or custom computation logic here."""
    logger.info(
        "%s close=%s open=%s min=%s max=%s volume=%s at=%s history=%d",
        format_asset_identity(active_id, tick_data, asset_names_by_id),
        tick_data.get("close"),
        tick_data.get("open"),
        tick_data.get("min"),
        tick_data.get("max"),
        tick_data.get("volume"),
        tick_data.get("at"),
        len(history_buffer),
    )


async def handle_ticks(websocket: Any) -> None:
    logger.info("Extension connected.")
    try:
        async for raw_message in websocket:
            try:
                data = json.loads(raw_message)
            except (json.JSONDecodeError, TypeError):
                logger.warning("Ignoring malformed JSON frame.")
                continue

            if not isinstance(data, dict) or data.get("name") != "candle-generated":
                continue

            message = data.get("msg")
            if not isinstance(message, dict):
                logger.warning("Ignoring candle frame without a valid msg object.")
                continue

            active_id = message.get("active_id")
            if active_id is None:
                logger.warning("Ignoring candle frame without active_id.")
                continue

            tick_data = dict(message)
            history_buffer = history_by_active_id[active_id]
            history_buffer.append(tick_data)
            process_tick(active_id, tick_data, history_buffer)
    except ConnectionClosed:
        logger.info("Extension disconnected.")


async def main() -> None:
    asset_names_by_id.update(load_asset_names())
    async with websockets.serve(
        handle_ticks,
        HOST,
        PORT,
        ping_interval=20,
        ping_timeout=20,
        max_size=1_048_576,
    ):
        logger.info("Listening for tick data on ws://%s:%d", HOST, PORT)
        await asyncio.Future()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Receiver stopped.")
