"""
Dashboard view with real-time operational metrics, model status, and main controls.
"""

import os
import subprocess
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QPushButton, QFrame, QScrollArea, QMessageBox, QCheckBox, QSizePolicy
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont, QColor
from config import CONFIG
from app.services.contact_validator import ContactRecord
from app.utils.logger import logger

class MetricCard(QFrame):
    """Custom styled metric display card with word-wrapping and anti-clipping geometry."""
    def __init__(self, title: str, initial_value: str = "0", icon_str: str = "📊", accent_color: str = "#6366F1", parent=None):
        super().__init__(parent)
        self.setObjectName("MetricCard")
        self.setStyleSheet(f"""
            QFrame#MetricCard {{
                background-color: #1A1C29;
                border: 1px solid #2D324D;
                border-radius: 8px;
            }}
            QFrame#MetricCard:hover {{
                border-color: {accent_color};
            }}
        """)
        self.setMinimumHeight(96)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Preferred)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(4)

        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(6)

        icon_lbl = QLabel(icon_str)
        icon_lbl.setStyleSheet("font-size: 15px; background: transparent; border: none;")
        icon_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        
        self.title_lbl = QLabel(title)
        self.title_lbl.setStyleSheet("color: #94A3B8; font-size: 11px; font-weight: 600; background: transparent; border: none;")
        self.title_lbl.setWordWrap(True)
        self.title_lbl.setAlignment(Qt.AlignVCenter | Qt.AlignLeft)
        
        top_row.addWidget(icon_lbl, 0, Qt.AlignVCenter)
        top_row.addWidget(self.title_lbl, 1)
        layout.addLayout(top_row)

        self.value_lbl = QLabel(initial_value)
        self.value_lbl.setStyleSheet("color: #F8FAFC; font-size: 24px; font-weight: 800; background: transparent; border: none; padding: 0; margin: 0;")
        self.value_lbl.setMinimumHeight(32)
        self.value_lbl.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        layout.addWidget(self.value_lbl)

    def set_value(self, val):
        self.value_lbl.setText(str(val))

