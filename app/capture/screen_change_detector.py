"""
Screen change detection using lightweight thumbnail difference.
Avoids wasteful OCR and vision model invocations when screen is static.
"""

from typing import Tuple, Optional
from PIL import Image
from config import CONFIG
from app.utils.logger import logger

class ScreenChangeDetector:
    """Computes perceptual difference between consecutive captured frames."""

    def __init__(self, threshold_percent: float = None, pause_after_unchanged: int = None):
        self.threshold_percent = threshold_percent or CONFIG.capture.change_threshold_percent
        self.pause_after_unchanged = pause_after_unchanged or CONFIG.capture.pause_after_unchanged_frames
        self._previous_thumb_bytes: Optional[bytes] = None
        self._unchanged_count: int = 0
        self._thumb_size = (64, 64)

    def check_change(self, current_image: Image.Image) -> Tuple[bool, float, bool]:
        """
        Analyzes current frame against previous frame.
        Returns:
            (is_changed: bool, diff_percent: float, should_pause: bool)
        """
        # Downsample to small grayscale thumbnail for fast memory-conscious diff
        thumb = current_image.convert("L").resize(self._thumb_size, Image.Resampling.BILINEAR)
        current_bytes = thumb.tobytes()

        if self._previous_thumb_bytes is None:
            # First frame is always considered a change
            self._previous_thumb_bytes = current_bytes
            self._unchanged_count = 0
            return True, 100.0, False

        # Calculate Mean Absolute Difference
        total_diff = 0
        total_pixels = len(current_bytes)
        prev = self._previous_thumb_bytes

        for i in range(total_pixels):
            total_diff += abs(current_bytes[i] - prev[i])

        # Maximum possible difference is total_pixels * 255
        diff_percent = (total_diff / (total_pixels * 255.0)) * 100.0
        self._previous_thumb_bytes = current_bytes

        # Check if content has moved (any diff >= 0.04% is true movement)
        is_changed = diff_percent >= self.threshold_percent

        if is_changed or diff_percent >= 0.04:
            self._unchanged_count = 0
            should_pause = False
        else:
            self._unchanged_count += 1
            should_pause = self._unchanged_count >= self.pause_after_unchanged
            if should_pause:
                logger.info(f"Screen stationary for {self._unchanged_count} consecutive frames. Triggering auto-pause.")

        return is_changed, diff_percent, should_pause

    def reset(self) -> None:
        """Resets the previous frame memory and unchanged counter."""
        self._previous_thumb_bytes = None
        self._unchanged_count = 0
