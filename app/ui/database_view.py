"""
Historical Contact Database and Bulk Export View.
Interfaces with SQLite database for long-term storage, bulk operations, and full exports.
"""

from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QMessageBox, QCheckBox, QFrame
)
from PySide6.QtCore import Qt
from config import CONFIG
from app.database.repository import ContactRepository
from app.services.csv_service import CSVService

class DatabaseView(QWidget):
    """View to explore the persistent SQLite contact repository and manage bulk exports."""

    def __init__(self, repo: ContactRepository = None, csv_service: CSVService = None, parent=None):
        super().__init__(parent)
        self.repo = repo or ContactRepository()
        self.csv_service = csv_service or CSVService(repo=self.repo)
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # Header Info Card
        info_frame = QFrame()
        info_frame.setObjectName("DbInfoCard")
        info_frame.setStyleSheet("""
            QFrame#DbInfoCard {
                background-color: #1A1C29;
                border: 1px solid #2D324D;
                border-radius: 8px;
            }
        """)
        info_layout = QHBoxLayout(info_frame)
        info_layout.setContentsMargins(16, 12, 16, 12)

        db_path = Path(CONFIG.db_path)
        size_kb = (db_path.stat().st_size / 1024.0) if db_path.exists() else 0.0

        lbl_info = QLabel(f"🗄️ SQLite Database: {CONFIG.db_path} ({size_kb:.1f} KB)")
        lbl_info.setStyleSheet("color: #E2E8F0; font-size: 13px; font-weight: 600;")
        info_layout.addWidget(lbl_info)
        info_layout.addStretch()

        btn_refresh = QPushButton("🔄 Reload DB")
        btn_refresh.setStyleSheet("background-color: #24273A; color: white; padding: 6px 12px; border-radius: 6px; border: 1px solid #3B4261;")
        btn_refresh.clicked.connect(self.load_data)
        info_layout.addWidget(btn_refresh)

        main_layout.addWidget(info_frame)

        # Database Table
        self.table = QTableWidget()
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Date", "Name", "Organization", "Email", "Phone", "Link / URL", "Status"
        ])
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #12131C;
                alternate-background-color: #181A26;
                color: #F1F5F9;
                gridline-color: #24273A;
                border: 1px solid #2D324D;
                border-radius: 8px;
            }
            QHeaderView::section {
                background-color: #1A1C29;
                color: #94A3B8;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #2D324D;
                padding: 8px;
            }
        """)
        self.table.setAlternatingRowColors(True)
        main_layout.addWidget(self.table)

        # Export Controls Row
        export_bar = QHBoxLayout()
        export_bar.setSpacing(12)

        self.chk_exclude_unreviewed = QCheckBox("Exclude unreviewed records from export")
        self.chk_exclude_unreviewed.setStyleSheet("color: #CBD5E1; font-size: 12px;")
        export_bar.addWidget(self.chk_exclude_unreviewed)

        export_bar.addStretch()

        btn_export_all = QPushButton("💾 Export Full Database to CSV")
        btn_export_all.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; padding: 8px 16px; border-radius: 6px; border: none;")
        btn_export_all.clicked.connect(self._export_full_db)
        export_bar.addWidget(btn_export_all)

        main_layout.addLayout(export_bar)
        self.load_data()

    def load_data(self):
        """Fetches records from SQLite."""
        self._records = self.repo.get_all_contacts(limit=None)
        self.table.setRowCount(len(self._records))
        for row, rec in enumerate(self._records):
            self.table.setItem(row, 0, QTableWidgetItem(rec.record_id[:8]))
            self.table.setItem(row, 1, QTableWidgetItem(rec.collected_at[:19].replace("T", " ")))
            self.table.setItem(row, 2, QTableWidgetItem(rec.person_or_profile_name or "-"))
            self.table.setItem(row, 3, QTableWidgetItem(rec.organization_name or "-"))
            self.table.setItem(row, 4, QTableWidgetItem(rec.business_email or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(rec.normalized_phone or rec.contact_number or "-"))
            
            url_str = rec.website_url or rec.social_profile_url or rec.source_url or "-"
            url_item = QTableWidgetItem(url_str)
            if url_str != "-":
                url_item.setToolTip(f"Double-click to open in browser:\n{url_str}")
            self.table.setItem(row, 6, url_item)
            self.table.setItem(row, 7, QTableWidgetItem(rec.review_status))

    def _on_cell_double_clicked(self, row: int, col: int):
        import webbrowser
        if hasattr(self, "_records") and 0 <= row < len(self._records):
            rec = self._records[row]
            if col == 6:
                target_url = rec.website_url or rec.social_profile_url or rec.source_url
                if target_url:
                    webbrowser.open(target_url)

    def _export_full_db(self):
        records = self.repo.get_all_contacts(limit=None)
        if not records:
            QMessageBox.information(self, "No Records", "Database is empty.")
            return

        file_path, _ = QFileDialog.getSaveFileName(
            self, "Save Full Contact Database",
            str(CONFIG.csv_path), "CSV Files (*.csv)"
        )
        if file_path:
            exclude = self.chk_exclude_unreviewed.isChecked()
            count = self.csv_service.export_records_to_file(records, file_path, exclude_unreviewed=exclude)
            QMessageBox.information(self, "Export Successful", f"Saved {count} contacts to:\n{file_path}")
