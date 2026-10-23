"""
Unit tests for multi-tier deduplication and fingerprint stability.
"""

from app.services.contact_validator import ContactRecord
from app.services.deduplication import Deduplicator

def test_same_email_is_duplicate():
    dedup = Deduplicator()
    rec1 = ContactRecord(
        person_or_profile_name="Alice Smith",
        business_email="alice@company.com"
    )
    rec2 = ContactRecord(
        person_or_profile_name="Alice S.",
        business_email="alice@company.com"
    )

    h1 = dedup.register(rec1)
    assert dedup.is_duplicate(rec2)
    assert h1 == dedup.generate_fingerprint(rec2)

def test_different_people_same_organization_not_merged():
    """Verify distinct individuals at the same company are NEVER merged."""
    dedup = Deduplicator()
    rec1 = ContactRecord(
        person_or_profile_name="Alice Johnson",
        organization_name="Global Corp",
        business_email="alice@global.com"
    )
    rec2 = ContactRecord(
        person_or_profile_name="Bob Miller",
        organization_name="Global Corp",
        business_email="bob@global.com"
    )

    h1 = dedup.register(rec1)
    h2 = dedup.generate_fingerprint(rec2)

    assert h1 != h2
    assert not dedup.is_duplicate(rec2)

def test_same_phone_is_duplicate():
    dedup = Deduplicator()
    rec1 = ContactRecord(
        person_or_profile_name="Charlie Brown",
        normalized_phone="+14155550199"
    )
    rec2 = ContactRecord(
        person_or_profile_name="Charlie B.",
        normalized_phone="+14155550199"
    )

    dedup.register(rec1)
    assert dedup.is_duplicate(rec2)
