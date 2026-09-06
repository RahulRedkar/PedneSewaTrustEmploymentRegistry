"""
Private Jobs View for Pedne Sewa Trust - Employment Facilitation Platform.
Manages curated private-sector opportunities in Pernem, Mopa Airport, Tuem Industrial Area,
and North Goa. Connects consented candidates to verified openings.
"""

from typing import List, Optional
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QMessageBox, QFrame, QScrollArea,
    QFormLayout, QTextEdit, QSpinBox, QDoubleSpinBox
)
from PySide6.QtCore import Qt
from database.repository import repository
from models.candidate import Candidate
from models.facilitation import PrivateJob, PrivateJobApplication
from facilitation.matching_engine import matching_engine, DISCLAIMER_TEXT
from ui.components.icons import AppIcons


class PrivateJobsView(QWidget):
    """Browse curated private jobs, add new openings, and match consented candidates."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.refresh_jobs()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(16)

        # Header Section
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title = QLabel("Curated Private Job Opportunities", self)
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1E293B;")
        subtitle = QLabel("Local industry openings in Pernem, Mopa Airport, Tuem Electronic City, and North Goa", self)
        subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Add Job Button
        btn_add = QPushButton("Add Job Opening", self)
        btn_add.setProperty("class", "PrimaryButton")
        btn_add.setIcon(AppIcons.add_candidate())
        btn_add.clicked.connect(self._show_add_job_dialog)
        header_layout.addWidget(btn_add)

        btn_refresh = QPushButton("Refresh", self)
        btn_refresh.setProperty("class", "SecondaryButton")
        btn_refresh.setIcon(AppIcons.refresh())
        btn_refresh.clicked.connect(self.refresh_jobs)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        # Filters Bar
        filter_card = QFrame(self)
        filter_card.setProperty("class", "Card")
        filter_layout = QHBoxLayout(filter_card)
        filter_layout.setContentsMargins(16, 12, 16, 12)
        filter_layout.setSpacing(12)

        self.txt_search = QLineEdit(self)
        self.txt_search.setPlaceholderText("Search by Job Title, Employer, or Location...")
        self.txt_search.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.txt_search, 2)

        self.cmb_status = QComboBox(self)
        self.cmb_status.addItems(["All Statuses", "ACTIVE", "CLOSING SOON", "CLOSED", "FILLED"])
        self.cmb_status.currentIndexChanged.connect(self._filter_table)
        filter_layout.addWidget(self.cmb_status, 1)

        layout.addWidget(filter_card)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(8)
        self.table.setHorizontalHeaderLabels([
            "ID", "Job Title", "Employer", "Location",
            "Salary Range", "Min Qual", "Deadline", "Actions"
        ])
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

    def refresh_jobs(self):
        self.all_jobs = repository.get_all_private_jobs()
        self._populate_table(self.all_jobs)

    def _filter_table(self):
        query = self.txt_search.text().strip().lower()
        status_filter = self.cmb_status.currentText()

        filtered = []
        for j in self.all_jobs:
            text_haystack = f"{j.job_title} {j.employer} {j.location}".lower()
            if query and query not in text_haystack:
                continue
            if status_filter != "All Statuses" and j.status != status_filter:
                continue
            filtered.append(j)
        self._populate_table(filtered)

    def _populate_table(self, jobs: List[PrivateJob]):
        self.table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self.table.setItem(row, 0, QTableWidgetItem(job.job_id))
            self.table.setItem(row, 1, QTableWidgetItem(job.job_title))
            self.table.setItem(row, 2, QTableWidgetItem(job.employer))
            self.table.setItem(row, 3, QTableWidgetItem(job.location))
            self.table.setItem(row, 4, QTableWidgetItem(job.salary_range or "Not Disclosed"))
            self.table.setItem(row, 5, QTableWidgetItem(job.required_qualification))
            self.table.setItem(row, 6, QTableWidgetItem(job.application_deadline or "Open"))

            action_box = QWidget()
            box_layout = QHBoxLayout(action_box)
            box_layout.setContentsMargins(4, 2, 4, 2)
            box_layout.setSpacing(6)

            btn_match = QPushButton("Match Candidates", action_box)
            btn_match.setProperty("class", "SecondaryButton")
            btn_match.setIcon(AppIcons.match())
            btn_match.clicked.connect(lambda checked, j=job: self._show_matching_dialog(j))
            box_layout.addWidget(btn_match)

            btn_apply = QPushButton("Record App", action_box)
            btn_apply.setProperty("class", "SecondaryButton")
            btn_apply.clicked.connect(lambda checked, j=job: self._show_apply_dialog(j))
            box_layout.addWidget(btn_apply)

            self.table.setCellWidget(row, 7, action_box)

    def _show_add_job_dialog(self):
        dialog = AddPrivateJobDialog(self)
        if dialog.exec():
            self.refresh_jobs()

    def _show_matching_dialog(self, job: PrivateJob):
        dialog = PrivateJobMatchingDialog(job, self)
        dialog.exec()

    def _show_apply_dialog(self, job: PrivateJob):
        dialog = RecordPrivateJobApplicationDialog(job, self)
        if dialog.exec():
            QMessageBox.information(self, "Application Recorded", f"Candidate application for '{job.job_title}' recorded successfully.")


class AddPrivateJobDialog(QDialog):
    """Dialog for creating a new curated private job opening."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Curated Private Job Opening")
        self.resize(520, 480)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_employer = QLineEdit(self)
        form.addRow("Employer / Company *:", self.txt_employer)

        self.txt_title = QLineEdit(self)
        form.addRow("Job Title *:", self.txt_title)

        self.txt_location = QLineEdit("Pernem, Goa", self)
        form.addRow("Location *:", self.txt_location)

        self.txt_salary = QLineEdit(self)
        self.txt_salary.setPlaceholderText("e.g. ₹20,000 - ₹25,000 / month")
        form.addRow("Salary Range:", self.txt_salary)

        self.cmb_qual = QComboBox(self)
        self.cmb_qual.addItems([
            "10th / SSC", "12th / HSSC", "ITI", "Diploma",
            "Graduate / Bachelor's", "Post Graduate / Master's", "Any"
        ])
        form.addRow("Min Qualification:", self.cmb_qual)

        self.spn_exp = QDoubleSpinBox(self)
        self.spn_exp.setRange(0.0, 30.0)
        self.spn_exp.setSingleStep(0.5)
        form.addRow("Min Experience (Years):", self.spn_exp)

        self.txt_skills = QLineEdit(self)
        self.txt_skills.setPlaceholderText("e.g. Computer, Customer Service, English")
        form.addRow("Required Skills:", self.txt_skills)

        self.txt_desc = QTextEdit(self)
        self.txt_desc.setMaximumHeight(80)
        form.addRow("Job Description:", self.txt_desc)

        self.txt_contact = QLineEdit(self)
        self.txt_contact.setPlaceholderText("Name / Phone / Email")
        form.addRow("Recruiter / HR Contact:", self.txt_contact)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton("Save Job Opening", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        employer = self.txt_employer.text().strip()
        title = self.txt_title.text().strip()
        if not employer or not title:
            QMessageBox.warning(self, "Validation", "Employer and Job Title are required.")
            return

        job_id = f"PVT-{datetime.now().strftime('%Y%m%d%H%M%S')}"
        job = PrivateJob(
            job_id=job_id,
            employer=employer,
            job_title=title,
            location=self.txt_location.text().strip() or "Pernem",
            salary_range=self.txt_salary.text().strip(),
            required_qualification=self.cmb_qual.currentText(),
            required_experience_years=self.spn_exp.value(),
            required_skills=self.txt_skills.text().strip(),
            job_description=self.txt_desc.toPlainText().strip(),
            contact_person=self.txt_contact.text().strip(),
            verification_status="VERIFIED",
            status="ACTIVE"
        )
        repository.save_private_job(job)
        self.accept()


class PrivateJobMatchingDialog(QDialog):
    """Displays consented candidate matches for a private opportunity."""

    def __init__(self, job: PrivateJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Candidate Matches: {job.job_title} ({job.employer})")
        self.resize(760, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Job Summary Card
        job_card = QFrame(self)
        job_card.setProperty("class", "Card")
        j_layout = QVBoxLayout(job_card)
        j_layout.setContentsMargins(14, 12, 14, 12)
        j_layout.setSpacing(4)

        lbl_title = QLabel(f"Role: {self.job.job_title} — {self.job.employer}", self)
        lbl_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #1E293B;")
        lbl_req = QLabel(
            f"Location: {self.job.location} | Min Qual: {self.job.required_qualification} | Exp: {self.job.required_experience_years} yrs | Skills: {self.job.required_skills or 'General'}",
            self
        )
        lbl_req.setStyleSheet("font-size: 12px; color: #64748B;")
        j_layout.addWidget(lbl_title)
        j_layout.addWidget(lbl_req)
        layout.addWidget(job_card)

        # Matching Candidates List
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(10)

        all_candidates = repository.get_all_candidates()
        matched = []
        for c in all_candidates:
            # Check consent status: only match consented candidates for private sector
            consent = repository.get_candidate_consent(c.candidate_id)
            status = consent.consent_status if consent else "Not Asked"
            if status != "Consented":
                continue

            docs = repository.get_candidate_documents(c.candidate_id)
            res = matching_engine.match_candidate_to_private_job(c, self.job, docs)
            if res.match_tier in ("HIGH MATCH", "MEDIUM MATCH"):
                matched.append((c, res))

        matched.sort(key=lambda x: (0 if x[1].match_tier == "HIGH MATCH" else 1, -x[1].score))

        if not matched:
            lbl_none = QLabel("No consented candidates currently match this opportunity.", self)
            lbl_none.setStyleSheet("color: #64748B; font-style: italic; padding: 20px;")
            c_layout.addWidget(lbl_none)
        else:
            for cand, res in matched:
                card = self._build_candidate_match_card(cand, res)
                c_layout.addWidget(card)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        btn_close = QPushButton("Close", self)
        btn_close.setProperty("class", "SecondaryButton")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 0, Qt.AlignRight)

    def _build_candidate_match_card(self, cand: Candidate, res) -> QFrame:
        card = QFrame()
        card.setStyleSheet("QFrame { background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px; }")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        header = QHBoxLayout()
        name_lbl = QLabel(f"<b>{cand.full_name}</b> ({cand.candidate_id}) — {cand.village}", card)
        name_lbl.setStyleSheet("font-size: 14px; color: #1E293B;")
        header.addWidget(name_lbl)
        header.addStretch()

        tier_color = "#15803D" if res.match_tier == "HIGH MATCH" else "#D97706"
        tier_bg = "#DCFCE7" if res.match_tier == "HIGH MATCH" else "#FEF3C7"
        badge = QLabel(f"{res.match_tier} ({res.score:.0f}%)", card)
        badge.setStyleSheet(f"background-color: {tier_bg}; color: {tier_color}; font-weight: 700; font-size: 11px; padding: 3px 8px; border-radius: 4px;")
        header.addWidget(badge)
        layout.addLayout(header)

        for m in res.matched_criteria:
            lbl_m = QLabel(m, card)
            lbl_m.setStyleSheet("color: #15803D; font-size: 12px;")
            layout.addWidget(lbl_m)

        return card


class RecordPrivateJobApplicationDialog(QDialog):
    """Records candidate application for a private job."""

    def __init__(self, job: PrivateJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Record Application: {job.job_title}")
        self.resize(460, 320)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_cand = QComboBox(self)
        self.candidates = repository.get_all_candidates()
        for c in self.candidates:
            self.cmb_cand.addItem(f"{c.full_name} ({c.candidate_id}) - {c.village}", c.candidate_id)
        form.addRow("Select Candidate *:", self.cmb_cand)

        self.txt_date = QLineEdit(datetime.now().strftime("%Y-%m-%d"), self)
        form.addRow("Application Date (YYYY-MM-DD):", self.txt_date)

        self.cmb_status = QComboBox(self)
        self.cmb_status.addItems(["APPLIED", "SHORTLISTED", "INTERVIEW_SCHEDULED", "OFFER_EXTENDED", "HIRED", "REJECTED", "WITHDRAWN"])
        form.addRow("Status:", self.cmb_status)

        self.txt_notes = QTextEdit(self)
        self.txt_notes.setMaximumHeight(70)
        form.addRow("Notes / Interview Date:", self.txt_notes)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton("Save Application", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        cid = self.cmb_cand.currentData()
        if not cid:
            QMessageBox.warning(self, "Validation", "Please select a candidate.")
            return

        app = PrivateJobApplication(
            candidate_id=cid,
            job_id=self.job.job_id,
            company_employer=self.job.employer,
            job_title=self.job.job_title,
            application_date=self.txt_date.text().strip(),
            application_status=self.cmb_status.currentText(),
            notes=self.txt_notes.toPlainText().strip()
        )
        repository.save_private_job_application(app)
        self.accept()
