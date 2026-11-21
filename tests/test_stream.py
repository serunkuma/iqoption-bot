import json
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from engine.stream import (
    CandleBuilder,
    EventError,
    HourlyParquetStore,
    RollingCandleWindow,
    StreamBufferError,
    StreamStore,
    TickEvent,
)
from engine.stream.parquet import StoreWriteError

from .helpers import BASE


def payload(moment, price):
    return {"received_at": moment.isoformat(), "close": price}


def event(sequence: int, offset_seconds: float, price: float = 1.0) -> TickEvent:
    return TickEvent(
        sequence=sequence,
        received_at=BASE + timedelta(seconds=offset_seconds),
        active_id=0,
        price=price,
    )


class TickEventTests(unittest.TestCase):
    def test_payload_becomes_an_event(self) -> None:
        moment = BASE + timedelta(seconds=5)
        parsed = TickEvent.from_payload(
            3, 7, {"received_at": moment.isoformat(), "close": 1.25}
        )

        self.assertEqual(parsed.sequence, 3)
        self.assertEqual(parsed.active_id, 7)
        self.assertEqual(parsed.price, 1.25)
        self.assertEqual(parsed.utc_offset_seconds, 0)
        self.assertEqual(parsed.epoch, moment.timestamp())

    def test_naive_timestamp_is_rejected(self) -> None:
        with self.assertRaises(EventError):
            TickEvent.from_payload(
                0, 0, {"received_at": "2026-11-18T12:00:00", "close": 1.0}
            )

    def test_non_numeric_price_is_rejected(self) -> None:
        with self.assertRaises(EventError):
            TickEvent.from_payload(
                0, 0, {"received_at": BASE.isoformat(), "close": "1.0"}
            )

    def test_duplicate_prices_are_distinct_events(self) -> None:
        first = event(0, 0.0, 1.0)
        second = event(1, 0.0, 1.0)
        self.assertNotEqual(first, second)


class CandleBuilderTests(unittest.TestCase):
    def test_first_tick_opens_the_forming_candle(self) -> None:
        builder = CandleBuilder(60)
        update = builder.ingest(event(0, 0.0, 1.0))

        self.assertTrue(update.accepted)
        self.assertEqual(update.closed, ())
        self.assertEqual(builder.forming_key, int(BASE.timestamp() // 60))

    def test_next_minute_closes_the_previous_candle(self) -> None:
        builder = CandleBuilder(60)
        builder.ingest(event(0, 0.0, 1.0))
        builder.ingest(event(1, 10.0, 1.4))
        builder.ingest(event(2, 20.0, 0.8))
        update = builder.ingest(event(3, 60.0, 1.2))

        self.assertTrue(update.accepted)
        self.assertEqual(len(update.closed), 1)
        candle = update.closed[0]
        self.assertEqual(candle.open, 1.0)
        self.assertEqual(candle.high, 1.4)
        self.assertEqual(candle.low, 0.8)
        self.assertEqual(candle.close, 0.8)
        self.assertEqual(candle.tick_count, 3)
        self.assertEqual(candle.first_sequence, 0)
        self.assertEqual(candle.last_sequence, 2)
        self.assertEqual(candle.finalized_at, BASE + timedelta(seconds=60))
        self.assertEqual(len(candle.prices), 3)

    def test_late_event_is_rejected(self) -> None:
        builder = CandleBuilder(60)
        builder.ingest(event(0, 0.0))
        builder.ingest(event(1, 60.0))
        update = builder.ingest(event(2, 5.0))

        self.assertFalse(update.accepted)
        self.assertTrue(update.late)
        self.assertEqual(update.reason, "late")

    def test_skipped_minute_reports_a_gap(self) -> None:
        builder = CandleBuilder(60)
        builder.ingest(event(0, 0.0))
        update = builder.ingest(event(1, 180.0))

        self.assertEqual(len(update.closed), 1)
        self.assertEqual(len(update.gaps), 2)

    def test_instrument_change_is_rejected(self) -> None:
        builder = CandleBuilder(60)
        builder.ingest(event(0, 0.0))
        other = TickEvent(
            sequence=1,
            received_at=BASE + timedelta(seconds=10),
            active_id=9,
            price=1.0,
        )
        update = builder.ingest(other)

        self.assertFalse(update.accepted)
        self.assertEqual(update.reason, "instrument")


class RollingWindowTests(unittest.TestCase):
    def test_window_is_ready_only_when_full_and_contiguous(self) -> None:
        builder = CandleBuilder(60)
        window = RollingCandleWindow(3)

        builder.ingest(event(0, 0.0))
        builder.ingest(event(1, 60.0))
        builder.ingest(event(2, 120.0))
        update = builder.ingest(event(3, 180.0))
        for candle in update.closed:
            window.append(candle)

        self.assertEqual(len(window), 1)
        self.assertFalse(window.ready)

    def test_gap_resets_contiguity(self) -> None:
        builder = CandleBuilder(60)
        window = RollingCandleWindow(3)

        builder.ingest(event(0, 0.0))
        for sequence, offset in enumerate((240.0, 300.0, 360.0), start=1):
            update = builder.ingest(event(sequence, offset))
            for candle in update.closed:
                window.append(candle)

        # Closed buckets 0, 4, 5: three candles, but not contiguous.
        self.assertEqual(len(window), 3)
        self.assertFalse(window.contiguous)
        self.assertFalse(window.ready)


class StreamStoreTests(unittest.TestCase):
    def test_ingest_assigns_sequences_and_persists_candles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                directory,
                interval_seconds=60,
                window_size=3,
                flush_events=10,
                compression="none",
            )
            store.ingest(0, payload(BASE, 1.0))
            store.ingest(0, payload(BASE + timedelta(seconds=10), 1.2))
            result = store.ingest(0, payload(BASE + timedelta(seconds=60), 1.1))

            self.assertTrue(result.accepted)
            self.assertEqual(result.sequence, 2)
            self.assertEqual(len(result.closed), 1)
            self.assertEqual(store.last_sequence, 2)
            self.assertEqual(store.counters["ticks"], 3)
            self.assertEqual(store.counters["candles_closed"], 1)

            candles = store.read_candles()
            self.assertEqual(len(candles), 1)
            self.assertEqual(candles.iloc[0]["tick_count"], 2)

            events = store.read_events()
            self.assertEqual(len(events), 3)
            self.assertEqual(events["sequence"].tolist(), [0, 1, 2])

            store.close()
            self.assertTrue((Path(directory) / "state.json").is_file())

    def test_late_event_is_counted_and_not_stored(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                directory, flush_events=10, compression="none"
            )
            store.ingest(0, payload(BASE, 1.0))
            store.ingest(0, payload(BASE + timedelta(seconds=60), 1.1))
            result = store.ingest(0, payload(BASE + timedelta(seconds=5), 1.3))

            self.assertFalse(result.accepted)
            self.assertTrue(result.late)
            self.assertEqual(store.counters["late_rejected"], 1)
            self.assertEqual(store.last_sequence, 1)
            store.close()

    def test_window_becomes_ready_after_three_closed_candles(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                directory,
                window_size=3,
                flush_events=10,
                compression="none",
            )
            ready = False
            for minute in range(4):
                result = store.ingest(
                    0,
                    payload(BASE + timedelta(minutes=minute), 1.0 + minute),
                )
                ready = ready or result.window_ready

            self.assertTrue(ready)
            self.assertTrue(store.window_ready)
            store.close()

    def test_state_restores_the_forming_candle(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                directory, window_size=3, flush_events=10, compression="none"
            )
            for minute in range(3):
                store.ingest(
                    0,
                    payload(BASE + timedelta(minutes=minute, seconds=30), 1.0 + minute),
                )
            last_sequence = store.last_sequence
            forming_key = store.builder.forming_key
            finalized = store.last_finalized_bucket
            store.close()

            recovered = StreamStore(
                directory, window_size=3, flush_events=10, compression="none"
            )
            self.assertEqual(recovered.last_sequence, last_sequence)
            self.assertEqual(recovered.builder.forming_key, forming_key)
            self.assertEqual(recovered.last_finalized_bucket, finalized)
            recovered.close()

    def test_buffer_limit_fails_closed_after_a_write_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                directory,
                flush_events=1,
                max_buffer_events=2,
                compression="none",
            )

            def broken_flush() -> None:
                raise StoreWriteError("disk full")

            store.sink.flush = broken_flush  # type: ignore[method-assign]
            with self.assertRaises(StreamBufferError):
                for second in range(5):
                    store.ingest(0, payload(BASE + timedelta(seconds=second), 1.0))

            self.assertEqual(store.degraded, "buffer_limit")


