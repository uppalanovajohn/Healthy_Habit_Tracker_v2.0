import sys
from typing import Optional

from models import HabitRecord
from validator import prompt_category, prompt_value, prompt_date
from storage import SQLiteHabitRepository, HabitRepository, import_bulk_csv
from analytics import (
    print_summary_table,
    print_paginated_records,
    export_markdown_report,
    export_trend_chart,
)
from logger_config import setup_logger

logger = setup_logger()

BANNER = r"""
====================================================================
   ____                 _____      _                   
  / ___|_ __ ___  ___ _|_   _|   _| |_ _   _ _ __ ___  
 | |  _| '__/ _ \/ _ \ '_ \| || | | | __| | | | '__/ _ \ 
 | |_| | | |  __/  __/ | | | || |_| | |_| |_| | | |  __/ 
  \____|_|  \___|\___|_| |_|_| \__,_|\__|\__,_|_|  \___| 
                                                         
  PROJECT #33: HEALTHY HABIT TRACKER (v2.0 - Production Edition)
====================================================================
"""


def run_cli(repo: Optional[HabitRepository] = None) -> None:
    if repo is None:
        repo = SQLiteHabitRepository()

    print(BANNER)
    initial_records = repo.get_all()
    print(f"  [INFO] Connected to SQLite/JSON storage ({len(initial_records)} record(s) indexed).")
    logger.info("CLI session started with %d existing records.", len(initial_records))

    while True:
        print("
--- MAIN MENU ---")
        print("1. Log New Habit Entry")
        print("2. View Executive Summary, Streaks & Warnings")
        print("3. Search & Filter Records (Indexed Query)")
        print("4. View All Records (Paginated)")
        print("5. Export Visual Trend Chart (PNG)")
        print("6. Export Executive Markdown Report (.md)")
        print("7. Bulk Import Legacy CSV Dataset")
        print("8. Launch Desktop GUI (Tkinter)")
        print("9. Exit")

        choice = input("
Select an option (1-9): ").strip()

        if choice == "1":
            cat = prompt_category()
            val = prompt_value(cat)
            date_str = prompt_date()
            notes = input("Optional notes: ").strip()

            new_rec = HabitRecord(date=date_str, category=cat, value=val, notes=notes)
            repo.add_record(new_rec)
            print(f"  [SUCCESS] Logged {val} for {cat} on {date_str}.")

        elif choice == "2":
            print_summary_table(repo.get_all())

        elif choice == "3":
            query = input("Enter keyword, category (reading/exercise/hydration), or YYYY-MM: ").strip()
            matches = repo.search(query)
            print_paginated_records(matches)

        elif choice == "4":
            print_paginated_records(repo.get_all())

        elif choice == "5":
            result = export_trend_chart(repo.get_all())
            if result.startswith("ERROR"):
                print(f"  [!] {result}")
            else:
                print(f"  [SUCCESS] Trend chart saved to: {result}")

        elif choice == "6":
            path = export_markdown_report(repo.get_all())
            print(f"  [SUCCESS] Markdown executive report saved to: {path}")

        elif choice == "7":
            csv_path = input("Enter CSV file path (default: bulk_import_sample.csv): ").strip()
            if not csv_path:
                csv_path = "bulk_import_sample.csv"
            added, errors = import_bulk_csv(csv_path, repo)
            print(f"
  [IMPORT COMPLETE] Imported {added} valid record(s).")
            if errors:
                print(f"  [VALIDATION LOG] Rejected {len(errors)} invalid row(s):")
                for err in errors:
                    print(f"    - {err}")

        elif choice == "8":
            try:
                from gui import launch_gui
                print("  [INFO] Launching Tkinter GUI window...")
                launch_gui(repo)
            except Exception as exc:
                logger.error("Failed to launch GUI: %s", exc)
                print(f"  [!] GUI unavailable in this environment: {exc}")

        elif choice == "9":
            logger.info("CLI session exited cleanly.")
            print("
Exiting Healthy Habit Tracker v2.0. Stay consistent!")
            break
        else:
            print("  [!] Invalid menu selection. Please enter a number from 1 to 9.")


if __name__ == "__main__":
    if "--gui" in sys.argv:
        from gui import launch_gui
        launch_gui(SQLiteHabitRepository())
    else:
        run_cli()
