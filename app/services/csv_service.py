"""
Thread-safe CSV management service for murtuzadeveloper Smart Leads.
Implements UTF-8 with BOM for Excel compatibility, formula injection protection,
and automatic queuing when Excel locks the file.
"""

import csv
import os
import threading
from pathlib import Path
from typing import List, Optional
from config import CONFIG
from app.services.contact_validator import ContactRecord
from app.security.data_redaction import sanitize_csv_cell
from app.database.repository import ContactRepository
from app.utils.logger import logger

CSV_COLUMNS = [
    "record_id",
    "collected_at",
    "person_or_profile_name",
    "job_title",
    "organization_name",
    "business_email",
    "contact_number",
    "normalized_phone",
    "website_url",
    "social_profile_url",
    "source_application",
    "source_url",
    "evidence",
    "email_validation_status",
    "phone_validation_status",
    "review_status"
]

class CSVService:
    """Handles thread-safe writing, queuing, and exporting of contact records to CSV."""

    def __init__(self, file_path: str = None, repo: ContactRepository = None):
        self.file_path = file_path or CONFIG.csv_path
        self.repo = repo or ContactRepository(CONFIG.db_path)
        self._lock = threading.Lock()
        self.init_csv()

    def init_csv(self) -> None:
        """Ensures the destination directory exists and writes header if file doesn't exist."""
        with self._lock:
            path = Path(self.file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists() or path.stat().st_size == 0:
                try:
                    with open(path, "w", newline="", encoding="utf-8-sig") as f:
                        writer = csv.writer(f)
                        writer.writerow(CSV_COLUMNS)
                    logger.info(f"Initialized CSV header at {self.file_path}")
                except Exception as e:
                    logger.error(f"Failed to initialize CSV at {self.file_path}: {e}")

    def reset_csv(self) -> None:
        """Overwrites CSV file with a fresh header row for a new capture session."""
        with self._lock:
            path = Path(self.file_path)
            path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with open(path, "w", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    writer.writerow(CSV_COLUMNS)
                logger.info(f"Reset CSV file at {self.file_path}")
            except Exception as e:
                logger.error(f"Failed to reset CSV at {self.file_path}: {e}")

    def append_record(self, record: ContactRecord) -> bool:
        """
        Appends a record to the CSV file. If Excel has the file locked (PermissionError),
        the record is safely saved to the SQLite pending queue and retried later.
        """
        row_data = [
            sanitize_csv_cell(getattr(record, col, ""))
            for col in CSV_COLUMNS
        ]

        with self._lock:
            try:
                # First, attempt to flush any pending queue items
                self._flush_pending_no_lock()

                path = Path(self.file_path)
                file_exists = path.exists() and path.stat().st_size > 0

                with open(path, "a", newline="", encoding="utf-8-sig") as f:
                    writer = csv.writer(f)
                    if not file_exists:
                        writer.writerow(CSV_COLUMNS)
                    writer.writerow(row_data)
                    f.flush()
                    try:
                        os.fsync(f.fileno())
                    except Exception:
                        pass
                return True

            except (PermissionError, IOError) as pe:
                logger.warning(f"CSV file is locked by another process (e.g. Excel). Queuing record {record.record_id} to DB: {pe}")
                try:
                    self.repo.enqueue_pending_csv(record)
                except Exception as db_err:
                    logger.error(f"Failed to enqueue locked record: {db_err}")
                return False

            except Exception as e:
                logger.error(f"Unexpected error appending to CSV: {e}")
                self.repo.enqueue_pending_csv(record)
                return False

    def _flush_pending_no_lock(self) -> int:
        """Internal helper to write pending queued records without acquiring self._lock twice."""
        pending = self.repo.pop_pending_csv_records()
        if not pending:
            return 0

        path = Path(self.file_path)
        file_exists = path.exists() and path.stat().st_size > 0

        written_count = 0
        try:
            with open(path, "a", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                if not file_exists:
                    writer.writerow(CSV_COLUMNS)
                    file_exists = True

                for qid, record in pending:
                    row_data = [
                        sanitize_csv_cell(getattr(record, col, ""))
                        for col in CSV_COLUMNS
                    ]
                    writer.writerow(row_data)
                    self.repo.delete_pending_csv_record(qid)
                    written_count += 1
                f.flush()
                try:
                    os.fsync(f.fileno())
                except Exception:
                    pass
            if written_count > 0:
                logger.info(f"Successfully flushed {written_count} pending locked records to CSV.")
        except Exception:
            # File still locked; items remain in DB queue
            pass
        return written_count

    def flush_pending(self) -> int:
        """Public thread-safe call to flush pending queued records."""
        with self._lock:
            return self._flush_pending_no_lock()

    def export_records_to_file(
        self,
        records: List[ContactRecord],
        target_path: str,
        exclude_unreviewed: bool = False
    ) -> int:
        """
        Exports a filtered subset or all records to a user-specified CSV location.
        """
        path = Path(target_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        count = 0

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(CSV_COLUMNS)
            for rec in records:
                if exclude_unreviewed and rec.review_status == "PENDING":
                    continue
                row_data = [
                    sanitize_csv_cell(getattr(rec, col, ""))
                    for col in CSV_COLUMNS
                ]
                writer.writerow(row_data)
                count += 1
            f.flush()

        logger.info(f"Exported {count} records to {target_path}")
        return count
