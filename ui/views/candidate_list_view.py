"""
Candidate Database Browser View for Pedne Sewa Trust - Employment Registry.
Provides multi-field real-time searching, category filtering, per-candidate
Cloud Backup status badges, and View/Edit/Delete actions using Qt standard icons.
"""

from datetime import datetime
from typing import List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from models.candidate import Candidate
from database.repository import repository
from export.csv_exporter import csv_exporter
from app.constants import (
    PERNEM_VILLAGES,
    QUALIFICATION_LEVELS,
    EMPLOYMENT_STATUSES,
    SYNC_STATUS_SYNCED,
    SYNC_STATUS_PENDING,
    SYNC_STATUS_FAILED
)
from app.signals import signals
from ui.dialogs.candidate_details_dialog import CandidateDetailsDialog
from ui.dialogs.candidate_edit_dialog import CandidateEditDialog
from ui.components.icons import AppIcons
from utils.logger import logger


class CandidateListView(QWidget):
    """Searchable tabular browser for the candidate registry."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.candidates_cache: List[Candidate] = []
        self.displayed_candidates: List[Candidate] = []
        self._init_ui()
        self._connect_signals()
        self.refresh_table()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Header Bar
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("Candidate Database", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        self.count_lbl = QLabel("Showing 0 registered candidates", self)
        self.count_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(self.count_lbl)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Top Buttons using Qt icons
        btn_export = QPushButton("Export CSV (Filtered)", self)
        btn_export.setProperty("class", "SecondaryButton")
        btn_export.setIcon(AppIcons.export_file())
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._on_export_csv)

        btn_refresh = QPushButton("Refresh", self)
        btn_refresh.setProperty("class", "SecondaryButton")
        btn_refresh.setIcon(AppIcons.refresh())
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_table)

        header_layout.addWidget(btn_export)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        # 2. Search & Filter Drawer Card
        filter_card = QFrame(self)
        filter_card.setProperty("class", "ContentCard")
        f_layout = QVBoxLayout(filter_card)
        f_layout.setContentsMargins(14, 12, 14, 12)
        f_layout.setSpacing(10)

        # Search Row
        search_row = QHBoxLayout()
        self.search_input = QLineEdit(filter_card)
        self.search_input.setPlaceholderText("Search by Name, Candidate ID, Mobile, Village, Qualification, Employer, Role, Skills...")
        self.search_input.textChanged.connect(self.apply_filters)
        self.search_input.setClearButtonEnabled(True)
        search_row.addWidget(self.search_input)
        f_layout.addLayout(search_row)

        # Filter Dropdowns Row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        self.filter_status = QComboBox(filter_card)
        self.filter_status.addItems(["All Statuses"] + EMPLOYMENT_STATUSES)
        self.filter_status.currentIndexChanged.connect(self.apply_filters)

        self.filter_village = QComboBox(filter_card)
        self.filter_village.addItems(["All Villages"] + PERNEM_VILLAGES)
        self.filter_village.currentIndexChanged.connect(self.apply_filters)

        self.filter_qual = QComboBox(filter_card)
        self.filter_qual.addItems(["All Qualifications"] + QUALIFICATION_LEVELS)
        self.filter_qual.currentIndexChanged.connect(self.apply_filters)

        btn_clear_filters = QPushButton("Clear Filters", filter_card)
        btn_clear_filters.setProperty("class", "SecondaryButton")
        btn_clear_filters.setIcon(AppIcons.clear())
        btn_clear_filters.clicked.connect(self._clear_filters)

        lbl_s = QLabel("Status:", filter_card); lbl_s.setStyleSheet("color: #64748B; font-weight: 600;")
        lbl_v = QLabel("Village:", filter_card); lbl_v.setStyleSheet("color: #64748B; font-weight: 600;")
        lbl_q = QLabel("Qualification:", filter_card); lbl_q.setStyleSheet("color: #64748B; font-weight: 600;")

        filter_row.addWidget(lbl_s)
        filter_row.addWidget(self.filter_status)
        filter_row.addWidget(lbl_v)
        filter_row.addWidget(self.filter_village)
        filter_row.addWidget(lbl_q)
        filter_row.addWidget(self.filter_qual)
        filter_row.addWidget(btn_clear_filters)
        filter_row.addStretch()

        f_layout.addLayout(filter_row)
        layout.addWidget(filter_card)

        # 3. Candidate Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "Candidate ID", "Full Name", "Mobile", "Village", "Qualification",
            "Employment", "Role / Details", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(6, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(7, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.table.cellDoubleClicked.connect(self._on_row_double_clicked)
        layout.addWidget(self.table)

    def _connect_signals(self):
        signals.candidate_saved.connect(lambda cid: self.refresh_table())
        signals.candidate_updated.connect(lambda cid: self.refresh_table())
        signals.candidate_deleted.connect(lambda cid: self.refresh_table())
        signals.sync_completed.connect(lambda stats: self.refresh_table())
        signals.database_restored.connect(self.refresh_table)

    def refresh_table(self):
        self.candidates_cache = repository.get_all_candidates(include_deleted=False)
        self.apply_filters()

    def _clear_filters(self):
        self.search_input.clear()
        self.filter_status.setCurrentIndex(0)
        self.filter_village.setCurrentIndex(0)
        self.filter_qual.setCurrentIndex(0)

    def apply_filters(self):
        search_txt = self.search_input.text().strip().lower()
        sel_status = self.filter_status.currentText()
        sel_village = self.filter_village.currentText()
        sel_qual = self.filter_qual.currentText()

        results = []
        for c in self.candidates_cache:
            if search_txt:
                searchable_str = (
                    f"{c.candidate_id} {c.full_name} {c.mobile} {c.alternate_mobile} {c.email} "
                    f"{c.village} {c.address} {c.education.highest_qualification} {c.education.degree_course} "
                    f"{c.education.skills} {c.employment.department_company} {c.employment.designation} "
                    f"{c.employment.previous_experience} "
                    f"{c.employment.govt_post_exam} {c.employment.self_emp_business_nature} "
                    f"{c.preferences.preferred_sector} {c.preferences.preferred_role}"
                ).lower()
                if search_txt not in searchable_str:
                    continue

            if sel_status != "All Statuses" and c.employment.status != sel_status:
                continue

            if sel_village != "All Villages" and c.village != sel_village:
                continue

            if sel_qual != "All Qualifications" and c.education.highest_qualification != sel_qual:
                continue

            results.append(c)

        self.displayed_candidates = results
        self.count_lbl.setText(f"Showing {len(results)} of {len(self.candidates_cache)} registered candidates")
        self._populate_table_rows(results)

    def _populate_table_rows(self, candidates: List[Candidate]):
        self.table.setRowCount(len(candidates))

        for row_idx, c in enumerate(candidates):
            # 0: ID
            item_id = QTableWidgetItem(c.candidate_id)
            item_id.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, item_id)

            # 1: Full Name
            item_name = QTableWidgetItem(c.full_name)
            self.table.setItem(row_idx, 1, item_name)

            # 2: Mobile
            item_mob = QTableWidgetItem(c.mobile)
            item_mob.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, item_mob)

            # 3: Village
            self.table.setItem(row_idx, 3, QTableWidgetItem(c.village))

            # 4: Qualification
            self.table.setItem(row_idx, 4, QTableWidgetItem(c.education.highest_qualification or "—"))

            # 5: Employment Status
            item_status = QTableWidgetItem(c.employment.status)
            item_status.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 5, item_status)

            # 6: Role / Details
            detail_summary = "—"
            if c.employment.status == "EMPLOYED":
                role = c.employment.designation or c.employment.category or "Employed"
                org = f" at {c.employment.department_company}" if c.employment.department_company else ""
                detail_summary = f"{role}{org}"
            elif c.employment.status == "UNEMPLOYED":
                has_prev = bool((c.employment.years_experience and c.employment.years_experience > 0) or (c.employment.previous_experience and c.employment.previous_experience.strip()))
                exp_prefix = ""
                if has_prev:
                    yrs = f"{c.employment.years_experience} yrs" if c.employment.years_experience else "Exp"
                    role_or_org = f" ({c.employment.previous_experience})" if c.employment.previous_experience else ""
                    exp_prefix = f"Prev Exp: {yrs}{role_or_org} | "

                if c.employment.govt_applied:
                    detail_summary = f"{exp_prefix}Applied: {c.employment.govt_post_exam or 'Govt Exam'} ({c.employment.govt_result_status or 'Awaiting'})"
                else:
                    detail_summary = f"{exp_prefix}Never Applied for Govt" if has_prev else "Never Applied for Govt"
            elif c.employment.status == "SELF_EMPLOYED":
                detail_summary = f"Business: {c.employment.self_emp_business_nature or 'Local Venture'}"
            elif c.employment.status == "STUDENT":
                detail_summary = f"Course: {c.employment.student_current_course or 'Student'}"

            self.table.setItem(row_idx, 6, QTableWidgetItem(detail_summary))

            # 7: Action Buttons (View, Edit, Delete)
            action_widget = self._create_actions_widget(c)
            self.table.setCellWidget(row_idx, 7, action_widget)

    def _create_cloud_badge_item(self, c: Candidate) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)

        if c.sync_status == SYNC_STATUS_SYNCED:
            item.setText("☁ Synced")
            item.setForeground(QColor("#15803D"))
            tip = f"Backed up to Google Sheets: {c.last_synced_at or 'Recently'}"
        elif c.sync_status == SYNC_STATUS_PENDING:
            item.setText("⏳ Pending")
            item.setForeground(QColor("#B45309"))
            tip = "Safely stored in local SQLite database. Awaiting next background sync."
        else:
            item.setText("⚠ Failed")
            item.setForeground(QColor("#DC2626"))
            tip = "Previous sync encountered network error. Local data safe; will retry."

        item.setToolTip(tip)
        return item

    def _create_actions_widget(self, candidate: Candidate) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        btn_view = QPushButton(w)
        btn_view.setIcon(AppIcons.view_details())
        btn_view.setToolTip("View candidate profile")
        btn_view.setFixedSize(30, 26)
        btn_view.setProperty("class", "SecondaryButton")
        btn_view.setCursor(Qt.PointingHandCursor)
        btn_view.clicked.connect(lambda: self._view_candidate(candidate))

        btn_edit = QPushButton(w)
        btn_edit.setIcon(AppIcons.edit())
        btn_edit.setToolTip("Edit candidate")
        btn_edit.setFixedSize(30, 26)
        btn_edit.setProperty("class", "SecondaryButton")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(lambda: self._edit_candidate(candidate))

        btn_del = QPushButton(w)
        btn_del.setIcon(AppIcons.delete())
        btn_del.setToolTip("Delete candidate")
        btn_del.setFixedSize(30, 26)
        btn_del.setProperty("class", "DangerButton")
        btn_del.setCursor(Qt.PointingHandCursor)
        btn_del.clicked.connect(lambda: self._delete_candidate(candidate))

        layout.addWidget(btn_view)
        layout.addWidget(btn_edit)
        layout.addWidget(btn_del)
        layout.addStretch()
        return w

    def _view_candidate(self, candidate: Candidate):
        dlg = CandidateDetailsDialog(candidate, self)
        dlg.exec()

    def _edit_candidate(self, candidate: Candidate):
        dlg = CandidateEditDialog(candidate, self)
        dlg.exec()

    def _delete_candidate(self, candidate: Candidate):
        reply = QMessageBox.question(
            self,
            "Confirm Deletion",
            f"Are you sure you want to permanently delete candidate {candidate.candidate_id} ({candidate.full_name})?\n\n"
            "This action cannot be undone.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                repository.delete_candidate(candidate.candidate_id)
                signals.candidate_deleted.emit(candidate.candidate_id)
                QMessageBox.information(self, "Candidate Deleted", f"Candidate {candidate.candidate_id} has been removed.")
            except Exception as e:
                logger.error("Failed to delete candidate: %s", e)
                QMessageBox.critical(self, "Deletion Error", f"Could not delete candidate: {e}")

    def _on_row_double_clicked(self, row: int, col: int):
        if row < len(self.displayed_candidates):
            c = self.displayed_candidates[row]
            self._view_candidate(c)

    def _on_export_csv(self):
        if not self.displayed_candidates:
            QMessageBox.information(self, "No Records", "There are no candidates matching the active filter to export.")
            return

        default_filename = f"PST_Candidates_Filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Filtered Candidates to CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            filepath = csv_exporter.export_filtered(self.displayed_candidates, target_filepath=file_path)
            QMessageBox.information(self, "Export Successful", f"Successfully saved {len(self.displayed_candidates)} candidate records to:\n\n{filepath}")
        except Exception as e:
            logger.error("CSV export error: %s", e)
            QMessageBox.critical(self, "Export Failed", f"Failed to export CSV: {e}")

    def select_and_view_candidate(self, candidate_id: str):
        for c in self.candidates_cache:
            if c.candidate_id == candidate_id:
                self._view_candidate(c)
                break