class DashboardView(QWidget):
    """Main operational dashboard for murtuzadeveloper Smart Leads."""

    # UI Action Signals
    start_capture_requested = Signal()
    pause_capture_requested = Signal()
    resume_capture_requested = Signal()
    stop_capture_requested = Signal()
    capture_current_screen_requested = Signal()
    select_region_requested = Signal()
    test_lm_studio_requested = Signal()
    auto_scroll_toggled = Signal(bool)
    auto_expand_toggled = Signal(bool)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()

    def init_ui(self):
        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setStyleSheet("QScrollArea { background-color: transparent; border: none; }")

        container = QWidget()
        container.setStyleSheet("background-color: transparent;")
        main_layout = QVBoxLayout(container)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(16)

        # 1. Header Banner
        header_frame = QFrame()
        header_frame.setObjectName("HeaderBanner")
        header_frame.setStyleSheet("""
            QFrame#HeaderBanner {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #1E1B4B, stop:1 #141625);
                border: 1px solid #4338CA;
                border-radius: 10px;
            }
        """)
        header_layout = QHBoxLayout(header_frame)
        header_layout.setContentsMargins(18, 14, 18, 14)

        info_box = QVBoxLayout()
        info_box.setSpacing(4)
        title = QLabel(CONFIG.app_name)
        title.setStyleSheet("color: #FFFFFF; font-size: 22px; font-weight: 800; background: transparent; border: none; padding: 2px 0;")
        title.setMinimumHeight(32)
        subtitle = QLabel(CONFIG.app_subtitle)
        subtitle.setStyleSheet("color: #A5B4FC; font-size: 13px; background: transparent; border: none; padding: 2px 0;")
        subtitle.setMinimumHeight(20)
        info_box.addWidget(title)
        info_box.addWidget(subtitle)
        header_layout.addLayout(info_box)

        header_layout.addStretch()

        # Status Badges in Header
        status_box = QHBoxLayout()
        status_box.setSpacing(12)

        # Capture Status Indicator
        self.capture_badge = QLabel("● IDLE")
        self.capture_badge.setAlignment(Qt.AlignCenter)
        self.capture_badge.setStyleSheet("""
            background-color: #1E293B;
            color: #94A3B8;
            font-size: 12px;
            font-weight: bold;
            padding: 6px 14px;
            border: 1px solid #334155;
            border-radius: 12px;
        """)
        status_box.addWidget(self.capture_badge)

        # LM Studio Status Indicator
        self.lm_badge = QLabel("● LM Studio: Checking...")
        self.lm_badge.setAlignment(Qt.AlignCenter)
        self.lm_badge.setStyleSheet("""
            background-color: #1E293B;
            color: #CBD5E1;
            font-size: 12px;
            font-weight: bold;
            padding: 6px 14px;
            border: 1px solid #334155;
            border-radius: 12px;
        """)
        status_box.addWidget(self.lm_badge)

        header_layout.addLayout(status_box)
        main_layout.addWidget(header_frame)

        # 2. Controls Action Toolbar (2 Clean Non-Clipping Rows)
        controls_frame = QFrame()
        controls_frame.setObjectName("ControlsToolbar")
        controls_frame.setStyleSheet("""
            QFrame#ControlsToolbar {
                background-color: #161824;
                border: 1px solid #24273A;
                border-radius: 8px;
            }
        """)
        controls_layout = QVBoxLayout(controls_frame)
        controls_layout.setContentsMargins(14, 12, 14, 12)
        controls_layout.setSpacing(10)

        # Row 1: Primary Capture & Control Buttons + File Outputs
        row1_layout = QHBoxLayout()
        row1_layout.setSpacing(8)

        # Start Button
        self.btn_start = QPushButton("▶ Start Capture")
        self.btn_start.setToolTip("Starts continuous screen capture with auto-scrolling and contact extraction.")
        self.btn_start.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 14px;
                border-radius: 6px;
                border: none;
                min-width: 110px;
            }
            QPushButton:hover { background-color: #059669; }
            QPushButton:disabled { background-color: #064E3B; color: #6EE7B7; }
        """)
        self.btn_start.clicked.connect(self.start_capture_requested.emit)
        row1_layout.addWidget(self.btn_start)

        # Pause / Resume Button
        self.btn_pause = QPushButton("⏸ Pause")
        self.btn_pause.setEnabled(False)
        self.btn_pause.setStyleSheet("""
            QPushButton {
                background-color: #F59E0B;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 12px;
                border-radius: 6px;
                border: none;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #D97706; }
            QPushButton:disabled { background-color: #451A03; color: #FCD34D; }
        """)
        self.btn_pause.clicked.connect(self._toggle_pause)
        row1_layout.addWidget(self.btn_pause)

        # Stop Button
        self.btn_stop = QPushButton("⏹ Stop")
        self.btn_stop.setEnabled(False)
        self.btn_stop.setStyleSheet("""
            QPushButton {
                background-color: #EF4444;
                color: #FFFFFF;
                font-weight: bold;
                font-size: 13px;
                padding: 8px 12px;
                border-radius: 6px;
                border: none;
                min-width: 70px;
            }
            QPushButton:hover { background-color: #DC2626; }
            QPushButton:disabled { background-color: #450A0A; color: #FCA5A5; }
        """)
        self.btn_stop.clicked.connect(self.stop_capture_requested.emit)
        row1_layout.addWidget(self.btn_stop)

        # Capture Current Screen (Instant shot)
        self.btn_snap = QPushButton("📸 Capture Screen")
        self.btn_snap.setToolTip("Capture the current active screen immediately.")
        self.btn_snap.setStyleSheet("""
            QPushButton {
                background-color: #3B82F6;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 12px;
                border-radius: 6px;
                border: none;
                min-width: 110px;
            }
            QPushButton:hover { background-color: #2563EB; }
        """)
        self.btn_snap.clicked.connect(self.capture_current_screen_requested.emit)
        row1_layout.addWidget(self.btn_snap)

        # Select Screen Region
        self.btn_region = QPushButton("⛶ Select Region")
        self.btn_region.setToolTip("Select a specific screen region for capture.")
        self.btn_region.setStyleSheet("""
            QPushButton {
                background-color: #6366F1;
                color: #FFFFFF;
                font-weight: 600;
                font-size: 13px;
                padding: 8px 12px;
                border-radius: 6px;
                border: none;
                min-width: 110px;
            }
            QPushButton:hover { background-color: #4F46E5; }
        """)
        self.btn_region.clicked.connect(self.select_region_requested.emit)
        row1_layout.addWidget(self.btn_region)

        row1_layout.addStretch()

        # Open CSV & Folder in Row 1 (Right Side)
        btn_open_csv = QPushButton("📄 Open CSV")
        btn_open_csv.setToolTip(f"Open output CSV file:\n{CONFIG.csv_path}")
        btn_open_csv.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #38BDF8;
                font-weight: 600;
                font-size: 12px;
                padding: 7px 12px;
                border-radius: 6px;
                border: 1px solid #0284C7;
                min-width: 85px;
            }
            QPushButton:hover { background-color: #0369A1; color: white; }
        """)
        btn_open_csv.clicked.connect(self._open_csv_file)
        row1_layout.addWidget(btn_open_csv)

        btn_open_folder = QPushButton("📁 Output Folder")
        btn_open_folder.setToolTip("Open the directory containing the exported CSV files.")
        btn_open_folder.setStyleSheet("""
            QPushButton {
                background-color: #1E293B;
                color: #94A3B8;
                font-weight: 600;
                font-size: 12px;
                padding: 7px 12px;
                border-radius: 6px;
                border: 1px solid #334155;
                min-width: 95px;
            }
            QPushButton:hover { background-color: #334155; color: white; }
        """)
        btn_open_folder.clicked.connect(self._open_output_folder)
        row1_layout.addWidget(btn_open_folder)

        controls_layout.addLayout(row1_layout)

        # Row 2: Automation Checkboxes & Diagnostics
        row2_layout = QHBoxLayout()
        row2_layout.setSpacing(10)

        # Auto-Scroll CheckBox
        self.chk_auto_scroll = QCheckBox("⚡ Auto-Scroll")
        self.chk_auto_scroll.setChecked(CONFIG.capture.auto_scroll_enabled)
        self.chk_auto_scroll.setToolTip("Automatically scrolls down active window after each capture cycle.")
        self.chk_auto_scroll.setStyleSheet("""
            QCheckBox {
                color: #38BDF8;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 12px;
                background-color: #0F172A;
                border: 1px solid #1E3A8A;
                border-radius: 6px;
            }
            QCheckBox:hover {
                background-color: #1E293B;
                border-color: #38BDF8;
            }
        """)
        self.chk_auto_scroll.toggled.connect(self._on_auto_scroll_toggled)
        row2_layout.addWidget(self.chk_auto_scroll)

        # Auto-Expand "Read more" (WhatsApp) CheckBox
        self.chk_auto_expand = QCheckBox("💬 Auto-Expand WhatsApp")
        self.chk_auto_expand.setChecked(getattr(CONFIG.capture, "auto_expand_read_more", True))
        self.chk_auto_expand.setToolTip("Automatically clicks '... Read more' on WhatsApp messages to reveal full contact details.")
        self.chk_auto_expand.setStyleSheet("""
            QCheckBox {
                color: #34D399;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 12px;
                background-color: #064E3B;
                border: 1px solid #059669;
                border-radius: 6px;
            }
            QCheckBox:hover {
                background-color: #047857;
                border-color: #34D399;
            }
        """)
        self.chk_auto_expand.toggled.connect(self._on_auto_expand_toggled)
        row2_layout.addWidget(self.chk_auto_expand)

        row2_layout.addStretch()

        # Test LM Studio Button
        self.btn_test_lm = QPushButton("🔌 Test LM Studio")
        self.btn_test_lm.setToolTip("Test API connectivity and verify active model in LM Studio.")
        self.btn_test_lm.setStyleSheet("""
            QPushButton {
                background-color: #24273A;
                color: #E2E8F0;
                font-weight: 600;
                font-size: 12px;
                padding: 6px 14px;
                border-radius: 6px;
                border: 1px solid #3B4261;
            }
            QPushButton:hover { background-color: #2D324D; border-color: #6366F1; }
        """)
        self.btn_test_lm.clicked.connect(self.test_lm_studio_requested.emit)
        row2_layout.addWidget(self.btn_test_lm)

        controls_layout.addLayout(row2_layout)
        main_layout.addWidget(controls_frame)

        # 3. Live Metrics Grid (10 Live Metric Cards - Clean Anti-Clipping Geometry)
        grid_layout = QGridLayout()
        grid_layout.setSpacing(10)

        self.card_captures = MetricCard("Captures", "0", "🖼️", "#3B82F6")
        self.card_contacts = MetricCard("Contacts", "0", "👥", "#10B981")
        self.card_emails = MetricCard("Emails", "0", "✉️", "#8B5CF6")
        self.card_phones = MetricCard("Phones", "0", "📞", "#06B6D4")
        self.card_links = MetricCard("Links / URLs", "0", "🔗", "#38BDF8")
        self.card_orgs = MetricCard("Organizations", "0", "🏢", "#F59E0B")

        self.card_titles = MetricCard("Job Titles", "0", "💼", "#EC4899")
        self.card_duplicates = MetricCard("Duplicates", "0", "🔁", "#64748B")
        self.card_approved = MetricCard("Approved", "0", "✅", "#10B981")
        self.card_csv_status = MetricCard("CSV Status", "Ready", "💾", "#0284C7")
        self.card_errors = MetricCard("Errors", "0", "⚠️", "#EF4444")

        # Row 1
        grid_layout.addWidget(self.card_captures, 0, 0)
        grid_layout.addWidget(self.card_contacts, 0, 1)
        grid_layout.addWidget(self.card_emails, 0, 2)
        grid_layout.addWidget(self.card_phones, 0, 3)
        grid_layout.addWidget(self.card_links, 0, 4)
        grid_layout.addWidget(self.card_orgs, 0, 5)

        # Row 2
        grid_layout.addWidget(self.card_titles, 1, 0)
        grid_layout.addWidget(self.card_duplicates, 1, 1)
        grid_layout.addWidget(self.card_approved, 1, 2)
        grid_layout.addWidget(self.card_csv_status, 1, 3)
        grid_layout.addWidget(self.card_errors, 1, 4)

        main_layout.addLayout(grid_layout)

        # 4. Last Saved Record Card
        self.last_record_frame = QFrame()
        self.last_record_frame.setObjectName("LastRecordCard")
        self.last_record_frame.setStyleSheet("""
            QFrame#LastRecordCard {
                background-color: #1A1C29;
                border: 1px solid #2D324D;
                border-radius: 8px;
            }
        """)
        lr_layout = QVBoxLayout(self.last_record_frame)
        lr_layout.setContentsMargins(16, 12, 16, 12)
        lr_layout.setSpacing(6)

        lr_title = QLabel("LATEST EXTRACTED CONTACT")
        lr_title.setStyleSheet("color: #818CF8; font-size: 11px; font-weight: bold; background: transparent; border: none;")
        lr_layout.addWidget(lr_title)

        self.lr_content = QLabel("No contacts extracted yet in this session. Click 'Start Auto-Capture' or 'Capture Now' to begin.")
        self.lr_content.setStyleSheet("color: #CBD5E1; font-size: 13px; background: transparent; border: none;")
        self.lr_content.setWordWrap(True)
        lr_layout.addWidget(self.lr_content)

        main_layout.addWidget(self.last_record_frame)
        main_layout.addStretch()

        scroll_area.setWidget(container)
        root_layout.addWidget(scroll_area)

    def update_metrics(self, stats: dict):
        """Updates metric cards with true numbers from repository/workers."""
        if "total_records" in stats:
            self.card_contacts.set_value(stats["total_records"])
        if "total_emails" in stats:
            self.card_emails.set_value(stats["total_emails"])
        if "total_phones" in stats:
            self.card_phones.set_value(stats["total_phones"])
        if "total_links" in stats:
            self.card_links.set_value(stats["total_links"])
        if "total_orgs" in stats:
            self.card_orgs.set_value(stats["total_orgs"])
        if "total_titles" in stats:
            self.card_titles.set_value(stats["total_titles"])
        if "total_approved" in stats:
            self.card_approved.set_value(stats["total_approved"])
        if "duplicates_skipped" in stats:
            self.card_duplicates.set_value(stats["duplicates_skipped"])

    def set_captures_count(self, count: int):
        self.card_captures.set_value(count)

    def set_last_saved_record(self, record: ContactRecord):
        """Displays formatted snippet of the latest contact extracted."""
        name = record.person_or_profile_name or "Unknown Name"
        org = record.organization_name or "N/A"
        email = record.business_email or "No Email"
        phone = record.normalized_phone or record.contact_number or "No Phone"
        src = record.source_application or "Screen"
        link_str = f" | 🔗 {record.website_url or record.social_profile_url}" if (record.website_url or record.social_profile_url) else ""
        self.lr_content.setText(f"👤 {name} | 🏢 {org} | ✉️ {email} | 📞 {phone}{link_str} | 🖥️ {src}")

    def update_capture_state(self, state: str):
        """Updates capture status badge and button enabled states."""
        state_upper = state.upper()
        if "ACTIVE" in state_upper:
            self.capture_badge.setText("● CAPTURING")
            self.capture_badge.setStyleSheet("background-color: #065F46; color: #34D399; font-size: 12px; font-weight: bold; padding: 6px 14px; border: 1px solid #059669; border-radius: 12px;")
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_pause.setText("⏸ Pause")
            self.btn_stop.setEnabled(True)
        elif "PAUSE" in state_upper:
            self.capture_badge.setText("● PAUSED")
            self.capture_badge.setStyleSheet("background-color: #78350F; color: #FBBF24; font-size: 12px; font-weight: bold; padding: 6px 14px; border: 1px solid #D97706; border-radius: 12px;")
            self.btn_start.setEnabled(False)
            self.btn_pause.setEnabled(True)
            self.btn_pause.setText("▶ Resume")
            self.btn_stop.setEnabled(True)
        else:
            self.capture_badge.setText("● IDLE")
            self.capture_badge.setStyleSheet("background-color: #1E293B; color: #94A3B8; font-size: 12px; font-weight: bold; padding: 6px 14px; border: 1px solid #334155; border-radius: 12px;")
            self.btn_start.setEnabled(True)
            self.btn_pause.setEnabled(False)
            self.btn_pause.setText("⏸ Pause")
            self.btn_stop.setEnabled(False)

    def update_lm_studio_badge(self, connected: bool, message: str, model_id: str = ""):
        """Updates LM Studio status badge."""
        if connected:
            self.lm_badge.setText(f"● LM Studio: {model_id or 'Online'}")
            self.lm_badge.setStyleSheet("background-color: #064E3B; color: #6EE7B7; font-size: 12px; font-weight: bold; padding: 6px 14px; border: 1px solid #059669; border-radius: 12px;")
        else:
            self.lm_badge.setText("● LM Studio: Offline")
            self.lm_badge.setStyleSheet("background-color: #450A0A; color: #FCA5A5; font-size: 12px; font-weight: bold; padding: 6px 14px; border: 1px solid #DC2626; border-radius: 12px;")

    def is_auto_scroll_enabled(self) -> bool:
        """Returns True if auto-scrolling is currently enabled in the checkbox."""
        return self.chk_auto_scroll.isChecked()

    def set_auto_scroll_enabled(self, enabled: bool):
        """Updates the checkbox checked state without emitting recursive signals."""
        self.chk_auto_scroll.blockSignals(True)
        self.chk_auto_scroll.setChecked(enabled)
        self.chk_auto_scroll.blockSignals(False)

    def _on_auto_scroll_toggled(self, is_on: bool):
        CONFIG.capture.auto_scroll_enabled = is_on
        self.auto_scroll_toggled.emit(is_on)
        logger.info(f"Dashboard auto-scroll toggled: {'ENABLED' if is_on else 'DISABLED'}")

    def is_auto_expand_enabled(self) -> bool:
        """Returns True if auto-expanding 'Read more' is currently enabled."""
        return self.chk_auto_expand.isChecked()

    def set_auto_expand_enabled(self, enabled: bool):
        """Updates the auto-expand checkbox without recursive signals."""
        self.chk_auto_expand.blockSignals(True)
        self.chk_auto_expand.setChecked(enabled)
        self.chk_auto_expand.blockSignals(False)

    def _on_auto_expand_toggled(self, is_on: bool):
        CONFIG.capture.auto_expand_read_more = is_on
        self.auto_expand_toggled.emit(is_on)
        logger.info(f"Dashboard auto-expand Read more toggled: {'ENABLED' if is_on else 'DISABLED'}")

    def show_countdown(self, seconds: int):
        """Displays countdown indicator prompting user to switch to target window."""
        if seconds > 0:
            self.capture_badge.setText(f"⏳ Switch App: {seconds}s")
            self.capture_badge.setStyleSheet("""
                background-color: #1E3A8A;
                color: #93C5FD;
                font-size: 12px;
                font-weight: bold;
                padding: 6px 14px;
                border: 1px solid #3B82F6;
                border-radius: 12px;
            """)
        else:
            self.update_capture_state("ACTIVE")

    def _toggle_pause(self):
        if self.btn_pause.text().startswith("⏸"):
            self.pause_capture_requested.emit()
        else:
            self.resume_capture_requested.emit()

    def _open_csv_file(self):
        path = Path(CONFIG.csv_path)
        if not path.exists():
            QMessageBox.information(self, "CSV Not Found", f"CSV file does not exist yet at:\n{CONFIG.csv_path}")
            return
        try:
            os.startfile(str(path))
        except Exception as e:
            QMessageBox.warning(self, "Open Error", f"Could not launch CSV viewer: {e}")

    def _open_output_folder(self):
        folder = Path(CONFIG.csv_path).parent
        try:
            os.startfile(str(folder))
        except Exception as e:
            QMessageBox.warning(self, "Open Error", f"Could not open directory: {e}")
