import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

from collector.control_state import apply_command
from collector.market_data_worker import (
    LocalOrderBook,
    SequenceGap,
    control_requests_stop,
    data_path,
    normalize_mode,
    normalize_symbols,
    read_control_state,
    validate_session_id,
)


class MarketDataWorkerTests(unittest.TestCase):
    def test_symbol_and_mode_validation(self):
        self.assertEqual(normalize_symbols("twtusdt,TWTUSDC,twtusdt"), ("TWTUSDT", "TWTUSDC"))
        self.assertEqual(normalize_mode("burst"), "BURST")
        with self.assertRaises(ValueError):
            normalize_symbols("BTCBUSD")
        with self.assertRaises(ValueError):
            normalize_mode("FAST")
        self.assertEqual(validate_session_id("opaque-123"), "opaque-123")
        with self.assertRaises(ValueError):
            validate_session_id("../bad")

    def test_local_book_depth_and_sequence_gap(self):
        book = LocalOrderBook("TWTUSDT")
        book.apply_snapshot(
            {
                "lastUpdateId": 100,
                "bids": [["1.0000", "100"], ["0.9950", "200"]],
                "asks": [["1.0050", "100"], ["1.0100", "200"]],
            }
        )
        delta = book.apply_depth(
            {
                "U": 101,
                "u": 101,
                "b": [["1.0000", "120"]],
                "a": [["1.0050", "80"]],
            }
        )
        self.assertGreater(delta["bid_add_1pct_usd"], 0)
        self.assertGreater(delta["ask_remove_1pct_usd"], 0)
        self.assertGreater(book.depth_quote("bid", 0.01), 0)
        self.assertGreater(book.depth_quote("ask", 0.01), 0)
        with self.assertRaises(SequenceGap):
            book.apply_depth({"U": 103, "u": 103, "b": [], "a": []})

    def test_control_state_start_update_stop_finalize(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "session.json"
            started = apply_command(
                path,
                "opaque-123",
                "START",
                "TWTUSDT,TWTUSDC,TRXUSDT,TRXUSDC",
                "WATCH",
                300,
            )
            self.assertTrue(started["should_dispatch"])
            self.assertEqual(started["state"]["desired_state"], "RUNNING")
            updated = apply_command(
                path,
                "opaque-123",
                "UPDATE",
                "TWTUSDT,TWTUSDC,AAVEUSDT,AAVEUSDC",
                "BURST",
                600,
            )
            self.assertFalse(updated["should_dispatch"])
            self.assertEqual(updated["state"]["revision"], 2)
            stopped = apply_command(path, "opaque-123", "STOP")
            self.assertEqual(stopped["state"]["desired_state"], "STOP_REQUESTED")
            finalized = apply_command(path, "opaque-123", "FINALIZE")
            self.assertEqual(finalized["state"]["desired_state"], "STOPPED")
            failed = apply_command(path, "opaque-123", "FAIL", detail="network failed")
            self.assertEqual(failed["state"]["desired_state"], "FAILED")
            self.assertEqual(failed["state"]["last_error"], "network failed")

    def test_control_url_validation_and_partition_path(self):
        payload = {
            "session_id": "opaque-123",
            "desired_state": "STOP_REQUESTED",
        }
        response = mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps(payload).encode("utf-8")
        response.__enter__.return_value.__exit__ = mock.Mock(return_value=False)
        with mock.patch("urllib.request.urlopen", return_value=response):
            loaded = read_control_state("https://example.invalid/state.json", "opaque-123")
        self.assertTrue(control_requests_stop(loaded))
        path = data_path(
            Path("out"),
            "opaque-123",
            datetime(2026, 10, 7, tzinfo=timezone.utc),
        )
        self.assertEqual(
            path.as_posix(),
            "out/sessions/opaque-123/2026-10-07/market_aggregates.csv",
        )


if __name__ == "__main__":
    unittest.main()
