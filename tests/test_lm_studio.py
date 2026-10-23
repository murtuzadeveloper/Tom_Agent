"""
Unit tests for LM Studio client, connection testing, and Markdown JSON parsing.
"""

from unittest.mock import patch, MagicMock
import requests
from app.services.lm_studio_client import LMStudioClient

def test_parse_json_markdown_block():
    client = LMStudioClient()
    raw_markdown = """
    Here is the extracted contact info:
    ```json
    {
        "person_or_profile_name": "Alexander Hayes",
        "job_title": "Chief Technology Officer",
        "organization_name": "Quantum Horizon AI",
        "business_email": "a.hayes@quantumhorizon.ai",
        "contact_number": "+1 650 555 0142",
        "evidence": "Visible on company leadership card"
    }
    ```
    Hope this helps!
    """
    parsed = client._parse_json_markdown(raw_markdown)
    assert parsed is not None
    assert parsed["person_or_profile_name"] == "Alexander Hayes"
    assert parsed["organization_name"] == "Quantum Horizon AI"
    assert parsed["business_email"] == "a.hayes@quantumhorizon.ai"

def test_connection_refused_handling():
    client = LMStudioClient(base_url="http://127.0.0.1:9999/v1")
    with patch("requests.get", side_effect=requests.exceptions.ConnectionError("Connection refused")):
        success, msg, models = client.test_connection()
        assert not success
        assert "Could not reach LM Studio" in msg
        assert len(models) == 0

def test_invalid_non_json_model_output():
    client = LMStudioClient()
    raw_text = "I'm sorry, but I cannot find any contact information on this screen."
    parsed = client._parse_json_markdown(raw_text)
    assert parsed is None
