"""
Government Jobs View for Pedne Sewa Trust - Employment Facilitation Platform.
Displays official active notices from GSSC, GPSC, and Goa Online Portal.
Provides intelligent candidate matching with document gap detection,
multi-application tracking, and official advertisement disclaimer.
"""

from datetime import datetime
from typing import Optional, List
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QDialog, QMessageBox, QFrame, QScrollArea,
    QFormLayout, QTextEdit
)
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QColor
from database.repository import repository
from models.candidate import Candidate
from models.facilitation import GovernmentJob, GovernmentJobApplication
from facilitation.job_adapters import (
    GSSCJobAdapter, GPSCJobAdapter, GoaRecruitmentPortalAdapter, seed_initial_sample_jobs
)
from facilitation.matching_engine import matching_engine, DISCLAIMER_TEXT
from ui.components.icons import AppIcons


class GovernmentJobsView(QWidget):
    """Browse official Goa Government jobs, match candidates, and track applications."""

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
        title = QLabel("Government Job Opportunities (Goa)", self)
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #1E293B;")
        subtitle = QLabel("Official recruitment notices from GSSC, GPSC, and Goa State Portals (Cached locally)", self)
        subtitle.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title)
        title_box.addWidget(subtitle)
        header_layout.addLayout(title_box)
        header_layout.addStretch()

        # Add Job Button
        btn_add = QPushButton("Add Notice", self)
        btn_add.setProperty("class", "PrimaryButton")
        btn_add.setIcon(AppIcons.add_candidate())
        btn_add.clicked.connect(self._show_add_job_dialog)
        header_layout.addWidget(btn_add)

        # Seed / Refresh button
        btn_refresh = QPushButton("Refresh Notices", self)
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
        self.txt_search.setPlaceholderText("Search by Post Name or Department...")
        self.txt_search.textChanged.connect(self._filter_table)
        filter_layout.addWidget(self.txt_search, 2)

        self.cmb_status = QComboBox(self)
        self.cmb_status.addItems(["All Statuses", "OPEN", "CLOSING SOON", "CLOSED"])
        self.cmb_status.currentIndexChanged.connect(self._filter_table)
        filter_layout.addWidget(self.cmb_status, 1)

        layout.addWidget(filter_card)

        # Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(9)
        self.table.setHorizontalHeaderLabels([
            "ID", "Post Name", "Department", "Vacancies",
            "Min Qualification", "Pay Level", "Closing Date", "Status", "Actions"
        ])
        self.table.setColumnWidth(0, 105)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setColumnWidth(2, 175)
        self.table.setColumnWidth(3, 75)
        self.table.setColumnWidth(4, 155)
        self.table.setColumnWidth(5, 120)
        self.table.setColumnWidth(6, 100)
        self.table.setColumnWidth(7, 85)
        self.table.setColumnWidth(8, 330)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setAlternatingRowColors(True)
        layout.addWidget(self.table, 1)

    def refresh_jobs(self):
        """Loads jobs from local repository (seeds if empty)."""
        seed_initial_sample_jobs(repository)
        self.all_jobs = repository.get_all_government_jobs()
        self._populate_table(self.all_jobs)

    def _filter_table(self):
        query = self.txt_search.text().strip().lower()
        status_filter = self.cmb_status.currentText()

        filtered = []
        for j in self.all_jobs:
            if query and (query not in j.post_name.lower() and query not in j.department.lower()):
                continue
            if status_filter != "All Statuses" and j.status != status_filter:
                continue
            filtered.append(j)
        self._populate_table(filtered)

    def _populate_table(self, jobs: List[GovernmentJob]):
        self.table.setRowCount(len(jobs))
        for row, job in enumerate(jobs):
            self.table.setItem(row, 0, QTableWidgetItem(job.job_id))
            self.table.setItem(row, 1, QTableWidgetItem(job.post_name))
            self.table.setItem(row, 2, QTableWidgetItem(job.department))
            
            vac_item = QTableWidgetItem(str(job.vacancies_count))
            vac_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row, 3, vac_item)
            
            self.table.setItem(row, 4, QTableWidgetItem(job.minimum_qualification))
            self.table.setItem(row, 5, QTableWidgetItem(job.pay_level_salary))
            self.table.setItem(row, 6, QTableWidgetItem(job.application_closing_date))

            # Status pill
            status_item = QTableWidgetItem(job.status)
            status_item.setTextAlignment(Qt.AlignCenter)
            if job.status == "OPEN":
                status_item.setForeground(QColor("#15803D"))
            elif job.status == "CLOSED":
                status_item.setForeground(QColor("#64748B"))
            else:
                status_item.setForeground(QColor("#D97706"))
            self.table.setItem(row, 7, status_item)

            # Actions widget
            action_box = QWidget()
            box_layout = QHBoxLayout(action_box)
            box_layout.setContentsMargins(4, 2, 4, 2)
            box_layout.setSpacing(5)

            btn_view = QPushButton("View", action_box)
            btn_view.setProperty("class", "SecondaryButton")
            btn_view.setIcon(AppIcons.view())
            btn_view.setToolTip("View full notice details and requirements")
            btn_view.clicked.connect(lambda checked, j=job: self._show_view_job_dialog(j))
            box_layout.addWidget(btn_view)

            btn_edit = QPushButton("Edit", action_box)
            btn_edit.setProperty("class", "SecondaryButton")
            btn_edit.setIcon(AppIcons.edit())
            btn_edit.setToolTip("Edit recruitment notice details")
            btn_edit.clicked.connect(lambda checked, j=job: self._show_edit_job_dialog(j))
            box_layout.addWidget(btn_edit)

            is_open = (job.status == "OPEN")
            btn_toggle = QPushButton("Close" if is_open else "Reopen", action_box)
            btn_toggle.setProperty("class", "SecondaryButton")
            btn_toggle.setToolTip("Close notice or reopen it" if is_open else "Reopen this notice")
            btn_toggle.clicked.connect(lambda checked, j=job: self._toggle_job_status(j))
            box_layout.addWidget(btn_toggle)

            btn_match = QPushButton("Match", action_box)
            btn_match.setProperty("class", "SecondaryButton")
            btn_match.setIcon(AppIcons.match())
            btn_match.setToolTip("Match registered candidates against this post")
            btn_match.clicked.connect(lambda checked, j=job: self._show_matching_dialog(j))
            box_layout.addWidget(btn_match)

            self.table.setCellWidget(row, 8, action_box)

    def _show_add_job_dialog(self):
        dialog = AddGovernmentJobDialog(self)
        if dialog.exec():
            self.refresh_jobs()

    def _show_view_job_dialog(self, job: GovernmentJob):
        dialog = ViewGovernmentJobDialog(job, self)
        dialog.exec()

    def _show_edit_job_dialog(self, job: GovernmentJob):
        dialog = EditGovernmentJobDialog(job, self)
        if dialog.exec():
            self.refresh_jobs()

    def _toggle_job_status(self, job: GovernmentJob):
        new_status = "CLOSED" if job.status == "OPEN" else "OPEN"
        repository.update_government_job_status(job.job_id, new_status)
        self.refresh_jobs()

    def _show_matching_dialog(self, job: GovernmentJob):
        dialog = GovernmentJobMatchingDialog(job, self)
        dialog.exec()

    def _show_apply_dialog(self, job: GovernmentJob):
        dialog = RecordGovJobApplicationDialog(job, self)
        if dialog.exec():
            QMessageBox.information(self, "Application Recorded", f"Candidate application for '{job.post_name}' recorded successfully.")


