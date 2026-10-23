"""
Database repository for persistence, deduplication checking, and recovery.
"""

import json
from typing import List, Optional, Tuple, Dict, Any
from app.database.db import get_db_connection, init_db
from app.services.contact_validator import ContactRecord
from app.utils.logger import logger

class ContactRepository:
    """Manages persistent SQLite operations for Smart Leads."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path
        init_db(self.db_path)

    def insert_contact(self, record: ContactRecord, dedup_hash: str) -> bool:
        """
        Inserts a new contact record. Returns True if saved, False if duplicate.
        """
        sql = """
        INSERT INTO contacts (
            record_id, collected_at, person_or_profile_name, job_title,
            organization_name, business_email, contact_number, normalized_phone,
            website_url, social_profile_url, source_application, source_url,
            evidence, email_validation_status, phone_validation_status,
            review_status, deduplication_hash
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        try:
            with get_db_connection(self.db_path) as conn:
                conn.execute(sql, (
                    record.record_id,
                    record.collected_at,
                    record.person_or_profile_name,
                    record.job_title,
                    record.organization_name,
                    record.business_email,
                    record.contact_number,
                    record.normalized_phone,
                    record.website_url,
                    record.social_profile_url,
                    record.source_application,
                    record.source_url,
                    record.evidence,
                    record.email_validation_status,
                    record.phone_validation_status,
                    record.review_status,
                    dedup_hash
                ))
                conn.commit()
                return True
        except Exception as e:
            # UNIQUE constraint failed on deduplication_hash
            if "UNIQUE constraint failed" in str(e):
                return False
            logger.error(f"Error inserting contact {record.record_id}: {e}")
            return False

    def is_hash_exists(self, dedup_hash: str) -> bool:
        """Checks if a deduplication hash already exists in the database."""
        sql = "SELECT 1 FROM contacts WHERE deduplication_hash = ? LIMIT 1;"
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(sql, (dedup_hash,))
            return cur.fetchone() is not None

    def clear_all_contacts(self) -> None:
        """Clears all contacts and pending CSV queue entries from the database."""
        with get_db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM contacts;")
            conn.execute("DELETE FROM pending_csv_queue;")
            conn.commit()

    def get_all_contacts(
        self,
        limit: Optional[int] = None,
        review_filter: Optional[str] = None,
        search_query: Optional[str] = None
    ) -> List[ContactRecord]:
        """Fetches contacts with optional review filter and search string. If limit is None or <= 0, returns all."""
        conditions = []
        params = []

        if review_filter and review_filter != "ALL":
            conditions.append("review_status = ?")
            params.append(review_filter)

        if search_query and search_query.strip():
            like_term = f"%{search_query.strip()}%"
            conditions.append("""
            (person_or_profile_name LIKE ? OR
             organization_name LIKE ? OR
             business_email LIKE ? OR
             contact_number LIKE ? OR
             job_title LIKE ? OR
             website_url LIKE ? OR
             social_profile_url LIKE ? OR
             source_url LIKE ?)
            """)
            params.extend([like_term, like_term, like_term, like_term, like_term, like_term, like_term, like_term])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        if limit is not None and limit > 0:
            sql = f"SELECT * FROM contacts {where_clause} ORDER BY collected_at DESC LIMIT ?;"
            params.append(limit)
        else:
            sql = f"SELECT * FROM contacts {where_clause} ORDER BY collected_at DESC;"

        records = []
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(sql, params)
            for row in cur.fetchall():
                data = dict(row)
                data.pop("deduplication_hash", None)
                records.append(ContactRecord(**data))
        return records

    def update_review_status(self, record_id: str, new_status: str) -> bool:
        """Updates the review status ('PENDING', 'APPROVED', 'REJECTED') of a record."""
        sql = "UPDATE contacts SET review_status = ? WHERE record_id = ?;"
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(sql, (new_status, record_id))
            conn.commit()
            return cur.rowcount > 0

    def update_contact_fields(self, record_id: str, updates: Dict[str, Any]) -> bool:
        """Updates specific fields of a contact record."""
        allowed_fields = [
            "person_or_profile_name", "job_title", "organization_name",
            "business_email", "contact_number", "normalized_phone",
            "website_url", "social_profile_url", "evidence", "review_status"
        ]
        set_clauses = []
        params = []
        for k, v in updates.items():
            if k in allowed_fields:
                set_clauses.append(f"{k} = ?")
                params.append(v)

        if not set_clauses:
            return False

        params.append(record_id)
        sql = f"UPDATE contacts SET {', '.join(set_clauses)} WHERE record_id = ?;"
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(sql, params)
            conn.commit()
            return cur.rowcount > 0

    def delete_contact(self, record_id: str) -> bool:
        """Deletes a contact by record_id."""
        sql = "DELETE FROM contacts WHERE record_id = ?;"
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(sql, (record_id,))
            conn.commit()
            return cur.rowcount > 0

    def enqueue_pending_csv(self, record: ContactRecord) -> None:
        """Enqueues a record that could not be written to CSV due to a file lock."""
        sql = """
        INSERT INTO pending_csv_queue (record_id, record_json, created_at)
        VALUES (?, ?, ?);
        """
        with get_db_connection(self.db_path) as conn:
            conn.execute(sql, (
                record.record_id,
                record.model_dump_json() if hasattr(record, "model_dump_json") else record.json(),
                record.collected_at
            ))
            conn.commit()

    def pop_pending_csv_records(self) -> List[Tuple[int, ContactRecord]]:
        """Retrieves and clears pending CSV records for flush retry."""
        results = []
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute("SELECT id, record_json FROM pending_csv_queue ORDER BY id ASC;")
            rows = cur.fetchall()
            for r in rows:
                qid = r["id"]
                data = json.loads(r["record_json"])
                results.append((qid, ContactRecord(**data)))
        return results

    def delete_pending_csv_record(self, queue_id: int) -> None:
        """Removes a successfully flushed record from the pending queue."""
        with get_db_connection(self.db_path) as conn:
            conn.execute("DELETE FROM pending_csv_queue WHERE id = ?;", (queue_id,))
            conn.commit()

    def get_summary_stats(self) -> dict:
        """Aggregates metrics for the live dashboard."""
        sql = """
        SELECT
            COUNT(*) as total_records,
            SUM(CASE WHEN business_email IS NOT NULL AND business_email != '' THEN 1 ELSE 0 END) as total_emails,
            SUM(CASE WHEN (normalized_phone IS NOT NULL AND normalized_phone != '') OR (contact_number IS NOT NULL AND contact_number != '') THEN 1 ELSE 0 END) as total_phones,
            SUM(CASE WHEN (website_url IS NOT NULL AND website_url != '') OR (social_profile_url IS NOT NULL AND social_profile_url != '') OR (source_url IS NOT NULL AND source_url LIKE 'http%') THEN 1 ELSE 0 END) as total_links,
            SUM(CASE WHEN organization_name IS NOT NULL AND organization_name != '' THEN 1 ELSE 0 END) as total_orgs,
            SUM(CASE WHEN job_title IS NOT NULL AND job_title != '' THEN 1 ELSE 0 END) as total_titles,
            SUM(CASE WHEN review_status = 'APPROVED' THEN 1 ELSE 0 END) as total_approved
        FROM contacts;
        """
        with get_db_connection(self.db_path) as conn:
            cur = conn.execute(sql)
            row = cur.fetchone()
            if row:
                return {
                    "total_records": row["total_records"] or 0,
                    "total_emails": row["total_emails"] or 0,
                    "total_phones": row["total_phones"] or 0,
                    "total_links": row["total_links"] or 0,
                    "total_orgs": row["total_orgs"] or 0,
                    "total_titles": row["total_titles"] or 0,
                    "total_approved": row["total_approved"] or 0,
                }
            return {
                "total_records": 0, "total_emails": 0, "total_phones": 0,
                "total_links": 0, "total_orgs": 0, "total_titles": 0, "total_approved": 0
            }

    def clean_and_repair_stored_contacts(self) -> int:
        """
        Cleans, repairs, and sanitizes existing records in the database:
        - Deletes records captured from LM Studio, noise UI text, or containing no valid contact points.
        - Corrects OCR email domain typos and repairs deduplication.
        - Normalizes names, organizations, job titles, and evidence.
        """
        from app.services.contact_validator import clean_person_name, clean_organization_name, normalize_telephone, correct_ocr_email_typos
        from app.services.ocr_service import (
            derive_name_from_email, format_domain_organization,
            extract_job_title_from_context, clean_context_evidence, DISALLOWED_ORGS
        )

        records = self.get_all_contacts()
        updated_count = 0
        seen_clean_emails = set()

        for rec in records:
            # 1. Delete LM Studio noise records or noise text
            is_lm_studio = any("lmstudio" in str(f).lower() or "lm studio" in str(f).lower() 
                               for f in [rec.source_application, rec.organization_name, rec.person_or_profile_name])
            if is_lm_studio and not rec.business_email:
                self.delete_contact(rec.record_id)
                updated_count += 1
                continue

            # 2. Correct OCR typos in business email
            clean_email = rec.business_email
            if rec.business_email:
                clean_email = correct_ocr_email_typos(rec.business_email.strip().lower())
                # Merge duplicate records created by OCR typos
                if clean_email in seen_clean_emails:
                    self.delete_contact(rec.record_id)
                    updated_count += 1
                    continue
                seen_clean_emails.add(clean_email)

            # 3. Check and clean phone
            norm_phone = None
            if rec.contact_number:
                _, norm_phone, status = normalize_telephone(rec.contact_number, default_region="PK")
                if status == "INVALID":
                    rec.contact_number = None
                    rec.normalized_phone = None
                else:
                    rec.normalized_phone = norm_phone

            # Drop record if it has NO contact points
            has_link = bool(rec.social_profile_url or rec.website_url or (rec.source_url and str(rec.source_url).startswith("http")))
            if not clean_email and not rec.normalized_phone and not has_link:
                self.delete_contact(rec.record_id)
                updated_count += 1
                continue

            # 4. Clean and derive Name
            cleaned_name = clean_person_name(rec.person_or_profile_name)
            if cleaned_name and cleaned_name.lower() in ("mgrhr", "talent", "manager", "admin", "recruiter", "careers", "hr", "fecruitment", "pplsuccess", "activity", "log"):
                cleaned_name = None
            if not cleaned_name and clean_email:
                cleaned_name = derive_name_from_email(clean_email)

            # 5. Clean Organization
            cleaned_org = clean_organization_name(rec.organization_name)
            if cleaned_org and cleaned_org.lower() in DISALLOWED_ORGS:
                cleaned_org = None
            if not cleaned_org and clean_email:
                domain = clean_email.split('@')[-1].lower()
                generic_domains = ("gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me", "aol.com")
                if domain not in generic_domains:
                    cleaned_org = format_domain_organization(domain.split('.')[0])

            # 6. Extract / Clean Job Title from evidence
            cleaned_title = rec.job_title
            if not cleaned_title and rec.evidence:
                ev_lines = [seg.strip() for seg in rec.evidence.split('|') if seg.strip()]
                cleaned_title = extract_job_title_from_context(ev_lines)

            # 7. Clean Evidence Snippet
            cleaned_ev = rec.evidence
            if rec.evidence:
                ev_lines = [seg.strip() for seg in rec.evidence.split('|') if seg.strip()]
                cleaned_ev = clean_context_evidence(ev_lines)

            # Update if anything changed
            updates = {
                "person_or_profile_name": cleaned_name,
                "job_title": cleaned_title,
                "organization_name": cleaned_org,
                "business_email": clean_email,
                "contact_number": rec.contact_number,
                "normalized_phone": rec.normalized_phone,
                "evidence": cleaned_ev
            }

            self.update_contact_fields(rec.record_id, updates)
            updated_count += 1

        return updated_count