class ReceiverBridgeTests(unittest.TestCase):
    def test_receiver_payload_reaches_the_stream_store(self) -> None:
        from components import receiver

        with tempfile.TemporaryDirectory() as directory:
            store = StreamStore(
                directory,
                window_size=3,
                flush_events=10,
                compression="none",
            )
            receiver.set_tick_sink(
                lambda active_id, frame: store.ingest(active_id, frame)
            )
            try:
                for minute in range(3):
                    for second in (0, 30):
                        frame = json.dumps(
                            {
                                "name": "candle-generated",
                                "msg": {
                                    "active_id": 0,
                                    "close": 1.0 + minute / 100,
                                },
                            }
                        )
                        accepted = receiver.accept_frame(
                            frame,
                            now=BASE + timedelta(minutes=minute, seconds=second),
                        )
                        self.assertTrue(accepted)
            finally:
                receiver.set_tick_sink(None)
                store.close()

            self.assertEqual(store.counters["ticks"], 6)
            self.assertEqual(store.counters["candles_closed"], 2)


class HourlyParquetStoreTests(unittest.TestCase):
    def test_flush_writes_parts_and_recover_finds_the_tail(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sink = HourlyParquetStore(directory, compression="none")
            for sequence in range(3):
                sink.add_event(event(sequence, sequence))
            builder = CandleBuilder(60)
            builder.ingest(event(0, 0.0))
            closed = builder.ingest(event(1, 60.0)).closed
            for candle in closed:
                sink.add_candle(candle)
            sink.flush()

            self.assertEqual(len(sink.read_events()), 3)
            self.assertEqual(len(sink.read_candles()), 1)

            recovered = sink.recover()
            self.assertEqual(recovered["last_flushed_sequence"], 2)
            self.assertIsNotNone(recovered["last_finalized_bucket"])

    def test_state_file_round_trips(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            sink = HourlyParquetStore(directory, compression="none")
            sink.save_state({"last_flushed_sequence": 12, "last_finalized_bucket": 3})

            state = sink.load_state()

        self.assertEqual(state["last_flushed_sequence"], 12)
        self.assertEqual(state["last_finalized_bucket"], 3)


if __name__ == "__main__":
    unittest.main()
