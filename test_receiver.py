import asyncio
import json
import unittest

import websockets

import receiver


class ReceiverTests(unittest.IsolatedAsyncioTestCase):
    def test_formats_payload_identity_when_no_local_name_is_mapped(self) -> None:
        identity = receiver.format_asset_identity(
            12,
            {"active_id": 12, "symbol": "USDJPY"},
            {},
        )
        self.assertEqual(identity, "asset=symbol=USDJPY active_id=12")

    async def test_retains_all_candle_fields_and_logs_asset_identity(self) -> None:
        receiver.history_by_active_id.clear()
        receiver.asset_names_by_id.clear()
        receiver.asset_names_by_id["42"] = "EUR/USD"
        candle = {
            "name": "candle-generated",
            "msg": {
                "active_id": 42,
                "close": 1.25,
                "open": 1.2,
                "min": 1.1,
                "max": 1.3,
                "volume": 7,
                "at": 123,
                "symbol": "EURUSD",
                "interval": 60,
            },
        }

        async with websockets.serve(receiver.handle_ticks, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            with self.assertLogs(receiver.logger, level="INFO") as logs:
                async with websockets.connect(f"ws://127.0.0.1:{port}") as client:
                    await client.send(json.dumps(candle))
                    await asyncio.sleep(0.01)

        history = receiver.history_by_active_id[42]
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["interval"], 60)
        self.assertEqual(history[0]["symbol"], "EURUSD")
        self.assertTrue(any("asset=EUR/USD active_id=42" in line for line in logs.output))
        self.assertTrue(any("payload_identity=[symbol=EURUSD]" in line for line in logs.output))

    def test_loads_local_asset_names(self) -> None:
        from pathlib import Path
        from tempfile import TemporaryDirectory

        with TemporaryDirectory() as directory:
            path = Path(directory) / "asset_names.json"
            path.write_text('{"42": "EUR/USD"}', encoding="utf-8")
            self.assertEqual(receiver.load_asset_names(path), {"42": "EUR/USD"})


if __name__ == "__main__":
    unittest.main()
