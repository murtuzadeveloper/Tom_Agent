"""
Unit and integration tests for link, URL, application portal, and form collection.
"""

import tempfile
from pathlib import Path
from app.services.ocr_service import OCRService, URL_REGEX, SOCIAL_REGEX, extract_org_from_url
from app.services.contact_validator import normalize_url, clean_and_validate_record, ContactRecord
from app.services.deduplication import Deduplicator
from app.database.repository import ContactRepository

def test_url_and_social_regexes():
    sample_text = """
    Apply here: https://forms.gle/xYz12345
    Alternative: bit.ly/frontend-job
    Company site: www.innovatetech.io
    Career portal: https://jobs.lever.co/stripe/software-engineer
    LinkedIn Profile: https://linkedin.com/in/sarah-smith-dev
    Company LinkedIn: https://www.linkedin.com/company/acme-corp
    Twitter: https://x.com/tech_lead
    """

    urls = URL_REGEX.findall(sample_text)
    assert any("forms.gle" in u for u in urls)
    assert any("bit.ly" in u for u in urls)
    assert any("www.innovatetech.io" in u for u in urls)
    assert any("lever.co" in u for u in urls)

    socials = SOCIAL_REGEX.findall(sample_text)
    assert any("linkedin.com/in/sarah-smith-dev" in s for s in socials)
    assert any("linkedin.com/company/acme-corp" in s for s in socials)
    assert any("x.com/tech_lead" in s for s in socials)

def test_normalize_url():
    assert normalize_url("www.example.com") == "https://www.example.com"
    assert normalize_url("forms.gle/abc123") == "https://forms.gle/abc123"
    assert normalize_url("bit.ly/job-post") == "https://bit.ly/job-post"
    assert normalize_url("https://company.com/apply.") == "https://company.com/apply"
    assert normalize_url("http://127.0.0.1:1234") is None
    assert normalize_url("localhost") is None
    assert normalize_url("") is None

def test_extract_org_from_url():
    assert extract_org_from_url("https://jobs.lever.co/stripe/123") == "Stripe"
    assert extract_org_from_url("https://boards.greenhouse.io/airbnb/jobs/456") == "Airbnb"
    assert extract_org_from_url("https://uber.workable.com/j/789") == "Uber"
    assert extract_org_from_url("https://linkedin.com/company/microsoft") == "Microsoft"
    assert extract_org_from_url("https://careers.netflix.com/jobs") == "Netflix"

def test_extract_standalone_links_and_forms_from_screen():
    ocr_service = OCRService()
    screen_text = """
    Pakistan Software Community - WhatsApp
    Job Announcements:
    
    Hiring React Native Developer
    Company: CyberTech Solutions
    Apply through form: https://forms.gle/dev98765
    
    Senior Backend Architect
    Apply directly: https://jobs.lever.co/fintechcorp/arch-01
    
    Connect with our Lead Recruiter:
    https://linkedin.com/in/emma-watson-hr
    """

    win_info = {"title": "WhatsApp", "process_name": "WhatsApp.Root.exe"}
    records = ocr_service.extract_structured_contacts(screen_text, win_info)

    assert len(records) >= 3

    # Check Form application record
    rec_form = next((r for r in records if "forms.gle" in (r.website_url or "")), None)
    assert rec_form is not None
    assert rec_form.job_title == "React Native Developer"
    assert rec_form.organization_name == "CyberTech Solutions"
    assert "https://forms.gle/dev98765" in rec_form.website_url

    # Check Lever career link record
    rec_lever = next((r for r in records if "lever.co" in (r.website_url or "")), None)
    assert rec_lever is not None
    assert "Backend" in (rec_lever.job_title or "")
    assert rec_lever.organization_name == "Fintechcorp"

    # Check LinkedIn Recruiter profile
    rec_li = next((r for r in records if "emma-watson-hr" in (r.social_profile_url or "")), None)
    assert rec_li is not None
    assert "Emma Watson" in (rec_li.person_or_profile_name or "")

def test_extract_mixed_screen_with_email_phone_and_links():
    ocr_service = OCRService()
    screen_text = """
    Directory Listing
    
    John Doe
    Engineering Lead
    john@nexus.io
    +1 (415) 555-0123
    https://nexus.io
    
    Career Opportunity:
    UI/UX Product Designer
    Submit portfolio: https://forms.gle/uxdesign2026
    """

    records = ocr_service.extract_structured_contacts(screen_text, {"process_name": "chrome.exe", "title": "Jobs"})
    assert len(records) >= 2

    # John Doe should have email, phone, and website
    john = next((r for r in records if r.business_email == "john@nexus.io"), None)
    assert john is not None
    assert john.person_or_profile_name == "John Doe"
    assert john.website_url == "https://nexus.io"

    # Separate form link must ALSO be extracted
    form_rec = next((r for r in records if "uxdesign2026" in (r.website_url or "")), None)
    assert form_rec is not None
    assert form_rec.job_title == "UI/UX Product Designer"

def test_url_deduplication():
    dedup = Deduplicator()
    rec1 = ContactRecord(
        job_title="DevOps Engineer",
        website_url="https://forms.gle/devops123"
    )
    rec2 = ContactRecord(
        job_title="DevOps Engineer",
        website_url="https://forms.gle/devops123/"
    )
    rec3 = ContactRecord(
        job_title="Full Stack Engineer",
        website_url="https://forms.gle/devops123"
    )

    h1 = dedup.register(rec1)
    assert dedup.is_duplicate(rec2)
    assert h1 == dedup.generate_fingerprint(rec2)

    # Different role on same URL should have different fingerprint
    h3 = dedup.generate_fingerprint(rec3)
    assert h1 != h3

def test_database_url_search_and_stats():
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = str(Path(tmpdir) / "test.sqlite3")
        repo = ContactRepository(db_path)

        rec = ContactRecord(
            job_title="Cloud Engineer",
            organization_name="CloudBase",
            website_url="https://cloudbase.io/careers"
        )
        saved = repo.insert_contact(rec, "hash_cloudbase")
        assert saved

        # Search by URL substring
        results = repo.get_all_contacts(search_query="cloudbase.io")
        assert len(results) == 1
        assert results[0].website_url == "https://cloudbase.io/careers"

        # Check stats includes total_links
        stats = repo.get_summary_stats()
        assert stats["total_records"] == 1
        assert stats["total_links"] == 1
