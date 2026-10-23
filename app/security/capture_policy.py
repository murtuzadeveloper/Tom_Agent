"""
Screen capture policy and privacy gatekeeper.
Prevents capturing passwords, banking windows, credential managers, and restricted content.
"""

from typing import Tuple, Optional
from config import CONFIG
from app.utils.logger import logger

class CapturePolicy:
    """Enforces safety, privacy policies, and process blocklists."""

    @classmethod
    def is_window_allowed(cls, window_title: str, process_name: str) -> Tuple[bool, str]:
        """
        Validates if the active window is permitted for capture.
        Returns (is_allowed, reason_if_blocked).
        """
        title_lower = (window_title or "").lower()
        proc_lower = (process_name or "").lower()

        # Check process blocklist
        for blocked_proc in CONFIG.security.blocked_process_names:
            if blocked_proc.lower() in proc_lower:
                reason = f"Blocked sensitive application: {process_name}"
                logger.warning(f"CapturePolicy rejected: {reason}")
                return False, reason

        # Check window title keywords
        for keyword in CONFIG.security.blocked_window_keywords:
            if keyword in title_lower:
                reason = f"Window title contains restricted keyword '{keyword}': '{window_title}'"
                logger.warning(f"CapturePolicy rejected: {reason}")
                return False, reason

        return True, "Allowed"

    @classmethod
    def is_messaging_app(cls, window_title: str, process_name: str) -> bool:
        """Detects if the active window is a messaging application (e.g. WhatsApp Desktop)."""
        combined = f"{window_title} {process_name}".lower()
        messaging_signatures = ["whatsapp", "telegram", "slack", "signal", "discord", "skype", "teams"]
        return any(sig in combined for sig in messaging_signatures)
