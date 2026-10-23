"""
End-to-end integration test of the extraction pipeline using synthetic fixtures and mock inference.
"""

import tempfile
from pathlib import Path
from unittest.mock import patch
from tests.fixtures.synthetic_contacts import generate_synthetic_contact_image
from app.services.contact_validator import clean_and_validate_record
from app.services.deduplication import Deduplicator
from app.database.repository import ContactRepository
from app.services.csv_service import CSVService

def test_full_extraction_pipeline_flow():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.db")
        csv_path = str(Path(tmpdir) / "output.csv")

        repo = ContactRepository(db_path)
        csv_service = CSVService(csv_path, repo=repo)
        deduplicator = Deduplicator()

        # 1. Generate Synthetic Card Image
        image = generate_synthetic_contact_image("tech_director")
        assert image.size == (600, 320)

        # 2. Simulated Model Structured Response
        simulated_model_output = {
            "person_or_profile_name": "Sarah Jenkins",
            "job_title": "Director of Engineering",
            "organization_name": "Apex Cloud Technologies",
            "business_email": "s.jenkins@apexcloud.tech",
            "contact_number": "+1 (415) 555-0199",
            "website_url": "https://www.apexcloud.tech",
            "social_profile_url": "https://linkedin.com/in/sarahjenkins-apex",
            "evidence": "Sarah Jenkins Director of Engineering Apex Cloud"
        }

        # 3. Validation & Normalization
        record = clean_and_validate_record(simulated_model_output)
        assert record is not None
        assert record.person_or_profile_name == "Sarah Jenkins"
        assert record.normalized_phone == "+14155550199"
        assert record.email_validation_status == "VALID_SYNTAX"

        # 4. Deduplication & Persistence
        fingerprint = deduplicator.generate_fingerprint(record)
        assert not deduplicator.is_duplicate(record)

        deduplicator.register(record)
        saved_db = repo.insert_contact(record, fingerprint)
        assert saved_db

        saved_csv = csv_service.append_record(record)
        assert saved_csv

        # 5. Verify CSV content
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            csv_text = f.read()
            assert "Sarah Jenkins" in csv_text
            assert "s.jenkins@apexcloud.tech" in csv_text
            assert "+14155550199" in csv_text

        # 6. Verify duplicate is rejected on second attempt
        assert deduplicator.is_duplicate(record)
        saved_dup = repo.insert_contact(record, fingerprint)
        assert not saved_dup
