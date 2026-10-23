"""
Active window detection and metadata inspector using Windows User32 and Psapi APIs.
Identifies active process name, window title, and bounding dimensions.
"""

import sys
import os
import ctypes
from typing import Dict, Any, Optional, Tuple
from app.utils.logger import logger

try:
    import psutil
    HAVE_PSUTIL = True
except ImportError:
    HAVE_PSUTIL = False

class RECT(ctypes.Structure):
    _fields_ = [
        ("left", ctypes.c_long),
        ("top", ctypes.c_long),
        ("right", ctypes.c_long),
        ("bottom", ctypes.c_long)
    ]

class WindowDetector:
    """Retrieves active foreground window info on Windows."""

    @classmethod
    def get_active_window_info(cls) -> Dict[str, Any]:
        """
        Returns a dictionary with:
        {
            "hwnd": int,
            "title": str,
            "process_name": str,
            "rect": (left, top, width, height),
            "is_browser": bool,
            "is_whatsapp": bool
        }
        """
        default_info = {
            "hwnd": 0,
            "title": "Desktop Screen",
            "process_name": "explorer.exe",
            "rect": (0, 0, 1920, 1080),
            "is_browser": False,
            "is_whatsapp": False,
            "is_own_app": False
        }

        if sys.platform != "win32":
            return default_info

        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()
            if not hwnd:
                return default_info

            # Retrieve Window Title
            length = user32.GetWindowTextLengthW(hwnd)
            buff = ctypes.create_unicode_buffer(length + 1)
            user32.GetWindowTextW(hwnd, buff, length + 1)
            title = buff.value or "Untitled Window"

            # Retrieve Bounding Rect
            rect = RECT()
            user32.GetWindowRect(hwnd, ctypes.byref(rect))
            width = max(0, rect.right - rect.left)
            height = max(0, rect.bottom - rect.top)

            # Retrieve Process Name
            pid = ctypes.c_ulong()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            process_name = "unknown.exe"

            if HAVE_PSUTIL and pid.value:
                try:
                    proc = psutil.Process(pid.value)
                    process_name = proc.name()
                except Exception:
                    pass

            proc_lower = process_name.lower()
            title_lower = title.lower()

            is_browser = any(b in proc_lower for b in ["chrome", "msedge", "firefox", "brave", "opera", "vivaldi"])
            is_whatsapp = "whatsapp" in proc_lower or "whatsapp" in title_lower

            my_pid = os.getpid()
            is_own_app = (pid.value == my_pid) or ("smart leads" in title_lower)

            browser_url = None
            if is_browser:
                m_url = re.search(r'(https?://[^\s<>"\'`()]+|www\.[^\s<>"\'`()]+)', title)
                if m_url:
                    browser_url = m_url.group(0)

            return {
                "hwnd": hwnd,
                "title": title,
                "process_name": process_name,
                "rect": (rect.left, rect.top, width, height),
                "is_browser": is_browser,
                "is_whatsapp": is_whatsapp,
                "is_own_app": is_own_app,
                "url": browser_url
            }

        except Exception as e:
            logger.debug(f"WindowDetector query failed: {e}")
            return default_info
