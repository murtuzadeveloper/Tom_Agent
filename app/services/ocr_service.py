"""
OCR Service supporting Windows Media OCR, Tesseract OCR, and regex-based contact heuristics.
Pre-processes captured images to maximize text readability.
"""

import re
import os
import shutil
from typing import Optional, Dict, Any, List, Tuple
from PIL import Image, ImageEnhance, ImageFilter
from app.utils.logger import logger
from app.security.data_redaction import sanitize_ocr_text

# Regex patterns for contact signals in OCR text
EMAIL_REGEX = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_REGEX = re.compile(r'(?:\+?\d{1,3}[-.\s]?)?\(?\d{2,4}\)?[-.\s]?\d{3,4}[-.\s]?\d{3,4}\b')
# Broad URL regex: matches standard URLs, www.*, career portals, and shorteners (forms.gle, bit.ly, etc.)
URL_REGEX = re.compile(
    r'(?i)\b(?:https?://[^\s<>"\'`()]+|www\.[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+(?:/[^\s<>"\'`()]*)?|(?:forms\.gle|bit\.ly|tinyurl\.com|lnkd\.in|wa\.me|t\.me|linktr\.ee|shorturl\.at)/[a-zA-Z0-9_.-]+(?:/[^\s<>"\'`()]*)?)'
)

# Social profiles: LinkedIn (personal profile, company, job view), Twitter/X, Instagram, Facebook, GitHub, YouTube, Medium
SOCIAL_REGEX = re.compile(
    r'(?i)(?:https?://)?(?:www\.)?(?:linkedin\.com/(?:in|company|jobs/view)/[a-zA-Z0-9_%-]+|twitter\.com/[a-zA-Z0-9_]+|x\.com/[a-zA-Z0-9_]+|instagram\.com/[a-zA-Z0-9_.]+|facebook\.com/[a-zA-Z0-9_.]+|github\.com/[a-zA-Z0-9_%-]+|youtube\.com/(?:@[a-zA-Z0-9_.-]+|c/[a-zA-Z0-9_.-]+)|medium\.com/@[a-zA-Z0-9_.-]+)'
)

GENERIC_EMAIL_PREFIXES = {
    "info", "hr", "careers", "career", "jobs", "job", "contact", "sales",
    "support", "admin", "administrator", "help", "office", "team", "inquiry",
    "enquiries", "enquiry", "billing", "marketing", "talent", "recruitment",
    "recruiter", "fecruitment", "pplsuccess", "peoplesuccess", "hiring", "apply", "cv", "resume", "work", "accounts", "account",
    "hello", "hi", "general", "mail", "contactus", "feedback", "service",
    "mgrhr", "mgr", "manager", "hrm", "gm", "ceo", "md", "cfo", "cto",
    "lead", "head", "talentacquisition", "hrd", "hro", "acquisition", "pk",
    "corporate", "people", "talentteam", "success"
}

DISALLOWED_ORGS = {
    "whatsapp", "lm studio", "lmstudio", "chrome", "edge", "firefox",
    "desktop", "telegram", "slack", "discord", "windows", "desktop screen",
    "taskbar", "explorer", "gmail", "yahoo", "hotmail", "outlook", "icloud",
    "proton", "aol", "mail", "inbox", "unknown", "none", "null", "n/a",
    "system", "chat", "group", "privacy", "notification"
}

KNOWN_CORP_SUFFIXES = [
    "programmers", "solutions", "solution", "technologies", "technology",
    "insights", "logistics", "innovators", "consulting", "services",
    "ventures", "capital", "analytics", "software", "systems", "system",
    "digital", "interactive", "security", "network", "networks",
    "health", "pharma", "global", "group", "studio", "studios",
    "saanga", "agency", "media", "cloud", "labs", "lab", "dev", "tech", "co"
]

