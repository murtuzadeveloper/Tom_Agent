"""
Screen capture subsystem supporting full-screen, active window, and custom region capture.
Uses MSS for high performance with Pillow ImageGrab fallback.
"""

from typing import Optional, Tuple, Dict, Any, List
from PIL import Image
from app.utils.logger import logger
from app.capture.window_detector import WindowDetector

try:
    import mss
    HAVE_MSS = True
except ImportError:
    HAVE_MSS = False

try:
    from PIL import ImageGrab
    HAVE_IMAGEGRAB = True
except ImportError:
    HAVE_IMAGEGRAB = False

class ScreenCaptureEngine:
    """Captures displays, windows, and arbitrary screen bounding boxes."""

    def __init__(self):
        self._sct = None
        if HAVE_MSS:
            try:
                self._sct = mss.mss()
            except Exception as e:
                logger.warning(f"Failed to initialize MSS: {e}. Falling back to ImageGrab.")

    def get_monitors(self) -> List[Dict[str, int]]:
        """Returns list of available monitor dimensions."""
        if self._sct:
            return self._sct.monitors
        return [{"top": 0, "left": 0, "width": 1920, "height": 1080}]

    def capture_fullscreen(self, monitor_index: int = 1) -> Optional[Image.Image]:
        """
        Captures the selected monitor (1 = primary monitor in MSS).
        """
        if self._sct:
            try:
                monitors = self._sct.monitors
                mon = monitors[monitor_index] if monitor_index < len(monitors) else monitors[1]
                sct_img = self._sct.grab(mon)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception as e:
                logger.warning(f"MSS capture_fullscreen failed: {e}")

        if HAVE_IMAGEGRAB:
            try:
                return ImageGrab.grab(all_screens=True)
            except Exception as e:
                logger.error(f"ImageGrab capture failed: {e}")

        return None

    def capture_region(self, bbox: Tuple[int, int, int, int]) -> Optional[Image.Image]:
        """
        Captures a specific screen rectangle: (left, top, width, height).
        """
        left, top, width, height = bbox
        if width <= 0 or height <= 0:
            return None

        if self._sct:
            try:
                region = {"left": int(left), "top": int(top), "width": int(width), "height": int(height)}
                sct_img = self._sct.grab(region)
                return Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
            except Exception as e:
                logger.warning(f"MSS capture_region failed: {e}")

        if HAVE_IMAGEGRAB:
            try:
                return ImageGrab.grab(bbox=(left, top, left + width, top + height))
            except Exception as e:
                logger.error(f"ImageGrab capture_region failed: {e}")

        return None

    def capture_active_window(self) -> Tuple[Optional[Image.Image], Dict[str, Any]]:
        """
        Finds the active foreground window and captures its bounding rectangle.
        Returns (captured_pil_image, window_metadata_dict).
        """
        win_info = WindowDetector.get_active_window_info()
        rect = win_info["rect"]
        img = self.capture_region(rect)
        if img is None:
            # Fallback to full screen if window coordinates were invalid
            img = self.capture_fullscreen()
        return img, win_info

    def close(self):
        """Releases MSS resources."""
        if self._sct:
            try:
                self._sct.close()
            except Exception:
                pass
