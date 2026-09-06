"""
Recruiters View for Pedne Sewa Trust - Employment Facilitation Platform.
Manages recruiter registrations, verification status (UNVERIFIED, VERIFIED, BLOCKED),
controlled candidate data sharing (Level 1 Shortlist vs Level 2 Profile),
and audit trail history.
"""

from typing import List, Optional
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QMessageBox, QFrame, QTabWidget,
    QFormLayout, QTextEdit, QFileDialog, QListWidget, QAbstractItemView
)
from PySide6.QtCore import Qt
from database.repository import repository
from models.facilitation import Recruiter
from facilitation.recruiter_service import recruiter_service
from ui.components.icons import AppIcons


class RecruitersView(QWidget):
    """Recruiter management, verification, candidate export, and sharing audit trail."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Section
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Recruiters & Candidate Facilitation", self)
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1E293B;")
        subtitle = QLabel("Verified employer network, controlled profile sharing, and audit logging", self)
        subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Add Recruiter Button
        btn_add = QPushButton("Register Recruiter", self)
        btn_add.setProperty("class", "PrimaryButton")
        btn_add.setIcon(AppIcons.recruiters())
        btn_add.clicked.connect(self._show_add_recruiter_dialog)
        header_layout.addWidget(btn_add)

        btn_refresh = QPushButton("Refresh", self)
        btn_refresh.setProperty("class", "SecondaryButton")
        btn_refresh.setIcon(AppIcons.refresh())
        btn_refresh.clicked.connect(self.refresh_data)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        # Tabs: 1. Registered Recruiters, 2. Sharing Audit Trail
        self.tabs = QTabWidget(self)

        # Tab 1: Recruiters
        tab_recruiters = QWidget()
        rec_layout = QVBoxLayout(tab_recruiters)
        rec_layout.setContentsMargins(0, 12, 0, 0)
        rec_layout.setSpacing(12)

        self.table_recruiters = QTableWidget(self)
        self.table_recruiters.setColumnCount(8)
        self.table_recruiters.setHorizontalHeaderLabels([
            "ID", "Company", "Contact Person", "Phone", "Email",
            "Verification", "Shares", "Actions"
        ])
        self.table_recruiters.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_recruiters.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_recruiters.setAlternatingRowColors(True)
        rec_layout.addWidget(self.table_recruiters)

        self.tabs.addTab(tab_recruiters, "Registered Employers / Recruiters")

        # Tab 2: Sharing History & Audit Trail
        tab_audit = QWidget()
        aud_layout = QVBoxLayout(tab_audit)
        aud_layout.setContentsMargins(0, 12, 0, 0)
        aud_layout.setSpacing(12)

        self.table_audit = QTableWidget(self)
        self.table_audit.setColumnCount(7)
        self.table_audit.setHorizontalHeaderLabels([
            "Timestamp", "Recruiter", "Candidate ID", "Export Mode",
            "Consent at Sharing", "Shared By", "Notes"
        ])
        self.table_audit.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table_audit.setSelectionBehavior(QTableWidget.SelectRows)
        self.table_audit.setAlternatingRowColors(True)
        aud_layout.addWidget(self.table_audit)

        self.tabs.addTab(tab_audit, "Controlled Sharing History")

        layout.addWidget(self.tabs, 1)

    def refresh_data(self):
        self._load_recruiters()
        self._load_shares()

    def _load_recruiters(self):
        recruiters = repository.get_all_recruiters()
        self.table_recruiters.setRowCount(len(recruiters))
        for row, r in enumerate(recruiters):
            self.table_recruiters.setItem(row, 0, QTableWidgetItem(r.recruiter_id))
            self.table_recruiters.setItem(row, 1, QTableWidgetItem(r.company))
            self.table_recruiters.setItem(row, 2, QTableWidgetItem(f"{r.contact_person} ({r.designation})"))
            self.table_recruiters.setItem(row, 3, QTableWidgetItem(r.phone))
            self.table_recruiters.setItem(row, 4, QTableWidgetItem(r.email))

            # Status item
            item_status = QTableWidgetItem(r.verification_status)
            if r.verification_status == "VERIFIED":
                item_status.setForeground(QColor("#15803D"))
            elif r.verification_status == "BLOCKED":
                item_status.setForeground(QColor("#B91C1C"))
            else:
                item_status.setForeground(QColor("#D97706"))
            self.table_recruiters.setItem(row, 5, item_status)

            self.table_recruiters.setItem(row, 6, QTableWidgetItem(str(r.candidates_shared_count)))

            # Actions
            action_box = QWidget()
            b_layout = QHBoxLayout(action_box)
            b_layout.setContentsMargins(4, 2, 4, 2)
            b_layout.setSpacing(6)

            btn_export = QPushButton("Share Candidates", action_box)
            btn_export.setProperty("class", "SecondaryButton")
            btn_export.clicked.connect(lambda checked, rec=r: self._show_export_dialog(rec))
            b_layout.addWidget(btn_export)

            if r.verification_status != "VERIFIED":
                btn_verify = QPushButton("Verify", action_box)
                btn_verify.setProperty("class", "SecondaryButton")
                btn_verify.clicked.connect(lambda checked, rid=r.recruiter_id: self._set_recruiter_status(rid, "VERIFIED"))
                b_layout.addWidget(btn_verify)
            else:
                btn_block = QPushButton("Block", action_box)
                btn_block.setProperty("class", "SecondaryButton")
                btn_block.clicked.connect(lambda checked, rid=r.recruiter_id: self._set_recruiter_status(rid, "BLOCKED"))
                b_layout.addWidget(btn_block)

            self.table_recruiters.setCellWidget(row, 7, action_box)

    def _load_shares(self):
        shares = repository.get_recruiter_shares()
        self.table_audit.setRowCount(len(shares))
        for row, s in enumerate(shares):
            self.table_audit.setItem(row, 0, QTableWidgetItem(s.shared_date[:19].replace("T", " ")))
            self.table_audit.setItem(row, 1, QTableWidgetItem(s.recruiter_id))
            self.table_audit.setItem(row, 2, QTableWidgetItem(s.candidate_id))
            self.table_audit.setItem(row, 3, QTableWidgetItem(s.export_mode))
            self.table_audit.setItem(row, 4, QTableWidgetItem(s.consent_status_at_sharing))
            self.table_audit.setItem(row, 5, QTableWidgetItem(s.shared_by))
            self.table_audit.setItem(row, 6, QTableWidgetItem(s.notes))

    def _set_recruiter_status(self, recruiter_id: str, new_status: str):
        repository.update_recruiter_status(recruiter_id, new_status, actor="Operator", notes=f"Operator changed verification to {new_status}")
        self.refresh_data()

    def _show_add_recruiter_dialog(self):
        dialog = AddRecruiterDialog(self)
        if dialog.exec():
            self.refresh_data()

    def _show_export_dialog(self, recruiter: Recruiter):
        if recruiter.verification_status != "VERIFIED":
            QMessageBox.warning(
                self, "Verification Required",
                f"Recruiter '{recruiter.company}' is currently {recruiter.verification_status}.\n\n"
                "To protect candidate privacy, candidate profiles can only be shared with VERIFIED recruiters."
            )
            return

        dialog = ExportCandidatesForRecruiterDialog(recruiter, self)
        if dialog.exec():
            self.refresh_data()


class AddRecruiterDialog(QDialog):
    """Registers a new employer/recruiter."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Register Employer / Recruiter")
        self.resize(480, 420)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_company = QLineEdit(self)
        form.addRow("Company / Organization *:", self.txt_company)

        self.txt_contact = QLineEdit(self)
        form.addRow("Contact Person *:", self.txt_contact)

        self.txt_desig = QLineEdit("HR / Talent Acquisition", self)
        form.addRow("Designation:", self.txt_desig)

        self.txt_phone = QLineEdit(self)
        form.addRow("Phone / Mobile *:", self.txt_phone)

        self.txt_email = QLineEdit(self)
        form.addRow("Email Address *:", self.txt_email)

        self.txt_industry = QLineEdit(self)
        self.txt_industry.setPlaceholderText("e.g. Aviation, Hospitality, Manufacturing")
        form.addRow("Industry:", self.txt_industry)

        self.txt_location = QLineEdit("North Goa", self)
        form.addRow("Office Location:", self.txt_location)

        self.cmb_verif = QComboBox(self)
        self.cmb_verif.addItems(["UNVERIFIED", "VERIFIED"])
        form.addRow("Initial Status:", self.cmb_verif)

        self.txt_notes = QTextEdit(self)
        self.txt_notes.setMaximumHeight(60)
        form.addRow("Verification Notes:", self.txt_notes)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton("Register", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        company = self.txt_company.text().strip()
        contact = self.txt_contact.text().strip()
        phone = self.txt_phone.text().strip()
        email = self.txt_email.text().strip()

        if not company or not contact or not phone or not email:
            QMessageBox.warning(self, "Validation", "Company, Contact Person, Phone, and Email are mandatory.")
            return

        rec_id = f"REC-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        rec = Recruiter(
            recruiter_id=rec_id,
            company=company,
            contact_person=contact,
            designation=self.txt_desig.text().strip(),
            phone=phone,
            email=email,
            industry=self.txt_industry.text().strip(),
            location=self.txt_location.text().strip(),
            verification_status=self.cmb_verif.currentText(),
            notes=self.txt_notes.toPlainText().strip()
        )
        repository.save_recruiter(rec)
        self.accept()