JOB_PATTERNS = [
    re.compile(r'\b(?:Associate\s+)?Business\s+Developer?\b', re.IGNORECASE),
    re.compile(r'\bBusiness\s+Development\s+(?:Executive|Manager|Associate|Lead|Representative|Specialist)\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:Project|Product)\s+Manager\b', re.IGNORECASE),
    re.compile(r'\bScrum\s+Master\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+|Principal\s+)?(?:Software|Solutions?|Enterprise|Cloud|Systems?)\s+(?:Engineer|Architect|Developer)\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:Full\s*Stack|Frontend|Backend|Mobile|Web)\s+Developer\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:React|Node|Node\.js|Python|Java|\.NET|PHP|Laravel|Flutter|Android|iOS|Angular|Vue)\s+Developer\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:UI/UX|UI|UX|Product|Graphic)\s+Designer\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:QA|SQA|Quality\s+Assurance|Test\s+Automation)\s+Engineer\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:Data\s+Scientist|Data\s+Analyst|Data\s+Engineer|Machine\s+Learning\s+Engineer|AI\s+Engineer)\b', re.IGNORECASE),
    re.compile(r'\b(?:Senior\s+|Junior\s+|Lead\s+|Associate\s+)?(?:DevOps|Site\s+Reliability|Cloud|Infrastructure)\s+Engineer\b', re.IGNORECASE),
    re.compile(r'\b(?:Technical\s+Recruiter|Talent\s+Acquisition\s+(?:Specialist|Executive|Lead)|HR\s+(?:Executive|Manager|Officer|Associate|Generalist))\b', re.IGNORECASE),
    re.compile(r'\b(?:SEO\s+Specialist|Digital\s+Marketing\s+(?:Executive|Manager|Specialist)|Content\s+Writer)\b', re.IGNORECASE),
    re.compile(r'\b(?:Account\s+Executive|Sales\s+Executive|Customer\s+Success\s+Manager)\b', re.IGNORECASE),
    re.compile(r'\b(?:Director\s+of\s+[A-Za-z\s]{3,20}|Head\s+of\s+[A-Za-z\s]{3,20})\b', re.IGNORECASE),
]

JOB_PREFIX_REGEX = re.compile(
    r'(?:position|role|designation|job\s*title|looking\s*for|hiring\s*(?:for)?|urgently\s*looking\s*for|vacancy\s*(?:for)?|requirement\s*(?:for)?)\s*[:\-–]?\s*([A-Za-z0-9\s/&+\-]{3,40})',
    re.IGNORECASE
)

BOILERPLATE_REGEX = re.compile(
    r'(?:Advanced chat privacy was turned on|Messages and calls are end-to-end encrypted|A child can be exposed|Waiting for this message|This message was deleted|Idle TTL and Auto-Evict|Pakistan IT Jobs\s+\d|practices\s*\|\s*@\s*Jobs in Pakistan)',
    re.IGNORECASE
)

def derive_name_from_email(email: str) -> Optional[str]:
    """Derives human first and last name from email username if structured."""
    if not email or "@" not in email:
        return None

    local_part = email.split('@')[0].lower().strip()
    if not local_part or local_part in GENERIC_EMAIL_PREFIXES:
        return None

    # Strip numbers at end (e.g. slurvohr.02 -> slurvohr)
    local_part = re.sub(r'\d+$', '', local_part).rstrip('._-')
    if not local_part or len(local_part) < 3 or local_part in GENERIC_EMAIL_PREFIXES:
        return None

    # Reject role and generic indicator subwords
    role_subwords = {
        "success", "recruit", "talent", "career", "hiring", "apply", "admin",
        "office", "support", "billing", "service", "inquiry", "info", "people",
        "team", "jobs", "work", "staff", "corp", "mail"
    }
    if any(rw in local_part for rw in role_subwords):
        return None

    # Check for dotted, underscored, or hyphenated names: arsal.siddiqui, aqsa.zahid
    for delim in ['.', '_', '-']:
        if delim in local_part:
            parts = [
                p for p in local_part.split(delim)
                if p.isalpha() and len(p) >= 2 and p not in GENERIC_EMAIL_PREFIXES
            ]
            if len(parts) >= 2:
                return " ".join(p.capitalize() for p in parts[:3])
            elif len(parts) == 1 and len(parts[0]) >= 3:
                return parts[0].capitalize()

    # Single clean name (e.g. bilal, maria, kashish, maaz)
    if local_part.isalpha() and 3 <= len(local_part) <= 15:
        if local_part not in {"system", "user", "guest", "test", "demo", "client", "developer", "engineer"}:
            return local_part.capitalize()

    return None

