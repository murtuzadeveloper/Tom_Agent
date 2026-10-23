"""
Live Results Table View.
Provides searchable, sortable contacts table with inline editing, evidence inspection, approval, and CSV export.
"""

import webbrowser
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QComboBox, QMessageBox, QDialog, QFormLayout, QDialogButtonBox,
    QFileDialog, QFrame
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor
from config import CONFIG
from app.services.contact_validator import ContactRecord
from app.database.repository import ContactRepository
from app.services.csv_service import CSVService
from app.utils.logger import logger

class EditContactDialog(QDialog):
    """Dialog to edit an extracted contact's details before final export."""

    def __init__(self, record: ContactRecord, parent=None):
        super().__init__(parent)
        self.record = record
        self.setWindowTitle(f"Edit Contact - {record.person_or_profile_name or 'New Contact'}")
        self.resize(460, 420)
        self.setStyleSheet("""
            QDialog {
                background-color: #1A1C29;
                color: #F8FAFC;
            }
            QLabel { color: #CBD5E1; font-weight: 600; }
            QLineEdit {
                background-color: #0F111A;
                color: #FFFFFF;
                border: 1px solid #334155;
                border-radius: 6px;
                padding: 6px 10px;
            }
        """)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_name = QLineEdit(record.person_or_profile_name or "")
        form.addRow("Name:", self.txt_name)

        self.txt_title = QLineEdit(record.job_title or "")
        form.addRow("Job Title:", self.txt_title)

        self.txt_org = QLineEdit(record.organization_name or "")
        form.addRow("Organization:", self.txt_org)

        self.txt_email = QLineEdit(record.business_email or "")
        form.addRow("Email:", self.txt_email)

        self.txt_phone = QLineEdit(record.normalized_phone or record.contact_number or "")
        form.addRow("Phone:", self.txt_phone)

        self.txt_website = QLineEdit(record.website_url or "")
        form.addRow("Website:", self.txt_website)

        self.txt_social = QLineEdit(record.social_profile_url or "")
        form.addRow("Social URL:", self.txt_social)

        self.txt_evidence = QLineEdit(record.evidence or "")
        form.addRow("Notes / Context:", self.txt_evidence)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def get_updated_data(self) -> dict:
        return {
            "person_or_profile_name": self.txt_name.text().strip() or None,
            "job_title": self.txt_title.text().strip() or None,
            "organization_name": self.txt_org.text().strip() or None,
            "business_email": self.txt_email.text().strip() or None,
            "contact_number": self.txt_phone.text().strip() or None,
            "normalized_phone": self.txt_phone.text().strip() or None,
            "website_url": self.txt_website.text().strip() or None,
            "social_profile_url": self.txt_social.text().strip() or None,
            "evidence": self.txt_evidence.text().strip() or None
        }

