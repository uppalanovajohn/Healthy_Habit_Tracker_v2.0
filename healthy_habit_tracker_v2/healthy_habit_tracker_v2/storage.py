import csv
import json
import os
import sqlite3
import tempfile
from abc import ABC, abstractmethod
from contextlib import contextmanager
from typing import List, Tuple, Optional

from models import HabitRecord
from validator import validate_record_fields
from logger_config import setup_logger

logger = setup_logger()

DATA_DIR = "data"
DB_FILE = os.path.join(DATA_DIR, "habits.db")
JSON_FILE = os.path.join(DATA_DIR, "habits.json")
CSV_BACKUP_FILE = os.path.join(DATA_DIR, "habits.csv")
EXPORT_DIR = "exports"

# Cross-platform file lock helper
try:
    import fcntl
    HAS_FCNTL = True
except ImportError:
    HAS_FCNTL = False

try:
    import msvcrt
    HAS_MSVCRT = True
except ImportError:
    HAS_MSVCRT = False


def ensure_directories() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(EXPORT_DIR, exist_ok=True)


@contextmanager
def file_lock(lock_path: str):
    """Cross-platform exclusive file lock to prevent concurrent write corruption."""
    ensure_directories()
    lock_file = open(lock_path, "w", encoding="utf-8")
    try:
        if HAS_FCNTL:
            fcntl.flock(lock_file.fileno(), fcntl.LOCK_EX)
        elif HAS_MSVCRT:
            msvcrt.locking(lock_file.fileno(), msvcrt.LK_LOCK, 1)
        yield
    finally:
        try:
            if HAS_FCNTL:
                fcntl.flock(lock_file.fileno(), fcntl.LOCK_UN)
            elif HAS_MSVCRT:
                msvcrt.locking(lock_file.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        lock_file.close()


class HabitRepository(ABC):
    """Abstract Repository interface decoupling storage engine from business logic."""

    @abstractmethod
    def add_record(self, record: HabitRecord) -> HabitRecord:
        pass

    @abstractmethod
    def add_many(self, records: List[HabitRecord]) -> int:
        pass

    @abstractmethod
    def get_all(self) -> List[HabitRecord]:
        pass

    @abstractmethod
    def search(self, query: str) -> List[HabitRecord]:
        pass


class SQLiteHabitRepository(HabitRepository):
    """Indexed SQLite repository eliminating O(N) scan bottlenecks with WAL concurrency."""

    def __init__(self, db_path: str = DB_FILE, json_mirror: str = JSON_FILE, csv_mirror: str = CSV_BACKUP_FILE):
        ensure_directories()
        self.db_path = db_path
        self.json_mirror = json_mirror
        self.csv_mirror = csv_mirror
        self.lock_path = f"{self.db_path}.lock"
        self._init_schema()
        self._bootstrap_from_json_if_empty()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL;")
        return conn

    def _init_schema(self) -> None:
        with file_lock(self.lock_path):
            with self._connect() as conn:
                conn.execute(
                    """
                    CREATE TABLE IF NOT EXISTS habits (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL,
                        category TEXT NOT NULL,
                        value REAL NOT NULL,
                        notes TEXT DEFAULT ''
                    );
                    """
                )
                conn.execute("CREATE INDEX IF NOT EXISTS idx_habits_date ON habits(date DESC);")
                conn.execute("CREATE INDEX IF NOT EXISTS idx_habits_category ON habits(category);")
                conn.commit()
        logger.debug("SQLite schema and indexes verified at %s", self.db_path)

    def _bootstrap_from_json_if_empty(self) -> None:
        """Migrates existing JSON seed data into SQLite automatically on first run."""
        if len(self.get_all()) == 0 and os.path.exists(self.json_mirror):
            json_records = load_json_records(self.json_mirror)
            if json_records:
                self.add_many(json_records)
                logger.info("Bootstrapped %d records from %s into SQLite.", len(json_records), self.json_mirror)

    def add_record(self, record: HabitRecord) -> HabitRecord:
        with file_lock(self.lock_path):
            with self._connect() as conn:
                cur = conn.execute(
                    "INSERT INTO habits (date, category, value, notes) VALUES (?, ?, ?, ?)",
                    (record.date, record.category, record.value, record.notes),
                )
                record.record_id = cur.lastrowid
                conn.commit()
        logger.info("Inserted record ID=%s (%s: %s on %s)", record.record_id, record.category, record.value, record.date)
        self._sync_mirrors()
        return record

    def add_many(self, records: List[HabitRecord]) -> int:
        if not records:
            return 0
        with file_lock(self.lock_path):
            with self._connect() as conn:
                conn.executemany(
                    "INSERT INTO habits (date, category, value, notes) VALUES (?, ?, ?, ?)",
                    [(r.date, r.category, r.value, r.notes) for r in records],
                )
                conn.commit()
        logger.info("Bulk inserted %d records into SQLite.", len(records))
        self._sync_mirrors()
        return len(records)

    def get_all(self) -> List[HabitRecord]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT id, date, category, value, notes FROM habits ORDER BY date DESC, id DESC"
            ).fetchall()
        return [
            HabitRecord(
                record_id=row["id"],
                date=row["date"],
                category=row["category"],
                value=row["value"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def search(self, query: str) -> List[HabitRecord]:
        """Uses SQLite indexed LIKE queries rather than full Python memory scans."""
        pattern = f"%{query.strip().lower()}%"
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, date, category, value, notes
                FROM habits
                WHERE LOWER(category) LIKE ? OR LOWER(notes) LIKE ? OR date LIKE ?
                ORDER BY date DESC, id DESC
                """,
                (pattern, pattern, pattern),
            ).fetchall()
        return [
            HabitRecord(
                record_id=row["id"],
                date=row["date"],
                category=row["category"],
                value=row["value"],
                notes=row["notes"],
            )
            for row in rows
        ]

    def _sync_mirrors(self) -> None:
        """Atomically mirrors SQLite state to JSON and CSV for portability."""
        records = self.get_all()
        save_json_records(records, self.json_mirror, self.csv_mirror)


def load_json_records(filepath: str = JSON_FILE) -> List[HabitRecord]:
    ensure_directories()
    if not os.path.exists(filepath):
        save_json_records([], filepath)
        return []

    try:
        with open(filepath, "r", encoding="utf-8") as f:
            raw_data = json.load(f)
        if not isinstance(raw_data, list):
            raise ValueError("JSON root must be a list.")
        records = []
        for item in raw_data:
            ok, cleaned, _ = validate_record_fields(
                item.get("date", ""), item.get("category", ""), item.get("value", "")
            )
            if ok and cleaned:
                cleaned["notes"] = str(item.get("notes", "")).strip()
                records.append(HabitRecord.from_dict(cleaned))
        return records
    except (json.JSONDecodeError, ValueError, OSError) as exc:
        logger.error("Corrupted or unreadable JSON file at %s: %s. Resetting clean file.", filepath, exc)
        save_json_records([], filepath)
        return []


def save_json_records(
    records: List[HabitRecord],
    filepath: str = JSON_FILE,
    csv_filepath: Optional[str] = CSV_BACKUP_FILE,
) -> None:
    """Thread/process-safe atomic write using file locks + os.replace."""
    ensure_directories()
    lock_path = f"{filepath}.lock"
    serialized = [r.to_dict() for r in records]

    with file_lock(lock_path):
        dir_name = os.path.dirname(filepath) or "."
        fd, tmp_path = tempfile.mkstemp(dir=dir_name, prefix=".tmp_habits_", suffix=".json")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_file:
                json.dump(serialized, tmp_file, indent=4)
            os.replace(tmp_path, filepath)
        except Exception as exc:
            logger.error("Atomic JSON write failed: %s", exc)
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
            raise

        if csv_filepath:
            with open(csv_filepath, "w", newline="", encoding="utf-8") as cf:
                writer = csv.DictWriter(cf, fieldnames=["date", "category", "value", "notes"])
                writer.writeheader()
                for row in serialized:
                    writer.writerow({k: row.get(k, "") for k in ["date", "category", "value", "notes"]})


def import_bulk_csv(csv_path: str, repo: HabitRepository) -> Tuple[int, List[str]]:
    """Bulk CSV import with row-by-row validation, logging, and batch repository commit."""
    if not os.path.exists(csv_path):
        msg = f"File not found: {csv_path}"
        logger.warning("Bulk CSV import failed: %s", msg)
        return 0, [msg]

    valid_batch: List[HabitRecord] = []
    errors: List[str] = []

    try:
        with open(csv_path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames or not {"date", "category", "value"}.issubset(set(reader.fieldnames)):
                msg = "CSV missing required headers: date, category, value"
                logger.warning("Bulk CSV import aborted: %s", msg)
                return 0, [msg]

            for idx, row in enumerate(reader, start=2):
                ok, cleaned, err_msg = validate_record_fields(
                    row.get("date", ""), row.get("category", ""), row.get("value", "")
                )
                if ok and cleaned:
                    cleaned["notes"] = str(row.get("notes", "")).strip()
                    valid_batch.append(HabitRecord.from_dict(cleaned))
                else:
                    errors.append(f"Row {idx}: {err_msg}")
    except OSError as exc:
        logger.error("OS error reading CSV %s: %s", csv_path, exc)
        errors.append(f"File read error: {exc}")

    added_count = repo.add_many(valid_batch) if valid_batch else 0
    logger.info("Bulk CSV import finished: %d imported, %d rejected.", added_count, len(errors))
    return added_count, errors
