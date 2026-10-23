"""
Strict Pydantic schema and normalization logic for extracted contacts.
Validates email syntax via email-validator and normalizes telephone numbers via phonenumbers.
"""

import uuid
import re
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel, Field

# Try importing email_validator and phonenumbers with robust fallbacks
try:
    from email_validator import validate_email as _validate_email, EmailNotValidError
    HAVE_EMAIL_VALIDATOR = True
except ImportError:
    HAVE_EMAIL_VALIDATOR = False

try:
    import phonenumbers
    from phonenumbers import PhoneNumberFormat, geocoder
    HAVE_PHONENUMBERS = True
except ImportError:
    HAVE_PHONENUMBERS = False

BASIC_EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')

class ContactRecord(BaseModel):
    """Structured contact extraction model."""
    record_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    collected_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    person_or_profile_name: Optional[str] = None
    job_title: Optional[str] = None
    organization_name: Optional[str] = None
    business_email: Optional[str] = None
    contact_number: Optional[str] = None
    normalized_phone: Optional[str] = None
    website_url: Optional[str] = None
    social_profile_url: Optional[str] = None
    source_application: Optional[str] = None
    source_url: Optional[str] = None
    evidence: Optional[str] = None
    email_validation_status: str = "UNCHECKED"
    phone_validation_status: str = "UNCHECKED"
    review_status: str = "PENDING"  # PENDING, APPROVED, REJECTED

    def has_contact_details(self) -> bool:
        """Determines if the record contains at least one meaningful contact point."""
        return bool(
            (self.business_email and self.business_email.strip()) or
            (self.contact_number and self.contact_number.strip()) or
            (self.normalized_phone and self.normalized_phone.strip()) or
            (self.social_profile_url and self.social_profile_url.strip()) or
            (self.website_url and self.website_url.strip()) or
            (self.source_url and self.source_url.strip() and self.source_url.lower().startswith("http"))
        )

def normalize_url(url_str: Optional[str]) -> Optional[str]:
    """
    Cleans, normalizes, and validates web URLs and links extracted via OCR or model.
    Handles trailing punctuation from sentence context, prefixes with https:// if scheme is missing.
    """
    if not url_str or not isinstance(url_str, str):
        return None

    cleaned = url_str.strip().strip('"\'`<>[]{}()|\\;,')
    cleaned = re.sub(r'[.,;:]+$', '', cleaned)

    if not cleaned or len(cleaned) < 4:
        return None

    lower = cleaned.lower()
    if any(bad in lower for bad in ["127.0.0.1", "localhost", "none", "null", "unknown", "example.com"]):
        return None
    if lower.startswith(("javascript:", "mailto:", "data:")):
        return None

    if lower.startswith("www."):
        cleaned = "https://" + cleaned
    elif re.match(r'^(?:forms\.gle|bit\.ly|tinyurl\.com|lnkd\.in|wa\.me|t\.me|linktr\.ee|shorturl\.at|lever\.co|greenhouse\.io|workable\.com)/', lower):
        cleaned = "https://" + cleaned
    elif not lower.startswith(("http://", "https://")):
        if re.match(r'^[a-zA-Z0-9-]+\.[a-zA-Z]{2,}(?:/.*)?$', cleaned):
            cleaned = "https://" + cleaned
        else:
            return None

    return cleaned

def correct_ocr_email_typos(email_str: str) -> str:
    """Corrects common OCR character misrecognitions in email addresses."""
    if not email_str or "@" not in email_str:
        return email_str

    local, domain = email_str.rsplit('@', 1)
    domain = domain.lower().strip()

    # Common TLD corrections
    if domain.endswith(".ce"):
        domain = domain[:-3] + ".co"
    elif domain.endswith(".c0m"):
        domain = domain[:-4] + ".com"
    elif domain.endswith(".0rg"):
        domain = domain[:-4] + ".org"
    elif domain.endswith(".sl") and "camnitive" in domain:
        domain = domain[:-3] + ".ai"
    elif domain.endswith(".con"):
        domain = domain[:-4] + ".com"

    # Digits misread for vowels in domain roots (e.g., xper2q0 -> xper2go, xper2g0 -> xper2go)
    domain = re.sub(r'xper2[qg][0o]\.com', 'xper2go.com', domain)
    domain = re.sub(r'([a-z]+)0([a-z]+)\.(com|org|net)', r'\g<1>o\g<2>.\3', domain)

    return f"{local}@{domain}"

def validate_and_normalize_email(email_str: Optional[str]) -> tuple[Optional[str], str]:
    """
    Validates email syntax and normalizes common OCR typos.
    Returns (cleaned_email, status).
    Status: 'VALID_SYNTAX', 'INVALID', or 'NONE'
    """
    if not email_str or not email_str.strip():
        return None, "NONE"

    cleaned = correct_ocr_email_typos(email_str.strip().lower())

    if HAVE_EMAIL_VALIDATOR:
        try:
            val = _validate_email(cleaned, check_deliverability=False)
            return val.normalized, "VALID_SYNTAX"
        except EmailNotValidError:
            return cleaned, "INVALID"
    else:
        if BASIC_EMAIL_REGEX.match(cleaned):
            return cleaned, "VALID_SYNTAX"
        return cleaned, "INVALID"