class ResultsView(QWidget):
    """View to review, filter, edit, and export extracted contact records."""

    contacts_changed = Signal()

    def __init__(self, repo: ContactRepository = None, csv_service: CSVService = None, parent=None):
        super().__init__(parent)
        self.repo = repo or ContactRepository()
        self.csv_service = csv_service or CSVService(repo=self.repo)
        self._current_records: List[ContactRecord] = []
        # Auto-clean existing records on view load to fix irrelevant legacy fields
        try:
            self.repo.clean_and_repair_stored_contacts()
        except Exception as e:
            logger.debug(f"Initial repair skipped: {e}")
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # 1. Search and Filter Bar
        filter_bar = QHBoxLayout()
        filter_bar.setSpacing(12)

        self.txt_search = QLineEdit()
        self.txt_search.setPlaceholderText("🔍 Search contacts by name, organization, email, phone, or link/URL...")
        self.txt_search.setStyleSheet("""
            QLineEdit {
                background-color: #1A1C29;
                color: #F8FAFC;
                border: 1px solid #2D324D;
                border-radius: 6px;
                padding: 8px 12px;
                font-size: 13px;
            }
            QLineEdit:focus { border-color: #6366F1; }
        """)
        self.txt_search.textChanged.connect(self.refresh_table)
        filter_bar.addWidget(self.txt_search, stretch=2)

        # Status Filter Combo
        self.combo_status = QComboBox()
        self.combo_status.addItems(["All Review Statuses", "PENDING", "APPROVED", "REJECTED"])
        self.combo_status.setStyleSheet("""
            QComboBox {
                background-color: #1A1C29;
                color: #CBD5E1;
                border: 1px solid #2D324D;
                border-radius: 6px;
                padding: 6px 12px;
                font-size: 13px;
            }
        """)
        self.combo_status.currentIndexChanged.connect(self.refresh_table)
        filter_bar.addWidget(self.combo_status)

        # Refresh Button
        btn_refresh = QPushButton("🔄 Refresh")
        btn_refresh.setStyleSheet("background-color: #24273A; color: white; padding: 7px 14px; border-radius: 6px; border: 1px solid #3B4261;")
        btn_refresh.clicked.connect(self.refresh_table)
        filter_bar.addWidget(btn_refresh)

        main_layout.addLayout(filter_bar)

        # 2. Main Results Table
        self.table = QTableWidget()
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "Status", "Name", "Job Title", "Organization", "Email", "Phone", "Link / URL", "Source", "Notes / Context"
        ])
        self.table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet("""
            QTableWidget {
                background-color: #12131C;
                alternate-background-color: #181A26;
                color: #F1F5F9;
                gridline-color: #24273A;
                border: 1px solid #2D324D;
                border-radius: 8px;
                font-size: 12px;
            }
            QHeaderView::section {
                background-color: #1A1C29;
                color: #94A3B8;
                font-weight: bold;
                border: none;
                border-bottom: 2px solid #2D324D;
                padding: 8px;
            }
            QTableWidget::item:selected {
                background-color: #312E81;
                color: #FFFFFF;
            }
        """)
        main_layout.addWidget(self.table)

        # 3. Actions Toolbar (Approve, Reject, Delete, Open URL, Export)
        actions_bar = QHBoxLayout()
        actions_bar.setSpacing(10)

        btn_approve = QPushButton("✅ Approve Selected")
        btn_approve.setStyleSheet("background-color: #059669; color: white; font-weight: bold; font-size: 12px; padding: 7px 12px; border-radius: 6px; border: none;")
        btn_approve.clicked.connect(lambda: self._set_selected_status("APPROVED"))
        actions_bar.addWidget(btn_approve)

        btn_reject = QPushButton("❌ Reject Selected")
        btn_reject.setStyleSheet("background-color: #DC2626; color: white; font-weight: bold; font-size: 12px; padding: 7px 12px; border-radius: 6px; border: none;")
        btn_reject.clicked.connect(lambda: self._set_selected_status("REJECTED"))
        actions_bar.addWidget(btn_reject)

        btn_edit = QPushButton("✏️ Edit Selected")
        btn_edit.setStyleSheet("background-color: #4F46E5; color: white; font-weight: 600; font-size: 12px; padding: 7px 12px; border-radius: 6px; border: none;")
        btn_edit.clicked.connect(self._edit_selected)
        actions_bar.addWidget(btn_edit)

        btn_clean = QPushButton("✨ Clean & Fix Leads")
        btn_clean.setStyleSheet("background-color: #7C3AED; color: white; font-weight: 600; font-size: 12px; padding: 7px 12px; border-radius: 6px; border: none;")
        btn_clean.clicked.connect(self._clean_and_repair)
        actions_bar.addWidget(btn_clean)

        btn_open_url = QPushButton("🌐 Open Source URL")
        btn_open_url.setStyleSheet("background-color: #2563EB; color: white; font-weight: 600; font-size: 12px; padding: 7px 12px; border-radius: 6px; border: none;")
        btn_open_url.clicked.connect(self._open_selected_url)
        actions_bar.addWidget(btn_open_url)

        btn_delete = QPushButton("🗑️ Delete")
        btn_delete.setStyleSheet("background-color: #334155; color: #FCA5A5; font-weight: 600; font-size: 12px; padding: 7px 12px; border-radius: 6px; border: 1px solid #475569;")
        btn_delete.clicked.connect(self._delete_selected)
        actions_bar.addWidget(btn_delete)

        actions_bar.addStretch()

        btn_export = QPushButton("📥 Export Selected to CSV")
        btn_export.setStyleSheet("background-color: #0284C7; color: white; font-weight: bold; font-size: 12px; padding: 7px 14px; border-radius: 6px; border: none;")
        btn_export.clicked.connect(self._export_selected)
        actions_bar.addWidget(btn_export)

        main_layout.addLayout(actions_bar)
        self.refresh_table()

    def refresh_table(self):
        """Loads records from repository and populates table."""
        search = self.txt_search.text().strip()
        status_sel = self.combo_status.currentText()
        review_filter = None if status_sel.startswith("All") else status_sel

        self._current_records = self.repo.get_all_contacts(
            limit=None,
            review_filter=review_filter,
            search_query=search
        )

        self.table.setRowCount(len(self._current_records))
        for row, rec in enumerate(self._current_records):
            # Status Item
            status_item = QTableWidgetItem(rec.review_status)
            if rec.review_status == "APPROVED":
                status_item.setForeground(QColor("#34D399"))
            elif rec.review_status == "REJECTED":
                status_item.setForeground(QColor("#F87171"))
            else:
                status_item.setForeground(QColor("#FBBF24"))
            self.table.setItem(row, 0, status_item)

            self.table.setItem(row, 1, QTableWidgetItem(rec.person_or_profile_name or "-"))
            self.table.setItem(row, 2, QTableWidgetItem(rec.job_title or "-"))
            self.table.setItem(row, 3, QTableWidgetItem(rec.organization_name or "-"))
            self.table.setItem(row, 4, QTableWidgetItem(rec.business_email or "-"))
            self.table.setItem(row, 5, QTableWidgetItem(rec.normalized_phone or rec.contact_number or "-"))

            # Link / URL item
            url_str = rec.website_url or rec.social_profile_url or rec.source_url or "-"
            url_item = QTableWidgetItem(url_str)
            if url_str != "-":
                url_item.setForeground(QColor("#60A5FA"))
                url_item.setToolTip(f"Double-click to open in browser:\n{url_str}")
            self.table.setItem(row, 6, url_item)

            self.table.setItem(row, 7, QTableWidgetItem(rec.source_application or "Desktop"))

            # Notes / Context snippet
            evidence_snip = (rec.evidence or "")[:70]
            self.table.setItem(row, 8, QTableWidgetItem(evidence_snip or "-"))

    def _on_cell_double_clicked(self, row: int, col: int):
        """Opens link if URL column clicked; otherwise opens edit dialog."""
        if 0 <= row < len(self._current_records):
            rec = self._current_records[row]
            if col == 6:
                target_url = rec.website_url or rec.social_profile_url or rec.source_url
                if target_url:
                    webbrowser.open(target_url)
                    return
            self._edit_selected()

    def _clean_and_repair(self):
        """Cleans and fixes legacy irrelevant fields in the database."""
        count = self.repo.clean_and_repair_stored_contacts()
        self.refresh_table()
        self.contacts_changed.emit()
        QMessageBox.information(
            self,
            "Leads Cleaned & Repaired",
            f"Successfully processed and updated {count} lead record(s).\n\n"
            "• Noise names removed ('system ...', 'Job Openings:', 'Pakistan Jobs ...', '& m9')\n"
            "• Real human names derived from email usernames\n"
            "• Missing Job Titles extracted from context\n"
            "• Organizations cleaned (removed 'WhatsApp', formatted corporate domains)\n"
            "• Invalid phone numbers cleaned\n"
            "• WhatsApp boilerplate stripped from notes"
        )

    def _get_selected_record(self) -> Optional[ContactRecord]:
        row = self.table.currentRow()
        if 0 <= row < len(self._current_records):
            return self._current_records[row]
        return None

    def _set_selected_status(self, new_status: str):
        rows = set(item.row() for item in self.table.selectedItems())
        if not rows:
            QMessageBox.information(self, "Selection Required", "Please select at least one row.")
            return

        for r in rows:
            if r < len(self._current_records):
                rec = self._current_records[r]
                self.repo.update_review_status(rec.record_id, new_status)
        self.refresh_table()
        self.contacts_changed.emit()

    def _edit_selected(self):
        rec = self._get_selected_record()
        if not rec:
            QMessageBox.information(self, "Selection Required", "Please select a row to edit.")
            return

        dlg = EditContactDialog(rec, self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            updates = dlg.get_updated_data()
            self.repo.update_contact_fields(rec.record_id, updates)
            self.refresh_table()
            self.contacts_changed.emit()

    def _open_selected_url(self):
        rec = self._get_selected_record()
        if not rec:
            QMessageBox.information(self, "Selection Required", "Please select a row.")
            return

        target_url = rec.source_url or rec.website_url or rec.social_profile_url
        if target_url:
            webbrowser.open(target_url)
        else:
            QMessageBox.information(self, "No URL", "No website or profile URL was recorded for this contact.")

    def _delete_selected(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()), reverse=True)
        if not rows:
            QMessageBox.information(self, "Selection Required", "Please select a row to delete.")
            return

        confirm = QMessageBox.question(
            self, "Confirm Delete",
            f"Are you sure you want to delete {len(rows)} selected record(s)?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if confirm == QMessageBox.StandardButton.Yes:
            for r in rows:
                if r < len(self._current_records):
                    self.repo.delete_contact(self._current_records[r].record_id)
            self.refresh_table()
            self.contacts_changed.emit()

    def _export_selected(self):
        rows = sorted(set(item.row() for item in self.table.selectedItems()))
        if not rows:
            QMessageBox.information(self, "Selection Required", "Please select records to export.")
            return

        selected_records = [self._current_records[r] for r in rows if r < len(self._current_records)]
        file_path, _ = QFileDialog.getSaveFileName(
            self, "Export Selected Contacts to CSV",
            str(CONFIG.csv_path), "CSV Files (*.csv)"
        )
        if file_path:
            count = self.csv_service.export_records_to_file(selected_records, file_path)
            QMessageBox.information(self, "Export Complete", f"Successfully exported {count} records to:\n{file_path}")
