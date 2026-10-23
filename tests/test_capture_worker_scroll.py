"""
Unit tests for CaptureWorker auto-scrolling orchestration and pause behavior.
"""

from unittest.mock import MagicMock, patch
from PIL import Image
from app.workers.capture_worker import CaptureWorker

def test_capture_worker_continues_scrolling_even_if_frame_unchanged():
    """
    Guarantees that when a frame is visually unchanged, CaptureWorker does NOT skip
    the auto-scroll step, ensuring the window moves down to reach new content.
    """
    worker = CaptureWorker(mode="A", auto_scroll=True)
    worker.engine = MagicMock()
    dummy_img = Image.new("RGB", (100, 100), color=(255, 255, 255))
    worker.engine.capture_fullscreen.return_value = dummy_img

    worker.change_detector = MagicMock()
    # is_changed=False, diff_percent=0.2, should_pause=False
    worker.change_detector.check_change.return_value = (False, 0.2, False)

    worker.auto_scroller = MagicMock()
    worker.auto_scroller.can_scroll.return_value = True
    worker.auto_scroller.scroll_count = 1
    worker.auto_scroller.max_scrolls = 50

    with patch("app.capture.window_detector.WindowDetector.get_active_window_info") as mock_win, \
         patch("app.security.capture_policy.CapturePolicy.is_window_allowed", return_value=(True, "")):

        mock_win.return_value = {
            "hwnd": 12345,
            "title": "Directory Listing",
            "process_name": "chrome.exe",
            "rect": (100, 100, 1200, 800),
            "is_browser": True,
            "is_whatsapp": False,
            "is_own_app": False
        }

        frame_ready_mock = MagicMock()
        frame_skipped_mock = MagicMock()
        worker.frame_ready.connect(frame_ready_mock)
        worker.frame_skipped.connect(frame_skipped_mock)

        # Simulate one iteration of the loop body
        win_info = mock_win.return_value
        image = worker.engine.capture_fullscreen()
        is_changed, diff_percent, should_pause = worker.change_detector.check_change(image)

        assert not is_changed
        assert not should_pause

        # Frame should be skipped for extraction
        if is_changed:
            worker.frame_ready.emit(image, win_info, diff_percent)
        else:
            worker.frame_skipped.emit("Screen unchanged", diff_percent)

        # But auto-scroll MUST execute
        if worker.auto_scroll and worker.auto_scroller.can_scroll():
            worker.auto_scroller.scroll_active_window(win_info.get("rect"), hwnd=win_info.get("hwnd"))

        frame_ready_mock.assert_not_called()
        frame_skipped_mock.assert_called_once_with("Screen unchanged", 0.2)
        worker.auto_scroller.scroll_active_window.assert_called_once_with((100, 100, 1200, 800), hwnd=12345)
