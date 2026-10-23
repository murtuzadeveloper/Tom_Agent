"""
Configuration module for murtuzadeveloper Smart Leads.
Optimized for Windows 11 x64, Intel i7-9850H, 16 GB RAM, NVIDIA MX150 (2 GB VRAM).
"""

import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import List

# Base Directories
WORKSPACE_ROOT = Path(__file__).resolve().parent
DATA_DIR = WORKSPACE_ROOT / "data"
LOGS_DIR = WORKSPACE_ROOT / "logs"
DATA_DIR.mkdir(parents=True, exist_ok=True)
LOGS_DIR.mkdir(parents=True, exist_ok=True)

# Default CSV Output Path (detects OneDrive Desktop on Windows 11)
USER_PROFILE = Path(os.environ.get("USERPROFILE", str(Path.home())))
ONEDRIVE_DESKTOP = USER_PROFILE / "OneDrive" / "Desktop"
DESKTOP_DIR = ONEDRIVE_DESKTOP if ONEDRIVE_DESKTOP.exists() else (USER_PROFILE / "Desktop")
DEFAULT_CSV_PATH = str(DESKTOP_DIR / "murtuzadeveloper_Smart_Leads.csv")
DEFAULT_DB_PATH = str(DATA_DIR / "smart_leads.sqlite3")

@dataclass
class HardwareLimits:
    """Hardware constraints and conservative performance tuning."""
    max_inference_concurrency: int = 1       # strictly 1 model request at a time
    low_memory_mode: bool = True             # scale images down to preserve VRAM/RAM
    max_screenshot_dimension: int = 1280     # max width/height before vision prompt
    screenshot_jpeg_quality: int = 80        # balance readability and payload size
    max_frame_buffer_size: int = 100         # buffer size for real-time capture (no frame drops)
    memory_pause_threshold_percent: float = 88.0 # pause if RAM usage exceeds 88%

@dataclass
class LMStudioConfig:
    """LM Studio local server connection settings."""
    base_url: str = "http://127.0.0.1:1234/v1"
    default_model: str = "gemma-4-12b-qat"
    fallback_model: str = "qwen2.5-vl-3b-instruct"
    timeout_seconds: int = 35                # realistic timeout (35s) for local GGUF models on CPU/MX150
    max_output_tokens: int = 350             # fast structured generation
    temperature: float = 0.1
    enable_vision: bool = True
    ocr_first_mode: bool = True              # run OCR first; only call vision if ambiguous
    max_retries: int = 1                     # max 1 retry to keep UI real-time

@dataclass
class CaptureConfig:
    """Screen capture and change-detection parameters."""
    capture_interval_seconds: float = 1.4    # fast, responsive real-time capture
    change_threshold_percent: float = 0.12   # sensitive diff threshold (0.12% catches any text scrolling)
    max_captures_per_session: int = 100000   # high limit for continuous batch scraping
    max_runtime_minutes: int = 180           # up to 3 hours continuous session
    pause_after_unchanged_frames: int = 50   # stop only when scrolling truly ends (bottom of page reached after extended attempts)
    max_auto_scroll_actions: int = 100000    # continuous scrolling until bottom of page is reached
    delay_between_scroll_seconds: float = 0.6 # responsive scroll delay
    scroll_pixel_increment: int = 400
    auto_scroll_enabled: bool = True         # Enabled by default
    auto_scroll_wheel_steps: int = 4         # Gentle 4 steps down (guarantees ~65% overlap)
    switch_window_grace_seconds: float = 2.0 # Countdown to let user switch to target window
    viewport_scroll_ratio: float = 0.35      # Scroll 35% of viewport height to guarantee ~65% overlap
    adaptive_pacing: bool = False            # Don't throttle scrolling on slow LLM calls (OCR runs <50ms)
    auto_expand_read_more: bool = True       # Automatically clicks "... Read more" on WhatsApp/messaging apps
    read_more_click_delay_seconds: float = 0.25 # Wait for message bubble to expand before re-capture
    max_read_more_clicks_per_frame: int = 6  # Max buttons to click per cycle (ensures no truncated messages are skipped)

    @property
    def auto_click_read_more(self) -> bool:
        return self.auto_expand_read_more

    @auto_click_read_more.setter
    def auto_click_read_more(self, val: bool):
        self.auto_expand_read_more = val

@dataclass
class SecurityConfig:
    """Privacy, redaction, and compliance policies."""
    strict_business_mode: bool = True        # reject personal-only chats without org info
    require_confirmation_messaging: bool = True # confirm before reading WhatsApp/chat
    prevent_formula_injection: bool = True   # escape =, +, -, @ in CSV
    redact_sensitive_credentials: bool = True # scrub credit cards, passwords, API keys
    blocked_process_names: List[str] = field(default_factory=lambda: [
        "1password.exe", "bitwarden.exe", "keepass.exe", "keepassxc.exe",
        "lastpass.exe", "mstsc.exe", "taskmgr.exe", "lmstudio.exe"
    ])
    blocked_window_keywords: List[str] = field(default_factory=lambda: [
        "password", "vault", "banking", "login", "authenticate", "pin", "checkout", "cvv",
        "lm studio", "lmstudio"
    ])

@dataclass
class AppConfig:
    """Unified application configuration."""
    app_name: str = "murtuzadeveloper Smart Leads"
    app_subtitle: str = "AI-Powered Screen Intelligence & Contact Extraction"
    version: str = "1.0.0"
    author: str = "murtuzadeveloper"
    
    csv_path: str = DEFAULT_CSV_PATH
    db_path: str = DEFAULT_DB_PATH
    
    hardware: HardwareLimits = field(default_factory=HardwareLimits)
    lm_studio: LMStudioConfig = field(default_factory=LMStudioConfig)
    capture: CaptureConfig = field(default_factory=CaptureConfig)
    security: SecurityConfig = field(default_factory=SecurityConfig)

# Global configuration instance
CONFIG = AppConfig()
