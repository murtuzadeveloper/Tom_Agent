"""
Unit tests for visual change detection and auto-pause triggering.
"""

from PIL import Image, ImageDraw
from app.capture.screen_change_detector import ScreenChangeDetector

def test_first_frame_always_triggers_change():
    detector = ScreenChangeDetector(threshold_percent=2.5)
    img = Image.new("RGB", (200, 200), color=(100, 100, 100))
    is_changed, diff_percent, should_pause = detector.check_change(img)
    assert is_changed
    assert diff_percent == 100.0
    assert not should_pause

def test_identical_frame_detects_no_change():
    detector = ScreenChangeDetector(threshold_percent=2.5)
    img = Image.new("RGB", (200, 200), color=(120, 120, 120))
    # Frame 1
    detector.check_change(img)
    # Frame 2 (identical)
    is_changed, diff_percent, should_pause = detector.check_change(img)
    assert not is_changed
    assert diff_percent < 0.1
    assert not should_pause

def test_different_frame_triggers_change():
    detector = ScreenChangeDetector(threshold_percent=2.5)
    img1 = Image.new("RGB", (200, 200), color=(255, 255, 255))
    detector.check_change(img1)

    img2 = Image.new("RGB", (200, 200), color=(0, 0, 0))
    is_changed, diff_percent, should_pause = detector.check_change(img2)
    assert is_changed
    assert diff_percent > 50.0

def test_auto_pause_after_repeated_unchanged_frames():
    detector = ScreenChangeDetector(threshold_percent=2.5, pause_after_unchanged=3)
    img = Image.new("RGB", (200, 200), color=(50, 50, 50))
    detector.check_change(img)  # Frame 1 (first)

    detector.check_change(img)  # unchanged 1
    detector.check_change(img)  # unchanged 2
    is_changed, diff, should_pause = detector.check_change(img)  # unchanged 3 -> pause!

    assert not is_changed
    assert should_pause
