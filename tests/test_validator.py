"""
Unit tests for contact schema validation, email syntax checking, and phone normalization.
"""

import pytest
from app.services.contact_validator import (
    ContactRecord,
    validate_and_normalize_email,
    normalize_telephone,
    clean_and_validate_record
)

def test_valid_email_normalization():
    email, status = validate_and_normalize_email("  Test.User+Filter@Domain.COM  ")
    assert email == "test.user+filter@domain.com"
    assert status == "VALID_SYNTAX"

def test_invalid_email_syntax():
    email, status = validate_and_normalize_email("not-an-email@com")
    assert status == "INVALID"

def test_phone_normalization_e164():
    raw, e164, status = normalize_telephone("+1 (415) 555-2671", default_region="US")
    assert e164 == "+14155552671"
    assert status in ("VALID_E164", "POSSIBLE")

def test_clean_and_validate_record_null_handling():
    raw_data = {
        "person_or_profile_name": "Jane Doe",
        "job_title": "null",
        "organization_name": "N/A",
        "business_email": "jane.doe@example.com",
        "contact_number": "   ",
        "website_url": "unknown"
    }
    rec = clean_and_validate_record(raw_data)
    assert rec is not None
    assert rec.person_or_profile_name == "Jane Doe"
    assert rec.job_title is None
    assert rec.organization_name is None
    assert rec.business_email == "jane.doe@example.com"
    assert rec.contact_number is None
    assert rec.website_url is None
    assert rec.email_validation_status == "VALID_SYNTAX"

def test_empty_record_rejected():
    empty_data = {
        "person_or_profile_name": "",
        "business_email": None,
        "contact_number": None
    }
    rec = clean_and_validate_record(empty_data)
    assert rec is None