class GovernmentJobMatchingDialog(QDialog):
    """Displays matched candidates with tiered results, document gap breakdown, and disclaimer."""

    def __init__(self, job: GovernmentJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Candidate Matches: {job.post_name} ({job.department})")
        self.resize(780, 560)
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

        lbl_title = QLabel(f"Post: {self.job.post_name} — {self.job.department}", self)
        lbl_title.setStyleSheet("font-weight: 700; font-size: 15px; color: #1E293B;")
        lbl_req = QLabel(
            f"Requirements: Min Qualification: {self.job.minimum_qualification} | Age: {self.job.age_limit_min}-{self.job.age_limit_max} yrs | Exp: {self.job.experience_requirement_years} yrs",
            self
        )
        lbl_req.setStyleSheet("font-size: 12px; color: #64748B;")
        j_layout.addWidget(lbl_title)
        j_layout.addWidget(lbl_req)
        layout.addWidget(job_card)

        # Mandatory Disclaimer Alert Banner
        disclaimer_banner = QFrame(self)
        disclaimer_banner.setStyleSheet("background-color: #FEF3C7; border: 1px solid #F59E0B; border-radius: 6px; padding: 10px;")
        d_layout = QHBoxLayout(disclaimer_banner)
        d_layout.setContentsMargins(10, 8, 10, 8)
        lbl_disc = QLabel(f"⚠️ <b>{DISCLAIMER_TEXT}</b>", self)
        lbl_disc.setStyleSheet("color: #92400E; font-size: 12px;")
        d_layout.addWidget(lbl_disc)
        layout.addWidget(disclaimer_banner)

        # Results Scroll Area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        container = QWidget()
        c_layout = QVBoxLayout(container)
        c_layout.setSpacing(10)

        # Run match for all candidates
        all_candidates = repository.get_all_candidates()
        match_results = []
        for c in all_candidates:
            docs = repository.get_candidate_documents(c.candidate_id)
            res = matching_engine.match_candidate_to_government_job(c, self.job, docs)
            if res.match_tier in ("HIGH MATCH", "MEDIUM MATCH"):
                match_results.append((c, res))

        # Sort: HIGH MATCH first, then by score descending
        match_results.sort(key=lambda x: (0 if x[1].match_tier == "HIGH MATCH" else 1, -x[1].score))

        if not match_results:
            lbl_none = QLabel("No active candidates meet the minimum qualification and age requirements.", self)
            lbl_none.setStyleSheet("color: #64748B; font-style: italic; padding: 20px;")
            c_layout.addWidget(lbl_none)
        else:
            for cand, res in match_results:
                card = self._build_candidate_match_card(cand, res)
                c_layout.addWidget(card)

        c_layout.addStretch()
        scroll.setWidget(container)
        layout.addWidget(scroll, 1)

        # Close button
        btn_close = QPushButton("Close", self)
        btn_close.setProperty("class", "SecondaryButton")
        btn_close.clicked.connect(self.accept)
        layout.addWidget(btn_close, 0, Qt.AlignRight)

    def _build_candidate_match_card(self, cand: Candidate, res) -> QFrame:
        card = QFrame()
        card.setProperty("class", "Card")
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

        # Criteria matches
        for m in res.matched_criteria[:3]:
            lbl_m = QLabel(m, card)
            lbl_m.setStyleSheet("color: #15803D; font-size: 12px;")
            layout.addWidget(lbl_m)

        # Document gaps
        if res.document_gaps:
            lbl_gap_header = QLabel("Document Requirements to Complete Before Applying:", card)
            lbl_gap_header.setStyleSheet("color: #B91C1C; font-weight: 600; font-size: 12px; margin-top: 4px;")
            layout.addWidget(lbl_gap_header)
            for g in res.document_gaps:
                lbl_g = QLabel(g, card)
                lbl_g.setStyleSheet("color: #DC2626; font-size: 12px; padding-left: 8px;")
                layout.addWidget(lbl_g)

        return card


class RecordGovJobApplicationDialog(QDialog):
    """Records a candidate's application submission."""

    def __init__(self, job: GovernmentJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Record Application: {job.post_name}")
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
        self.cmb_status.addItems(["APPLIED", "ADMIT_CARD_ISSUED", "EXAM_ATTENDED", "SELECTED", "REJECTED", "WITHDRAWN"])
        form.addRow("Status:", self.cmb_status)

        self.txt_notes = QTextEdit(self)
        self.txt_notes.setMaximumHeight(70)
        form.addRow("Notes / Roll No:", self.txt_notes)

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

        app = GovernmentJobApplication(
            candidate_id=cid,
            job_id=self.job.job_id,
            advertisement_number=self.job.advertisement_number,
            post_name=self.job.post_name,
            department=self.job.department,
            application_date=self.txt_date.text().strip(),
            application_status=self.cmb_status.currentText(),
            notes=self.txt_notes.toPlainText().strip()
        )
        repository.save_government_job_application(app)
        self.accept()


class AddGovernmentJobDialog(QDialog):
    """Allows facilitators to add official Goa Government recruitment notices."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Add Government Recruitment Notice")
        self.resize(560, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        form = QFormLayout()
        form.setSpacing(10)

        self.cmb_source = QComboBox(self)
        self.cmb_source.addItems(["GSSC", "GPSC", "Govt of Goa Recruitment", "Other Department"])
        form.addRow("Source Portal *:", self.cmb_source)

        self.txt_ad_num = QLineEdit(self)
        self.txt_ad_num.setPlaceholderText("e.g. Advt No. 01/2026/GSSC")
        form.addRow("Advertisement No.:", self.txt_ad_num)

        self.txt_dept = QLineEdit(self)
        self.txt_dept.setPlaceholderText("e.g. Directorate of Education")
        form.addRow("Department *:", self.txt_dept)

        self.txt_post = QLineEdit(self)
        self.txt_post.setPlaceholderText("e.g. Lower Division Clerk / Jr. Stenographer")
        form.addRow("Post Name *:", self.txt_post)

        self.txt_vacancies = QLineEdit("1", self)
        form.addRow("Vacancies Count:", self.txt_vacancies)

        self.txt_qual = QLineEdit(self)
        self.txt_qual.setPlaceholderText("e.g. 12th Pass / Graduate / ITI")
        form.addRow("Min Qualification *:", self.txt_qual)

        self.txt_exp = QLineEdit("0.0", self)
        form.addRow("Min Experience (Yrs):", self.txt_exp)

        age_box = QHBoxLayout()
        self.txt_age_min = QLineEdit("18", self)
        self.txt_age_max = QLineEdit("45", self)
        age_box.addWidget(QLabel("Min:"))
        age_box.addWidget(self.txt_age_min)
        age_box.addWidget(QLabel("Max:"))
        age_box.addWidget(self.txt_age_max)
        form.addRow("Age Limits:", age_box)

        self.txt_salary = QLineEdit(self)
        self.txt_salary.setPlaceholderText("e.g. Level 2 (Rs 19,900 - 63,200)")
        form.addRow("Pay Level / Salary:", self.txt_salary)

        self.txt_closing = QLineEdit(datetime.now().strftime("%Y-%m-%d"), self)
        form.addRow("Application Deadline (YYYY-MM-DD) *:", self.txt_closing)

        self.txt_ad_url = QLineEdit(self)
        self.txt_ad_url.setPlaceholderText("https://...")
        form.addRow("Official Notice URL:", self.txt_ad_url)

        self.txt_apply_url = QLineEdit(self)
        self.txt_apply_url.setPlaceholderText("https://cbes.goa.gov.in or similar")
        form.addRow("Official Apply URL:", self.txt_apply_url)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton("Save Notice", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        dept = self.txt_dept.text().strip()
        post = self.txt_post.text().strip()
        qual = self.txt_qual.text().strip()
        closing = self.txt_closing.text().strip()
        if not dept or not post or not qual or not closing:
            QMessageBox.warning(self, "Validation", "Please fill in Department, Post Name, Qualification, and Deadline.")
            return

        import uuid
        job_id = f"GOV-{datetime.now().strftime('%Y%m')}-{uuid.uuid4().hex[:4].upper()}"
        try:
            vac = int(self.txt_vacancies.text().strip() or "1")
            exp = float(self.txt_exp.text().strip() or "0")
            age_min = int(self.txt_age_min.text().strip() or "18")
            age_max = int(self.txt_age_max.text().strip() or "45")
        except ValueError:
            QMessageBox.warning(self, "Validation", "Please enter valid numbers for vacancies, experience, and age.")
            return

        job = GovernmentJob(
            job_id=job_id,
            source=self.cmb_source.currentText(),
            advertisement_number=self.txt_ad_num.text().strip(),
            department=dept,
            post_name=post,
            vacancies_count=vac,
            minimum_qualification=qual,
            experience_requirement_years=exp,
            age_limit_min=age_min,
            age_limit_max=age_max,
            pay_level_salary=self.txt_salary.text().strip(),
            application_closing_date=closing,
            official_ad_url=self.txt_ad_url.text().strip(),
            official_apply_url=self.txt_apply_url.text().strip(),
            required_documents=["15-Year Residence Certificate", "Valid Employment Exchange Card"],
            status="OPEN"
        )
        repository.save_government_job(job)
        QMessageBox.information(self, "Saved", f"Government Notice '{post}' added successfully!")
        self.accept()


class ViewGovernmentJobDialog(QDialog):
    """Full detail viewer for a Government Job recruitment notice."""

    def __init__(self, job: GovernmentJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Notice Details — {job.post_name}")
        self.resize(650, 520)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Header card
        header_card = QFrame(self)
        header_card.setProperty("class", "Card")
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(14, 12, 14, 12)
        h_layout.setSpacing(4)

        lbl_title = QLabel(self.job.post_name, self)
        lbl_title.setStyleSheet("font-size: 17px; font-weight: 800; color: #0F172A;")
        lbl_dept = QLabel(f"Department: {self.job.department} | Source: {self.job.source}", self)
        lbl_dept.setStyleSheet("font-size: 13px; color: #475569; font-weight: 600;")
        h_layout.addWidget(lbl_title)
        h_layout.addWidget(lbl_dept)
        layout.addWidget(header_card)

        # Details form in scroll area
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        form = QFormLayout(content)
        form.setSpacing(10)

        def make_val(text: str, bold: bool = False, color: str = "#0F172A") -> QLabel:
            lbl = QLabel(text or "Not Specified")
            lbl.setStyleSheet(f"color: {color}; font-size: 13px; {'font-weight: 700;' if bold else ''}")
            lbl.setWordWrap(True)
            return lbl

        form.addRow("Advertisement No:", make_val(self.job.advertisement_number))
        form.addRow("Status:", make_val(self.job.status, bold=True, color="#15803D" if self.job.status == "OPEN" else "#64748B"))
        form.addRow("Vacancies Count:", make_val(str(self.job.vacancies_count), bold=True))
        form.addRow("Employment Type:", make_val(self.job.employment_type))
        form.addRow("Pay Level / Salary:", make_val(self.job.pay_level_salary))
        form.addRow("Minimum Qualification:", make_val(self.job.minimum_qualification, bold=True))
        form.addRow("Experience Requirement:", make_val(f"{self.job.experience_requirement_years} years"))
        form.addRow("Age Limits:", make_val(f"{self.job.age_limit_min} to {self.job.age_limit_max} years"))
        form.addRow("Language Requirements:", make_val(self.job.konkani_marathi_required))
        form.addRow("Application Deadline:", make_val(self.job.application_closing_date, bold=True, color="#DC2626"))

        # Required Documents
        docs_str = ", ".join(self.job.required_documents) if self.job.required_documents else "None specified"
        form.addRow("Required Documents:", make_val(docs_str))

        if self.job.official_apply_url:
            btn_portal = QPushButton("Open Official Portal ↗")
            btn_portal.setProperty("class", "SecondaryButton")
            btn_portal.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.job.official_apply_url)))
            form.addRow("Apply Portal:", btn_portal)

        if self.job.official_ad_url:
            btn_ad = QPushButton("Open Official Notice ↗")
            btn_ad.setProperty("class", "SecondaryButton")
            btn_ad.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(self.job.official_ad_url)))
            form.addRow("Official Notice:", btn_ad)

        scroll.setWidget(content)
        layout.addWidget(scroll, 1)

        # Footer Buttons
        btns = QHBoxLayout()
        btn_match = QPushButton("Match Registered Candidates", self)
        btn_match.setProperty("class", "PrimaryButton")
        btn_match.setIcon(AppIcons.match())
        btn_match.clicked.connect(self._open_match)
        btns.addWidget(btn_match)

        btns.addStretch()

        btn_close = QPushButton("Close", self)
        btn_close.clicked.connect(self.accept)
        btns.addWidget(btn_close)
        layout.addLayout(btns)

    def _open_match(self):
        self.accept()
        dlg = GovernmentJobMatchingDialog(self.job, self.parent())
        dlg.exec()


class EditGovernmentJobDialog(QDialog):
    """Dialog for editing an existing Government Job notice."""

    def __init__(self, job: GovernmentJob, parent=None):
        super().__init__(parent)
        self.job = job
        self.setWindowTitle(f"Edit Notice — {job.post_name}")
        self.resize(540, 560)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(12)

        title = QLabel(f"Edit Notice: {self.job.job_id}", self)
        title.setStyleSheet("font-size: 16px; font-weight: 700; color: #0F172A;")
        layout.addWidget(title)

        form = QFormLayout()
        form.setSpacing(10)

        self.cmb_source = QComboBox(self)
        self.cmb_source.addItems(["GSSC Portal", "GPSC Portal", "Goa Online Services", "Direct Department Notice", "Other"])
        idx = self.cmb_source.findText(self.job.source)
        if idx >= 0:
            self.cmb_source.setCurrentIndex(idx)
        form.addRow("Source Portal:", self.cmb_source)

        self.txt_ad_num = QLineEdit(self.job.advertisement_number, self)
        form.addRow("Advertisement Number:", self.txt_ad_num)

        self.txt_dept = QLineEdit(self.job.department, self)
        form.addRow("Department *:", self.txt_dept)

        self.txt_post = QLineEdit(self.job.post_name, self)
        form.addRow("Post Name *:", self.txt_post)

        self.txt_vacancies = QLineEdit(str(self.job.vacancies_count), self)
        form.addRow("Vacancies Count:", self.txt_vacancies)

        self.txt_qual = QLineEdit(self.job.minimum_qualification, self)
        form.addRow("Min Qualification *:", self.txt_qual)

        self.txt_exp = QLineEdit(str(self.job.experience_requirement_years), self)
        form.addRow("Min Experience (Yrs):", self.txt_exp)

        age_box = QHBoxLayout()
        self.txt_age_min = QLineEdit(str(self.job.age_limit_min), self)
        self.txt_age_max = QLineEdit(str(self.job.age_limit_max), self)
        age_box.addWidget(QLabel("Min:"))
        age_box.addWidget(self.txt_age_min)
        age_box.addWidget(QLabel("Max:"))
        age_box.addWidget(self.txt_age_max)
        form.addRow("Age Limits:", age_box)

        self.txt_salary = QLineEdit(self.job.pay_level_salary, self)
        form.addRow("Pay Level / Salary:", self.txt_salary)

        self.txt_closing = QLineEdit(self.job.application_closing_date, self)
        form.addRow("Application Deadline (YYYY-MM-DD) *:", self.txt_closing)

        self.cmb_status = QComboBox(self)
        self.cmb_status.addItems(["OPEN", "CLOSING SOON", "CLOSED"])
        s_idx = self.cmb_status.findText(self.job.status)
        if s_idx >= 0:
            self.cmb_status.setCurrentIndex(s_idx)
        form.addRow("Status:", self.cmb_status)

        self.txt_ad_url = QLineEdit(self.job.official_ad_url, self)
        form.addRow("Official Notice URL:", self.txt_ad_url)

        self.txt_apply_url = QLineEdit(self.job.official_apply_url, self)
        form.addRow("Official Apply URL:", self.txt_apply_url)

        layout.addLayout(form)

        btns = QHBoxLayout()
        btns.addStretch()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.clicked.connect(self.reject)
        btns.addWidget(btn_cancel)

        btn_save = QPushButton("Save Changes", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.setIcon(AppIcons.save())
        btn_save.clicked.connect(self._save)
        btns.addWidget(btn_save)
        layout.addLayout(btns)

    def _save(self):
        dept = self.txt_dept.text().strip()
        post = self.txt_post.text().strip()
        qual = self.txt_qual.text().strip()
        closing = self.txt_closing.text().strip()
        if not dept or not post or not qual or not closing:
            QMessageBox.warning(self, "Validation", "Please fill in Department, Post Name, Qualification, and Deadline.")
            return

        try:
            vac = int(self.txt_vacancies.text().strip() or "1")
            exp = float(self.txt_exp.text().strip() or "0")
            age_min = int(self.txt_age_min.text().strip() or "18")
            age_max = int(self.txt_age_max.text().strip() or "45")
        except ValueError:
            QMessageBox.warning(self, "Validation", "Please enter valid numbers for vacancies, experience, and age.")
            return

        self.job.source = self.cmb_source.currentText()
        self.job.advertisement_number = self.txt_ad_num.text().strip()
        self.job.department = dept
        self.job.post_name = post
        self.job.vacancies_count = vac
        self.job.minimum_qualification = qual
        self.job.experience_requirement_years = exp
        self.job.age_limit_min = age_min
        self.job.age_limit_max = age_max
        self.job.pay_level_salary = self.txt_salary.text().strip()
        self.job.application_closing_date = closing
        self.job.status = self.cmb_status.currentText()
        self.job.official_ad_url = self.txt_ad_url.text().strip()
        self.job.official_apply_url = self.txt_apply_url.text().strip()

        repository.save_government_job(self.job)
        QMessageBox.information(self, "Saved", f"Government Notice '{post}' updated successfully!")
        self.accept()


