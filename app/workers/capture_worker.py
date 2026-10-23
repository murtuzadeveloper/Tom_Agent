"""
Background capture worker thread.
Inspects screen at configurable intervals, performs change detection, and passes frames.
"""

import time
from typing import Optional, Tuple
from PySide6.QtCore import QThread, Signal
from config import CONFIG
from app.capture.screen_capture import ScreenCaptureEngine
from app.capture.screen_change_detector import ScreenChangeDetector
from app.capture.window_detector import WindowDetector
from app.capture.auto_scroller import AutoScroller
from app.capture.browser_controller import BrowserController
from app.capture.read_more_expander import ReadMoreExpander
from app.security.capture_policy import CapturePolicy
from app.utils.logger import logger

class CaptureWorker(QThread):
    """Orchestrates periodic screen captures, change detection, and automated scrolling."""

    frame_ready = Signal(object, dict, float)  # (PIL.Image, window_info, diff_percent)
    frame_skipped = Signal(str, float)         # (reason, diff_percent)
    auto_paused = Signal(str)                  # (reason)
    status_changed = Signal(str)               # (status text)
    session_finished = Signal(int)             # (total captures)
    auto_scroll_triggered = Signal(int, int)   # (scroll_count, max_scrolls)
    read_more_expanded = Signal(int)           # (count of buttons expanded)
    countdown_updated = Signal(int)            # (seconds left in switch grace period)

    def __init__(
        self,
        mode: str = "A",  # 'A': Current Screen, 'B': Region, 'C': Browser Scroll
        region_bbox: Optional[Tuple[int, int, int, int]] = None,
        auto_scroll: bool = True,
        auto_expand_read_more: bool = True,
        browser_controller: Optional[BrowserController] = None,
        is_extraction_busy_fn=None,
        parent=None
    ):
        super().__init__(parent)
        self.mode = mode
        self.region_bbox = region_bbox
        self.auto_scroll = auto_scroll
        self.auto_expand_read_more = auto_expand_read_more
        self.browser_controller = browser_controller
        self.is_extraction_busy_fn = is_extraction_busy_fn
        self.interval = CONFIG.capture.capture_interval_seconds
        self.max_captures = CONFIG.capture.max_captures_per_session
        self.is_running = False
        self.is_paused = False

        self.engine = ScreenCaptureEngine()
        self.change_detector = ScreenChangeDetector()
        self.auto_scroller = AutoScroller()
        self.read_more_expander = ReadMoreExpander()
        self.captures_count = 0

    def run(self):
        self.is_running = True
        self.is_paused = False
        self.captures_count = 0
        self.change_detector.reset()
        logger.info(f"CaptureWorker started in Mode {self.mode} (Auto-Scroll={self.auto_scroll})")

        # 1. Grace Countdown Period (lets user switch to target window without rush)
        grace_seconds = int(CONFIG.capture.switch_window_grace_seconds)
        for sec in range(grace_seconds, 0, -1):
            if not self.is_running:
                return
            self.countdown_updated.emit(sec)
            self.status_changed.emit(f"Switch to target window ({sec}s)...")
            time.sleep(1.0)

        self.countdown_updated.emit(0)
        self.status_changed.emit("Capturing & Auto-Scrolling Active")

        start_time = time.time()
        max_duration_seconds = CONFIG.capture.max_runtime_minutes * 60

        while self.is_running:
            # Check maximum runtime
            if time.time() - start_time > max_duration_seconds:
                logger.info("Maximum session runtime reached.")
                self.auto_paused.emit("Max runtime reached")
                break

            # Check maximum capture count
            if self.captures_count >= self.max_captures:
                logger.info(f"Maximum captures ({self.max_captures}) reached.")
                self.auto_paused.emit(f"Reached max captures limit ({self.max_captures})")
                break

            # Handle Paused State
            if self.is_paused:
                time.sleep(0.5)
                continue

            try:
                # 1. Inspect Foreground Window
                win_info = WindowDetector.get_active_window_info()

                # If user is still viewing Smart Leads itself, pause capture until they switch
                if win_info.get("is_own_app"):
                    self.status_changed.emit("Waiting for you to switch to target application...")
                    self.frame_skipped.emit("Smart Leads is focused; please switch to your target window", 0.0)
                    time.sleep(1.0)
                    continue

                is_allowed, block_reason = CapturePolicy.is_window_allowed(
                    win_info.get("title", ""),
                    win_info.get("process_name", "")
                )

                if not is_allowed:
                    self.frame_skipped.emit(block_reason, 0.0)
                    time.sleep(self.interval)
                    continue

                # 2. Capture Frame based on Mode
                image = None
                if self.mode == "B" and self.region_bbox:
                    image = self.engine.capture_region(self.region_bbox)
                elif self.mode == "A":
                    image = self.engine.capture_fullscreen()
                elif self.mode == "C":
                    image, _ = self.engine.capture_active_window()

                if image is None:
                    self.frame_skipped.emit("Capture returned empty frame", 0.0)
                    time.sleep(self.interval)
                    continue

                # 2b. Auto-Expand "... Read more", "See more", "Show more" on messaging & social windows
                expanded_any = False
                if self.auto_expand_read_more and getattr(CONFIG.capture, "auto_expand_read_more", True):
                    offset = (0, 0)
                    scroll_rect = self.region_bbox if (self.mode == "B" and self.region_bbox) else win_info.get("rect")
                    if self.mode == "B" and self.region_bbox:
                        offset = (self.region_bbox[0], self.region_bbox[1])
                    elif self.mode == "C" and win_info.get("rect"):
                        r = win_info.get("rect")
                        offset = (r[0], r[1])

                    # Multi-pass expansion: catch newly visible buttons when upper messages expand
                    total_clicked = 0
                    for _ in range(3):
                        clicked = self.read_more_expander.expand_visible_read_more(
                            image,
                            screen_offset=offset,
                            window_rect=scroll_rect,
                            max_clicks=6
                        )
                        if clicked == 0:
                            break
                        total_clicked += clicked
                        expanded_any = True
                        time.sleep(CONFIG.capture.read_more_click_delay_seconds)
                        # Re-capture the frame with the expanded message content!
                        if self.mode == "B" and self.region_bbox:
                            image = self.engine.capture_region(self.region_bbox)
                        elif self.mode == "A":
                            image = self.engine.capture_fullscreen()
                        elif self.mode == "C":
                            image, _ = self.engine.capture_active_window()

                    if total_clicked > 0:
                        self.read_more_expanded.emit(total_clicked)

                # 3. Check for Visual Screen Change
                is_changed, diff_percent, should_pause = self.change_detector.check_change(image)

                # If any "Read more" was expanded, or during auto-scrolling with any visual movement (diff >= 0.02%),
                # ensure frame is marked changed so newly revealed messages are never skipped!
                if expanded_any or (self.auto_scroll and self.auto_scroller.scroll_count > 0 and diff_percent >= 0.02):
                    is_changed = True

                # If content appears stationary during active auto-scrolling:
                # Dispatch active recovery nudges at intervals to refocus window,
                # click message pane, and send Down Arrow keys so scrolling never halts!
                if self.auto_scroll and not is_changed:
                    unchanged = self.change_detector._unchanged_count
                    if unchanged in (3, 7, 15, 25, 35):
                        logger.info(f"⚡ Content stationary for {unchanged} frames; triggering active recovery nudge...")
                        scroll_rect = self.region_bbox if (self.mode == "B" and self.region_bbox) else win_info.get("rect")
                        self.auto_scroller.dispatch_recovery_nudge(scroll_rect, hwnd=win_info.get("hwnd"))

                if should_pause:
                    self.is_paused = True
                    pause_msg = "Reached bottom of page (content stopped moving after 50 recovery attempts)" if self.auto_scroll else "Screen unchanged for multiple frames"
                    logger.info(f"CaptureWorker paused: {pause_msg}")
                    self.auto_paused.emit(pause_msg)
                    continue

                # 4. Emit Frame for Extraction Worker (guaranteed zero message skipping)
                if is_changed:
                    self.captures_count += 1
                    self.frame_ready.emit(image, win_info, diff_percent)
                else:
                    self.frame_skipped.emit("Screen unchanged", diff_percent)

                # 5. Automated Scrolling (Paced to Capturing Capability)
                # MUST EXECUTE whenever auto_scroll is enabled so content continues scrolling
                if self.auto_scroll and self.auto_scroller.can_scroll():
                    # Target scroll rect: use region_bbox if in Region Mode, else window rect
                    scroll_rect = self.region_bbox if (self.mode == "B" and self.region_bbox) else win_info.get("rect")
                    target_hwnd = win_info.get("hwnd")

                    if self.mode == "C" and self.browser_controller and self.browser_controller.is_active:
                        self.auto_scroller.scroll_controlled_browser(self.browser_controller)
                    else:
                        self.auto_scroller.scroll_active_window(scroll_rect, hwnd=target_hwnd)

                    # Reset click cooldown on scroll so newly scrolled Read more buttons are clicked immediately
                    self.read_more_expander.reset_cooldown()

                    self.auto_scroll_triggered.emit(self.auto_scroller.scroll_count, self.auto_scroller.max_scrolls)

            except Exception as e:
                logger.error(f"Error in capture loop: {e}")
                self.frame_skipped.emit(f"Capture error: {str(e)}", 0.0)

            # Sleep for interval
            time.sleep(self.interval)

        self.engine.close()
        self.status_changed.emit("Capture Stopped")
        self.session_finished.emit(self.captures_count)
        logger.info(f"CaptureWorker terminated. Total captures: {self.captures_count}")

    def pause(self):
        """Pauses capture cycles without destroying the thread."""
        self.is_paused = True
        self.status_changed.emit("Capture Paused")
        logger.info("CaptureWorker paused by user.")

    def resume(self):
        """Resumes capture cycles."""
        self.is_paused = False
        self.change_detector.reset()
        self.status_changed.emit("Capturing Active")
        logger.info("CaptureWorker resumed by user.")

    def stop(self):
        """Gracefully halts the capture thread."""
        self.is_running = False
        self.is_paused = False
