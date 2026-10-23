"""
Unit tests for CSV writing, UTF-8 BOM encoding, formula injection prevention, and file lock queuing.
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import patch
from app.services.contact_validator import ContactRecord
from app.services.csv_service import CSVService
from app.database.repository import ContactRepository

def test_csv_init_with_utf8_bom():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "test_leads.csv"
        db_path = Path(tmpdir) / "test.db"
        repo = ContactRepository(str(db_path))
        svc = CSVService(str(csv_path), repo=repo)

        assert csv_path.exists()
        # Check for UTF-8 BOM bytes: b'\xef\xbb\xbf'
        with open(csv_path, "rb") as f:
            header_bytes = f.read(3)
            assert header_bytes == b'\xef\xbb\xbf'

def test_formula_injection_sanitization():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "formula_test.csv"
        db_path = Path(tmpdir) / "test.db"
        repo = ContactRepository(str(db_path))
        svc = CSVService(str(csv_path), repo=repo)

        rec = ContactRecord(
            person_or_profile_name="=cmd|'/C calc'!A0",
            business_email="+malicious@evil.com",
            job_title="-dangerous_flag"
        )
        svc.append_record(rec)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            content = f.read()
            # Escaped with single quote
            assert "'=cmd|'/C calc'!A0" in content
            assert "'+malicious@evil.com" in content
            assert "'-dangerous_flag" in content

def test_csv_file_lock_queues_to_sqlite():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "locked.csv"
        db_path = Path(tmpdir) / "test.db"
        repo = ContactRepository(str(db_path))
        svc = CSVService(str(csv_path), repo=repo)

        rec = ContactRecord(
            person_or_profile_name="Locked Person",
            business_email="locked@test.com"
        )

        # Simulate Excel holding an exclusive write lock (PermissionError)
        with patch("builtins.open", side_effect=PermissionError("File locked by Excel")):
            success = svc.append_record(rec)
            assert not success

        # Verify record was safely enqueued in SQLite
        pending = repo.pop_pending_csv_records()
        assert len(pending) == 1
        assert pending[0][1].person_or_profile_name == "Locked Person"

        # Now flush pending when lock is released
        flushed = svc.flush_pending()
        assert flushed == 1