class ExportCandidatesForRecruiterDialog(QDialog):
    """Controlled candidate export dialog enforcing candidate consent and tiered export."""

    def __init__(self, recruiter: Recruiter, parent=None):
        super().__init__(parent)
        self.recruiter = recruiter
        self.setWindowTitle(f"Share Candidates with {recruiter.company}")
        self.resize(680, 560)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Recruiter banner
        banner = QFrame(self)
        banner.setStyleSheet("background-color: #F0FDF4; border: 1px solid #86EFAC; border-radius: 6px; padding: 10px;")
        b_layout = QVBoxLayout(banner)
        lbl_rec = QLabel(f"<b>Verified Employer:</b> {self.recruiter.company} ({self.recruiter.contact_person})", self)
        lbl_rec.setStyleSheet("color: #166534; font-size: 13px;")
        lbl_sub = QLabel("Only candidates with explicit 'Consented' status will be exported. Level 3 sensitive IDs are blocked.", self)
        lbl_sub.setStyleSheet("color: #15803D; font-size: 11px;")
        b_layout.addWidget(lbl_rec)
        b_layout.addWidget(lbl_sub)
        layout.addWidget(banner)

        # Export Level Selection
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("Select Sharing Level:", self))
        self.cmb_mode = QComboBox(self)
        self.cmb_mode.addItems([
            "Level 1 Shortlist (Anonymised - ID, Age, Village, Qual, Skills, Exp)",
            "Level 2 Profile (Full - Name, Mobile, Email, Full Education & Exp)"
        ])
        mode_layout.addWidget(self.cmb_mode, 1)
        layout.addLayout(mode_layout)

        # Candidate Selection List
        layout.addWidget(QLabel("Select Candidates to Share (Multiple Selection Allowed):", self))
        self.cand_list = QListWidget(self)
        self.cand_list.setSelectionMode(QAbstractItemView.MultiSelection)

        self.candidates = repository.get_all_candidates()
        for c in self.candidates:
            consent = repository.get_candidate_consent(c.candidate_id)
            c_status = consent.consent_status if consent else "Not Asked"
            consent_tag = f"[{c_status.upper()}]" if c_status == "Consented" else f"[{c_status.upper()} - WILL BE BLOCKED]"
            item_text = f"{c.full_name} ({c.candidate_id}) — {c.village} — {c.education.highest_qualification or 'General'} {consent_tag}"
            self.cand_list.addItem(item_text)
        layout.addWidget(self.cand_list, 1)

        # Action buttons
        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_export = QPushButton("Export & Save CSV", self)
        btn_export.setProperty("class", "PrimaryButton")
        btn_export.setIcon(AppIcons.export_file())
        btn_export.clicked.connect(self._execute_export)
        btns.addWidget(btn_export)
        layout.addLayout(btns)

    def _execute_export(self):
        selected_indexes = [item.row() for item in self.cand_list.selectedIndexes()]
        if not selected_indexes:
            QMessageBox.warning(self, "Selection Required", "Please select at least one candidate from the list.")
            return

        selected_cand_ids = [self.candidates[i].candidate_id for i in selected_indexes]
        mode_raw = self.cmb_mode.currentText()
        mode = "Level 1 Shortlist" if "Level 1" in mode_raw else "Level 2 Profile"

        try:
            res = recruiter_service.export_candidates_for_recruiter(
                recruiter_id=self.recruiter.recruiter_id,
                candidate_ids=selected_cand_ids,
                export_mode=mode,
                actor="Operator"
            )
        except Exception as e:
            QMessageBox.critical(self, "Export Failed", f"Export rejected: {str(e)}")
            return

        if not res["success"]:
            QMessageBox.warning(
                self, "Export Blocked",
                f"{res['message']}\n\nNone of the selected candidates have 'Consented' status."
            )
            return

        # Show prompt to save CSV file
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Save {mode} CSV",
            f"{self.recruiter.company.replace(' ', '_')}_{mode.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)"
        )
        if file_path:
            with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
                f.write(res["csv_data"])

            excluded_msg = ""
            if res["excluded_candidates"]:
                excluded_msg = f"\n\nNote: {len(res['excluded_candidates'])} candidate(s) were excluded due to lack of explicit consent."

            QMessageBox.information(
                self, "Export Complete",
                f"Exported {res['exported_count']} candidate(s) to '{file_path}'.{excluded_msg}"
            )
            self.accept()
