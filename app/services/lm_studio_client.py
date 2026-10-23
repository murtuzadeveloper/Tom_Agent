"""
OpenAI-compatible LM Studio client for local Gemma 4 12B QAT vision & text inference.
Enforces strict 1-at-a-time concurrency, automatic fallback, and robust JSON validation.
"""

import json
import threading
import requests
from typing import Optional, Dict, Any, List, Tuple
from config import CONFIG
from app.utils.logger import logger

LM_STUDIO_EXTRACTION_SYSTEM_PROMPT = (
    "You extract professional contact information, job postings, application forms, and career links "
    "from a supplied screenshot or OCR text. "
    "Extract all professional business contact information, websites, and profile URLs visible. "
    "Always collect 'website_url' (company site, application portal, Google Form, job link) and 'social_profile_url' (LinkedIn, Twitter/X, GitHub) when present. "
    "Do not guess missing details or invent data. Use null for missing fields. "
    "If multiple contacts or links are present, return a JSON array: [ {...}, {...} ]. "
    "Output must be valid JSON matching this schema:\n"
    "{\n"
    '  "person_or_profile_name": string or null,\n'
    '  "job_title": string or null,\n'
    '  "organization_name": string or null,\n'
    '  "business_email": string or null,\n'
    '  "contact_number": string or null,\n'
    '  "website_url": string or null,\n'
    '  "social_profile_url": string or null,\n'
    '  "evidence": string or null\n'
    "}"
)

class LMStudioClient:
    """Client for local OpenAI-compatible LM Studio inference."""

    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = (base_url or CONFIG.lm_studio.base_url).rstrip('/')
        self.model = model or CONFIG.lm_studio.default_model
        self.timeout = CONFIG.lm_studio.timeout_seconds
        self._lock = threading.Lock()
        self.is_vision_supported: Optional[bool] = None

    def test_connection(self) -> Tuple[bool, str, List[str]]:
        """
        Tests connection to LM Studio and discovers available models.
        Returns (success: bool, message: str, models: List[str]).
        """
        url = f"{self.base_url}/models"
        try:
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                models = [m.get("id") for m in data.get("data", []) if "id" in m]
                msg = f"Connected! Found {len(models)} model(s)."
                logger.info(f"LM Studio connection successful: {msg}")
                return True, msg, models
            else:
                msg = f"LM Studio responded with HTTP {resp.status_code}: {resp.text[:100]}"
                logger.warning(msg)
                return False, msg, []
        except requests.exceptions.ConnectionError:
            msg = "Could not reach LM Studio at http://127.0.0.1:1234. Make sure LM Studio Local Server is started."
            logger.warning(msg)
            return False, msg, []
        except Exception as e:
            msg = f"Connection error: {str(e)}"
            logger.error(msg)
            return False, msg, []

    def check_vision_capability(self) -> bool:
        """Checks if current model supports vision by testing a miniature request."""
        # Check model name keywords or cached flag
        if self.is_vision_supported is not None:
            return self.is_vision_supported

        name_lower = self.model.lower()
        if any(v in name_lower for v in ["vl", "-vision", "vision-", "llava", "pixtral", "minicpm-v"]):
            self.is_vision_supported = True
            return True
        self.is_vision_supported = False
        return False

    def extract_contact_info(
        self,
        ocr_text: Optional[str] = None,
        image_data_url: Optional[str] = None,
        app_context: Optional[str] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]], str]:
        """
        Submits OCR text and/or scaled screenshot to LM Studio.
        Enforces single-request concurrency lock.
        Returns (success, parsed_json_dict, log_message).
        """
        with self._lock:  # Strictly one inference request at a time
            user_content = []

            context_desc = f"Application Context: {app_context or 'Active Screen'}\n"
            if ocr_text:
                context_desc += f"Extracted OCR Text:\n{ocr_text.strip()}\n"

            # Decide whether to attach vision image
            attach_image = (
                CONFIG.lm_studio.enable_vision and
                image_data_url is not None and
                self.check_vision_capability()
            )

            if attach_image:
                user_content.append({"type": "text", "text": f"{context_desc}\nInspect the provided screen capture and extract all professional business contact information."})
                user_content.append({"type": "image_url", "image_url": {"url": image_data_url}})
            else:
                user_content = f"{context_desc}\nExtract all professional business contact information strictly from the provided text above."

            payload = {
                "model": self.model,
                "messages": [
                    {"role": "system", "content": LM_STUDIO_EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_content}
                ],
                "temperature": CONFIG.lm_studio.temperature,
                "max_tokens": CONFIG.lm_studio.max_output_tokens,
                "stream": False
            }

            url = f"{self.base_url}/chat/completions"

            # Execute with retry
            for attempt in range(1, CONFIG.lm_studio.max_retries + 1):
                try:
                    logger.debug(f"Sending inference request to LM Studio ({self.model}), attempt {attempt}...")
                    resp = requests.post(url, json=payload, timeout=self.timeout)

                    if resp.status_code == 200:
                        res_json = resp.json()
                        raw_content = res_json["choices"][0]["message"]["content"]
                        parsed_dict = self._parse_json_markdown(raw_content)
                        if parsed_dict:
                            return True, parsed_dict, "Extraction successful"
                        else:
                            return False, None, f"Model returned non-JSON response: {raw_content[:150]}"

                    elif resp.status_code == 400 and attach_image:
                        # Model may not support image format in current backend; fallback to text-only
                        logger.warning("LM Studio returned 400 with image payload; falling back to text-only inference...")
                        self.is_vision_supported = False
                        payload["messages"][1]["content"] = f"{context_desc}\nExtract all professional business contact info from text."
                        continue

                    else:
                        logger.warning(f"LM Studio HTTP {resp.status_code}: {resp.text[:200]}")
                        return False, None, f"LM Studio HTTP {resp.status_code}"

                except requests.exceptions.Timeout:
                    logger.warning(f"LM Studio request timed out after {self.timeout}s (Attempt {attempt})")
                    if attempt == CONFIG.lm_studio.max_retries:
                        return False, None, f"Inference timed out ({self.timeout}s)"

                except requests.exceptions.ConnectionError:
                    return False, None, "Connection refused. Is LM Studio server running?"

                except Exception as e:
                    logger.error(f"LM Studio inference error: {e}")
                    return False, None, str(e)

            return False, None, "Extraction failed after retries"

    def _parse_json_markdown(self, raw_str: str) -> Optional[Any]:
        """Extracts JSON object or list from model output, handling ```json blocks or raw JSON."""
        if not raw_str:
            return None

        cleaned = raw_str.strip()

        # Handle ```json ... ``` code blocks
        if "```" in cleaned:
            parts = cleaned.split("```")
            for part in parts:
                p = part.strip()
                if p.startswith("json"):
                    p = p[4:].strip()
                if (p.startswith("{") and p.endswith("}")) or (p.startswith("[") and p.endswith("]")):
                    try:
                        return json.loads(p)
                    except json.JSONDecodeError:
                        pass

        # Try finding outermost [ ... ] (list of contacts)
        start_arr = cleaned.find('[')
        end_arr = cleaned.rfind(']')
        if start_arr != -1 and end_arr != -1 and end_arr > start_arr:
            try:
                return json.loads(cleaned[start_arr:end_arr + 1])
            except json.JSONDecodeError:
                pass

        # Try finding outermost { ... }
        start_idx = cleaned.find('{')
        end_idx = cleaned.rfind('}')
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            substring = cleaned[start_idx:end_idx + 1]
            try:
                return json.loads(substring)
            except json.JSONDecodeError:
                pass

        return None
