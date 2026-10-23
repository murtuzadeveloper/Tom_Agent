"""
Data redaction and sanitization utilities.
Scrubs passwords, credit card numbers, auth tokens, and protects against formula injection.
"""

import re
from typing import Optional

# Regex Patterns for Sensitive Data
CREDIT_CARD_REGEX = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
SSN_REGEX = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
AUTH_BEARER_REGEX = re.compile(r'(?i)\b(?:bearer\s+[a-z0-9_\-\.]{16,}|ghp_[a-z0-9]{36}|ey[a-z0-9_-]{10,}\.[a-z0-9_-]{10,})\b')
PASSWORD_FIELD_REGEX = re.compile(r'(?i)(password|passwd|pwd|secret|api[_-]?key)\s*[:=]\s*(\S+)')

def sanitize_ocr_text(text: str) -> str:
    """
    Sanitizes raw OCR text by masking sensitive credentials,
    credit cards, and authorization tokens before model submission.
    """
    if not text:
        return ""
    
    redacted = CREDIT_CARD_REGEX.sub("[REDACTED_CARD]", text)
    redacted = SSN_REGEX.sub("[REDACTED_SSN]", redacted)
    redacted = AUTH_BEARER_REGEX.sub("[REDACTED_TOKEN]", redacted)
    redacted = PASSWORD_FIELD_REGEX.sub(r'\1: [REDACTED_SECRET]', redacted)
    return redacted

def sanitize_csv_cell(value: Optional[str]) -> str:
    """
    Prevents CSV Spreadsheet Formula Injection (CSV Injection / DDE).
    If a cell value starts with '=', '+', '-', or '@', or tab/CR,
    it is prepended with a single quote to prevent execution in Excel/Calc.
    """
    if not value:
        return ""
    
    text = str(value).strip()
    if text and text[0] in ('=', '+', '-', '@', '\t', '\r'):
        return f"'{text}"
    return text