def format_domain_organization(domain_root: str) -> str:
    """Intelligently splits and formats corporate domain roots."""
    cleaned = domain_root.replace('-', ' ').replace('_', ' ').strip().lower()
    if not cleaned:
        return ""

    # Check if domain ends with known corporate suffixes: bigbyteinsights -> Bigbyte Insights
    for suffix in KNOWN_CORP_SUFFIXES:
        if cleaned.endswith(suffix) and len(cleaned) > len(suffix) + 2:
            prefix = cleaned[:-len(suffix)].strip()
            return f"{prefix.capitalize()} {suffix.capitalize()}"

    # If already spaced or single word
    return " ".join(w.capitalize() for w in cleaned.split())

def extract_org_from_url(url: str) -> Optional[str]:
    """Extracts candidate company name from career portals, job boards, or corporate websites."""
    if not url:
        return None

    # Greenhouse boards: boards.greenhouse.io/<company>
    gh_match = re.search(r'boards\.greenhouse\.io/([a-zA-Z0-9_-]+)', url, re.IGNORECASE)
    if gh_match:
        return format_domain_organization(gh_match.group(1))

    # Lever jobs: jobs.lever.co/<company>
    lever_match = re.search(r'jobs\.lever\.co/([a-zA-Z0-9_-]+)', url, re.IGNORECASE)
    if lever_match:
        return format_domain_organization(lever_match.group(1))

    # Workable: <company>.workable.com
    workable_match = re.search(r'([a-zA-Z0-9_-]+)\.workable\.com', url, re.IGNORECASE)
    if workable_match:
        return format_domain_organization(workable_match.group(1))

    # LinkedIn Company: linkedin.com/company/<company>
    li_match = re.search(r'linkedin\.com/company/([a-zA-Z0-9_-]+)', url, re.IGNORECASE)
    if li_match:
        return format_domain_organization(li_match.group(1))

    # General domain root: https://careers.company.com or https://company.com/apply
    m_dom = re.search(r'(?:https?://)?(?:www\.)?(?:careers?\.)?([^/:]+)', url, re.IGNORECASE)
    if m_dom:
        host = m_dom.group(1).lower()
        parts = host.split('.')
        if len(parts) >= 2:
            root = parts[0] if parts[0] not in ("careers", "jobs", "apply", "app", "portal", "forms", "docs", "drive") else parts[1]
            if root not in {"google", "forms", "microsoft", "bitly", "bit", "tinyurl", "shorturl", "whatsapp", "wa", "telegram", "t", "linktr", "lnkd", "com", "org", "net"}:
                return format_domain_organization(root)

    return None

def extract_job_title_from_context(context_lines: List[str]) -> Optional[str]:
    """Extracts genuine job title from text lines using catalog and prefix matching."""
    # Strategy 1: Explicit job prefix
    for line in context_lines:
        m = JOB_PREFIX_REGEX.search(line)
        if m:
            candidate = m.group(1).strip()
            # Clean trailing prepositions or qualifiers
            candidate = re.sub(r'\s+(?:with|in|for|at|years|exp|experience|remote|onsite|hybrid).*$', '', candidate, flags=re.IGNORECASE)
            candidate = candidate.strip(" :,-–|")
            if 3 <= len(candidate) <= 35 and not any(bad in candidate.lower() for bad in ["whatsapp", "lm studio", "privacy"]):
                return " ".join(w.capitalize() for w in candidate.split())

    # Strategy 2: Pre-compiled job title patterns
    for line in context_lines:
        for pat in JOB_PATTERNS:
            m = pat.search(line)
            if m:
                matched = m.group(0).strip(" :,-–|")
                return " ".join(w.capitalize() if not w.upper() in ["UI/UX", "UI", "UX", "QA", "SQA", "HR", "AI", "SEO", "BDE", "BDM"] else w.upper() for w in matched.split())

    return None