NAME_BLACKLIST_WORDS = {
    "job", "jobs", "opening", "openings", "vacancy", "vacancies", "hiring",
    "urgent", "requirement", "requirements", "opportunity", "opportunities",
    "position", "positions", "role", "roles", "pakistan", "lahore", "karachi",
    "islamabad", "rawalpindi", "dubai", "remote", "onsite", "hybrid", "shift",
    "fulltime", "parttime", "experience", "years", "salary", "stipend", "skills",
    "qualification", "responsibilities", "system", "whatsapp", "chat", "privacy",
    "message", "messages", "group", "channel", "telegram", "profile", "company",
    "organization", "limited", "pvt", "ltd", "inc", "corp", "llc", "solutions",
    "technologies", "software", "developer", "engineer", "manager", "lead", "head",
    "officer", "executive", "intern", "specialist", "designer", "timing", "deadline",
    "apply", "email", "mail", "cv", "resume", "contact", "call", "send", "forward",
    "child", "advanced", "turned", "encryption", "encrypted", "deleted", "security",
    "notification", "today", "yesterday", "view", "details", "looking", "seeking",
    "search", "associate", "business", "development", "we", "are", "team", "stats",
    "idle", "ttl", "evict", "prompt", "model", "token", "tokens", "acquisition",
    "account", "accounts", "hurdles", "crossing", "activity", "log", "smart", "leads",
    "screen", "capture", "results", "database", "export", "dashboard", "settings",
    "preview", "mode", "window", "notice", "alert", "announcement", "post", "posts",
    "candidate", "candidates", "inquiry", "inquiries", "feedback", "overview",
    "description", "summary", "header", "footer", "button", "buttons", "filter",
    "table", "column", "row", "bl", "recent", "updates", "update", "online", "offline"
}

DISALLOWED_ORGANIZATIONS = {
    "whatsapp", "lm studio", "lmstudio", "chrome", "edge", "firefox",
    "desktop", "telegram", "slack", "discord", "windows", "desktop screen",
    "taskbar", "explorer", "gmail", "yahoo", "hotmail", "outlook", "icloud",
    "proton", "aol", "mail", "inbox", "unknown", "none", "null", "n/a",
    "system", "chat", "group", "privacy", "notification"
}

def clean_person_name(name: Optional[str]) -> Optional[str]:
    """Sanitizes candidate person name, rejecting noise, headlines, and system tokens."""
    if not name or not isinstance(name, str):
        return None

    cleaned = name.strip().strip('"\'`‘’“”.,:;*-+~()[]{}|/\\#&')
    if not cleaned or len(cleaned) < 3 or len(cleaned) > 40:
        return None

    # Reject if it contains digits, colons, or suspicious punctuation
    if any(ch in cleaned for ch in [':', ';', '*', '|', '/', '\\', '[', ']', '{', '}', '(', ')', '_', '@', '=', '+', '&', '$', '%', '^', '~', '#']):
        return None

    if re.search(r'\d', cleaned):
        return None

    words = cleaned.split()
    if len(words) < 1 or len(words) > 4:
        return None

    # Check words against blacklist
    lower_words = [w.lower() for w in words]
    if any(w in NAME_BLACKLIST_WORDS for w in lower_words):
        return None

    # Check each word has alphabetic content and starts cleanly
    for w in words:
        if not w.isalpha() or len(w) < 2:
            return None

    return " ".join(w.capitalize() for w in words)

def clean_organization_name(org: Optional[str]) -> Optional[str]:
    """Sanitizes organization name, rejecting messaging clients and application titles."""
    if not org or not isinstance(org, str):
        return None

    cleaned = org.strip().strip('"\'`‘’“”.,:;*-+~()[]{}|/\\')
    if not cleaned or len(cleaned) < 2 or len(cleaned) > 50:
        return None

    org_lower = cleaned.lower()
    if org_lower in DISALLOWED_ORGANIZATIONS or any(bad in org_lower for bad in ["whatsapp", "lm studio", "lmstudio", "desktop screen", "taskbar"]):
        return None

    return cleaned

