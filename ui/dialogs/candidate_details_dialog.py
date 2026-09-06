"""
Candidate Details Inspection Modal Dialog for Pedne Sewa Trust - Employment Registry.
Clean light NGO design with structured profile review and PDF export.
"""

from typing import Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTabWidget, QWidget, QFrame, QMessageBox, QTableWidget,
    QTableWidgetItem, QHeaderView, QScrollArea
)
from PySide6.QtCore import Qt
from models.candidate import Candidate
from database.repository import repository
from facilitation.document_manager import DocumentManager
from reports.pdf_generator import pdf_generator
from ui.components.icons import AppIcons
from utils.logger import logger


class CandidateDetailsDialog(QDialog):
    """Complete structured view of a registered candidate."""

    def __init__(self, candidate: Candidate, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        self.setWindowTitle(f"Candidate Profile — {candidate.candidate_id}")
        self.setMinimumSize(850, 640)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # 1. Header Info Card (Clean White with subtle border)
        header_card = QFrame(self)
        header_card.setProperty("class", "ContentCard")
        h_layout = QHBoxLayout(header_card)
        h_layout.setContentsMargins(16, 14, 16, 14)

        info_box = QVBoxLayout()
        info_box.setSpacing(2)
        name_lbl = QLabel(self.candidate.full_name, header_card)
        name_lbl.setStyleSheet("font-size: 20px; font-weight: 800; color: #0F172A;")

        sub_lbl = QLabel(
            f"Candidate ID: <b>{self.candidate.candidate_id}</b>  |  Village: <b>{self.candidate.village}</b>  |  Mobile: <b>{self.candidate.mobile}</b>",
            header_card
        )
        sub_lbl.setStyleSheet("font-size: 13px; color: #64748B;")

        info_box.addWidget(name_lbl)
        info_box.addWidget(sub_lbl)
        h_layout.addLayout(info_box)
        h_layout.addStretch()

        main_layout.addWidget(header_card)

        # 2. Tabs for Details
        tabs = QTabWidget(self)
        tabs.addTab(self._build_personal_tab(), "Personal Details")
        tabs.addTab(self._build_education_tab(), "Education")
        tabs.addTab(self._build_employment_tab(), "Employment Classification")
        tabs.addTab(self._build_preferences_tab(), "Preferences & Skills")
        tabs.addTab(self._build_documents_tab(), "Document Readiness")
        tabs.addTab(self._build_facilitation_tab(), "Facilitation & Applications")
        main_layout.addWidget(tabs)

        # 3. Footer Actions
        btn_layout = QHBoxLayout()
        btn_pdf = QPushButton("Export Candidate PDF", self)
        btn_pdf.setProperty("class", "SecondaryButton")
        btn_pdf.setIcon(AppIcons.export_file())
        btn_pdf.setCursor(Qt.PointingHandCursor)
        btn_pdf.clicked.connect(self._on_export_pdf)

        btn_close = QPushButton("Close", self)
        btn_close.setProperty("class", "PrimaryButton")
        btn_close.setCursor(Qt.PointingHandCursor)
        btn_close.clicked.connect(self.accept)

        btn_layout.addWidget(btn_pdf)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_close)
        main_layout.addLayout(btn_layout)

    def _create_row(self, label: str, val: Any) -> QHBoxLayout:
        row = QHBoxLayout()
        lbl = QLabel(f"<b>{label}:</b>")
        lbl.setFixedWidth(180)
        lbl.setStyleSheet("color: #64748B; font-size: 13px;")
        val_lbl = QLabel(str(val) if val not in (None, "") else "—")
        val_lbl.setStyleSheet("color: #0F172A; font-size: 13px; font-weight: 500;")
        val_lbl.setWordWrap(True)
        row.addWidget(lbl)
        row.addWidget(val_lbl)
        row.addStretch()
        return row

    def _build_personal_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        loc = repository.get_candidate_location(self.candidate.candidate_id)

        layout.addLayout(self._create_row("Full Legal Name", self.candidate.full_name))
        layout.addLayout(self._create_row("Date of Birth", self.candidate.dob))
        layout.addLayout(self._create_row("Age", f"{self.candidate.age} years" if self.candidate.age else ""))
        layout.addLayout(self._create_row("Gender", self.candidate.gender))
        layout.addLayout(self._create_row("House / Building", loc.house_building if loc else ""))
        layout.addLayout(self._create_row("Vaddo / Vado", loc.vaddo if loc else ""))
        layout.addLayout(self._create_row("Village", self.candidate.village))
        layout.addLayout(self._create_row("Polling Booth", loc.booth if loc else ""))
        layout.addLayout(self._create_row("Taluka", self.candidate.taluka))
        layout.addLayout(self._create_row("Pincode", self.candidate.pincode))
        layout.addLayout(self._create_row("Full Address / Landmark", self.candidate.address))
        layout.addLayout(self._create_row("Mobile Number", self.candidate.mobile))
        layout.addLayout(self._create_row("Alternate Mobile", self.candidate.alternate_mobile))
        layout.addLayout(self._create_row("Email Address", self.candidate.email))
        layout.addLayout(self._create_row("Registration Date", self.candidate.created_at))
        layout.addLayout(self._create_row("Last Updated", self.candidate.updated_at))
        layout.addStretch()
        return w

    def _build_education_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        edu = self.candidate.education
        layout.addLayout(self._create_row("Highest Qualification", edu.highest_qualification))
        layout.addLayout(self._create_row("Degree / Course", edu.degree_course))
        layout.addLayout(self._create_row("Specialisation", edu.specialisation))
        layout.addLayout(self._create_row("Institution Name", edu.institution))
        layout.addLayout(self._create_row("Passing Year", edu.passing_year))
        layout.addLayout(self._create_row("Additional Qualifications", edu.additional_qualifications))
        layout.addLayout(self._create_row("Certifications", edu.certifications))
        layout.addLayout(self._create_row("Recorded Skills", edu.skills))
        layout.addStretch()
        return w

    def _build_employment_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        emp = self.candidate.employment
        layout.addLayout(self._create_row("Employment Status", emp.status))

        if emp.status == "EMPLOYED":
            layout.addLayout(self._create_row("Sector Type", emp.category))
            layout.addLayout(self._create_row("Organisation / Dept", emp.department_company))
            layout.addLayout(self._create_row("Designation / Role", emp.designation))
            layout.addLayout(self._create_row("Work Location", emp.work_location))
            layout.addLayout(self._create_row("Years of Experience", emp.years_experience))
            layout.addLayout(self._create_row("Previous Experience", emp.previous_experience))
            layout.addLayout(self._create_row("Current Salary", f"₹{emp.current_salary:,.0f}" if emp.current_salary else ""))
        elif emp.status == "UNEMPLOYED":
            layout.addLayout(self._create_row("Government Status", "Applied for Government Employment" if emp.govt_applied else "Never Applied"))
            if emp.govt_applied:
                layout.addLayout(self._create_row("Post / Exam Applied", emp.govt_post_exam))
                layout.addLayout(self._create_row("Govt Department", emp.govt_department))
                layout.addLayout(self._create_row("Application Year", emp.govt_app_year))
                layout.addLayout(self._create_row("Result Status", emp.govt_result_status))
                layout.addLayout(self._create_row("Remarks", emp.govt_remarks))
        elif emp.status == "SELF_EMPLOYED":
            layout.addLayout(self._create_row("Nature of Business", emp.self_emp_business_nature))
            layout.addLayout(self._create_row("Business Location", emp.self_emp_location))
            layout.addLayout(self._create_row("Years Active", emp.self_emp_years_active))
            layout.addLayout(self._create_row("Employees Count", emp.self_emp_employees_count))
            layout.addLayout(self._create_row("Approx Monthly Income", f"₹{emp.self_emp_monthly_income:,.0f}" if emp.self_emp_monthly_income else ""))
        elif emp.status == "STUDENT":
            layout.addLayout(self._create_row("Current Course", emp.student_current_course))
            layout.addLayout(self._create_row("Institution Name", emp.student_institution))
            layout.addLayout(self._create_row("Expected Completion", emp.student_expected_year))
            layout.addLayout(self._create_row("Interested in Employment", "Yes" if emp.student_interested_in_employment else "No"))

        layout.addStretch()
        return w

    def _build_preferences_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)

        pref = self.candidate.preferences
        layout.addLayout(self._create_row("Preferred Sector", pref.preferred_sector))
        layout.addLayout(self._create_row("Preferred Role", pref.preferred_role))
        layout.addLayout(self._create_row("Preferred Location", pref.preferred_location))
        layout.addLayout(self._create_row("Willing to Relocate", "Yes" if pref.willing_to_relocate else "No"))
        layout.addLayout(self._create_row("Employment Type", pref.preferred_employment_type))
        layout.addLayout(self._create_row("Languages Known", pref.languages_known))
        layout.addLayout(self._create_row("Skills List", pref.skills_list))
        layout.addLayout(self._create_row("Certifications", pref.certifications_list))
        layout.addLayout(self._create_row("Total Work Experience", f"{pref.total_experience_years} years" if pref.total_experience_years else ""))
        layout.addLayout(self._create_row("Previous Employers", pref.previous_employers))
        layout.addLayout(self._create_row("Additional Remarks", pref.remarks))
        layout.addStretch()
        return w

    def _build_documents_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        docs = repository.get_candidate_documents(self.candidate.candidate_id)
        gov_readiness = DocumentManager.calculate_readiness(docs, "GOVERNMENT")
        priv_readiness = DocumentManager.calculate_readiness(docs, "PRIVATE")

        # Readiness summary banner
        banner = QFrame(w)
        banner.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        b_layout = QHBoxLayout(banner)

        gov_score = gov_readiness.get("readiness_score", 0)
        priv_score = priv_readiness.get("readiness_score", 0)

        lbl_gov = QLabel(f"<b>Government Readiness:</b> <span style='font-size: 15px; color: {'#15803D' if gov_score >= 80 else '#B45309' if gov_score >= 50 else '#DC2626'}; font-weight: 800;'>{gov_score}%</span>", banner)
        lbl_priv = QLabel(f"<b>Private Sector Readiness:</b> <span style='font-size: 15px; color: {'#15803D' if priv_score >= 80 else '#B45309' if priv_score >= 50 else '#DC2626'}; font-weight: 800;'>{priv_score}%</span>", banner)
        b_layout.addWidget(lbl_gov)
        b_layout.addSpacing(24)
        b_layout.addWidget(lbl_priv)
        b_layout.addStretch()
        layout.addWidget(banner)

        # Document table
        table = QTableWidget(len(docs), 4, w)
        table.setHorizontalHeaderLabels(["Category", "Document Type", "Status", "Reference / Notes"])
        table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        table.setAlternatingRowColors(True)

        for i, d in enumerate(docs):
            c_item = QTableWidgetItem(d.document_category)
            t_item = QTableWidgetItem(d.document_type)
            s_item = QTableWidgetItem(d.status)
            s_item.setTextAlignment(Qt.AlignCenter)
            if d.status == "Available":
                s_item.setForeground(Qt.darkGreen)
            elif d.status in ("Missing", "Expired"):
                s_item.setForeground(Qt.red)
            n_item = QTableWidgetItem(d.notes or "—")
            table.setItem(i, 0, c_item)
            table.setItem(i, 1, t_item)
            table.setItem(i, 2, s_item)
            table.setItem(i, 3, n_item)

        layout.addWidget(table)
        return w

    def _build_facilitation_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        # Consent Section
        consent = repository.get_candidate_consent(self.candidate.candidate_id)
        c_status = consent.consent_status if consent else "Not Asked"
        c_method = consent.consent_method if consent else "—"
        c_date = consent.consent_date if consent else "—"
        c_notes = consent.consent_notes if consent else "—"

        consent_card = QFrame(w)
        consent_card.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 12px;")
        cc_layout = QVBoxLayout(consent_card)
        cc_title = QLabel("<b>Recruiter Consent & Sharing Permission</b>", consent_card)
        cc_title.setStyleSheet("font-size: 13px; color: #0F172A;")
        cc_layout.addWidget(cc_title)

        c_row1 = QHBoxLayout()
        c_row1.addWidget(QLabel(f"Status: <b>{c_status}</b>"))
        c_row1.addSpacing(20)
        c_row1.addWidget(QLabel(f"Method: <b>{c_method}</b>"))
        c_row1.addSpacing(20)
        c_row1.addWidget(QLabel(f"Date: <b>{c_date}</b>"))
        c_row1.addStretch()
        cc_layout.addLayout(c_row1)

        c_row2 = QLabel(f"Notes: {c_notes}")
        c_row2.setStyleSheet("color: #475569; font-size: 12px;")
        cc_layout.addWidget(c_row2)
        layout.addWidget(consent_card)

        # Applications Section
        gov_apps = repository.get_government_job_applications(candidate_id=self.candidate.candidate_id)
        priv_apps = repository.get_private_job_applications(candidate_id=self.candidate.candidate_id)

        app_title = QLabel(f"<b>Application History ({len(gov_apps) + len(priv_apps)} Recorded Applications)</b>", w)
        app_title.setStyleSheet("font-size: 14px; font-weight: 700; color: #0F172A;")
        layout.addWidget(app_title)

        all_apps = []
        for ga in gov_apps:
            all_apps.append(("Government", ga.job_id, ga.application_date, ga.status, ga.remarks))
        for pa in priv_apps:
            all_apps.append(("Private", pa.job_id, pa.application_date, pa.status, pa.notes))

        app_table = QTableWidget(len(all_apps), 5, w)
        app_table.setHorizontalHeaderLabels(["Sector", "Job ID / Ref", "Date", "Status", "Notes / Remarks"])
        app_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        app_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        app_table.horizontalHeader().setSectionResizeMode(2, QHeaderView.ResizeToContents)
        app_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        app_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        app_table.setAlternatingRowColors(True)

        for i, (sec, jid, adate, ast, rem) in enumerate(all_apps):
            app_table.setItem(i, 0, QTableWidgetItem(sec))
            app_table.setItem(i, 1, QTableWidgetItem(jid))
            app_table.setItem(i, 2, QTableWidgetItem(adate))
            s_item = QTableWidgetItem(ast)
            s_item.setTextAlignment(Qt.AlignCenter)
            app_table.setItem(i, 3, s_item)
            app_table.setItem(i, 4, QTableWidgetItem(rem or "—"))

        layout.addWidget(app_table)
        return w

    def _on_export_pdf(self):
        try:
            flat = self.candidate.to_flat_dict()
            headers = ["Field", "Value"]
            rows = [[k, str(v)] for k, v in flat.items()]
            out_file = pdf_generator.generate_report(
                report_title=f"Candidate Record — {self.candidate.candidate_id}",
                headers=headers,
                data_rows=rows,
                filter_summary=f"Candidate: {self.candidate.full_name}"
            )
            QMessageBox.information(self, "PDF Export Complete", f"Candidate profile exported successfully to:\n{out_file}")
        except Exception as e:
            logger.error("Could not generate candidate PDF: %s", e)
            QMessageBox.critical(self, "Export Error", f"Failed to generate candidate PDF: {e}")
