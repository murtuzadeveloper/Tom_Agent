"""
Controlled browser automation controller for Mode C using Playwright.
Gracefully falls back to manual controlled scrolling if Playwright is not installed.
"""

from typing import Optional, Tuple
from config import CONFIG
from app.utils.logger import logger

class BrowserController:
    """Manages controlled scrolling of supported public webpages."""

    def __init__(self):
        self._playwright = None
        self._browser = None
        self._page = None
        self.is_active = False

    def is_playwright_installed(self) -> bool:
        """Checks if Playwright is available in the Python environment."""
        try:
            import playwright
            return True
        except ImportError:
            return False

    def start_session(self, url: str) -> Tuple[bool, str]:
        """Launches a controlled browser session navigated to target URL."""
        if not self.is_playwright_installed():
            msg = "Playwright is not installed. Manual scroll mode with change detection will be used instead."
            logger.info(msg)
            return False, msg

        try:
            from playwright.sync_api import sync_playwright
            self._playwright = sync_playwright().start()
            self._browser = self._playwright.chromium.launch(headless=False)
            self._page = self._browser.new_page()
            self._page.goto(url, wait_until="domcontentloaded", timeout=30000)
            self.is_active = True
            msg = f"Started controlled browser session for {url}"
            logger.info(msg)
            return True, msg
        except Exception as e:
            msg = f"Failed to start Playwright browser: {e}"
            logger.error(msg)
            self.stop_session()
            return False, msg

    def scroll_down(self, pixel_increment: int = None) -> bool:
        """Scrolls the controlled page down by pixel_increment."""
        if not self.is_active or not self._page:
            return False

        increment = pixel_increment or CONFIG.capture.scroll_pixel_increment
        try:
            self._page.evaluate(f"window.scrollBy(0, {increment});")
            self._page.wait_for_timeout(int(CONFIG.capture.delay_between_scroll_seconds * 1000))
            return True
        except Exception as e:
            logger.warning(f"Browser scroll error: {e}")
            return False

    def is_at_bottom(self) -> bool:
        """Checks if the webpage has reached the bottom of scroll height."""
        if not self.is_active or not self._page:
            return True
        try:
            return self._page.evaluate(
                "(window.innerHeight + window.scrollY) >= (document.body.offsetHeight - 50)"
            )
        except Exception:
            return False

    def stop_session(self) -> None:
        """Closes browser and cleans up Playwright resources."""
        if self._page:
            try:
                self._page.close()
            except Exception:
                pass
            self._page = None

        if self._browser:
            try:
                self._browser.close()
            except Exception:
                pass
            self._browser = None

        if self._playwright:
            try:
                self._playwright.stop()
            except Exception:
                pass
            self._playwright = None

        self.is_active = False
