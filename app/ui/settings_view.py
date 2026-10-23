"""
Settings and Configuration View.
Provides full control over LM Studio endpoints, models, hardware limits, CSV destination, and security policies.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QLabel,
    QLineEdit, QSpinBox, QDoubleSpinBox, QCheckBox, QPushButton,
    QGroupBox, QFileDialog, QMessageBox, QScrollArea, QFrame
)
from PySide6.QtCore import Qt, Signal
from config import CONFIG
from app.services.lm_studio_client import LMStudioClient
from app.utils.logger import logger

class SettingsView(QWidget):
    """Configuration interface for murtuzadeveloper Smart Leads."""

    settings_saved = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.lm_client = LMStudioClient()
        self.init_ui()

    def init_ui(self):
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setStyleSheet("background-color: transparent;")

        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(20)

        group_style = """
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
            QLabel { color: #CBD5E1; font-size: 12px; }
            QLineEdit, QSpinBox, QDoubleSpinBox {
                background-color: #1E293B;
                color: #F8FAFC;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """

        # 1. LM Studio Settings
        lm_box = QGroupBox("1. LOCAL LM STUDIO & MODEL INFERENCE")
        lm_box.setStyleSheet(group_style)
        lm_layout = QGridLayout(lm_box)
        lm_layout.setContentsMargins(16, 16, 16, 16)
        lm_layout.setSpacing(12)

        lm_layout.addWidget(QLabel("API Base URL:"), 0, 0)
        self.txt_base_url = QLineEdit(CONFIG.lm_studio.base_url)
        lm_layout.addWidget(self.txt_base_url, 0, 1)

        btn_test = QPushButton("🔌 Test Connection")
        btn_test.setStyleSheet("background-color: #4F46E5; color: white; font-weight: 600; padding: 6px 12px; border-radius: 6px; border: none;")
        btn_test.clicked.connect(self._test_connection)
        lm_layout.addWidget(btn_test, 0, 2)

        lm_layout.addWidget(QLabel("Model Identifier:"), 1, 0)
        self.txt_model = QLineEdit(CONFIG.lm_studio.default_model)
        lm_layout.addWidget(self.txt_model, 1, 1, 1, 2)

        self.lbl_lm_test_result = QLabel("Status: Click 'Test Connection' to discover models.")
        self.lbl_lm_test_result.setStyleSheet("color: #94A3B8; font-style: italic; font-size: 11px;")
        lm_layout.addWidget(self.lbl_lm_test_result, 2, 1, 1, 2)

        self.chk_ocr_first = QCheckBox("OCR-First Mode (extract text first, only invoke vision if needed)")
        self.chk_ocr_first.setChecked(CONFIG.lm_studio.ocr_first_mode)
        self.chk_ocr_first.setStyleSheet("color: #E2E8F0;")
        lm_layout.addWidget(self.chk_ocr_first, 3, 1, 1, 2)

        self.chk_enable_vision = QCheckBox("Enable Vision Inference (Submit screenshots to multimodal model)")
        self.chk_enable_vision.setChecked(CONFIG.lm_studio.enable_vision)
        self.chk_enable_vision.setStyleSheet("color: #E2E8F0;")
        lm_layout.addWidget(self.chk_enable_vision, 4, 1, 1, 2)

        layout.addWidget(lm_box)

        # 2. Hardware & Memory Tuning
        hw_box = QGroupBox("2. HARDWARE & MEMORY LIMITS (i7-9850H / MX150 2GB)")
        hw_box.setStyleSheet(group_style)
        hw_layout = QGridLayout(hw_box)
        hw_layout.setContentsMargins(16, 16, 16, 16)
        hw_layout.setSpacing(12)

        self.chk_low_memory = QCheckBox("Low-Memory Mode (Downscale images to prevent VRAM overflow)")
        self.chk_low_memory.setChecked(CONFIG.hardware.low_memory_mode)
        self.chk_low_memory.setStyleSheet("color: #E2E8F0;")
        hw_layout.addWidget(self.chk_low_memory, 0, 0, 1, 2)

        hw_layout.addWidget(QLabel("Max Image Dimension (px):"), 1, 0)
        self.spin_max_dim = QSpinBox()
        self.spin_max_dim.setRange(640, 2560)
        self.spin_max_dim.setValue(CONFIG.hardware.max_screenshot_dimension)
        hw_layout.addWidget(self.spin_max_dim, 1, 1)

        hw_layout.addWidget(QLabel("Pause on RAM Usage (%):"), 2, 0)
        self.spin_ram_limit = QDoubleSpinBox()
        self.spin_ram_limit.setRange(50.0, 98.0)
        self.spin_ram_limit.setValue(CONFIG.hardware.memory_pause_threshold_percent)
        hw_layout.addWidget(self.spin_ram_limit, 2, 1)

        layout.addWidget(hw_box)

        # 3. Storage and CSV Destination
        store_box = QGroupBox("3. STORAGE & OUTPUT DESTINATION")
        store_box.setStyleSheet(group_style)
        store_layout = QGridLayout(store_box)
        store_layout.setContentsMargins(16, 16, 16, 16)
        store_layout.setSpacing(12)

        store_layout.addWidget(QLabel("Output CSV Path:"), 0, 0)
        self.txt_csv_path = QLineEdit(CONFIG.csv_path)
        store_layout.addWidget(self.txt_csv_path, 0, 1)

        btn_browse_csv = QPushButton("Browse...")
        btn_browse_csv.setStyleSheet("background-color: #24273A; color: white; padding: 6px 12px; border-radius: 6px; border: 1px solid #3B4261;")
        btn_browse_csv.clicked.connect(self._browse_csv)
        store_layout.addWidget(btn_browse_csv, 0, 2)

        self.chk_prevent_injection = QCheckBox("Prevent Spreadsheet Formula Injection (Escape =, +, -, @)")
        self.chk_prevent_injection.setChecked(CONFIG.security.prevent_formula_injection)
        self.chk_prevent_injection.setStyleSheet("color: #E2E8F0;")
        store_layout.addWidget(self.chk_prevent_injection, 1, 1, 1, 2)

        layout.addWidget(store_box)

        # Save Button
        btn_save = QPushButton("💾 Save All Settings")
        btn_save.setStyleSheet("""
            QPushButton {
                background-color: #10B981;
                color: white;
                font-size: 14px;
                font-weight: bold;
                padding: 10px 24px;
                border-radius: 8px;
                border: none;
            }
            QPushButton:hover { background-color: #059669; }
        """)
        btn_save.clicked.connect(self._save_settings)
        layout.addWidget(btn_save, alignment=Qt.AlignmentFlag.AlignRight)

        layout.addStretch()
        scroll.setWidget(container)

        view_layout = QVBoxLayout(self)
        view_layout.setContentsMargins(0, 0, 0, 0)
        view_layout.addWidget(scroll)

    def _browse_csv(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "Select Destination CSV File",
            self.txt_csv_path.text(), "CSV Files (*.csv)"
        )
        if path:
            self.txt_csv_path.setText(path)

    def _test_connection(self):
        url = self.txt_base_url.text().strip()
        client = LMStudioClient(base_url=url)
        success, msg, models = client.test_connection()
        if success:
            models_str = ", ".join(models[:3]) + (f" (+{len(models)-3} more)" if len(models) > 3 else "")
            self.lbl_lm_test_result.setText(f"✅ {msg} | Models: {models_str or 'None'}")
            self.lbl_lm_test_result.setStyleSheet("color: #34D399; font-weight: bold;")
            if models and not self.txt_model.text().strip():
                self.txt_model.setText(models[0])
        else:
            self.lbl_lm_test_result.setText(f"❌ {msg}")
            self.lbl_lm_test_result.setStyleSheet("color: #F87171; font-weight: bold;")

    def _save_settings(self):
        CONFIG.lm_studio.base_url = self.txt_base_url.text().strip()
        CONFIG.lm_studio.default_model = self.txt_model.text().strip()
        CONFIG.lm_studio.ocr_first_mode = self.chk_ocr_first.isChecked()
        CONFIG.lm_studio.enable_vision = self.chk_enable_vision.isChecked()

        CONFIG.hardware.low_memory_mode = self.chk_low_memory.isChecked()
        CONFIG.hardware.max_screenshot_dimension = self.spin_max_dim.value()
        CONFIG.hardware.memory_pause_threshold_percent = self.spin_ram_limit.value()

        CONFIG.csv_path = self.txt_csv_path.text().strip()
        CONFIG.security.prevent_formula_injection = self.chk_prevent_injection.isChecked()

        QMessageBox.information(self, "Settings Saved", "Application settings have been updated successfully.")
        self.settings_saved.emit()