def extract_person_name_from_context(context_lines: List[str]) -> Optional[str]:
    """Extracts genuine person name from context lines, strictly filtering noise."""
    from app.services.contact_validator import clean_person_name

    # Check for explicit name indicators
    name_cue_regex = re.compile(
        r'(?:contact(?:\s+person)?|hr|recruiter|poc|hiring\s+manager|posted\s+by|send\s+cv\s+to|reach\s+out\s+to)\s*[:\-–]\s*([A-Za-z\s]{3,30})',
        re.IGNORECASE
    )
    for line in context_lines:
        m = name_cue_regex.search(line)
        if m:
            clean = clean_person_name(m.group(1))
            if clean:
                return clean

    # Check for 2-3 capitalized words in a line
    for line in context_lines:
        words = line.split()
        if 2 <= len(words) <= 3:
            # Check each word begins with uppercase and is strictly alphabetic
            if all(w.isalpha() and len(w) >= 2 and w[0].isupper() and w[1:].islower() for w in words):
                clean = clean_person_name(line)
                if clean:
                    return clean

    return None

def clean_context_evidence(context_lines: List[str]) -> str:
    """Strips WhatsApp security notices and timestamps, leaving clean recruitment context."""
    cleaned_lines = []
    for line in context_lines:
        l_str = line.strip()
        if not l_str:
            continue
        if BOILERPLATE_REGEX.search(l_str):
            continue
        # Strip timestamps e.g. 8:52pm, 3:00 Pm - 11:00 Pm
        l_clean = re.sub(r'\b\d{1,2}:\d{2}\s*(?:am|pm|AM|PM)?\b', '', l_str).strip()
        if len(l_clean) > 5:
            cleaned_lines.append(l_clean)

    evidence = " | ".join(cleaned_lines)
    # Collapse multiple pipes or spaces
    evidence = re.sub(r'\|\s*\|+', '|', evidence)
    return evidence[:180].strip(" |")

