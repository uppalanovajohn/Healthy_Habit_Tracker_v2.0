# Healthy Habit Tracker v2.0 (GreenFuture Hack — Project #33)

A modular, production-ready Python 3.10+ habit tracking application supporting both **Interactive Terminal CLI** and **Desktop Tkinter GUI** modes.

## What's New in v2.0 (Addressing Evaluation Feedback)
- **Repository Architecture (`SQLiteHabitRepository`):** Indexed SQLite database (`data/habits.db`) with WAL mode and automatic atomic JSON/CSV mirroring—eliminating $O(N)$ flat-file scan bottlenecks.
- **Cross-Platform File Locking & Atomic Writes:** Exclusive file locks (`fcntl` / `msvcrt`) + `os.replace` prevent corruption during concurrent writes.
- **Structured Observability (`logger_config.py`):** Rotating file logs (`logs/tracker.log`) replacing console `print` error reporting.
- **Habit Streaks & 7-Day Goal Compliance:** Calculates consecutive goal streaks (`current` & `best`) and rolling 7-day compliance percentages.
- **Optional Tkinter Desktop GUI:** Launch directly via `python main.py --gui` or Option `8` in the CLI menu.
- **Packaging & Expanded Test Suite:** Includes `pyproject.toml`, concurrency thread tests, and mocked CLI input loop tests.

## Quickstart
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run Interactive CLI (pre-seeded with 42 records)
python main.py

# 3. Or launch Desktop Tkinter GUI directly
python main.py --gui

# 4. Run full automated test suite (including concurrency & CLI mock tests)
python -m unittest test_tracker.py
```
