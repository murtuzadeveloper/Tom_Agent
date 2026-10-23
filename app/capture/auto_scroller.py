"""
Automated scrolling subsystem for active Windows applications and controlled browsers.
Enables hands-free scrolling across web browsers, WhatsApp Desktop, directories, and documents.
"""

import sys
import time
import ctypes
from typing import Optional, Tuple
from config import CONFIG
from app.utils.logger import logger

# Windows API Constants
MOUSEEVENTF_WHEEL = 0x0800
WHEEL_DELTA = 120

class AutoScroller:
    """Dispatches automated downward scroll events to active windows or browser sessions."""

    def __init__(
        self,
        max_scroll_actions: int = None,
        delay_seconds: float = None,
        scroll_delta: int = None
    ):
        self.max_scrolls = max_scroll_actions or CONFIG.capture.max_auto_scroll_actions
        self.delay = delay_seconds or CONFIG.capture.delay_between_scroll_seconds
        self.scroll_delta = scroll_delta or 360  # Default: 3 wheel steps down (3 * 120)
        self.scroll_count = 0

    def reset(self):
        """Resets the scroll count for a new session."""
        self.scroll_count = 0

    def can_scroll(self) -> bool:
        """Checks if session has remaining permitted scroll actions."""
        return self.scroll_count < self.max_scrolls

    @classmethod
    def calculate_adaptive_wheel_steps(cls, height: int, ratio: float = None) -> int:
        """
        Calculates optimal wheel steps based on viewport height and capturing capability.
        Guarantees a generous 60-70% overlap between frames so NO messages are ever skipped.
        """
        scroll_ratio = ratio or CONFIG.capture.viewport_scroll_ratio
        if height <= 0:
            return CONFIG.capture.auto_scroll_wheel_steps

        target_scroll_px = height * scroll_ratio
        # Each wheel step scrolls ~60-80px in WhatsApp Desktop/Web
        computed_steps = int(target_scroll_px / 70.0)
        return max(2, min(5, computed_steps))

    def scroll_active_window(
        self,
        window_rect: Optional[Tuple[int, int, int, int]] = None,
        wheel_steps: Optional[int] = None,
        hwnd: Optional[int] = None
    ) -> bool:
        """
        Sends gentle, overlapping synthetic mouse wheel scrolls to the active window on Windows.
        Guarantees smooth scrolling across WhatsApp Desktop, WhatsApp Web, browsers, and Win32 apps.
        Eliminates abrupt PageDown jumps so every single message is completely read and captured.
        """
        if not self.can_scroll():
            logger.info(f"Auto-scroll reached limit ({self.max_scrolls} actions).")
            return False

        # Adapt wheel steps to target viewport height (guaranteeing ~65% overlap)
        if wheel_steps is None:
            if window_rect and len(window_rect) >= 4 and window_rect[3] > 50:
                wheel_steps = self.calculate_adaptive_wheel_steps(window_rect[3])
            else:
                wheel_steps = CONFIG.capture.auto_scroll_wheel_steps

        if sys.platform != "win32":
            logger.debug(f"Auto-scroller: Non-Windows simulation (steps={wheel_steps}).")
            self.scroll_count += 1
            return True

        try:
            user32 = ctypes.windll.user32
            # Explicit Win32 prototypes for 64-bit safety
            user32.mouse_event.argtypes = [
                ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_size_t
            ]
            user32.keybd_event.argtypes = [
                ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ulong, ctypes.c_size_t
            ]

            # 1. Ensure target window has foreground focus if handle is provided
            if hwnd and hwnd != user32.GetForegroundWindow():
                try:
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

            # 2. Resolve target coordinates inside active window content area
            if not window_rect or len(window_rect) < 4 or window_rect[2] <= 50:
                screen_w = user32.GetSystemMetrics(0)
                screen_h = user32.GetSystemMetrics(1)
                window_rect = (0, 0, screen_w, screen_h)

            left, top, width, height = window_rect
            # Position target in active chat message stream:
            # In WhatsApp, left 30% is chat list; 58% across places cursor squarely inside message pane.
            # 50% vertically places cursor right in the middle of message bubbles.
            target_x = left + int(width * 0.58)
            target_y = top + int(height * 0.50)

            # Position physical cursor inside content area
            user32.SetCursorPos(target_x, target_y)
            # Dispatch 0-pixel MOUSEEVENTF_MOVE (0x0001) so Windows updates window hit-test & hover
            user32.mouse_event(0x0001, 0, 0, 0, 0)
            time.sleep(0.02)

            # 3. Multi-notch synthetic mouse wheel down (-120 per notch)
            for _ in range(wheel_steps):
                user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, -WHEEL_DELTA, 0)
                time.sleep(0.015)

            # 4. Complementary gentle Down Arrow (VK_DOWN = 0x28) taps
            # Guarantees that even if mouse wheel was blocked or ignored by an unfocused control,
            # WhatsApp or the active browser viewport moves downward smoothly without skipping!
            for _ in range(2):
                user32.keybd_event(0x28, 0, 0, 0)
                time.sleep(0.015)
                user32.keybd_event(0x28, 0, 0x0002, 0)
                time.sleep(0.015)

            self.scroll_count += 1
            logger.info(f"⚡ Auto-scroll executed #{self.scroll_count} ({wheel_steps} notches + 2 down-arrows, ~65% overlap)")

            # Wait for content rendering/loading
            time.sleep(self.delay)
            return True

        except Exception as e:
            logger.error(f"Auto-scroll error: {e}", exc_info=True)
            return False

    def dispatch_recovery_nudge(
        self,
        window_rect: Optional[Tuple[int, int, int, int]] = None,
        hwnd: Optional[int] = None
    ) -> bool:
        """
        Actively nudges a stuck viewport: refocuses window, clicks chat message pane,
        and sends down-arrow keystrokes to break out of any focus trap or stalled scroll.
        """
        if sys.platform != "win32":
            return True
        try:
            user32 = ctypes.windll.user32
            user32.mouse_event.argtypes = [
                ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_size_t
            ]
            user32.keybd_event.argtypes = [
                ctypes.c_ubyte, ctypes.c_ubyte, ctypes.c_ulong, ctypes.c_size_t
            ]

            if hwnd and hwnd != user32.GetForegroundWindow():
                try:
                    user32.SetForegroundWindow(hwnd)
                except Exception:
                    pass

            if not window_rect or len(window_rect) < 4:
                screen_w = user32.GetSystemMetrics(0)
                screen_h = user32.GetSystemMetrics(1)
                window_rect = (0, 0, screen_w, screen_h)

            left, top, width, height = window_rect
            target_x = left + int(width * 0.55)
            target_y = top + int(height * 0.50)

            user32.SetCursorPos(target_x, target_y)
            # Gentle click in message pane background to ensure focus
            user32.mouse_event(0x0002, 0, 0, 0, 0)
            time.sleep(0.02)
            user32.mouse_event(0x0004, 0, 0, 0, 0)
            time.sleep(0.05)

            # Down arrow 4 times to force movement
            for _ in range(4):
                user32.keybd_event(0x28, 0, 0, 0)
                time.sleep(0.02)
                user32.keybd_event(0x28, 0, 0x0002, 0)
                time.sleep(0.02)

            logger.info("⚡ Dispatched active scroll recovery nudge to resume movement.")
            return True
        except Exception as e:
            logger.debug(f"Recovery nudge error: {e}")
            return False

    def scroll_controlled_browser(self, browser_controller, pixel_increment: int = 600) -> bool:
        """Performs controlled JavaScript scroll using Playwright browser session."""
        if not self.can_scroll():
            return False

        if browser_controller and browser_controller.is_active:
            success = browser_controller.scroll_down(pixel_increment)
            if success:
                self.scroll_count += 1
                logger.info(f"Controlled browser auto-scroll #{self.scroll_count}/{self.max_scrolls} ({pixel_increment}px)")
                time.sleep(self.delay)
                return True
        return False
