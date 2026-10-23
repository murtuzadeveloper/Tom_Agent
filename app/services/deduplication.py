"""
Deduplication service for contact records.
Uses a multi-tier fingerprinting strategy to prevent duplicate contacts
without merging distinct individuals working for the same company.
"""

import hashlib
from typing import Set, Optional
from app.services.contact_validator import ContactRecord

class Deduplicator:
    """Manages unique contact fingerprints in memory and database."""

    def __init__(self):
        self._seen_hashes: Set[str] = set()

    def generate_fingerprint(self, record: ContactRecord) -> str:
        """
        Generates a stable deterministic SHA-256 fingerprint for a record.
        Strict rule: Do not merge different people solely because of the same organization.
        """
        # Tier 1: Normalized business email is universally unique
        if record.business_email and record.email_validation_status != "INVALID":
            raw_key = f"email:{record.business_email.strip().lower()}"
            return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # Tier 2: Normalized telephone number (E.164) is unique
        if record.normalized_phone:
            raw_key = f"phone:{record.normalized_phone.strip()}"
            return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # Tier 3: Social profile URL (e.g. LinkedIn / Twitter profile)
        if record.social_profile_url:
            clean_social = record.social_profile_url.strip().lower().rstrip('/')
            return hashlib.sha256(f"social:{clean_social}".encode('utf-8')).hexdigest()

        # Tier 4: Website URL or Application Link
        if record.website_url:
            clean_web = record.website_url.strip().lower().rstrip('/')
            raw_key = f"web:{clean_web}"
            if record.job_title:
                raw_key += f"::{record.job_title.strip().lower()}"
            return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # Tier 5: Source URL (if starts with http)
        if record.source_url and record.source_url.strip().lower().startswith("http"):
            clean_src = record.source_url.strip().lower().rstrip('/')
            raw_key = f"source_url:{clean_src}"
            if record.job_title:
                raw_key += f"::{record.job_title.strip().lower()}"
            return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # Tier 6: Person name combined with Organization
        if record.person_or_profile_name and record.organization_name:
            p_name = record.person_or_profile_name.strip().lower()
            org_name = record.organization_name.strip().lower()
            raw_key = f"person_org:{p_name}::{org_name}"
            return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # Tier 7: Person name combined with Source URL or raw contact number
        if record.person_or_profile_name and (record.source_url or record.contact_number):
            p_name = record.person_or_profile_name.strip().lower()
            aux = (record.source_url or record.contact_number or "").strip().lower()
            raw_key = f"person_aux:{p_name}::{aux}"
            return hashlib.sha256(raw_key.encode('utf-8')).hexdigest()

        # Fallback: Record ID
        return hashlib.sha256(f"record:{record.record_id}".encode('utf-8')).hexdigest()

    def is_duplicate(self, record: ContactRecord) -> bool:
        """Checks if the record fingerprint was already processed."""
        fingerprint = self.generate_fingerprint(record)
        return fingerprint in self._seen_hashes

    def register(self, record: ContactRecord) -> str:
        """Registers the record fingerprint. Returns the generated hash."""
        fingerprint = self.generate_fingerprint(record)
        self._seen_hashes.add(fingerprint)
        return fingerprint

    def clear(self) -> None:
        """Resets the in-memory deduplication set."""
        self._seen_hashes.clear()
