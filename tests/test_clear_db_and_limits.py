"""
Unit tests for database clearing on session start, CSV reset, and >2000 record scaling.
"""

import tempfile
from pathlib import Path
from app.services.contact_validator import ContactRecord
from app.database.repository import ContactRepository
from app.services.csv_service import CSVService
from app.services.deduplication import Deduplicator

def test_clear_all_contacts():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        repo = ContactRepository(db_path)

        rec = ContactRecord(
            person_or_profile_name="John Doe",
            business_email="john@example.com",
            organization_name="Example Corp"
        )
        repo.insert_contact(rec, "hash_123")
        repo.enqueue_pending_csv(rec)

        assert len(repo.get_all_contacts()) == 1
        assert len(repo.pop_pending_csv_records()) == 1

        # Clear database
        repo.clear_all_contacts()

        assert len(repo.get_all_contacts()) == 0
        assert len(repo.pop_pending_csv_records()) == 0

def test_get_all_contacts_exceeds_2000_limit():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        repo = ContactRepository(db_path)

        # Insert 2500 records
        for i in range(2500):
            rec = ContactRecord(
                person_or_profile_name=f"Person {i}",
                business_email=f"user_{i}@example.com",
                organization_name="Test Org"
            )
            repo.insert_contact(rec, f"hash_{i}")

        # Default limit=None should return all 2500 records
        all_records = repo.get_all_contacts()
        assert len(all_records) == 2500

        # Custom limit should also work
        limited_records = repo.get_all_contacts(limit=50)
        assert len(limited_records) == 50

def test_reset_csv():
    with tempfile.TemporaryDirectory() as tmpdir:
        csv_path = Path(tmpdir) / "leads.csv"
        db_path = Path(tmpdir) / "test.db"
        repo = ContactRepository(str(db_path))
        svc = CSVService(str(csv_path), repo=repo)

        # Append records
        for i in range(5):
            rec = ContactRecord(
                person_or_profile_name=f"Lead {i}",
                business_email=f"lead_{i}@test.com"
            )
            svc.append_record(rec)

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
            assert len(lines) == 6  # 1 header + 5 records

        # Reset CSV
        svc.reset_csv()

        with open(csv_path, "r", encoding="utf-8-sig") as f:
            lines = f.readlines()
            assert len(lines) == 1  # only header remains

def test_deduplicator_clear():
    dedup = Deduplicator()
    rec = ContactRecord(
        person_or_profile_name="Alice Smith",
        business_email="alice@smith.com"
    )

    dedup.register(rec)
    assert dedup.is_duplicate(rec) is True

    # Clear deduplicator
    dedup.clear()
    assert dedup.is_duplicate(rec) is False
