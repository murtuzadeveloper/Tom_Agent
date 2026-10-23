"""
Capture Configuration and Live Preview View.
Configures Mode A, Mode B, and Mode C parameters, with interactive region selection and visual feedback.
"""

from typing import Optional, Tuple
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QRadioButton, QButtonGroup, QSpinBox, QDoubleSpinBox,
    QFrame, QLineEdit, QGroupBox, QSizePolicy, QCheckBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap, QImage
from config import CONFIG
from app.utils.image_utils import pil_to_qpixmap
from app.utils.logger import logger

class CaptureView(QWidget):
    """View to select capture modes, configure intervals, and monitor live screen thumbnails."""

    mode_changed = Signal(str)          # 'A', 'B', 'C'
    region_selection_requested = Signal()
    config_updated = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.selected_region: Optional[Tuple[int, int, int, int]] = None
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(20)

        # 1. Mode Selection Group
        mode_box = QGroupBox("1. SELECT SCREEN CAPTURE MODE")
        mode_box.setStyleSheet("""
            QGroupBox {
                color: #F8FAFC;
                font-size: 13px;
                font-weight: bold;
                border: 1px solid #2D324D;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
                background-color: #161824;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 5px;
                color: #818CF8;
            }
        """)
        mode_layout = QVBoxLayout(mode_box)
        mode_layout.setSpacing(12)

        self.btn_group = QButtonGroup(self)

        # Mode A
        self.radio_mode_a = QRadioButton("Mode A: Current Screen (Primary Display / Active Window)")
        self.radio_mode_a.setChecked(True)
        self.radio_mode_a.setStyleSheet("color: #E2E8F0; font-size: 13px; padding: 4px;")
        self.btn_group.addButton(self.radio_mode_a, 1)
        mode_layout.addWidget(self.radio_mode_a)

        desc_a = QLabel("Inspects the entire display or active foreground window. Automatically checks for visual changes before triggering OCR.")
        desc_a.setStyleSheet("color: #94A3B8; font-size: 11px; margin-left: 24px;")
        mode_layout.addWidget(desc_a)

        # Mode B
        self.radio_mode_b = QRadioButton("Mode B: Selected Screen Region (Crop Area)")
        self.radio_mode_b.setStyleSheet("color: #E2E8F0; font-size: 13px; padding: 4px;")
        self.btn_group.addButton(self.radio_mode_b, 2)
        mode_layout.addWidget(self.radio_mode_b)

        mode_b_row = QHBoxLayout()
        mode_b_row.setContentsMargins(24, 0, 0, 0)
        self.btn_pick_region = QPushButton("⛶ Draw Screen Rectangle")
        self.btn_pick_region.setStyleSheet("""
            QPushButton {
                background-color: #4F46E5;
                color: white;
                font-weight: 600;
                padding: 6px 14px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover { background-color: #4338CA; }
        """)
        self.btn_pick_region.clicked.connect(self.region_selection_requested.emit)
        mode_b_row.addWidget(self.btn_pick_region)

        self.lbl_region_coords = QLabel("No region selected (Full screen default)")
        self.lbl_region_coords.setStyleSheet("color: #CBD5E1; font-size: 12px; font-style: italic;")
        mode_b_row.addWidget(self.lbl_region_coords)
        mode_b_row.addStretch()
        mode_layout.addLayout(mode_b_row)

        # Mode C
        self.radio_mode_c = QRadioButton("Mode C: Controlled Webpage Scrolling (Playwright / Manual)")
        self.radio_mode_c.setStyleSheet("color: #E2E8F0; font-size: 13px; padding: 4px;")
        self.btn_group.addButton(self.radio_mode_c, 3)
        mode_layout.addWidget(self.radio_mode_c)

        mode_c_row = QHBoxLayout()
        mode_c_row.setContentsMargins(24, 0, 0, 0)
        self.txt_browser_url = QLineEdit()
        self.txt_browser_url.setPlaceholderText("https://example.com/team-or-directory")
        self.txt_browser_url.setStyleSheet("""
            QLineEdit {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
                font-size: 12px;
            }
        """)
        mode_c_row.addWidget(self.txt_browser_url)
        mode_layout.addLayout(mode_c_row)

        self.btn_group.idClicked.connect(self._on_mode_radio_changed)
        main_layout.addWidget(mode_box)

        # 2. Capture Tuning Parameters & Live Thumbnail Preview
        bottom_row = QHBoxLayout()
        bottom_row.setSpacing(16)

        # Parameters Frame
        params_box = QGroupBox("2. PERFORMANCE & DETECTION TUNING")
        params_box.setStyleSheet(mode_box.styleSheet())
        params_layout = QGridLayout(params_box)
        params_layout.setContentsMargins(16, 16, 16, 16)
        params_layout.setSpacing(12)

        # Interval
        params_layout.addWidget(QLabel("Capture Interval (seconds):"), 0, 0)
        self.spin_interval = QDoubleSpinBox()
        self.spin_interval.setRange(1.0, 30.0)
        self.spin_interval.setSingleStep(0.5)
        self.spin_interval.setValue(CONFIG.capture.capture_interval_seconds)
        self.spin_interval.setStyleSheet("background-color: #1E293B; color: white; padding: 4px; border: 1px solid #334155;")
        self.spin_interval.valueChanged.connect(self._on_params_changed)
        params_layout.addWidget(self.spin_interval, 0, 1)

        # Change Threshold
        params_layout.addWidget(QLabel("Change Detection Threshold (%):"), 1, 0)
        self.spin_threshold = QDoubleSpinBox()
        self.spin_threshold.setRange(0.01, 50.0)
        self.spin_threshold.setDecimals(2)
        self.spin_threshold.setSingleStep(0.05)
        self.spin_threshold.setValue(CONFIG.capture.change_threshold_percent)
        self.spin_threshold.setStyleSheet(self.spin_interval.styleSheet())
        self.spin_threshold.valueChanged.connect(self._on_params_changed)
        params_layout.addWidget(self.spin_threshold, 1, 1)

        # Max Captures
        params_layout.addWidget(QLabel("Max Captures per Session:"), 2, 0)
        self.spin_max_captures = QSpinBox()
        self.spin_max_captures.setRange(5, 500000)
        self.spin_max_captures.setValue(CONFIG.capture.max_captures_per_session)
        self.spin_max_captures.setStyleSheet(self.spin_interval.styleSheet())
        self.spin_max_captures.valueChanged.connect(self._on_params_changed)
        params_layout.addWidget(self.spin_max_captures, 2, 1)

        # Pause after unchanged
        params_layout.addWidget(QLabel("Pause After N Unchanged Frames:"), 3, 0)
        self.spin_pause_unchanged = QSpinBox()
        self.spin_pause_unchanged.setRange(2, 50)
        self.spin_pause_unchanged.setValue(CONFIG.capture.pause_after_unchanged_frames)
        self.spin_pause_unchanged.setStyleSheet(self.spin_interval.styleSheet())
        self.spin_pause_unchanged.valueChanged.connect(self._on_params_changed)
        params_layout.addWidget(self.spin_pause_unchanged, 3, 1)

        # Auto-Scroll Enable Checkbox
        self.chk_auto_scroll = QCheckBox("Automatically Scroll Down After Each Capture")
        self.chk_auto_scroll.setChecked(CONFIG.capture.auto_scroll_enabled)
        self.chk_auto_scroll.setStyleSheet("color: #38BDF8; font-weight: bold; font-size: 12px; margin-top: 6px;")
        self.chk_auto_scroll.toggled.connect(self._on_params_changed)
        params_layout.addWidget(self.chk_auto_scroll, 4, 0, 1, 2)

        # Scroll Wheel Steps
        params_layout.addWidget(QLabel("Scroll Amount (Wheel Steps):"), 5, 0)
        self.spin_scroll_steps = QSpinBox()
        self.spin_scroll_steps.setRange(1, 20)
        self.spin_scroll_steps.setValue(CONFIG.capture.auto_scroll_wheel_steps)
        self.spin_scroll_steps.setStyleSheet(self.spin_interval.styleSheet())
        self.spin_scroll_steps.valueChanged.connect(self._on_params_changed)
        params_layout.addWidget(self.spin_scroll_steps, 5, 1)

        # Auto-Expand "Read more" (WhatsApp) Checkbox
        self.chk_auto_expand = QCheckBox("Automatically Click '... Read more' on WhatsApp Messages")
        self.chk_auto_expand.setChecked(getattr(CONFIG.capture, "auto_expand_read_more", True))
        self.chk_auto_expand.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px; margin-top: 4px;")
        self.chk_auto_expand.toggled.connect(self._on_params_changed)
        params_layout.addWidget(self.chk_auto_expand, 6, 0, 1, 2)

        bottom_row.addWidget(params_box, stretch=1)

        # Live Thumbnail Preview
        preview_box = QGroupBox("LIVE CAPTURE PREVIEW")
        preview_box.setStyleSheet(mode_box.styleSheet())
        prev_layout = QVBoxLayout(preview_box)
        prev_layout.setContentsMargins(12, 12, 12, 12)

        self.lbl_preview = QLabel("Capture preview will appear here when active.")
        self.lbl_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lbl_preview.setStyleSheet("""
            background-color: #0F111A;
            color: #64748B;
            border: 1px dashed #2D324D;
            border-radius: 6px;
            font-size: 12px;
        """)
        self.lbl_preview.setMinimumSize(280, 160)
        prev_layout.addWidget(self.lbl_preview)

        self.lbl_preview_info = QLabel("Target: None | Change: 0.0%")
        self.lbl_preview_info.setStyleSheet("color: #94A3B8; font-size: 11px;")
        prev_layout.addWidget(self.lbl_preview_info)

        bottom_row.addWidget(preview_box, stretch=1)
        main_layout.addLayout(bottom_row)
        main_layout.addStretch()

    def _on_mode_radio_changed(self, button_id: int):
        mode_map = {1: "A", 2: "B", 3: "C"}
        mode = mode_map.get(button_id, "A")
        self.mode_changed.emit(mode)

    def get_selected_mode(self) -> str:
        if self.radio_mode_b.isChecked():
            return "B"
        elif self.radio_mode_c.isChecked():
            return "C"
        return "A"

    def set_selected_region(self, bbox: Tuple[int, int, int, int]):
        self.selected_region = bbox
        left, top, w, h = bbox
        self.lbl_region_coords.setText(f"Coordinates: X={left}, Y={top}, W={w}, H={h} px")
        self.radio_mode_b.setChecked(True)
        self.mode_changed.emit("B")

    def _on_params_changed(self):
        CONFIG.capture.capture_interval_seconds = self.spin_interval.value()
        CONFIG.capture.change_threshold_percent = self.spin_threshold.value()
        CONFIG.capture.max_captures_per_session = self.spin_max_captures.value()
        CONFIG.capture.pause_after_unchanged_frames = self.spin_pause_unchanged.value()
        CONFIG.capture.auto_scroll_enabled = self.chk_auto_scroll.isChecked()
        CONFIG.capture.auto_scroll_wheel_steps = self.spin_scroll_steps.value()
        CONFIG.capture.auto_expand_read_more = self.chk_auto_expand.isChecked()
        self.config_updated.emit()

    def is_auto_scroll_enabled(self) -> bool:
        """Returns True if automated scrolling is toggled on."""
        return self.chk_auto_scroll.isChecked()

    def is_auto_expand_enabled(self) -> bool:
        """Returns True if auto-expanding 'Read more' is toggled on."""
        return self.chk_auto_expand.isChecked()

    def update_live_preview(self, pil_image, window_info: dict, diff_percent: float):
        """Displays scaled thumbnail of captured frame."""
        try:
            pixmap = pil_to_qpixmap(pil_image)
            scaled = pixmap.scaled(
                self.lbl_preview.width() - 8,
                self.lbl_preview.height() - 8,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation
            )
            self.lbl_preview.setPixmap(scaled)
            proc = window_info.get("process_name", "App")
            self.lbl_preview_info.setText(f"Target: {proc} | Diff: {diff_percent:.1f}%")
        except Exception as e:
            logger.debug(f"Preview update error: {e}")
