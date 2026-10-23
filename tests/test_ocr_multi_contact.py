"""
Unit tests for fast real-time multi-contact OCR extraction.
"""

from app.services.ocr_service import OCRService

def test_extract_multiple_contacts_from_screen_text():
    ocr_service = OCRService()
    sample_text = """
    Leadership Team - Tech Innovators
    
    Sarah Jenkins
    Director of Engineering
    s.jenkins@apexcloud.tech
    +1 (415) 555-0199
    https://apexcloud.tech
    
    Marcus Vance
    Head of Enterprise Growth
    marcus.vance@vancelogistics.co.uk
    +44 20 7946 0912
    https://vancelogistics.co.uk
    
    General Inquiries:
    hr@therecruitersloungeco.com
    """

    win_info = {
        "title": "Directory - Google Chrome",
        "process_name": "chrome.exe"
    }

    records = ocr_service.extract_structured_contacts(sample_text, win_info)

    # Must extract all 3 contacts from this single screen text
    assert len(records) == 3

    # Check Sarah Jenkins
    rec1 = next((r for r in records if "s.jenkins@apexcloud.tech" in (r.business_email or "")), None)
    assert rec1 is not None
    assert rec1.person_or_profile_name == "Sarah Jenkins"
    assert rec1.job_title == "Director of Engineering"
    assert "Apex" in (rec1.organization_name or "")
    assert rec1.normalized_phone == "+14155550199"

    # Check Marcus Vance
    rec2 = next((r for r in records if "marcus.vance@vancelogistics.co.uk" in (r.business_email or "")), None)
    assert rec2 is not None
    assert rec2.person_or_profile_name == "Marcus Vance"
    assert rec2.job_title == "Head of Enterprise Growth"
    assert "Vance" in (rec2.organization_name or "")

    # Check Recruiters Lounge email
    rec3 = next((r for r in records if "hr@therecruitersloungeco.com" in (r.business_email or "")), None)
    assert rec3 is not None
    assert "Recruiter" in (rec3.organization_name or "")

def test_whatsapp_job_postings_field_relevance():
    ocr_service = OCRService()
    sample_text = """
    Pakistan Jobs - WhatsApp
    Job Openings:
    
    Advanced chat privacy was turned on
    Messages and calls are end-to-end encrypted.
    
    Q Search Associate Business Developer
    Send resume to hr@savvyprogrammers.com
    
    UI/UX Designer
    Strong understanding of UX principles
    Send CV to slurvohr.02@gmail.com
    
    Hiring Senior Software Engineer
    Evamp & Saanga
    Contact Aqsa Zahid: agsa.zahid@evampsaanga.com
    
    Veeone Health
    arsal.siddiqui@veeonehealth.com
    +92 337 2611722
    """

    win_info = {
        "title": "WhatsApp",
        "process_name": "WhatsApp.Root.exe"
    }

    records = ocr_service.extract_structured_contacts(sample_text, win_info)
    assert len(records) >= 3

    # Ensure "WhatsApp" is NEVER extracted as an organization
    for r in records:
        assert (r.organization_name or "").lower() != "whatsapp"
        assert (r.person_or_profile_name or "") != "Job Openings:"
        assert (r.person_or_profile_name or "") != "Pakistan Jobs"
        assert "Advanced chat privacy" not in (r.evidence or "")

    # Check Savvy Programmers
    rec_savvy = next((r for r in records if "savvyprogrammers.com" in (r.business_email or "")), None)
    assert rec_savvy is not None
    assert rec_savvy.job_title == "Associate Business Developer"
    assert rec_savvy.organization_name == "Savvy Programmers"

    # Check UX Designer
    rec_ux = next((r for r in records if "slurvohr.02@gmail.com" in (r.business_email or "")), None)
    assert rec_ux is not None
    assert rec_ux.job_title == "UI/UX Designer"

    # Check Evamp Saanga
    rec_aqsa = next((r for r in records if "evampsaanga.com" in (r.business_email or "")), None)
    assert rec_aqsa is not None
    assert "Zahid" in (rec_aqsa.person_or_profile_name or "")
    assert rec_aqsa.job_title == "Senior Software Engineer"
    assert rec_aqsa.organization_name == "Evamp Saanga"

    # Check Veeone Health with derived name
    rec_vee = next((r for r in records if "veeonehealth.com" in (r.business_email or "")), None)
    assert rec_vee is not None
    assert rec_vee.person_or_profile_name == "Arsal Siddiqui"
    assert "Veeone" in (rec_vee.organization_name or "")
    assert rec_vee.normalized_phone == "+923372611722"

def test_email_name_cleaning():
    from app.services.ocr_service import derive_name_from_email

    # mgrhr should return None, NOT 'Mgrhr'
    assert derive_name_from_email("mgrhr@mntextiles.com") is None
    assert derive_name_from_email("talent@mntextiles.com") is None
    assert derive_name_from_email("hr@mntextiles.com") is None

    # faiga.hr should return 'Faiga', stripping '.hr'
    assert derive_name_from_email("faiga.hr@blipzmedia.com") == "Faiga"
    assert derive_name_from_email("arsal.siddiqui@veeonehealth.com") == "Arsal Siddiqui"
    assert derive_name_from_email("bilal@virtelligence.com") == "Bilal"



