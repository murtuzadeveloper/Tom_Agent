"""
Main Application Window for murtuzadeveloper Smart Leads.
Assembles dark-themed layout, navigation sidebar, global status ribbon, and background workers.
"""

from typing import Optional, Tuple
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget,
    QPushButton, QLabel, QFrame, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QTimer, Slot
from PySide6.QtGui import QIcon, QFont, QColor
from config import CONFIG
from app.ui.dashboard import DashboardView
from app.ui.capture_view import CaptureView
from app.ui.results_view import ResultsView
from app.ui.database_view import DatabaseView
from app.ui.settings_view import SettingsView
from app.ui.logs_view import LogsView
from app.ui.region_selector import RegionSelectorWidget
from app.workers.capture_worker import CaptureWorker
from app.workers.extraction_worker import ExtractionWorker
from app.database.repository import ContactRepository
from app.services.csv_service import CSVService
from app.services.lm_studio_client import LMStudioClient
from app.utils.logger import logger

class MainWindow(QMainWindow):
    """Main window with sidebar navigation and coordinated capture/extraction workers."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"{CONFIG.app_name} - {CONFIG.app_subtitle}")
        self.resize(1280, 820)
        self.setMinimumSize(1100, 700)

        # Core Services
        self.repo = ContactRepository(CONFIG.db_path)
        self.csv_service = CSVService(CONFIG.csv_path, repo=self.repo)
        self.lm_client = LMStudioClient()

        # Clean any historical noise or invalid records from SQLite database on launch
        try:
            self.repo.clean_and_repair_stored_contacts()
        except Exception as e:
            logger.debug(f"Startup DB repair skipped: {e}")

        # Background Workers
        self.capture_worker: Optional[CaptureWorker] = None
        self.extraction_worker: Optional[ExtractionWorker] = None

        # Interactive Region Selector
        self.region_selector = RegionSelectorWidget()
        self.region_selector.region_selected.connect(self._on_region_selected)

        self.init_ui()
        self._start_extraction_worker()

        # Check LM Studio connection after window shows
        QTimer.singleShot(1000, self._check_initial_lm_connection)

    def init_ui(self):
        # Global Dark Theme Stylesheet
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0F1017;
                color: #F8FAFC;
                font-family: 'Segoe UI', -apple-system, BlinkMacSystemFont, Roboto, sans-serif;
            }
            QWidget {
                color: #F8FAFC;
            }
            QScrollBar:vertical {
                border: none;
                background: #12131C;
                width: 8px;
                margin: 0;
            }
            QScrollBar::handle:vertical {
                background: #2D324D;
                min-height: 20px;
                border-radius: 4px;
            }
            QScrollBar::handle:vertical:hover {
                background: #4F46E5;
            }
        """)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        root_layout = QHBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Left Navigation Sidebar
        sidebar = QFrame()
        sidebar.setObjectName("AppSidebar")
        sidebar.setFixedWidth(240)
        sidebar.setStyleSheet("""
            QFrame#AppSidebar {
                background-color: #12131C;
                border-right: 1px solid #1E2030;
            }
        """)
        sb_layout = QVBoxLayout(sidebar)
        sb_layout.setContentsMargins(16, 20, 16, 20)
        sb_layout.setSpacing(8)

        # Brand Logo & Title
        brand_box = QVBoxLayout()
        lbl_brand = QLabel("murtuzadeveloper")
        lbl_brand.setStyleSheet("color: #818CF8; font-size: 11px; font-weight: bold; text-transform: uppercase; letter-spacing: 1px;")
        lbl_name = QLabel("Smart Leads")
        lbl_name.setStyleSheet("color: #FFFFFF; font-size: 18px; font-weight: 800;")
        lbl_sub = QLabel("AI Screen Intelligence")
        lbl_sub.setStyleSheet("color: #64748B; font-size: 11px;")

        brand_box.addWidget(lbl_brand)
        brand_box.addWidget(lbl_name)
        brand_box.addWidget(lbl_sub)
        sb_layout.addLayout(brand_box)
        sb_layout.addSpacing(20)

        # Navigation Buttons
        self.nav_buttons = []
        nav_items = [
            ("📊  Dashboard", 0),
            ("📷  Capture Mode", 1),
            ("⚡  Live Results", 2),
            ("🗄️  Contact Database", 3),
            ("📁  CSV Export", 3),
            ("⚙️  Settings", 4),
            ("📜  Activity Log", 5)
        ]

        for label, page_idx in nav_items:
            btn = QPushButton(label)
            btn.setCheckable(True)
            btn.setStyleSheet("""
                QPushButton {
                    background-color: transparent;
                    color: #94A3B8;
                    text-align: left;
                    font-size: 13px;
                    font-weight: 600;
                    padding: 10px 14px;
                    border-radius: 6px;
                    border: none;
                }
                QPushButton:hover {
                    background-color: #1A1C29;
                    color: #F8FAFC;
                }
                QPushButton:checked {
                    background-color: #1E1B4B;
                    color: #A5B4FC;
                    border-left: 3px solid #6366F1;
                }
            """)
            btn.clicked.connect(lambda checked, idx=page_idx, b=btn: self._on_nav_clicked(idx, b))
            sb_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.nav_buttons[0].setChecked(True)

        sb_layout.addStretch()

        # Target Hardware Specs Footer Card
        hw_card = QFrame()
        hw_card.setStyleSheet("background-color: #161824; border-radius: 6px; padding: 10px; border: 1px solid #24273A;")
        hw_layout = QVBoxLayout(hw_card)
        hw_layout.setContentsMargins(6, 6, 6, 6)
        lbl_hw = QLabel("🖥️ Target System\ni7-9850H | 16GB RAM\nNVIDIA MX150 (2GB)\nLocal Gemma 4 12B")
        lbl_hw.setStyleSheet("color: #64748B; font-size: 10px; line-height: 1.3;")
        hw_layout.addWidget(lbl_hw)
        sb_layout.addWidget(hw_card)

        root_layout.addWidget(sidebar)

        # 2. Main Content Area
        content_frame = QWidget()
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(0)

        # Top Global Ribbon Bar
        top_ribbon = QFrame()
        top_ribbon.setObjectName("TopRibbon")
        top_ribbon.setFixedHeight(54)
        top_ribbon.setStyleSheet("QFrame#TopRibbon { background-color: #12131C; border-bottom: 1px solid #1E2030; }")
        ribbon_layout = QHBoxLayout(top_ribbon)
        ribbon_layout.setContentsMargins(24, 8, 24, 8)
        ribbon_layout.setSpacing(16)

        self.lbl_ribbon_status = QLabel("● Capture: IDLE")
        self.lbl_ribbon_status.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 12px;")
        ribbon_layout.addWidget(self.lbl_ribbon_status)

        self.lbl_ribbon_mode = QLabel("Mode: Screen")
        self.lbl_ribbon_mode.setStyleSheet("background-color: #1E293B; color: #CBD5E1; font-size: 11px; padding: 4px 8px; border-radius: 4px;")
        ribbon_layout.addWidget(self.lbl_ribbon_mode)

        self.lbl_ribbon_lm = QLabel("LM Studio: Checking...")
        self.lbl_ribbon_lm.setStyleSheet("color: #94A3B8; font-size: 12px;")
        ribbon_layout.addWidget(self.lbl_ribbon_lm)

        ribbon_layout.addStretch()

        # Emergency Global Stop Button (Always visible)
        self.btn_global_stop = QPushButton("🛑 Stop Capture")
        self.btn_global_stop.setEnabled(False)
        self.btn_global_stop.setStyleSheet("""
            QPushButton {
                background-color: #7F1D1D;
                color: #FCA5A5;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
                border-radius: 6px;
                border: 1px solid #991B1B;
            }
            QPushButton:hover { background-color: #991B1B; color: white; }
            QPushButton:disabled { background-color: #24273A; color: #475569; border: none; }
        """)
        self.btn_global_stop.clicked.connect(self._stop_capture)
        ribbon_layout.addWidget(self.btn_global_stop)

        content_layout.addWidget(top_ribbon)

        # 3. Stacked Pages
        self.stack = QStackedWidget()
        self.dashboard_view = DashboardView()
        self.capture_view = CaptureView()
        self.results_view = ResultsView(repo=self.repo, csv_service=self.csv_service)
        self.database_view = DatabaseView(repo=self.repo, csv_service=self.csv_service)
        self.settings_view = SettingsView()
        self.logs_view = LogsView()

        self.stack.addWidget(self.dashboard_view)    # Page 0
        self.stack.addWidget(self.capture_view)      # Page 1
        self.stack.addWidget(self.results_view)      # Page 2
        self.stack.addWidget(self.database_view)     # Page 3
        self.stack.addWidget(self.settings_view)     # Page 4
        self.stack.addWidget(self.logs_view)         # Page 5

        content_layout.addWidget(self.stack)
        root_layout.addWidget(content_frame)

        # Connect Dashboard Signals
        self.dashboard_view.start_capture_requested.connect(self._start_capture)
        self.dashboard_view.pause_capture_requested.connect(self._pause_capture)
        self.dashboard_view.resume_capture_requested.connect(self._resume_capture)
        self.dashboard_view.stop_capture_requested.connect(self._stop_capture)
        self.dashboard_view.capture_current_screen_requested.connect(self._capture_current_screen_now)
        self.dashboard_view.select_region_requested.connect(self._launch_region_selector)
        self.dashboard_view.test_lm_studio_requested.connect(self._test_lm_studio)
        self.dashboard_view.auto_scroll_toggled.connect(self._on_dashboard_auto_scroll_toggled)
        self.dashboard_view.auto_expand_toggled.connect(self._on_dashboard_auto_expand_toggled)

        # Connect Capture View Signals
        self.capture_view.region_selection_requested.connect(self._launch_region_selector)
        self.capture_view.chk_auto_scroll.toggled.connect(self._on_capture_view_auto_scroll_toggled)
        self.capture_view.chk_auto_expand.toggled.connect(self._on_capture_view_auto_expand_toggled)

        # Initial Metrics Load
        initial_stats = self.repo.get_summary_stats()
        self.dashboard_view.update_metrics(initial_stats)

    def _on_nav_clicked(self, page_idx: int, clicked_btn: QPushButton):
        for btn in self.nav_buttons:
            btn.setChecked(btn == clicked_btn)
        self.stack.setCurrentIndex(page_idx)

    def _on_dashboard_auto_scroll_toggled(self, is_on: bool):
        """Synchronizes dashboard toggle with capture view and updates ribbon."""
        self.capture_view.chk_auto_scroll.blockSignals(True)
        self.capture_view.chk_auto_scroll.setChecked(is_on)
        self.capture_view.chk_auto_scroll.blockSignals(False)
        scroll_status = " | Auto-Scroll: ON (Adaptive)" if is_on else ""
        mode = self.capture_view.get_selected_mode()
        self.lbl_ribbon_mode.setText(f"Mode: {mode}{scroll_status}")

    def _on_capture_view_auto_scroll_toggled(self, is_on: bool):
        """Synchronizes capture settings toggle back to dashboard button."""
        self.dashboard_view.set_auto_scroll_enabled(is_on)
        scroll_status = " | Auto-Scroll: ON (Adaptive)" if is_on else ""
        mode = self.capture_view.get_selected_mode()
        self.lbl_ribbon_mode.setText(f"Mode: {mode}{scroll_status}")

    def _on_dashboard_auto_expand_toggled(self, is_on: bool):
        """Synchronizes dashboard auto-expand toggle with capture settings."""
        self.capture_view.chk_auto_expand.blockSignals(True)
        self.capture_view.chk_auto_expand.setChecked(is_on)
        self.capture_view.chk_auto_expand.blockSignals(False)

    def _on_capture_view_auto_expand_toggled(self, is_on: bool):
        """Synchronizes capture settings auto-expand toggle back to dashboard."""
        self.dashboard_view.set_auto_expand_enabled(is_on)

    def _start_extraction_worker(self):
        """Starts the background intelligence extraction consumer thread."""
        self.extraction_worker = ExtractionWorker(repo=self.repo, csv_service=self.csv_service)
        self.extraction_worker.record_extracted.connect(self._on_record_extracted)
        self.extraction_worker.stats_updated.connect(self.dashboard_view.update_metrics)
        self.extraction_worker.start()

    def _check_initial_lm_connection(self):
        """Tests local LM Studio connection silently on boot."""
        success, msg, models = self.lm_client.test_connection()
        self.dashboard_view.update_lm_studio_badge(success, msg, self.lm_client.model)
        if success:
            self.lbl_ribbon_lm.setText(f"LM Studio: {self.lm_client.model}")
            self.lbl_ribbon_lm.setStyleSheet("color: #34D399; font-weight: 600; font-size: 12px;")
        else:
            self.lbl_ribbon_lm.setText("LM Studio: Offline")
            self.lbl_ribbon_lm.setStyleSheet("color: #F87171; font-weight: 600; font-size: 12px;")

    def _test_lm_studio(self):
        success, msg, models = self.lm_client.test_connection()
        self.dashboard_view.update_lm_studio_badge(success, msg, self.lm_client.model)
        if success:
            QMessageBox.information(self, "LM Studio Connected", f"{msg}\nActive Model: {self.lm_client.model}")
        else:
            QMessageBox.warning(self, "LM Studio Offline", f"{msg}\nEnsure LM Studio Local Server is started at http://127.0.0.1:1234.")

    def _start_capture(self):
        """Starts the capture worker loop in the selected mode."""
        mode = self.capture_view.get_selected_mode()
        region = self.capture_view.selected_region if mode == "B" else None
        auto_scroll = self.dashboard_view.is_auto_scroll_enabled()
        CONFIG.capture.auto_scroll_enabled = auto_scroll
        auto_expand = self.dashboard_view.is_auto_expand_enabled()
        CONFIG.capture.auto_expand_read_more = auto_expand

        if self.capture_worker and self.capture_worker.isRunning():
            self.capture_worker.stop()
            self.capture_worker.wait(1000)

        # Clear database and reset deduplication / CSV for a fresh session on Start Capture
        try:
            self.repo.clear_all_contacts()
            self.csv_service.reset_csv()
            if self.extraction_worker:
                self.extraction_worker.deduplicator.clear()
                self.extraction_worker.extracted_count = 0
                self.extraction_worker.duplicate_count = 0

            # Reset UI metrics & refresh tables
            stats = self.repo.get_summary_stats()
            stats["duplicates_skipped"] = 0
            self.dashboard_view.update_metrics(stats)
            self.dashboard_view.set_captures_count(0)
            self.dashboard_view.lr_content.setText("No contacts extracted yet in this session. Capturing started...")
            self.results_view.refresh_table()
            self.database_view.load_data()
            logger.info("Cleared database, reset CSV, and reset deduplication cache for fresh capture session.")
        except Exception as e:
            logger.error(f"Error resetting database and CSV on start capture: {e}")

        # Pass extraction worker busy check for capability pacing
        is_busy_fn = self.extraction_worker.is_busy if self.extraction_worker else None

        self.capture_worker = CaptureWorker(
            mode=mode,
            region_bbox=region,
            auto_scroll=auto_scroll,
            auto_expand_read_more=auto_expand,
            is_extraction_busy_fn=is_busy_fn
        )
        self.capture_worker.frame_ready.connect(self._on_frame_ready)
        self.capture_worker.frame_skipped.connect(self._on_frame_skipped)
        self.capture_worker.auto_paused.connect(self._on_auto_paused)
        self.capture_worker.status_changed.connect(self._on_capture_status_changed)
        self.capture_worker.session_finished.connect(self._on_capture_finished)
        self.capture_worker.auto_scroll_triggered.connect(self._on_auto_scroll_triggered)
        self.capture_worker.read_more_expanded.connect(self._on_read_more_expanded)
        self.capture_worker.countdown_updated.connect(self.dashboard_view.show_countdown)

        self.capture_worker.start()

        self.btn_global_stop.setEnabled(True)
        self.dashboard_view.update_capture_state("ACTIVE")
        self.lbl_ribbon_status.setText("● Capture: ACTIVE")
        self.lbl_ribbon_status.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px;")
        scroll_status = " | Auto-Scroll: ON (Adaptive)" if auto_scroll else ""
        expand_status = " | Auto-Expand: ON" if auto_expand else ""
        self.lbl_ribbon_mode.setText(f"Mode: {mode}{scroll_status}{expand_status}")

    def _on_read_more_expanded(self, count: int):
        logger.info(f"✨ Auto-expanded {count} '... Read more' message(s) on screen")
        self.lbl_ribbon_status.setText(f"● Expanded {count} WhatsApp message(s)")
        self.lbl_ribbon_status.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px;")

    def _pause_capture(self):
        if self.capture_worker:
            self.capture_worker.pause()
            self.dashboard_view.update_capture_state("PAUSED")
            self.lbl_ribbon_status.setText("● Capture: PAUSED")
            self.lbl_ribbon_status.setStyleSheet("color: #FBBF24; font-weight: bold; font-size: 12px;")

    def _resume_capture(self):
        if self.capture_worker:
            self.capture_worker.resume()
            self.dashboard_view.update_capture_state("ACTIVE")
            self.lbl_ribbon_status.setText("● Capture: ACTIVE")
            self.lbl_ribbon_status.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px;")

    def _stop_capture(self):
        if self.capture_worker:
            self.capture_worker.stop()
        self.dashboard_view.update_capture_state("IDLE")
        self.btn_global_stop.setEnabled(False)
        self.lbl_ribbon_status.setText("● Capture: IDLE")
        self.lbl_ribbon_status.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 12px;")

    def _capture_current_screen_now(self):
        """Instant single screen capture triggered by user."""
        from app.capture.screen_capture import ScreenCaptureEngine
        engine = ScreenCaptureEngine()
        img, win_info = engine.capture_active_window()
        engine.close()

        if img:
            self.capture_view.update_live_preview(img, win_info, 100.0)
            if self.extraction_worker:
                self.extraction_worker.enqueue_frame(img, win_info, 100.0)
            logger.info("Triggered instant current screen capture.")

    def _launch_region_selector(self):
        """Opens fullscreen translucent overlay for drawing region."""
        self.region_selector.start_selection()

    def _on_region_selected(self, bbox: Tuple[int, int, int, int]):
        self.capture_view.set_selected_region(bbox)
        logger.info(f"Screen region selected: {bbox}")

    @Slot(object, dict, float)
    def _on_frame_ready(self, image, window_info: dict, diff_percent: float):
        """Dispatches captured frame to extraction worker and updates preview."""
        self.capture_view.update_live_preview(image, window_info, diff_percent)
        if self.extraction_worker:
            self.extraction_worker.enqueue_frame(image, window_info, diff_percent)
        if self.capture_worker:
            self.dashboard_view.set_captures_count(self.capture_worker.captures_count)

    @Slot(str, float)
    def _on_frame_skipped(self, reason: str, diff_percent: float):
        pass

    @Slot(str)
    def _on_auto_paused(self, reason: str):
        self.dashboard_view.update_capture_state("PAUSED")
        self.lbl_ribbon_status.setText(f"● Auto-Paused ({reason})")
        self.lbl_ribbon_status.setStyleSheet("color: #FBBF24; font-weight: bold; font-size: 12px;")

    @Slot(str)
    def _on_capture_status_changed(self, status: str):
        self.lbl_ribbon_status.setText(f"● {status}")
        if "waiting" in status.lower():
            self.lbl_ribbon_status.setStyleSheet("color: #FBBF24; font-weight: bold; font-size: 12px;")
        elif "stopped" in status.lower() or "idle" in status.lower():
            self.lbl_ribbon_status.setStyleSheet("color: #94A3B8; font-weight: bold; font-size: 12px;")
        else:
            self.lbl_ribbon_status.setStyleSheet("color: #34D399; font-weight: bold; font-size: 12px;")

    @Slot(int, int)
    def _on_auto_scroll_triggered(self, current: int, max_s: int):
        self.lbl_ribbon_status.setText(f"● Capturing & Auto-Scrolling (Scroll #{current})")
        logger.debug(f"Auto-scroll event #{current} executed.")

    @Slot(int)
    def _on_capture_finished(self, total: int):
        self.dashboard_view.update_capture_state("IDLE")
        self.btn_global_stop.setEnabled(False)

    @Slot(object, bool)
    def _on_record_extracted(self, record, is_duplicate: bool):
        """Updates dashboard snippet and refreshes results table when new record arrives."""
        if not is_duplicate:
            self.dashboard_view.set_last_saved_record(record)
            self.results_view.refresh_table()

    def closeEvent(self, event):
        """Clean shutdown of background threads."""
        if self.capture_worker:
            self.capture_worker.stop()
            self.capture_worker.wait(1000)

        if self.extraction_worker:
            self.extraction_worker.stop()
            self.extraction_worker.wait(1000)

        event.accept()
