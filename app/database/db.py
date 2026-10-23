"""
SQLite database setup and connection manager.
Uses WAL mode for high concurrency and robust local persistence.
"""

import sqlite3
import threading
from pathlib import Path
from contextlib import contextmanager
from config import CONFIG
from app.utils.logger import logger

_DB_LOCK = threading.Lock()

CREATE_TABLES_SQL = """
CREATE TABLE IF NOT EXISTS contacts (
    record_id TEXT PRIMARY KEY,
    collected_at TEXT NOT NULL,
    person_or_profile_name TEXT,
    job_title TEXT,
    organization_name TEXT,
    business_email TEXT,
    contact_number TEXT,
    normalized_phone TEXT,
    website_url TEXT,
    social_profile_url TEXT,
    source_application TEXT,
    source_url TEXT,
    evidence TEXT,
    email_validation_status TEXT,
    phone_validation_status TEXT,
    review_status TEXT,
    deduplication_hash TEXT UNIQUE
);

CREATE INDEX IF NOT EXISTS idx_contacts_email ON contacts(business_email);
CREATE INDEX IF NOT EXISTS idx_contacts_phone ON contacts(normalized_phone);
CREATE INDEX IF NOT EXISTS idx_contacts_dedup ON contacts(deduplication_hash);
CREATE INDEX IF NOT EXISTS idx_contacts_review ON contacts(review_status);

CREATE TABLE IF NOT EXISTS pending_csv_queue (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id TEXT NOT NULL,
    record_json TEXT NOT NULL,
    created_at TEXT NOT NULL,
    retry_count INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    mode TEXT,
    captures_processed INTEGER DEFAULT 0,
    contacts_extracted INTEGER DEFAULT 0,
    duplicates_skipped INTEGER DEFAULT 0
);
"""

def init_db(db_path: str = None) -> None:
    """Initializes the SQLite database with required tables and pragmas."""
    path = db_path or CONFIG.db_path
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    
    with _DB_LOCK:
        conn = sqlite3.connect(path)
        try:
            conn.execute("PRAGMA journal_mode = WAL;")
            conn.execute("PRAGMA synchronous = NORMAL;")
            conn.executescript(CREATE_TABLES_SQL)
            conn.commit()
            logger.info(f"Database initialized successfully at {path}")
        finally:
            conn.close()

@contextmanager
def get_db_connection(db_path: str = None):
    """Context manager for thread-safe SQLite database connections."""
    path = db_path or CONFIG.db_path
    conn = sqlite3.connect(path, timeout=15.0)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()
