"""
Unit tests for the AutoScroller automated scrolling subsystem.
"""

from unittest.mock import MagicMock
from app.capture.auto_scroller import AutoScroller

def test_auto_scroller_initial_state():
    scroller = AutoScroller(max_scroll_actions=5, delay_seconds=0.01)
    assert scroller.scroll_count == 0
    assert scroller.can_scroll()

def test_auto_scroller_limit_reached():
    scroller = AutoScroller(max_scroll_actions=3, delay_seconds=0.01)

    assert scroller.scroll_active_window()
    assert scroller.scroll_active_window()
    assert scroller.scroll_active_window()
    assert scroller.scroll_count == 3
    assert not scroller.can_scroll()

    # Further scroll attempt rejected
    assert not scroller.scroll_active_window()
    assert scroller.scroll_count == 3

def test_auto_scroller_reset():
    scroller = AutoScroller(max_scroll_actions=2, delay_seconds=0.01)
    scroller.scroll_active_window()
    scroller.scroll_active_window()
    assert not scroller.can_scroll()

    scroller.reset()
    assert scroller.scroll_count == 0
    assert scroller.can_scroll()

def test_auto_scroller_browser_controller_mock():
    scroller = AutoScroller(max_scroll_actions=5, delay_seconds=0.01)
    mock_browser = MagicMock()
    mock_browser.is_active = True
    mock_browser.scroll_down.return_value = True

    success = scroller.scroll_controlled_browser(mock_browser, pixel_increment=500)
    assert success
    assert scroller.scroll_count == 1
    mock_browser.scroll_down.assert_called_once_with(500)

def test_adaptive_wheel_steps_calculation():
    # Zero height returns fallback default
    steps_zero = AutoScroller.calculate_adaptive_wheel_steps(0)
    assert steps_zero >= 2

    # Standard height (1000px): 1000 * 0.35 / 70 = 5 steps
    steps_1000 = AutoScroller.calculate_adaptive_wheel_steps(1000, ratio=0.35)
    assert 2 <= steps_1000 <= 5

    # Extreme height is capped at 5 to guarantee ~65% overlap
    steps_large = AutoScroller.calculate_adaptive_wheel_steps(4000)
    assert steps_large <= 5
