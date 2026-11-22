import os
import tempfile
import threading
import unittest
from unittest.mock import patch

from models import HabitRecord
from validator import validate_record_fields
from storage import (
    SQLiteHabitRepository,
    save_json_records,
    load_json_records,
    import_bulk_csv,
)
from analytics import compute_summary
from main import run_cli


class TestHealthyHabitTrackerV2(unittest.TestCase):
    def test_validation_rules(self):
        ok, data, err = validate_record_fields("2026-11-20", "reading", "45")
        self.assertTrue(ok)
        self.assertEqual(data["value"], 45.0)
        self.assertEqual(err, "")

        ok_bad, _, err_bad = validate_record_fields("2026-11-20", "hydration", "99")
        self.assertFalse(ok_bad)
        self.assertIn("out of bounds", err_bad)

    def test_json_atomic_write_and_corruption_recovery(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            json_path = os.path.join(tmpdir, "habits.json")
            csv_path = os.path.join(tmpdir, "habits.csv")
            recs = [HabitRecord("2026-11-21", "exercise", 50.0, "Morning run")]
            save_json_records(recs, json_path, csv_path)

            loaded = load_json_records(json_path)
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0].notes, "Morning run")

            # Corrupt file and verify self-healing recovery
            with open(json_path, "w", encoding="utf-8") as f:
                f.write("{corrupted_json")
            recovered = load_json_records(json_path)
            self.assertEqual(recovered, [])

    def test_sqlite_repository_and_concurrent_writes(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = os.path.join(tmpdir, "test.db")
            json_path = os.path.join(tmpdir, "mirror.json")
            csv_path = os.path.join(tmpdir, "mirror.csv")
            repo = SQLiteHabitRepository(db_path=db_path, json_mirror=json_path, csv_mirror=csv_path)

            def worker(idx: int):
                repo.add_record(HabitRecord("2026-11-22", "hydration", 8.0, f"Thread-{idx}"))

            threads = [threading.Thread(target=worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            all_recs = repo.get_all()
            self.assertEqual(len(all_recs), 8)
            matches = repo.search("Thread-3")
            self.assertEqual(len(matches), 1)

    def test_streaks_and_compliance_analytics(self):
        recs = [
            HabitRecord("2026-11-20", "reading", 35.0, "Day 1"),
            HabitRecord("2026-11-21", "reading", 40.0, "Day 2"),
            HabitRecord("2026-11-22", "reading", 30.0, "Day 3"),
            HabitRecord("2026-11-22", "hydration", 5.0, "Low water"),
        ]
        summary = compute_summary(recs)
        self.assertEqual(summary["reading"]["current_streak"], 3)
        self.assertEqual(summary["reading"]["best_streak"], 3)
        self.assertEqual(summary["reading"]["status"], "ON TRACK")
        self.assertEqual(summary["hydration"]["status"], "BELOW GOAL (!)")

    def test_cli_menu_loop_mocked(self):
        """Tests end-to-end CLI workflow (log entry -> view summary -> exit) via mocked stdin."""
        with tempfile.TemporaryDirectory() as tmpdir:
            repo = SQLiteHabitRepository(
                db_path=os.path.join(tmpdir, "cli.db"),
                json_mirror=os.path.join(tmpdir, "cli.json"),
                csv_mirror=os.path.join(tmpdir, "cli.csv"),
            )
            simulated_inputs = [
                "1",           # Log New Habit Entry
                "exercise",    # Category
                "45",          # Value
                "2026-11-22",  # Date
                "CLI test",    # Notes
                "2",           # View Executive Summary
                "9",           # Exit
            ]
            with patch("builtins.input", side_effect=simulated_inputs):
                run_cli(repo=repo)

            saved = repo.get_all()
            self.assertEqual(len(saved), 1)
            self.assertEqual(saved[0].notes, "CLI test")


if __name__ == "__main__":
    unittest.main()