class OCRService:
    """Manages OCR text extraction and contact signal identification."""

    def __init__(self):
        self._tesseract_available = self._check_tesseract()

    def _check_tesseract(self) -> bool:
        """Checks if pytesseract is usable and the binary is found."""
        try:
            import pytesseract
            # Common Windows installation locations
            common_paths = [
                r"C:\Program Files\Tesseract-OCR\tesseract.exe",
                r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe")
            ]
            for p in common_paths:
                if os.path.exists(p):
                    pytesseract.pytesseract.tesseract_cmd = p
                    return True
            if shutil.which("tesseract"):
                return True
        except ImportError:
            pass
        return False

    def preprocess_image(self, image: Image.Image) -> Image.Image:
        """
        Enhances contrast and sharpness to improve OCR accuracy on screen text.
        """
        try:
            # Convert to grayscale
            gray = image.convert("L")
            # Enhance contrast
            enhancer = ImageEnhance.Contrast(gray)
            enhanced = enhancer.enhance(1.8)
            # Enhance sharpness
            sharpener = ImageEnhance.Sharpness(enhanced)
            sharpened = sharpener.enhance(1.5)
            return sharpened
        except Exception as e:
            logger.debug(f"Image preprocessing fallback to original: {e}")
            return image

    def extract_text(self, image: Image.Image) -> str:
        """
        Extracts readable text from the image using the best available engine.
        Sanitizes text to redact passwords and credentials.
        """
        preprocessed = self.preprocess_image(image)
        raw_text = ""

        # Strategy 1: Pytesseract
        if self._tesseract_available:
            try:
                import pytesseract
                raw_text = pytesseract.image_to_string(preprocessed, config="--psm 6", timeout=3.5)
            except Exception as e:
                logger.debug(f"Tesseract OCR failed or timed out: {e}")

        # Sanitize sensitive data before returning
        return sanitize_ocr_text(raw_text)

    def extract_contact_signals(self, ocr_text: str) -> Dict[str, Any]:
        """
        Analyzes OCR text for contact indicators: emails, phone numbers, websites, social links.
        Returns a dictionary of candidate signals.
        """
        if not ocr_text:
            return {"has_signals": False, "emails": [], "phones": [], "urls": [], "socials": []}

        emails = EMAIL_REGEX.findall(ocr_text)
        phones = [p for p in PHONE_REGEX.findall(ocr_text) if len(re.sub(r'\D', '', p)) >= 10]
        urls = URL_REGEX.findall(ocr_text)
        socials = SOCIAL_REGEX.findall(ocr_text)

        # Filter out common false-positive emails (e.g. image filenames, web assets)
        clean_emails = [e for e in emails if not e.lower().endswith(('.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'))]

        # Clean URLs and filter internal search/localhost
        clean_urls = []
        for u in urls:
            cand = u.strip().strip('"\'`<>[]{}()|\\;,').rstrip('.,;:')
            if len(cand) >= 5 and not any(bad in cand.lower() for bad in ["127.0.0.1", "localhost", "google.com/search", "bing.com/search"]):
                clean_urls.append(cand)

        clean_socials = [s.strip().strip('"\'`<>[]{}()|\\;,').rstrip('.,;:') for s in socials if len(s.strip()) >= 5]

        has_signals = bool(clean_emails or phones or clean_socials or clean_urls)
        return {
            "has_signals": has_signals,
            "emails": clean_emails,
            "phones": phones,
            "urls": clean_urls,
            "socials": clean_socials,
            "line_count": len(ocr_text.splitlines()),
            "text_length": len(ocr_text)
        }

    def extract_structured_contacts(self, ocr_text: str, window_info: dict = None) -> List[Any]:
        """
        Extracts ALL professional contacts, job postings, career links, and URLs directly
        from OCR text in real time (<20ms).
        Derives high-precision names, job titles, and organizations from surrounding context.
        """
        from app.services.contact_validator import clean_and_validate_record

        if not ocr_text:
            return []

        win_info = window_info or {}
        app_name = win_info.get("process_name", "Desktop")
        win_title = win_info.get("title", "")
        browser_url = win_info.get("url")

        # Block internal developer tools and LM Studio from being scraped
        if any(term in f"{app_name} {win_title}".lower() for term in ["lmstudio", "lm studio"]):
            return []

        signals = self.extract_contact_signals(ocr_text)
        if not signals["has_signals"]:
            return []

        lines = [line.strip() for line in ocr_text.splitlines() if line.strip()]
        total_lines = len(lines)
        results = []
        seen_emails = set()
        seen_phones = set()
        seen_urls = set()

        generic_email_domains = (
            "gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com", "proton.me", "aol.com", "com"
        )

        # 1. Process each detected email with surrounding context
        for email in signals["emails"]:
            from app.services.contact_validator import correct_ocr_email_typos
            norm_email = correct_ocr_email_typos(email.lower())
            # Normalize common OCR typo where 'hr@' is misread as 'br@'
            if norm_email.startswith("br@"):
                norm_email = "hr@" + norm_email[3:]
            email = norm_email

            if norm_email in seen_emails:
                continue
            seen_emails.add(norm_email)

            # Find line index where email appears
            email_line_idx = -1
            for idx, line in enumerate(lines):
                if email in line or norm_email in line.lower():
                    email_line_idx = idx
                    break

            # Search context window around email (5 lines before & after)
            context_start = max(0, email_line_idx - 5) if email_line_idx != -1 else 0
            context_end = min(total_lines, email_line_idx + 5) if email_line_idx != -1 else total_lines
            context_lines = lines[context_start:context_end]

            # 1a. Extract Name: prioritize context, fallback to structured email username
            person_name = extract_person_name_from_context(context_lines)
            if not person_name:
                person_name = derive_name_from_email(norm_email)

            # 1b. Extract Job Title
            job_title = extract_job_title_from_context(context_lines)

            # 1c. Extract Organization Name
            org_name = None
            domain = norm_email.split('@')[-1]
            if domain not in generic_email_domains:
                clean_dom = domain.split('.')[0]
                org_name = format_domain_organization(clean_dom)
            elif " - " in win_title:
                candidate = win_title.split(" - ")[-1].strip()
                if candidate.lower() not in DISALLOWED_ORGS:
                    org_name = candidate

            # Check context for explicit "Company:" cue
            for c_line in context_lines:
                comp_match = re.search(r'(?:company|organization|firm|agency|at)\s*[:\-–]\s*([A-Za-z0-9\s&.]{3,35})', c_line, re.IGNORECASE)
                if comp_match:
                    cand_org = comp_match.group(1).strip()
                    if cand_org.lower() not in DISALLOWED_ORGS:
                        org_name = cand_org
                        break

            # 1d. Extract Phone & URL from local context
            matched_phone = None
            matched_url = None
            matched_social = None
            for c_line in context_lines:
                if not matched_phone:
                    phone_match = PHONE_REGEX.search(c_line)
                    if phone_match:
                        cand_p = phone_match.group(0)
                        if 10 <= len(re.sub(r'\D', '', cand_p)) <= 15:
                            matched_phone = cand_p
                            seen_phones.add(cand_p)

                if not matched_social:
                    soc_match = SOCIAL_REGEX.search(c_line)
                    if soc_match:
                        matched_social = soc_match.group(0).strip(".,;:'\"")
                        seen_urls.add(matched_social.lower())

                if not matched_url:
                    url_match = URL_REGEX.search(c_line)
                    if url_match:
                        cand_u = url_match.group(0).strip(".,;:'\"")
                        if not any(bad in cand_u.lower() for bad in ["127.0.0.1", "localhost", "google.com/search", "bing.com/search"]):
                            matched_url = cand_u
                            seen_urls.add(cand_u.lower())

            # Fallback to general signals if not matched locally
            if not matched_url and signals["urls"]:
                for u in signals["urls"]:
                    if u.lower() not in seen_urls:
                        matched_url = u
                        seen_urls.add(u.lower())
                        break

            if not matched_social and signals["socials"]:
                for s in signals["socials"]:
                    if s.lower() not in seen_urls:
                        matched_social = s
                        seen_urls.add(s.lower())
                        break

            evidence_snippet = clean_context_evidence(context_lines)

            raw_dict = {
                "person_or_profile_name": person_name,
                "job_title": job_title,
                "organization_name": org_name,
                "business_email": email,
                "contact_number": matched_phone,
                "website_url": matched_url,
                "social_profile_url": matched_social,
                "source_application": app_name,
                "source_url": matched_url or matched_social or browser_url or win_title,
                "evidence": evidence_snippet
            }

            rec = clean_and_validate_record(raw_dict)
            if rec:
                results.append(rec)

        # 2. Process any remaining phone numbers that had no email on this screen
        for phone in signals["phones"]:
            if phone in seen_phones:
                continue
            digits = re.sub(r'\D', '', phone)
            if len(digits) < 10 or len(digits) > 15:
                continue
            seen_phones.add(phone)

            # Find context around phone
            phone_line_idx = -1
            for idx, line in enumerate(lines):
                if phone in line:
                    phone_line_idx = idx
                    break

            c_start = max(0, phone_line_idx - 4) if phone_line_idx != -1 else 0
            c_end = min(total_lines, phone_line_idx + 4) if phone_line_idx != -1 else total_lines
            c_lines = lines[c_start:c_end]

            person_name = extract_person_name_from_context(c_lines)
            job_title = extract_job_title_from_context(c_lines)

            org_name = None
            for c_line in c_lines:
                comp_match = re.search(r'(?:company|organization|firm|agency|at)\s*[:\-–]\s*([A-Za-z0-9\s&.]{3,35})', c_line, re.IGNORECASE)
                if comp_match:
                    cand_org = comp_match.group(1).strip()
                    if cand_org.lower() not in DISALLOWED_ORGS:
                        org_name = cand_org
                        break

            # Extract local URL & Social for phone contacts
            matched_url = None
            matched_social = None
            for c_line in c_lines:
                if not matched_social:
                    soc_match = SOCIAL_REGEX.search(c_line)
                    if soc_match:
                        matched_social = soc_match.group(0).strip(".,;:'\"")
                        seen_urls.add(matched_social.lower())

                if not matched_url:
                    url_match = URL_REGEX.search(c_line)
                    if url_match:
                        cand_u = url_match.group(0).strip(".,;:'\"")
                        if not any(bad in cand_u.lower() for bad in ["127.0.0.1", "localhost", "google.com/search", "bing.com/search"]):
                            matched_url = cand_u
                            seen_urls.add(cand_u.lower())

            evidence_snippet = clean_context_evidence(c_lines)
            raw_dict = {
                "person_or_profile_name": person_name,
                "job_title": job_title,
                "organization_name": org_name,
                "contact_number": phone,
                "website_url": matched_url,
                "social_profile_url": matched_social,
                "source_application": app_name,
                "source_url": matched_url or matched_social or browser_url or win_title,
                "evidence": evidence_snippet
            }
            rec = clean_and_validate_record(raw_dict)
            if rec:
                results.append(rec)

        # 3. Process standalone links, application portals, Google Forms, and social profiles
        candidate_links = []
        for u in signals["urls"]:
            if u.lower() not in seen_urls:
                candidate_links.append(u)
        for s in signals["socials"]:
            if s.lower() not in seen_urls:
                candidate_links.append(s)

        for raw_url in candidate_links:
            clean_u = raw_url.strip(".,;:'\"")
            if clean_u.lower() in seen_urls:
                continue
            if any(bad in clean_u.lower() for bad in ["127.0.0.1", "localhost", "google.com/search", "bing.com/search"]):
                continue

            seen_urls.add(clean_u.lower())

            url_line_idx = -1
            for idx, line in enumerate(lines):
                if clean_u in line or raw_url in line:
                    url_line_idx = idx
                    break

            c_start = max(0, url_line_idx - 4) if url_line_idx != -1 else 0
            c_end = min(total_lines, url_line_idx + 4) if url_line_idx != -1 else total_lines
            c_lines = lines[c_start:c_end]

            job_title = extract_job_title_from_context(c_lines)
            person_name = extract_person_name_from_context(c_lines)

            # Derive org name from cues in text or from the link itself
            org_name = None
            for c_line in c_lines:
                comp_match = re.search(r'(?:company|organization|firm|agency|at)\s*[:\-–]\s*([A-Za-z0-9\s&.]{3,35})', c_line, re.IGNORECASE)
                if comp_match:
                    cand_org = comp_match.group(1).strip()
                    if cand_org.lower() not in DISALLOWED_ORGS:
                        org_name = cand_org
                        break

            if not org_name:
                org_name = extract_org_from_url(clean_u)

            evidence_snippet = clean_context_evidence(c_lines) or clean_u
            is_social = bool(SOCIAL_REGEX.search(clean_u))

            raw_dict = {
                "person_or_profile_name": person_name,
                "job_title": job_title,
                "organization_name": org_name,
                "website_url": clean_u,
                "social_profile_url": clean_u if is_social else None,
                "source_application": app_name,
                "source_url": clean_u,
                "evidence": evidence_snippet
            }
            rec = clean_and_validate_record(raw_dict)
            if rec:
                results.append(rec)

        return results
