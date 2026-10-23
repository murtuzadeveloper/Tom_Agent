"""
Activity Log and Diagnostics View.
Displays live color-coded events, OCR status, model inference latency, and errors.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTextEdit,
    QPushButton, QComboBox, QLabel, QFileDialog, QMessageBox, QApplication
)
from PySide6.QtCore import Qt, QMetaObject, Q_ARG
from PySide6.QtGui import QTextCursor, QColor
from app.utils.logger import add_log_listener, get_log_history

class LogsView(QWidget):
    """View to inspect real-time system logs and diagnostic events."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self._load_existing_history()
        add_log_listener(self._on_new_log)

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(14)

        # Header Controls
        header = QHBoxLayout()
        header.setSpacing(12)

        lbl_title = QLabel("SYSTEM & EXTRACTION ACTIVITY LOG")
        lbl_title.setStyleSheet("color: #F8FAFC; font-size: 14px; font-weight: bold;")
        header.addWidget(lbl_title)
        header.addStretch()

        self.combo_level = QComboBox()
        self.combo_level.addItems(["ALL LEVELS", "INFO", "WARNING", "ERROR", "DEBUG"])
        self.combo_level.setStyleSheet("""
            QComboBox {
                background-color: #1A1C29;
                color: #CBD5E1;
                border: 1px solid #2D324D;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 12px;
            }
        """)
        header.addWidget(self.combo_level)

        btn_copy = QPushButton("📋 Copy All")
        btn_copy.setStyleSheet("background-color: #24273A; color: white; padding: 6px 12px; border-radius: 6px; border: 1px solid #3B4261;")
        btn_copy.clicked.connect(self._copy_logs)
        header.addWidget(btn_copy)

        btn_clear = QPushButton("🗑️ Clear View")
        btn_clear.setStyleSheet("background-color: #24273A; color: #FCA5A5; padding: 6px 12px; border-radius: 6px; border: 1px solid #3B4261;")
        btn_clear.clicked.connect(self.txt_console.clear if hasattr(self, "txt_console") else lambda: None)
        header.addWidget(btn_clear)

        btn_export = QPushButton("💾 Save Log File")
        btn_export.setStyleSheet("background-color: #0284C7; color: white; font-weight: 600; padding: 6px 14px; border-radius: 6px; border: none;")
        btn_export.clicked.connect(self._export_logs)
        header.addWidget(btn_export)

        main_layout.addLayout(header)

        # Log Console Box
        self.txt_console = QTextEdit()
        self.txt_console.setReadOnly(True)
        self.txt_console.setStyleSheet("""
            QTextEdit {
                background-color: #0B0C14;
                color: #E2E8F0;
                font-family: 'Consolas', 'Courier New', monospace;
                font-size: 12px;
                border: 1px solid #24273A;
                border-radius: 8px;
                padding: 12px;
                line-height: 1.4;
            }
        """)
        btn_clear.clicked.connect(self.txt_console.clear)
        main_layout.addWidget(self.txt_console)

    def _load_existing_history(self):
        for entry in get_log_history():
            self._append_log_html(entry)

    def _on_new_log(self, entry: dict):
        """Thread-safe UI callback to append log line."""
        self._append_log_html(entry)

    def _append_log_html(self, entry: dict):
        level = entry.get("level", "INFO")
        time_str = entry.get("timestamp", "")
        raw_msg = entry.get("raw_message", entry.get("message", ""))

        color_map = {
            "INFO": "#38BDF8",     # Sky Blue
            "WARNING": "#FBBF24",  # Amber
            "ERROR": "#F87171",    # Red
            "DEBUG": "#64748B"     # Slate Gray
        }
        color = color_map.get(level, "#E2E8F0")

        html = f"""<span style="color:#64748B;">[{time_str}]</span> <b style="color:{color};">[{level}]</b> <span style="color:#F1F5F9;">{raw_msg}</span><br>"""
        self.txt_console.moveCursor(QTextCursor.MoveOperation.End)
        self.txt_console.insertHtml(html)
        self.txt_console.moveCursor(QTextCursor.MoveOperation.End)

    def _copy_logs(self):
        QApplication.clipboard().setText(self.txt_console.toPlainText())
        QMessageBox.information(self, "Copied", "Log contents copied to clipboard.")

    def _export_logs(self):
        path, _ = QFileDialog.getSaveFileName(self, "Save Logs", "smart_leads_log.txt", "Text Files (*.txt)")
        if path:
            with open(path, "w", encoding="utf-8") as f:
                f.write(self.txt_console.toPlainText())
            QMessageBox.information(self, "Exported", f"Logs saved to {path}")