def normalize_telephone(
    phone_str: Optional[str],
    default_region: str = "US"
) -> tuple[Optional[str], Optional[str], str]:
    """
    Parses and normalizes a phone number to E.164.
    Returns (original_cleaned, normalized_e164, status).
    Status: 'VALID_E164', 'POSSIBLE', 'INVALID', 'NONE'
    """
    if not phone_str or not phone_str.strip():
        return None, None, "NONE"

    cleaned_raw = phone_str.strip()
    raw_lower = cleaned_raw.lower()

    # Reject console logs, stats, and non-phone strings
    if any(term in raw_lower for term in ["ttl", "evict", "stat", "fps", "http", "port", "127.0.0.1", "byte"]):
        return None, None, "INVALID"

    digits = re.sub(r'\D', '', cleaned_raw)

    # Valid international phone numbers have between 10 and 15 digits
    if len(digits) < 10 or len(digits) > 15:
        return None, None, "INVALID"

    # Reject repetitive digits (e.g. 0000000000, 1111111111)
    if len(set(digits)) <= 2:
        return None, None, "INVALID"

    # Handle Pakistani phone numbers directly
    # 03xx xxxxxxx (11 digits) -> +92 3xx xxxxxxx
    if digits.startswith("03") and len(digits) == 11:
        e164 = f"+92{digits[1:]}"
        return cleaned_raw, e164, "VALID_E164"
    # 923xx xxxxxxx (12 digits) -> +923xx xxxxxxx
    if digits.startswith("923") and len(digits) == 12:
        e164 = f"+{digits}"
        return cleaned_raw, e164, "VALID_E164"

    # Set region hint for phonenumbers library
    region_hint = "PK" if (digits.startswith("92") or digits.startswith("03")) else default_region

    if HAVE_PHONENUMBERS:
        try:
            parsed = phonenumbers.parse(cleaned_raw, None if cleaned_raw.startswith("+") else region_hint)
            if phonenumbers.is_valid_number(parsed):
                e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
                return cleaned_raw, e164, "VALID_E164"
            elif phonenumbers.is_possible_number(parsed):
                e164 = phonenumbers.format_number(parsed, PhoneNumberFormat.E164)
                return cleaned_raw, e164, "POSSIBLE"
            else:
                return None, None, "INVALID"
        except Exception:
            pass

    # Fallback digit normalization if 10-15 digits
    e164 = f"+{digits}" if not cleaned_raw.startswith("+") else f"+{digits}"
    return cleaned_raw, e164, "POSSIBLE"

def clean_and_validate_record(raw_dict: dict, default_region: str = "US") -> Optional[ContactRecord]:
    """
    Constructs, normalizes, and validates a ContactRecord from raw extraction data.
    Ensures missing values become None rather than made-up strings.
    """
    # Clean string fields
    cleaned = {}
    for k, v in raw_dict.items():
        if isinstance(v, str):
            val = v.strip()
            cleaned[k] = val if val and val.lower() not in ("none", "null", "n/a", "unknown", "") else None
        else:
            cleaned[k] = v

    # Sanitize Person Name
    cleaned["person_or_profile_name"] = clean_person_name(cleaned.get("person_or_profile_name"))

    # Sanitize Organization Name
    cleaned["organization_name"] = clean_organization_name(cleaned.get("organization_name"))

    # Email Validation
    email_val, email_status = validate_and_normalize_email(cleaned.get("business_email"))
    cleaned["business_email"] = email_val
    cleaned["email_validation_status"] = email_status

    # Phone Normalization
    orig_phone, norm_phone, phone_status = normalize_telephone(
        cleaned.get("contact_number"),
        default_region=default_region
    )
    cleaned["contact_number"] = orig_phone
    cleaned["normalized_phone"] = norm_phone
    cleaned["phone_validation_status"] = phone_status

    # Normalize Links and URLs
    cleaned["website_url"] = normalize_url(cleaned.get("website_url"))
    cleaned["social_profile_url"] = normalize_url(cleaned.get("social_profile_url"))
    cleaned["source_url"] = normalize_url(cleaned.get("source_url"))

    # If website_url is actually a social profile, ensure social_profile_url is populated
    if cleaned["website_url"] and not cleaned["social_profile_url"]:
        low_url = cleaned["website_url"].lower()
        if any(soc in low_url for soc in ["linkedin.com", "twitter.com", "x.com", "instagram.com", "facebook.com", "github.com", "wa.me", "t.me"]):
            cleaned["social_profile_url"] = cleaned["website_url"]

    # Derive person name from personal LinkedIn/social URL slug if missing
    if not cleaned.get("person_or_profile_name") and cleaned.get("social_profile_url"):
        slug_match = re.search(r'linkedin\.com/in/([a-zA-Z0-9_-]+)', cleaned["social_profile_url"], re.IGNORECASE)
        if slug_match:
            slug = slug_match.group(1).replace('-', ' ').replace('_', ' ')
            slug_words = [w for w in slug.split() if w.isalpha() and len(w) >= 2]
            if 1 <= len(slug_words) <= 4:
                cleaned["person_or_profile_name"] = " ".join(w.capitalize() for w in slug_words)

    try:
        record = ContactRecord(**cleaned)
        # Require at least one genuine contact detail (valid email, phone, or profile/website URL)
        if not record.has_contact_details():
            return None
        return record
    except Exception:
        return None
