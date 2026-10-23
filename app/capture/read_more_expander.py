"""
Read More Expander for WhatsApp Desktop, WhatsApp Web, and Messaging Applications.
Locates and clicks truncated message '... Read more' buttons to reveal full contact and job details.
Restricted strictly to message body pane; verifies text content before clicking.
"""

import sys
import time
import ctypes
import re
from typing import List, Tuple, Optional, Set
from PIL import Image
import numpy as np
import cv2
from config import CONFIG
from app.utils.logger import logger

class ReadMoreExpander:
    """Detects and clicks '... Read more' buttons on active messaging applications."""

    def __init__(self):
        self._tesseract_available = self._check_tesseract()
        self._recently_clicked: List[Tuple[int, int, float]] = []

    def _check_tesseract(self) -> bool:
        """Checks if pytesseract is usable."""
        try:
            import pytesseract
            return True
        except ImportError:
            return False

    def reset_cooldown(self):
        """Clears click history when scrolling moves the viewport to new messages."""
        self._recently_clicked.clear()

    def _is_recently_clicked(self, cx: int, cy: int, cooldown_seconds: float = 2.5) -> bool:
        """Prevents clicking the same screen coordinates repeatedly in a single cycle."""
        now = time.time()
        # Prune expired clicks
        self._recently_clicked = [
            (x, y, t) for (x, y, t) in self._recently_clicked if now - t < cooldown_seconds
        ]
        for x, y, _ in self._recently_clicked:
            if abs(cx - x) < 30 and abs(cy - y) < 30:
                return True
        return False

    def _mark_clicked(self, cx: int, cy: int):
        self._recently_clicked.append((cx, cy, time.time()))

    def find_read_more_coordinates(
        self,
        image: Image.Image,
        screen_offset: Tuple[int, int] = (0, 0),
        window_rect: Optional[Tuple[int, int, int, int]] = None
    ) -> List[Tuple[int, int]]:
        """
        Locates all genuine '... Read more', 'See more', or 'Show more' buttons in the active message pane.
        Strictly ignores taskbar, title bar, and sidebar unread badges.
        Verifies text content with OCR before returning click targets.
        """
        candidates: List[Tuple[int, int]] = []
        off_x, off_y = screen_offset
        img_w, img_h = image.size

        # Define chat message pane boundaries (WhatsApp desktop/web layout):
        if window_rect and len(window_rect) >= 4 and window_rect[2] > 200:
            wx, wy, ww, wh = window_rect
            # If offset is 0, window is in absolute image coords
            if off_x == 0 and off_y == 0:
                min_x = max(0, wx + int(ww * 0.15))
                max_x = min(img_w, wx + ww - 10)
                min_y = max(0, wy + 40)
                max_y = min(img_h, wy + wh - 45)
            else:
                min_x = 0
                max_x = img_w
                min_y = 0
                max_y = img_h
        elif off_x != 0 or off_y != 0 or img_w < 600 or img_h < 400:
            min_x = 0
            max_x = img_w
            min_y = 0
            max_y = img_h
        else:
            min_x = int(img_w * 0.15)
            max_x = int(img_w * 0.98)
            min_y = 40
            max_y = max(min_y + 40, img_h - 55)

        # -------------------------------------------------------------
        # Strategy 1: Pytesseract Chat Pane Word Matching (Single Fast Pass)
        # -------------------------------------------------------------
        if self._tesseract_available:
            try:
                import pytesseract
                from pytesseract import Output
                pane_crop = image.crop((min_x, min_y, max_x, max_y))
                data = pytesseract.image_to_data(pane_crop, output_type=Output.DICT, timeout=2.0)
                words = data.get("text", [])
                n = len(words)

                TRIGGER_WORDS = {"read", "see", "show", "view", "continue"}
                TARGET_WORDS = {"more", "reading", "mote", "mare", "morb"}
                COMBINED_WORDS = {"readmore", "seemore", "showmore", "viewmore", "continuereading"}

                for i in range(n):
                    raw_w = words[i].strip()
                    if not raw_w:
                        continue
                    w1 = re.sub(r'[^\w]', '', raw_w.lower())
                    if not w1:
                        continue

                    # Direct match: "readmore", "seemore", etc.
                    if any(c in w1 for c in COMBINED_WORDS):
                        cand_x = min_x + data["left"][i] + data["width"][i] // 2
                        cand_y = min_y + data["top"][i] + data["height"][i] // 2
                        cx = off_x + cand_x
                        cy = off_y + cand_y
                        if not self._is_recently_clicked(cx, cy):
                            candidates.append((cx, cy))

                    # Two-word sequence: "read/see/show/view" followed by "more"
                    elif w1 in TRIGGER_WORDS:
                        for k in range(1, 4):
                            if i + k >= n:
                                break
                            raw_w2 = words[i + k].strip()
                            if not raw_w2:
                                continue
                            w2 = re.sub(r'[^\w]', '', raw_w2.lower())
                            if not w2:
                                continue
                            if w2 in TARGET_WORDS or w2.startswith("more"):
                                dx = data["left"][i + k] - (data["left"][i] + data["width"][i])
                                dy = abs(data["top"][i] - data["top"][i + k])
                                if -15 <= dx < 75 and dy < 30:
                                    total_w = (data["left"][i + k] + data["width"][i + k]) - data["left"][i]
                                    cand_x = min_x + data["left"][i] + total_w // 2
                                    cand_y = min_y + data["top"][i] + data["height"][i] // 2
                                    cx = off_x + cand_x
                                    cy = off_y + cand_y
                                    if not self._is_recently_clicked(cx, cy):
                                        candidates.append((cx, cy))
                                break

            except Exception as e:
                logger.debug(f"OCR-based Read More search error: {e}")

        # If Strategy 1 already found candidates, return immediately without slow contour OCR loops!
        if candidates:
            unique_points: List[Tuple[int, int]] = []
            for pt in candidates:
                if not any(abs(pt[0] - up[0]) < 25 and abs(pt[1] - up[1]) < 25 for up in unique_points):
                    unique_points.append(pt)
            return unique_points

        # -------------------------------------------------------------
        # Strategy 2: OpenCV Link Color Detection (Green + Cyan/Blue links)
        # -------------------------------------------------------------
        try:
            img_rgb = np.array(image.convert("RGB"))
            pane_rgb = img_rgb[min_y:max_y, min_x:max_x]
            if pane_rgb.size > 0:
                hsv = cv2.cvtColor(pane_rgb, cv2.COLOR_RGB2HSV)

                # Detect Green link colors (WhatsApp Dark & Light mode)
                lower_green = np.array([30, 40, 40], dtype=np.uint8)
                upper_green = np.array([90, 255, 255], dtype=np.uint8)
                mask_green = cv2.inRange(hsv, lower_green, upper_green)

                # Detect Cyan / Blue link colors (WhatsApp Web / Chrome)
                lower_blue = np.array([85, 40, 40], dtype=np.uint8)
                upper_blue = np.array([135, 255, 255], dtype=np.uint8)
                mask_blue = cv2.inRange(hsv, lower_blue, upper_blue)

                link_mask = cv2.bitwise_or(mask_green, mask_blue)

                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (9, 3))
                dilated = cv2.dilate(link_mask, kernel, iterations=1)

                contours, _ = cv2.findContours(dilated, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                verified_count = 0

                for cnt in contours:
                    if verified_count >= 6:
                        break

                    bx, by, bw, bh = cv2.boundingRect(cnt)
                    if 25 <= bw <= 180 and 8 <= bh <= 32:
                        aspect_ratio = float(bw) / float(bh)
                        if 1.8 <= aspect_ratio <= 7.0:
                            abs_x = min_x + bx
                            abs_y = min_y + by
                            center_x = abs_x + bw // 2
                            center_y = abs_y + bh // 2

                            # Strict OCR verification: candidate MUST contain "read", "see", "show" and "more"
                            is_verified = False
                            if self._tesseract_available:
                                try:
                                    import pytesseract
                                    crop_pad_x = max(0, abs_x - 30)
                                    crop_pad_y = max(0, abs_y - 4)
                                    crop_w = min(img_w, abs_x + bw + 15)
                                    crop_h = min(img_h, abs_y + bh + 4)
                                    crop_img = image.crop((crop_pad_x, crop_pad_y, crop_w, crop_h))
                                    txt = pytesseract.image_to_string(crop_img, config="--psm 7", timeout=0.8).lower()
                                    if any(w in txt for w in ["read", "see", "show", "view"]) and "more" in txt:
                                        is_verified = True
                                    elif "readmore" in txt or "seemore" in txt:
                                        is_verified = True
                                except Exception:
                                    pass

                            if is_verified:
                                cx = off_x + center_x
                                cy = off_y + center_y
                                if not self._is_recently_clicked(cx, cy):
                                    candidates.append((cx, cy))
                                    verified_count += 1

        except Exception as e:
            logger.debug(f"Color-based Read More search error: {e}")

        unique_points: List[Tuple[int, int]] = []
        for pt in candidates:
            if not any(abs(pt[0] - up[0]) < 25 and abs(pt[1] - up[1]) < 25 for up in unique_points):
                unique_points.append(pt)

        return unique_points

    def expand_visible_read_more(
        self,
        image: Image.Image,
        screen_offset: Tuple[int, int] = (0, 0),
        window_rect: Optional[Tuple[int, int, int, int]] = None,
        max_clicks: int = 6
    ) -> int:
        """
        Detects verified '... Read more' buttons and dispatches synthetic left-clicks.
        Returns the number of buttons successfully clicked.
        """
        coords = self.find_read_more_coordinates(image, screen_offset, window_rect=window_rect)
        if not coords:
            return 0

        if sys.platform != "win32":
            logger.info(f"Simulated clicking {len(coords)} 'Read more' button(s)")
            return len(coords)

        user32 = ctypes.windll.user32
        user32.mouse_event.argtypes = [
            ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_int, ctypes.c_size_t
        ]

        clicked = 0
        limit = min(len(coords), max_clicks)

        for cx, cy in coords[:limit]:
            try:
                # 1. Position cursor at the center of "Read more"
                user32.SetCursorPos(cx, cy)
                time.sleep(0.02)

                # 2. Left Button Down (0x0002) and Up (0x0004)
                user32.mouse_event(0x0002, 0, 0, 0, 0)
                time.sleep(0.02)
                user32.mouse_event(0x0004, 0, 0, 0, 0)
                self._mark_clicked(cx, cy)
                clicked += 1
                logger.info(f"✨ Clicked verified '... Read more' button at ({cx}, {cy})")
                time.sleep(0.06)

            except Exception as e:
                logger.warning(f"Failed clicking 'Read more' at ({cx}, {cy}): {e}")

        return clicked
