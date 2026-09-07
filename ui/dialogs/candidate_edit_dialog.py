"""
Candidate Edit Modal Dialog for Pedne Sewa Trust - Employment Registry.
Allows modifying candidate details with validation, updating SQLite atomically,
and marking the record as PENDING for cloud synchronization.
"""

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTabWidget, QWidget, QFormLayout, QMessageBox,
    QGroupBox, QSpinBox, QDoubleSpinBox, QTextEdit, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression

from datetime import datetime
from models.candidate import Candidate
from models.facilitation import CandidateLocation, CandidateDocument, CandidateConsent
from facilitation.document_manager import DocumentManager, DOCUMENT_STATUSES
from app.constants import (
    PERNEM_VILLAGES,
    QUALIFICATION_LEVELS,
    GOVT_RESULT_STATUSES,
    JOB_SECTORS,
    EMPLOYMENT_TYPES
)
from app.signals import signals
from database.repository import repository
from utils.validators import validate_candidate_form
from ui.components.dob_picker import DateOfBirthPicker
from ui.components.status_selector import EmploymentStatusSelector
from ui.components.icons import AppIcons
from utils.logger import logger


class CandidateEditDialog(QDialog):
    """Full-featured modal form for modifying an existing candidate."""

    def __init__(self, candidate: Candidate, parent=None):
        super().__init__(parent)
        self.candidate = candidate
        self.setWindowTitle(f"Edit Candidate — {candidate.candidate_id}")
        self.setMinimumSize(850, 680)
        self._init_ui()
        self._populate_fields()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 20, 20, 20)
        main_layout.setSpacing(14)

        # Tabs
        self.tabs = QTabWidget(self)
        self.tabs.addTab(self._build_personal_tab(), "1. Personal Information")
        self.tabs.addTab(self._build_education_tab(), "2. Education")
        self.tabs.addTab(self._build_employment_tab(), "3. Employment Classification")
        self.tabs.addTab(self._build_preferences_tab(), "4. Preferences & Skills")
        self.tabs.addTab(self._build_documents_tab(), "5. Document Readiness")
        self.tabs.addTab(self._build_consent_tab(), "6. Recruiter Consent")
        main_layout.addWidget(self.tabs)

        # Footer Actions
        btn_layout = QHBoxLayout()
        btn_cancel = QPushButton("Cancel", self)
        btn_cancel.setProperty("class", "SecondaryButton")
        btn_cancel.setIcon(AppIcons.cancel())
        btn_cancel.clicked.connect(self.reject)

        btn_save = QPushButton("Save Changes", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.setIcon(AppIcons.save())
        btn_save.setMinimumHeight(38)
        btn_save.clicked.connect(self._on_save)

        btn_layout.addWidget(btn_cancel)
        btn_layout.addStretch()
        btn_layout.addWidget(btn_save)
        main_layout.addLayout(btn_layout)

    def _build_personal_tab(self) -> QWidget:
        w = QWidget()
        grid = QHBoxLayout(w)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(20)

        # Column Left
        col_left = QFormLayout()
        col_left.setSpacing(12)

        self.edit_id = QLineEdit(w)
        self.edit_id.setEnabled(False)
        self.edit_id.setStyleSheet("background-color: #F1F5F9; color: #475569;")
        col_left.addRow("Candidate ID:", self.edit_id)

        self.combo_intake_office = QComboBox(w)
        self.combo_intake_office.addItem("Pernem (PST)", "Pernem")
        self.combo_intake_office.addItem("Korgao (KPST)", "Korgao")
        col_left.addRow("Intake Office:", self.combo_intake_office)

        self.edit_name = QLineEdit(w)
        col_left.addRow("Full Name *:", self.edit_name)

        self.dob_picker = DateOfBirthPicker(w)
        self.dob_picker.age_calculated.connect(lambda age: self.edit_age.setValue(age))
        col_left.addRow("Date of Birth:", self.dob_picker)

        self.combo_gender = QComboBox(w)
        self.combo_gender.addItems(["", "Male", "Female", "Other", "Prefer not to say"])
        col_left.addRow("Gender:", self.combo_gender)

        self.edit_house = QLineEdit(w)
        self.edit_house.setPlaceholderText("H.No / Building / Flat No.")
        col_left.addRow("House / Building:", self.edit_house)

        self.edit_address = QTextEdit(w)
        self.edit_address.setMaximumHeight(64)
        col_left.addRow("Full Address / Landmark:", self.edit_address)

        self.edit_email = QLineEdit(w)
        col_left.addRow("Email Address:", self.edit_email)

        # Column Right
        col_right = QFormLayout()
        col_right.setSpacing(12)

        self.edit_mobile = QLineEdit(w)
        mobile_regex = QRegularExpression(r"^\d{0,10}$")
        self.edit_mobile.setValidator(QRegularExpressionValidator(mobile_regex, self.edit_mobile))
        col_right.addRow("Mobile Number *:", self.edit_mobile)

        self.edit_age = QSpinBox(w)
        self.edit_age.setRange(0, 120)
        self.edit_age.setSpecialValueText("Unspecified")
        col_right.addRow("Age (Years):", self.edit_age)

        self.combo_village = QComboBox(w)
        self.combo_village.addItems(PERNEM_VILLAGES)
        col_right.addRow("Village *:", self.combo_village)

        self.edit_vaddo = QLineEdit(w)
        self.edit_vaddo.setPlaceholderText("e.g. Deulwada, Madhlawada, Khorlim")
        col_right.addRow("Vaddo / Vado:", self.edit_vaddo)

        self.edit_booth = QLineEdit(w)
        self.edit_booth.setPlaceholderText("e.g. Booth 12 - GPS Morjim")
        col_right.addRow("Booth Name / No.:", self.edit_booth)

        pin_box = QHBoxLayout()
        self.edit_pincode = QLineEdit(w)
        pin_regex = QRegularExpression(r"^\d{0,6}$")
        self.edit_pincode.setValidator(QRegularExpressionValidator(pin_regex, self.edit_pincode))
        self.edit_taluka = QLineEdit("Pernem", w)
        self.edit_taluka.setReadOnly(True)
        self.edit_taluka.setStyleSheet("background-color: #F1F5F9; color: #475569;")
        pin_box.addWidget(self.edit_pincode, 1)
        pin_box.addWidget(QLabel("Taluka:"))
        pin_box.addWidget(self.edit_taluka, 1)
        col_right.addRow("Pincode / Taluka:", pin_box)

        self.edit_alt_mobile = QLineEdit(w)
        self.edit_alt_mobile.setValidator(QRegularExpressionValidator(mobile_regex, self.edit_alt_mobile))
        col_right.addRow("Alternate Mobile:", self.edit_alt_mobile)

        grid.addLayout(col_left, 1)
        grid.addLayout(col_right, 1)
        return w

    def _build_education_tab(self) -> QWidget:
        w = QWidget()
        grid = QHBoxLayout(w)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(20)

        col_left = QFormLayout()
        col_left.setSpacing(12)

        self.combo_qual = QComboBox(w)
        self.combo_qual.addItems([""] + QUALIFICATION_LEVELS)
        col_left.addRow("Highest Qualification:", self.combo_qual)

        self.edit_degree = QLineEdit(w)
        col_left.addRow("Degree / Course:", self.edit_degree)

        self.edit_specialisation = QLineEdit(w)
        col_left.addRow("Specialisation:", self.edit_specialisation)

        self.edit_institution = QLineEdit(w)
        col_left.addRow("Institution Name:", self.edit_institution)

        col_right = QFormLayout()
        col_right.setSpacing(12)

        self.edit_passing_year = QSpinBox(w)
        self.edit_passing_year.setRange(1950, 2035)
        self.edit_passing_year.setSpecialValueText("Unspecified")
        col_right.addRow("Passing Year:", self.edit_passing_year)

        self.edit_add_qual = QLineEdit(w)
        col_right.addRow("Additional Qual:", self.edit_add_qual)

        self.edit_certs = QLineEdit(w)
        col_right.addRow("Certifications:", self.edit_certs)

        self.edit_skills = QLineEdit(w)
        col_right.addRow("Recorded Skills:", self.edit_skills)

        grid.addLayout(col_left, 1)
        grid.addLayout(col_right, 1)
        return w

    def _build_employment_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        self.status_selector = EmploymentStatusSelector(w)
        self.status_selector.status_changed.connect(self._toggle_employment_views)
        layout.addWidget(self.status_selector)

        # Employed
        self.box_employed = QGroupBox("Employed Details", w)
        emp_form = QFormLayout(self.box_employed)
        emp_form.setSpacing(10)
        self.combo_emp_category = QComboBox(w)
        self.combo_emp_category.addItems(["Private", "Government"])
        self.edit_emp_org = QLineEdit(w)
        self.edit_emp_role = QLineEdit(w)
        self.edit_emp_loc = QLineEdit(w)
        self.edit_emp_exp = QDoubleSpinBox(w)
        self.edit_emp_exp.setRange(0, 70)
        self.edit_emp_exp.setDecimals(1)
        self.edit_emp_prev = QLineEdit(w)
        self.edit_emp_salary = QDoubleSpinBox(w)
        self.edit_emp_salary.setRange(0, 10000000)
        self.edit_emp_salary.setSpecialValueText("Optional")

        emp_form.addRow("Sector Type:", self.combo_emp_category)
        emp_form.addRow("Organisation / Dept:", self.edit_emp_org)
        emp_form.addRow("Designation / Role:", self.edit_emp_role)
        emp_form.addRow("Work Location:", self.edit_emp_loc)
        emp_form.addRow("Years of Experience:", self.edit_emp_exp)
        emp_form.addRow("Previous Experience:", self.edit_emp_prev)
        emp_form.addRow("Current Salary (₹):", self.edit_emp_salary)
        layout.addWidget(self.box_employed)

        # Unemployed
        self.box_unemployed = QGroupBox("Unemployed Details", w)
        unemp_form = QFormLayout(self.box_unemployed)
        unemp_form.setSpacing(10)

        # Unemployed Previous Work Experience
        self.combo_unemp_has_exp = QComboBox(w)
        self.combo_unemp_has_exp.addItems([
            "Fresher (No Previous Work Experience)",
            "Experienced (Has Previous Work Experience)"
        ])
        self.combo_unemp_has_exp.currentIndexChanged.connect(lambda idx: self.box_unemp_exp_fields.setVisible(idx == 1))

        self.box_unemp_exp_fields = QWidget(self.box_unemployed)
        f_unemp_exp = QFormLayout(self.box_unemp_exp_fields)
        f_unemp_exp.setContentsMargins(0, 0, 0, 0)
        f_unemp_exp.setSpacing(10)

        self.edit_unemp_exp = QDoubleSpinBox(w)
        self.edit_unemp_exp.setRange(0, 70)
        self.edit_unemp_exp.setDecimals(1)
        self.edit_unemp_exp.setSuffix(" yrs")
        f_unemp_exp.addRow("Years of Experience:", self.edit_unemp_exp)

        self.edit_unemp_prev = QLineEdit(w)
        self.edit_unemp_prev.setPlaceholderText("Previous organisations, roles, or designations held")
        f_unemp_exp.addRow("Previous Organisation / Role:", self.edit_unemp_prev)

        unemp_form.addRow("Previous Experience Status:", self.combo_unemp_has_exp)
        unemp_form.addRow(self.box_unemp_exp_fields)
        self.box_unemp_exp_fields.hide()

        self.combo_govt_applied = QComboBox(w)
        self.combo_govt_applied.addItems(["Never Applied for Government Job", "Applied for Government Employment"])
        self.combo_govt_applied.currentIndexChanged.connect(lambda idx: self.box_govt_fields.setVisible(idx == 1))

        self.box_govt_fields = QWidget(self.box_unemployed)
        f_govt = QFormLayout(self.box_govt_fields)
        f_govt.setContentsMargins(0, 0, 0, 0)
        f_govt.setSpacing(10)

        self.edit_govt_post = QLineEdit(w)
        self.edit_govt_dept = QLineEdit(w)
        self.combo_govt_status = QComboBox(w)
        self.combo_govt_status.addItems([""] + GOVT_RESULT_STATUSES)

        f_govt.addRow("Post / Exam Applied:", self.edit_govt_post)
        f_govt.addRow("Department / Org:", self.edit_govt_dept)
        f_govt.addRow("Result Status:", self.combo_govt_status)

        unemp_form.addRow("Government Status:", self.combo_govt_applied)
        unemp_form.addRow(self.box_govt_fields)
        layout.addWidget(self.box_unemployed)

        # Self-Employed
        self.box_self_emp = QGroupBox("Self-Employed Details", w)
        self_form = QFormLayout(self.box_self_emp)
        self_form.setSpacing(10)
        self.edit_self_nature = QLineEdit(w)
        self.edit_self_loc = QLineEdit(w)
        self.edit_self_income = QDoubleSpinBox(w)
        self.edit_self_income.setRange(0, 10000000)
        self.edit_self_income.setSpecialValueText("Optional")

        self_form.addRow("Nature of Business:", self.edit_self_nature)
        self_form.addRow("Business Location:", self.edit_self_loc)
        self_form.addRow("Approx Monthly Income (₹):", self.edit_self_income)
        layout.addWidget(self.box_self_emp)

        # Student
        self.box_student = QGroupBox("Student Details", w)
        stud_form = QFormLayout(self.box_student)
        stud_form.setSpacing(10)
        self.edit_stud_course = QLineEdit(w)
        self.edit_stud_inst = QLineEdit(w)
        self.combo_stud_job = QComboBox(w)
        self.combo_stud_job.addItems(["Yes", "No"])

        stud_form.addRow("Current Course:", self.edit_stud_course)
        stud_form.addRow("Institution Name:", self.edit_stud_inst)
        stud_form.addRow("Interested in Employment:", self.combo_stud_job)
        layout.addWidget(self.box_student)

        self._toggle_employment_views("UNEMPLOYED")
        return w

    def _build_preferences_tab(self) -> QWidget:
        w = QWidget()
        grid = QHBoxLayout(w)
        grid.setContentsMargins(16, 16, 16, 16)
        grid.setSpacing(20)

        col_left = QFormLayout()
        col_left.setSpacing(12)

        self.combo_pref_sector = QComboBox(w)
        self.combo_pref_sector.addItems([""] + JOB_SECTORS)
        col_left.addRow("Preferred Sector:", self.combo_pref_sector)

        self.edit_pref_role = QLineEdit(w)
        col_left.addRow("Preferred Role:", self.edit_pref_role)

        self.edit_pref_loc = QLineEdit(w)
        col_left.addRow("Preferred Location:", self.edit_pref_loc)

        self.combo_relocate = QComboBox(w)
        self.combo_relocate.addItems(["No", "Yes"])
        col_left.addRow("Willing to Relocate:", self.combo_relocate)

        col_right = QFormLayout()
        col_right.setSpacing(12)

        self.combo_pref_type = QComboBox(w)
        self.combo_pref_type.addItems(EMPLOYMENT_TYPES)
        col_right.addRow("Employment Type:", self.combo_pref_type)

        self.edit_pref_lang = QLineEdit(w)
        col_right.addRow("Languages Known:", self.edit_pref_lang)

        self.edit_pref_remarks = QTextEdit(w)
        self.edit_pref_remarks.setMaximumHeight(64)
        col_right.addRow("Additional Remarks:", self.edit_pref_remarks)

        grid.addLayout(col_left, 1)
        grid.addLayout(col_right, 1)
        return w

    def _build_documents_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        info = QLabel(
            "Track candidate document availability for job eligibility and readiness analysis.\n"
            "Privacy Directive: Sensitive ID numbers (Aadhaar, PAN) are NEVER stored or shared.",
            w
        )
        info.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(info)

        self.default_doc_types = [
            "15-Year Residence Certificate",
            "Employment Exchange Registration Card (Goa)",
            "10th / SSC Marksheet & Certificate",
            "12th / HSSC Marksheet & Certificate",
            "Degree / Diploma / ITI Certificate",
            "Birth Certificate",
            "Resume / Biodata",
            "Driving Licence",
            "Caste / EWS / PwD Certificate",
            "Passport Size Photos"
        ]

        self.doc_widgets = {}
        grid = QGridLayout()
        grid.setSpacing(10)
        grid.setContentsMargins(0, 6, 0, 6)
        grid.setColumnStretch(0, 4)
        grid.setColumnStretch(1, 2)
        grid.setColumnStretch(2, 4)

        h1 = QLabel("<b>Document Type</b>")
        h2 = QLabel("<b>Document Status</b>")
        h3 = QLabel("<b>Reference / Notes (No ID numbers)</b>")
        h1.setStyleSheet("color: #1E293B; font-size: 13px; font-weight: 700;")
        h2.setStyleSheet("color: #1E293B; font-size: 13px; font-weight: 700;")
        h3.setStyleSheet("color: #1E293B; font-size: 13px; font-weight: 700;")
        grid.addWidget(h1, 0, 0)
        grid.addWidget(h2, 0, 1)
        grid.addWidget(h3, 0, 2)

        row_idx = 1
        for dt in self.default_doc_types:
            lbl = QLabel(dt)
            lbl.setStyleSheet("font-size: 13px; font-weight: 500; color: #1E293B;")
            lbl.setMinimumWidth(280)

            combo = QComboBox()
            combo.setMinimumWidth(150)
            combo.view().setTextElideMode(Qt.ElideNone)
            combo.addItems(DOCUMENT_STATUSES)
            combo.setCurrentText("Missing")

            edit_note = QLineEdit()
            edit_note.setMinimumWidth(220)
            edit_note.setPlaceholderText("Optional notes or ack ref")

            grid.addWidget(lbl, row_idx, 0)
            grid.addWidget(combo, row_idx, 1)
            grid.addWidget(edit_note, row_idx, 2)
            self.doc_widgets[dt] = {"status": combo, "notes": edit_note}
            row_idx += 1

        layout.addLayout(grid)
        layout.addStretch()
        return w

    def _build_consent_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(14)

        info = QLabel(
            "Controlled Candidate Sharing: Candidates will ONLY be matched and shared with verified employers "
            "if explicit consent is granted. Recruiter access is logged in the immutable audit trail.",
            w
        )
        info.setStyleSheet("color: #0369A1; background-color: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 6px; padding: 12px; font-size: 12px;")
        layout.addWidget(info)

        form = QFormLayout()
        form.setSpacing(14)

        self.combo_consent_status = QComboBox(w)
        self.combo_consent_status.addItems(["Not Asked", "Consented", "Declined", "Withdrawn"])
        form.addRow("Consent Status:", self.combo_consent_status)

        self.combo_consent_method = QComboBox(w)
        self.combo_consent_method.addItems(["In-Person Form", "Phone/SMS", "Digital Consent"])
        form.addRow("Consent Method:", self.combo_consent_method)

        self.edit_consent_notes = QLineEdit(w)
        self.edit_consent_notes.setPlaceholderText("e.g. Consented for verified Pernem / Mopa airport vacancies")
        form.addRow("Consent Notes:", self.edit_consent_notes)

        layout.addLayout(form)
        layout.addStretch()
        return w

    def _toggle_employment_views(self, status: str):
        self.box_employed.setVisible(status == "EMPLOYED")
        self.box_unemployed.setVisible(status == "UNEMPLOYED")
        self.box_self_emp.setVisible(status == "SELF_EMPLOYED")
        self.box_student.setVisible(status == "STUDENT")

    def _populate_fields(self):
        c = self.candidate
        self.edit_id.setText(c.candidate_id)
        idx = self.combo_intake_office.findData(getattr(c, "intake_office", "Pernem") or "Pernem")
        self.combo_intake_office.setCurrentIndex(idx if idx >= 0 else 0)
        self.edit_name.setText(c.full_name)
        self.dob_picker.set_date_iso(c.dob)
        if c.age is not None:
            self.edit_age.setValue(c.age)
        self.combo_gender.setCurrentText(c.gender or "")
        self.combo_village.setCurrentText(c.village)
        self.edit_taluka.setText(c.taluka)
        self.edit_pincode.setText(c.pincode)
        self.edit_address.setText(c.address)
        self.edit_mobile.setText(c.mobile)
        self.edit_alt_mobile.setText(c.alternate_mobile)
        self.edit_email.setText(c.email)

        # Granular location
        loc = repository.get_candidate_location(c.candidate_id)
        if loc:
            self.edit_house.setText(loc.house_building)
            self.edit_vaddo.setText(loc.vaddo)
            self.edit_booth.setText(loc.booth)

        # Education
        edu = c.education
        self.combo_qual.setCurrentText(edu.highest_qualification)
        self.edit_degree.setText(edu.degree_course)
        self.edit_specialisation.setText(edu.specialisation)
        self.edit_institution.setText(edu.institution)
        if edu.passing_year:
            self.edit_passing_year.setValue(edu.passing_year)
        self.edit_add_qual.setText(edu.additional_qualifications)
        self.edit_certs.setText(edu.certifications)
        self.edit_skills.setText(edu.skills)

        # Employment
        emp = c.employment
        self.status_selector.set_status(emp.status or "UNEMPLOYED")

        self.combo_emp_category.setCurrentText(emp.category or "Private")
        self.edit_emp_org.setText(emp.department_company)
        self.edit_emp_role.setText(emp.designation)
        self.edit_emp_loc.setText(emp.work_location)
        self.edit_emp_exp.setValue(emp.years_experience or 0.0)
        self.edit_emp_prev.setText(emp.previous_experience)
        if emp.current_salary:
            self.edit_emp_salary.setValue(emp.current_salary)

        applied = emp.govt_applied
        self.combo_govt_applied.setCurrentIndex(1 if applied else 0)
        self.box_govt_fields.setVisible(applied)
        self.edit_govt_post.setText(emp.govt_post_exam)
        self.edit_govt_dept.setText(emp.govt_department)
        self.combo_govt_status.setCurrentText(emp.govt_result_status)

        has_unemp_exp = bool((emp.years_experience and emp.years_experience > 0) or (emp.previous_experience and emp.previous_experience.strip()))
        self.combo_unemp_has_exp.setCurrentIndex(1 if has_unemp_exp else 0)
        self.box_unemp_exp_fields.setVisible(has_unemp_exp)
        self.edit_unemp_exp.setValue(emp.years_experience or 0.0)
        self.edit_unemp_prev.setText(emp.previous_experience or "")

        self.edit_self_nature.setText(emp.self_emp_business_nature)
        self.edit_self_loc.setText(emp.self_emp_location)
        if emp.self_emp_monthly_income:
            self.edit_self_income.setValue(emp.self_emp_monthly_income)

        self.edit_stud_course.setText(emp.student_current_course)
        self.edit_stud_inst.setText(emp.student_institution)
        self.combo_stud_job.setCurrentText("Yes" if emp.student_interested_in_employment else "No")

        pref = c.preferences
        self.combo_pref_sector.setCurrentText(pref.preferred_sector)
        self.edit_pref_role.setText(pref.preferred_role)
        self.edit_pref_loc.setText(pref.preferred_location)
        self.combo_relocate.setCurrentText("Yes" if pref.willing_to_relocate else "No")
        self.combo_pref_type.setCurrentText(pref.preferred_employment_type)
        self.edit_pref_lang.setText(pref.languages_known)
        self.edit_pref_remarks.setText(pref.remarks)

        # Document inventory
        docs = repository.get_candidate_documents(c.candidate_id)
        doc_map = {d.document_type: d for d in docs}
        for dt, w_dict in self.doc_widgets.items():
            if dt in doc_map:
                w_dict["status"].setCurrentText(doc_map[dt].status)
                w_dict["notes"].setText(doc_map[dt].notes)

        # Consent
        consent = repository.get_candidate_consent(c.candidate_id)
        if consent:
            self.combo_consent_status.setCurrentText(consent.consent_status or "Not Asked")
            self.combo_consent_method.setCurrentText(consent.consent_method or "In-Person Form")
            self.edit_consent_notes.setText(consent.consent_notes or "")

    def _on_save(self):
        status = self.status_selector.get_status()

        if status == "EMPLOYED":
            years_exp = self.edit_emp_exp.value()
        elif status == "UNEMPLOYED":
            years_exp = self.edit_unemp_exp.value() if self.combo_unemp_has_exp.currentIndex() == 1 else 0.0
        else:
            years_exp = 0.0

        payload = {
            "full_name": self.edit_name.text().strip(),
            "mobile": self.edit_mobile.text().strip(),
            "alternate_mobile": self.edit_alt_mobile.text().strip(),
            "email": self.edit_email.text().strip(),
            "village": self.combo_village.currentText(),
            "pincode": self.edit_pincode.text().strip(),
            "employment_status": status,
            "age": self.edit_age.value() if self.edit_age.value() > 0 else None,
            "years_experience": years_exp
        }

        is_valid, errors = validate_candidate_form(payload)
        if not is_valid:
            err_msg = "\n".join(f"• {msg}" for msg in errors.values())
            QMessageBox.warning(self, "Validation Incomplete", f"Please check the required fields:\n\n{err_msg}")
            return

        c = self.candidate
        c.intake_office = self.combo_intake_office.currentData() or "Pernem"
        c.full_name = payload["full_name"]
        c.dob = self.dob_picker.get_date_iso()
        c.age = payload["age"]
        c.gender = self.combo_gender.currentText()
        c.village = payload["village"]
        c.taluka = self.edit_taluka.text().strip() or "Pernem"
        c.pincode = payload["pincode"]
        c.address = self.edit_address.toPlainText().strip()
        c.mobile = payload["mobile"]
        c.alternate_mobile = payload["alternate_mobile"]
        c.email = payload["email"]

        # Education
        c.education.highest_qualification = self.combo_qual.currentText()
        c.education.degree_course = self.edit_degree.text().strip()
        c.education.specialisation = self.edit_specialisation.text().strip()
        c.education.institution = self.edit_institution.text().strip()
        c.education.passing_year = self.edit_passing_year.value() if self.edit_passing_year.value() > 0 else None
        c.education.additional_qualifications = self.edit_add_qual.text().strip()
        c.education.certifications = self.edit_certs.text().strip()
        c.education.skills = self.edit_skills.text().strip()

        # Employment
        c.employment.status = status
        if status == "EMPLOYED":
            c.employment.category = self.combo_emp_category.currentText()
            c.employment.department_company = self.edit_emp_org.text().strip()
            c.employment.designation = self.edit_emp_role.text().strip()
            c.employment.work_location = self.edit_emp_loc.text().strip()
            c.employment.years_experience = self.edit_emp_exp.value()
            c.employment.previous_experience = self.edit_emp_prev.text().strip()
            c.employment.current_salary = self.edit_emp_salary.value() if self.edit_emp_salary.value() > 0 else None
        elif status == "UNEMPLOYED":
            if self.combo_unemp_has_exp.currentIndex() == 1:
                c.employment.years_experience = self.edit_unemp_exp.value()
                c.employment.previous_experience = self.edit_unemp_prev.text().strip()
            else:
                c.employment.years_experience = 0.0
                c.employment.previous_experience = ""

            applied = (self.combo_govt_applied.currentIndex() == 1)
            c.employment.govt_applied = applied
            c.employment.govt_post_exam = self.edit_govt_post.text().strip() if applied else ""
            c.employment.govt_department = self.edit_govt_dept.text().strip() if applied else ""
            c.employment.govt_result_status = self.combo_govt_status.currentText() if applied else ""
        elif status == "SELF_EMPLOYED":
            c.employment.self_emp_business_nature = self.edit_self_nature.text().strip()
            c.employment.self_emp_location = self.edit_self_loc.text().strip()
            c.employment.self_emp_monthly_income = self.edit_self_income.value() if self.edit_self_income.value() > 0 else None
        elif status == "STUDENT":
            c.employment.student_current_course = self.edit_stud_course.text().strip()
            c.employment.student_institution = self.edit_stud_inst.text().strip()
            c.employment.student_interested_in_employment = (self.combo_stud_job.currentText() == "Yes")

        # Preferences
        c.preferences.preferred_sector = self.combo_pref_sector.currentText()
        c.preferences.preferred_role = self.edit_pref_role.text().strip()
        c.preferences.preferred_location = self.edit_pref_loc.text().strip()
        c.preferences.willing_to_relocate = (self.combo_relocate.currentText() == "Yes")
        c.preferences.preferred_employment_type = self.combo_pref_type.currentText()
        c.preferences.languages_known = self.edit_pref_lang.text().strip()
        c.preferences.remarks = self.edit_pref_remarks.toPlainText().strip()

        try:
            repository.update_candidate(c)

            # Location update
            loc = CandidateLocation(
                candidate_id=c.candidate_id,
                house_building=self.edit_house.text().strip(),
                vaddo=self.edit_vaddo.text().strip(),
                village=c.village,
                booth=self.edit_booth.text().strip(),
                taluka=c.taluka,
                pincode=c.pincode,
                full_address_landmark=c.address
            )
            repository.save_candidate_location(loc)

            # Document inventory update
            docs_to_save = []
            for dt, widgets in self.doc_widgets.items():
                st = widgets["status"].currentText()
                notes = widgets["notes"].text().strip()
                cat = DocumentManager.get_category_for_type(dt)
                docs_to_save.append(CandidateDocument(
                    candidate_id=c.candidate_id,
                    document_type=dt,
                    document_category=cat,
                    status=st,
                    notes=notes
                ))
            repository.save_candidate_documents_bulk(c.candidate_id, docs_to_save)

            # Consent update
            c_status = self.combo_consent_status.currentText()
            consent = CandidateConsent(
                candidate_id=c.candidate_id,
                consent_status=c_status,
                consent_date=datetime.now().strftime("%Y-%m-%d") if c_status == "Consented" else "",
                consent_method=self.combo_consent_method.currentText() if c_status == "Consented" else "",
                consent_notes=self.edit_consent_notes.text().strip()
            )
            repository.save_candidate_consent(consent)

            signals.candidate_updated.emit(c.candidate_id)
            QMessageBox.information(
                self,
                "Candidate Updated",
                f"Candidate {c.candidate_id} updated successfully in local database!\nStatus marked as PENDING for cloud backup."
            )
            self.accept()
        except Exception as e:
            logger.error("Could not update candidate: %s", e)
            QMessageBox.critical(self, "Database Error", f"Failed to save updates: {e}")
