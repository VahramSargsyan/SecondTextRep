"""Deterministic safety tests for a future resilient 7-day public observation."""
import csv
import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from collector import seven_day_reliability as mod


START = datetime(2026, 10, 10, 12, 0, 0, tzinfo=timezone.utc)


class SevenDayReliabilityTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_root = Path(self.temp.name) / "data-state"
        self.session_id = "opaque-seven-day-v2"
        self.root = mod.session_root(self.data_root, self.session_id)

    def test_start_only_when_explicitly_requested_and_resume_after_shutdown(self):
        self.assertEqual(mod.plan(self.root, self.session_id, now=START)["action"], "idle")
        start = mod.plan(self.root, self.session_id, now=START, allow_start=True)
        self.assertEqual(start["action"], "collect")
        self.assertEqual(start["segment"], 1)
        self.assertEqual(start["duration_seconds"], 14400)
        partial_source = Path(self.temp.name) / "partial"
        partial_source.mkdir()
        (partial_source / "runtime_events.csv").write_text("event\nshutdown\n")
        receipt = mod.stage(partial_source, self.root, 1, "1234", now=START)
        self.assertTrue(receipt["partial_only"])
        self.assertTrue((self.root / "attempts/1/1234/runtime_events.csv").exists())
        # Interrupted segments are NOT counted as complete and must be retried.
        retry = mod.plan(self.root, self.session_id, now=START + timedelta(minutes=25))
        self.assertEqual(retry["segment"], 1)
        self.assertEqual(retry["action"], "collect")
        self.assertEqual(mod.plan(self.root, self.session_id,
                                  now=START + timedelta(hours=168))["action"], "finish")

    def test_completed_receipt_skips_segment_and_rejects_duplicate(self):
        mod.plan(self.root, self.session_id, now=START, allow_start=True)
        source = Path(self.temp.name) / "segment_source"
        source.mkdir()
        (source / "segment_manifest.json").write_text(json.dumps({
            "status": "SEGMENT_COMPLETE", "sequence_gap_count": 0,
            "sample_row_count": 100, "symbols": ["TWTUSDT"]
        }))
        receipt = mod.finish_segment(source, self.root, 1, "run-1")
        self.assertEqual(receipt["segment"], 1)
        with self.assertRaisesRegex(ValueError, "already committed"):
            mod.finish_segment(source, self.root, 1, "run-1")
        result = mod.plan(self.root, self.session_id, now=START + timedelta(hours=1))
        self.assertEqual(result["segment"], 2)

    def test_sequence_gap_fails_closed_without_completed_receipt(self):
        mod.plan(self.root, self.session_id, now=START, allow_start=True)
        source = Path(self.temp.name) / "gap_source"
        source.mkdir()
        (source / "segment_manifest.json").write_text(json.dumps({
            "status": "SEGMENT_COMPLETE", "sequence_gap_count": 1,
            "sample_row_count": 100
        }))
        with self.assertRaisesRegex(ValueError, "sequence gap"):
            mod.finish_segment(source, self.root, 1, "run-1")
        self.assertFalse((self.root / "segments/1/PERSISTED.json").exists())

    def test_exact_utc_minute_coverage_not_row_count_or_span(self):
        with patch.object(mod, "EXPECTED_HOURS", 1):
            mod.plan(self.root, self.session_id, now=START, allow_start=True)
            segment = self.root / "segments" / "1"
            day = segment / "2026-10-10"
            day.mkdir(parents=True)
            (segment / "segment_manifest.json").write_text(json.dumps({
                "status": "SEGMENT_COMPLETE", "sequence_gap_count": 0,
                "sample_row_count": 118
            }))
            (segment / "PERSISTED.json").write_text("{}")
            path = day / "market_aggregates.csv"
            fields = ["timestamp_utc", "symbol"]
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                for minute in range(1, 60):
                    for symbol in ("TWTUSDT", "TRXUSDT"):
                        writer.writerow({
                            "timestamp_utc": (START + timedelta(minutes=minute)).isoformat(),
                            "symbol": symbol
                        })
            good = mod.audit(self.root, ("TWTUSDT", "TRXUSDT"))
            self.assertEqual(good["status"], "COMPLETED")
            self.assertEqual(good["per_market"]["TWTUSDT"]["missing_minutes"], 0)
            # Add a duplicate while removing one minute: total row count unchanged,
            # but coverage must become INCOMPLETE.
            with path.open(newline="") as handle:
                rows = list(csv.DictReader(handle))
            rows = [row for row in rows if not (
                row["symbol"] == "TRXUSDT" and
                row["timestamp_utc"] == (START + timedelta(minutes=30)).isoformat()
            )]
            rows.append(rows[0].copy())
            with path.open("w", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=fields)
                writer.writeheader()
                writer.writerows(rows)
            incomplete = mod.audit(self.root, ("TWTUSDT", "TRXUSDT"))
            self.assertEqual(incomplete["status"], "INCOMPLETE")
            self.assertEqual(incomplete["per_market"]["TRXUSDT"]["missing_minutes"], 1)
            self.assertEqual(incomplete["per_market"]["TRXUSDT"]["rows"], 58)


if __name__ == "__main__":
    unittest.main()
