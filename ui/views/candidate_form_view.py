"""
Candidate Intake Form View for Pedne Sewa Trust - Employment Registry.
Implements structured data collection with native Qt input widgets,
calendar popup for Date of Birth, 2-column desktop layout,
dynamic employment classification sub-panels, and local SQLite persistence.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QFormLayout, QScrollArea, QMessageBox,
    QGroupBox, QSpinBox, QDoubleSpinBox, QFrame, QTextEdit, QGridLayout
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QRegularExpressionValidator
from PySide6.QtCore import QRegularExpression

from datetime import datetime
from models.candidate import Candidate, Education, Employment, EmploymentPreferences
from models.facilitation import CandidateLocation, CandidateDocument, CandidateConsent
from facilitation.document_manager import DocumentManager, DOCUMENT_STATUSES
from app.constants import (
    PERNEM_VILLAGES,
    QUALIFICATION_LEVELS,
    GOVT_RESULT_STATUSES,
    JOB_SECTORS,
    EMPLOYMENT_TYPES,
    OFFICE_PERNEM,
    OFFICE_KORGAO
)
from app.config import config

from app.signals import signals
from database.repository import repository
from utils.validators import validate_candidate_form
from ui.dialogs.duplicate_dialog import DuplicateCandidateDialog
from ui.components.dob_picker import DateOfBirthPicker
from ui.components.status_selector import EmploymentStatusSelector
from ui.components.icons import AppIcons
from utils.logger import logger


class CandidateFormView(QWidget):
    """Structured 2-column Candidate Registration Intake Form."""

    review_candidate_requested = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header Title Area
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Candidate Registration Intake Form", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        sub_lbl = QLabel("Fields marked with (*) are required. Records are safely stored in local SQLite first.", self)
        sub_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        main_layout.addLayout(title_box)

        # 2. Scroll Area for 2-column Form
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        form_content = QWidget()
        self.form_layout = QVBoxLayout(form_content)
        self.form_layout.setContentsMargins(0, 0, 0, 0)
        self.form_layout.setSpacing(16)

        # Section 1: Personal Details (2-column desktop layout)
        self._build_personal_section()

        # Section 2: Education Details
        self._build_education_section()

        # Section 3: Employment Classification
        self._build_employment_section()

        # Section 4: Employment Preferences & Skills
        self._build_preferences_section()

        # Section 5: Document Readiness & Inventory
        self._build_document_section()

        # Section 6: Recruiter Consent & Facilitation
        self._build_consent_section()

        scroll.setWidget(form_content)
        main_layout.addWidget(scroll)


        # 3. Action Buttons Footer
        btn_bar = QFrame(self)
        btn_bar.setProperty("class", "ContentCard")
        bb_layout = QHBoxLayout(btn_bar)
        bb_layout.setContentsMargins(12, 10, 12, 10)

        self.btn_reset = QPushButton("Clear Form", btn_bar)
        self.btn_reset.setProperty("class", "SecondaryButton")
        self.btn_reset.setIcon(AppIcons.clear())
        self.btn_reset.setCursor(Qt.PointingHandCursor)
        self.btn_reset.clicked.connect(self.reset_form)

        lbl_required = QLabel("* Required field", btn_bar)
        lbl_required.setStyleSheet("color: #DC2626; font-size: 12px; font-weight: 600;")

        self.btn_save = QPushButton("Save Candidate", btn_bar)
        self.btn_save.setProperty("class", "PrimaryButton")
        self.btn_save.setIcon(AppIcons.save())
        self.btn_save.setCursor(Qt.PointingHandCursor)
        self.btn_save.setMinimumHeight(40)
        self.btn_save.clicked.connect(self._on_save_clicked)

        bb_layout.addWidget(self.btn_reset)
        bb_layout.addSpacing(16)
        bb_layout.addWidget(lbl_required)
        bb_layout.addStretch()
        bb_layout.addWidget(self.btn_save)
        main_layout.addWidget(btn_bar)

    def _build_personal_section(self):
        group = QGroupBox("1. Personal Details")
        grid = QHBoxLayout(group)
        grid.setContentsMargins(16, 18, 16, 16)
        grid.setSpacing(20)

        # Column Left
        col_left = QFormLayout()
        col_left.setSpacing(12)

        # Intake Office (Pernem or Korgao -> generates PST vs KPST)
        self.combo_intake_office = QComboBox(group)
        self.combo_intake_office.addItem(f"{OFFICE_PERNEM} (ID Prefix: PST)", OFFICE_PERNEM)
        self.combo_intake_office.addItem(f"{OFFICE_KORGAO} (ID Prefix: KPST)", OFFICE_KORGAO)
        default_off = config.get("default_office", OFFICE_PERNEM)
        idx = self.combo_intake_office.findData(default_off)
        if idx >= 0:
            self.combo_intake_office.setCurrentIndex(idx)
        col_left.addRow("Intake Office *:", self.combo_intake_office)

        # Full Name (Required)
        self.edit_name = QLineEdit(group)
        self.edit_name.setPlaceholderText("Candidate's full legal name")
        col_left.addRow("Full Name *:", self.edit_name)

        # Date of Birth (Native Calendar popup, dd/MM/yyyy)
        self.dob_picker = DateOfBirthPicker(group)
        self.dob_picker.age_calculated.connect(self._on_age_auto_calculated)
        col_left.addRow("Date of Birth:", self.dob_picker)

        # Gender (Structured combo)
        self.combo_gender = QComboBox(group)
        self.combo_gender.addItems(["", "Male", "Female", "Other", "Prefer not to say"])
        col_left.addRow("Gender:", self.combo_gender)

        # House / Building
        self.edit_house = QLineEdit(group)
        self.edit_house.setPlaceholderText("H.No / Building / Flat No.")
        col_left.addRow("House / Building:", self.edit_house)

        # Full Address / Landmark
        self.edit_address = QTextEdit(group)
        self.edit_address.setPlaceholderText("Landmark, Street, Area notes")
        self.edit_address.setMaximumHeight(64)
        col_left.addRow("Full Address / Landmark:", self.edit_address)

        # Email
        self.edit_email = QLineEdit(group)
        self.edit_email.setPlaceholderText("candidate@example.com (optional)")
        col_left.addRow("Email Address:", self.edit_email)

        # Column Right
        col_right = QFormLayout()
        col_right.setSpacing(12)

        # Mobile Number (Required, 10-digit Indian validator)
        self.edit_mobile = QLineEdit(group)
        self.edit_mobile.setPlaceholderText("10-digit Indian mobile number")
        mobile_regex = QRegularExpression(r"^\d{0,10}$")
        self.edit_mobile.setValidator(QRegularExpressionValidator(mobile_regex, self.edit_mobile))
        col_right.addRow("Mobile Number *:", self.edit_mobile)

        # Age (Years) - Auto-calculated or manual entry
        self.edit_age = QSpinBox(group)
        self.edit_age.setRange(0, 120)
        self.edit_age.setSpecialValueText("Unspecified")
        col_right.addRow("Age (Years):", self.edit_age)

        # Village (Required, pre-populated)
        self.combo_village = QComboBox(group)
        self.combo_village.addItems(PERNEM_VILLAGES)
        col_right.addRow("Village *:", self.combo_village)

        # Vaddo / Vado (Independent searchable field)
        self.edit_vaddo = QLineEdit(group)
        self.edit_vaddo.setPlaceholderText("e.g. Deulwada, Madhlawada, Khorlim")
        col_right.addRow("Vaddo / Vado:", self.edit_vaddo)

        # Polling Booth Name / Number (Independent searchable field)
        self.edit_booth = QLineEdit(group)
        self.edit_booth.setPlaceholderText("e.g. Booth 12 - GPS Morjim")
        col_right.addRow("Booth Name / No.:", self.edit_booth)

        # Pincode & Taluka
        pin_box = QHBoxLayout()
        self.edit_pincode = QLineEdit(group)
        self.edit_pincode.setPlaceholderText("6-digit Pincode")
        pin_regex = QRegularExpression(r"^\d{0,6}$")
        self.edit_pincode.setValidator(QRegularExpressionValidator(pin_regex, self.edit_pincode))
        self.edit_taluka = QLineEdit("Pernem", group)
        self.edit_taluka.setReadOnly(True)
        self.edit_taluka.setStyleSheet("background-color: #F1F5F9; color: #475569;")
        pin_box.addWidget(self.edit_pincode, 1)
        pin_box.addWidget(QLabel("Taluka:"))
        pin_box.addWidget(self.edit_taluka, 1)
        col_right.addRow("Pincode / Taluka:", pin_box)


        # Alternate Mobile
        self.edit_alt_mobile = QLineEdit(group)
        self.edit_alt_mobile.setPlaceholderText("Backup contact number (optional)")
        self.edit_alt_mobile.setValidator(QRegularExpressionValidator(mobile_regex, self.edit_alt_mobile))
        col_right.addRow("Alternate Mobile:", self.edit_alt_mobile)

        grid.addLayout(col_left, 1)
        grid.addLayout(col_right, 1)
        self.form_layout.addWidget(group)

    def _build_education_section(self):
        group = QGroupBox("2. Education Details")
        grid = QHBoxLayout(group)
        grid.setContentsMargins(16, 18, 16, 16)
        grid.setSpacing(20)

        # Column Left
        col_left = QFormLayout()
        col_left.setSpacing(12)

        self.combo_qual = QComboBox(group)
        self.combo_qual.addItems([""] + QUALIFICATION_LEVELS)
        col_left.addRow("Highest Qualification:", self.combo_qual)

        self.edit_degree = QLineEdit(group)
        self.edit_degree.setPlaceholderText("e.g. B.Com, ITI Electrician, B.Sc Computer Science")
        col_left.addRow("Degree / Course:", self.edit_degree)

        self.edit_specialisation = QLineEdit(group)
        self.edit_specialisation.setPlaceholderText("e.g. Accounting, Electrical, Software")
        col_left.addRow("Specialisation:", self.edit_specialisation)

        self.edit_institution = QLineEdit(group)
        self.edit_institution.setPlaceholderText("College or University name")
        col_left.addRow("Institution / College:", self.edit_institution)

        # Column Right
        col_right = QFormLayout()
        col_right.setSpacing(12)

        self.edit_passing_year = QSpinBox(group)
        self.edit_passing_year.setRange(1950, 2035)
        self.edit_passing_year.setValue(1950)
        self.edit_passing_year.setSpecialValueText("Unspecified")
        col_right.addRow("Passing Year:", self.edit_passing_year)

        self.edit_add_qual = QLineEdit(group)
        self.edit_add_qual.setPlaceholderText("Any additional diplomas or certificates")
        col_right.addRow("Additional Qual:", self.edit_add_qual)

        self.edit_certs = QLineEdit(group)
        self.edit_certs.setPlaceholderText("e.g. Tally, AutoCAD, Welding, Barista, AWS")
        col_right.addRow("Certifications:", self.edit_certs)

        self.edit_edu_skills = QLineEdit(group)
        self.edit_edu_skills.setPlaceholderText("Key vocational or technical skills")
        col_right.addRow("Recorded Skills:", self.edit_edu_skills)

        grid.addLayout(col_left, 1)
        grid.addLayout(col_right, 1)
        self.form_layout.addWidget(group)

    def _build_employment_section(self):
        group = QGroupBox("3. Employment Classification *")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(14)

        # Distinct Segmented Status Cards
        self.status_selector = EmploymentStatusSelector(group)
        self.status_selector.status_changed.connect(self._on_status_changed)
        layout.addWidget(self.status_selector)

        # --- Dynamic Sub-panel A: Employed ---
        self.panel_employed = QFrame(group)
        self.panel_employed.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px;")
        f_emp = QFormLayout(self.panel_employed)
        f_emp.setSpacing(10)

        self.combo_emp_cat = QComboBox(self.panel_employed)
        self.combo_emp_cat.addItems(["Private", "Government"])
        f_emp.addRow("Sector Type:", self.combo_emp_cat)

        self.edit_emp_org = QLineEdit(self.panel_employed)
        self.edit_emp_org.setPlaceholderText("Department / Company / Organisation")
        f_emp.addRow("Organisation / Dept:", self.edit_emp_org)

        self.edit_emp_role = QLineEdit(self.panel_employed)
        self.edit_emp_role.setPlaceholderText("e.g. Junior Engineer, Clerk, Store Manager")
        f_emp.addRow("Designation / Role:", self.edit_emp_role)

        self.edit_emp_loc = QLineEdit(self.panel_employed)
        self.edit_emp_loc.setPlaceholderText("e.g. Panaji, Tuem, Mopa, Mapusa")
        f_emp.addRow("Work Location:", self.edit_emp_loc)

        self.edit_emp_years = QDoubleSpinBox(self.panel_employed)
        self.edit_emp_years.setRange(0, 60)
        self.edit_emp_years.setDecimals(1)
        f_emp.addRow("Years of Experience:", self.edit_emp_years)

        self.edit_emp_prev = QLineEdit(self.panel_employed)
        self.edit_emp_prev.setPlaceholderText("Previous organisations or roles held")
        f_emp.addRow("Previous Experience:", self.edit_emp_prev)

        self.edit_emp_salary = QDoubleSpinBox(self.panel_employed)
        self.edit_emp_salary.setRange(0, 10000000)
        self.edit_emp_salary.setSpecialValueText("Optional")
        f_emp.addRow("Current Salary (₹ Monthly):", self.edit_emp_salary)

        layout.addWidget(self.panel_employed)

        # --- Dynamic Sub-panel B: Unemployed ---
        self.panel_unemployed = QFrame(group)
        self.panel_unemployed.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px;")
        f_unemp = QFormLayout(self.panel_unemployed)
        f_unemp.setSpacing(10)

        # Previous Work Experience
        self.combo_unemp_has_exp = QComboBox(self.panel_unemployed)
        self.combo_unemp_has_exp.addItems([
            "Fresher (No Previous Work Experience)",
            "Experienced (Has Previous Work Experience)"
        ])
        self.combo_unemp_has_exp.currentIndexChanged.connect(self._on_unemp_exp_changed)
        f_unemp.addRow("Previous Experience Status:", self.combo_unemp_has_exp)

        self.box_unemp_exp_fields = QWidget(self.panel_unemployed)
        f_unemp_exp = QFormLayout(self.box_unemp_exp_fields)
        f_unemp_exp.setContentsMargins(0, 0, 0, 0)
        f_unemp_exp.setSpacing(10)

        self.edit_unemp_years = QDoubleSpinBox(self.box_unemp_exp_fields)
        self.edit_unemp_years.setRange(0, 60)
        self.edit_unemp_years.setDecimals(1)
        self.edit_unemp_years.setSuffix(" yrs")
        f_unemp_exp.addRow("Years of Experience:", self.edit_unemp_years)

        self.edit_unemp_prev = QLineEdit(self.box_unemp_exp_fields)
        self.edit_unemp_prev.setPlaceholderText("Previous organisations, roles, or designations held")
        f_unemp_exp.addRow("Previous Organisation / Role:", self.edit_unemp_prev)

        f_unemp.addRow(self.box_unemp_exp_fields)
        self.box_unemp_exp_fields.hide()

        # Government Status
        self.combo_unemp_applied = QComboBox(self.panel_unemployed)
        self.combo_unemp_applied.addItems(["Never Applied for Government Job", "Applied for Government Employment"])
        self.combo_unemp_applied.currentIndexChanged.connect(self._on_govt_applied_changed)
        f_unemp.addRow("Government Status:", self.combo_unemp_applied)

        self.box_govt_fields = QWidget(self.panel_unemployed)
        f_govt = QFormLayout(self.box_govt_fields)
        f_govt.setContentsMargins(0, 0, 0, 0)
        f_govt.setSpacing(10)

        self.edit_govt_post = QLineEdit(self.box_govt_fields)
        self.edit_govt_post.setPlaceholderText("Post / Exam Name (e.g. GPSC CCE, LDC, Sub-Inspector)")
        f_govt.addRow("Post / Exam Applied For:", self.edit_govt_post)

        self.edit_govt_dept = QLineEdit(self.box_govt_fields)
        self.edit_govt_dept.setPlaceholderText("e.g. Revenue Department, PWD, Electricity")
        f_govt.addRow("Department / Organisation:", self.edit_govt_dept)

        self.edit_govt_year = QSpinBox(self.box_govt_fields)
        self.edit_govt_year.setRange(2010, 2035)
        self.edit_govt_year.setValue(2025)
        f_govt.addRow("Application Year:", self.edit_govt_year)

        self.combo_govt_status = QComboBox(self.box_govt_fields)
        self.combo_govt_status.addItems(GOVT_RESULT_STATUSES)
        f_govt.addRow("Current Result Status:", self.combo_govt_status)

        self.edit_govt_remarks = QLineEdit(self.box_govt_fields)
        self.edit_govt_remarks.setPlaceholderText("e.g. Awaiting final merit list / Interview scheduled")
        f_govt.addRow("Remarks:", self.edit_govt_remarks)

        f_unemp.addRow(self.box_govt_fields)
        self.box_govt_fields.hide()  # Hidden by default when "Never Applied"
        layout.addWidget(self.panel_unemployed)

        # --- Dynamic Sub-panel C: Self-Employed ---
        self.panel_self_emp = QFrame(group)
        self.panel_self_emp.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px;")
        f_self = QFormLayout(self.panel_self_emp)
        f_self.setSpacing(10)

        self.edit_self_nature = QLineEdit(self.panel_self_emp)
        self.edit_self_nature.setPlaceholderText("e.g. Retail Grocery, Taxi / Rental, Electrical Works, Farming")
        f_self.addRow("Nature of Business / Work:", self.edit_self_nature)

        self.edit_self_loc = QLineEdit(self.panel_self_emp)
        self.edit_self_loc.setPlaceholderText("e.g. Pernem Market, Mandrem, Arambol Beach Road")
        f_self.addRow("Business Location:", self.edit_self_loc)

        self.edit_self_years = QDoubleSpinBox(self.panel_self_emp)
        self.edit_self_years.setRange(0, 60)
        self.edit_self_years.setDecimals(1)
        f_self.addRow("Years Active:", self.edit_self_years)

        self.edit_self_emp_count = QSpinBox(self.panel_self_emp)
        self.edit_self_emp_count.setRange(0, 500)
        self.edit_self_emp_count.setSpecialValueText("Optional")
        f_self.addRow("Number of Employees:", self.edit_self_emp_count)

        self.edit_self_income = QDoubleSpinBox(self.panel_self_emp)
        self.edit_self_income.setRange(0, 10000000)
        self.edit_self_income.setSpecialValueText("Optional")
        f_self.addRow("Approx Monthly Income (₹):", self.edit_self_income)

        layout.addWidget(self.panel_self_emp)

        # --- Dynamic Sub-panel D: Student ---
        self.panel_student = QFrame(group)
        self.panel_student.setStyleSheet("background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 6px; padding: 12px;")
        f_stud = QFormLayout(self.panel_student)
        f_stud.setSpacing(10)

        self.edit_stud_course = QLineEdit(self.panel_student)
        self.edit_stud_course.setPlaceholderText("Current course of study (e.g. Final Year B.Com)")
        f_stud.addRow("Current Course:", self.edit_stud_course)

        self.edit_stud_inst = QLineEdit(self.panel_student)
        self.edit_stud_inst.setPlaceholderText("College or University name")
        f_stud.addRow("Institution:", self.edit_stud_inst)

        self.edit_stud_exp_year = QSpinBox(self.panel_student)
        self.edit_stud_exp_year.setRange(2024, 2035)
        self.edit_stud_exp_year.setValue(2026)
        f_stud.addRow("Expected Completion Year:", self.edit_stud_exp_year)

        self.combo_stud_job = QComboBox(self.panel_student)
        self.combo_stud_job.addItems(["Yes", "No"])
        f_stud.addRow("Interested in Employment:", self.combo_stud_job)

        layout.addWidget(self.panel_student)

        # Set default visible sub-panel
        self._on_status_changed("UNEMPLOYED")
        self.form_layout.addWidget(group)

    def _build_preferences_section(self):
        group = QGroupBox("4. Preferences & Skills")
        grid = QHBoxLayout(group)
        grid.setContentsMargins(16, 18, 16, 16)
        grid.setSpacing(20)

        # Column Left
        col_left = QFormLayout()
        col_left.setSpacing(12)

        self.combo_pref_sector = QComboBox(group)
        self.combo_pref_sector.addItems([""] + JOB_SECTORS)
        col_left.addRow("Preferred Job Sector:", self.combo_pref_sector)

        self.edit_pref_role = QLineEdit(group)
        self.edit_pref_role.setPlaceholderText("e.g. Accountant, Front Desk, Supervisor, Driver")
        col_left.addRow("Preferred Job Role:", self.edit_pref_role)

        self.edit_pref_loc = QLineEdit(group)
        self.edit_pref_loc.setPlaceholderText("e.g. Pernem, Mopa Airport, Mapusa, Panaji")
        col_left.addRow("Preferred Location:", self.edit_pref_loc)

        self.combo_relocate = QComboBox(group)
        self.combo_relocate.addItems(["No", "Yes"])
        col_left.addRow("Willing to Relocate:", self.combo_relocate)

        # Column Right
        col_right = QFormLayout()
        col_right.setSpacing(12)

        self.combo_pref_type = QComboBox(group)
        self.combo_pref_type.addItems(EMPLOYMENT_TYPES)
        col_right.addRow("Employment Type:", self.combo_pref_type)

        self.edit_languages = QLineEdit(group)
        self.edit_languages.setText("Konkani, Marathi, English")
        col_right.addRow("Languages Known:", self.edit_languages)

        self.edit_total_exp = QDoubleSpinBox(group)
        self.edit_total_exp.setRange(0, 60)
        self.edit_total_exp.setDecimals(1)
        col_right.addRow("Total Work Experience (Yrs):", self.edit_total_exp)

        self.edit_remarks = QTextEdit(group)
        self.edit_remarks.setPlaceholderText("Specific employment requirements or notes")
        self.edit_remarks.setMaximumHeight(64)
        col_right.addRow("Additional Remarks:", self.edit_remarks)

        grid.addLayout(col_left, 1)
        grid.addLayout(col_right, 1)
        self.form_layout.addWidget(group)

    def _build_document_section(self):
        group = QGroupBox("5. Document Readiness")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "Track candidate document availability for job eligibility & readiness analysis.\n"
            "Privacy Directive: Sensitive identification numbers (Aadhaar, PAN) are NEVER stored or shared.",
            group
        )
        info_lbl.setStyleSheet("color: #475569; font-size: 12px;")
        layout.addWidget(info_lbl)

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
        h3 = QLabel("<b>Reference / Notes / Validity (No ID numbers)</b>")
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
            edit_note.setPlaceholderText("Optional notes or ack ref (never enter Aadhaar/PAN)")

            grid.addWidget(lbl, row_idx, 0)
            grid.addWidget(combo, row_idx, 1)
            grid.addWidget(edit_note, row_idx, 2)

            self.doc_widgets[dt] = {"status": combo, "notes": edit_note}
            row_idx += 1

        layout.addLayout(grid)
        self.form_layout.addWidget(group)

    def _build_consent_section(self):
        group = QGroupBox("6. Recruiter Consent & Facilitation")
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(12)

        info_lbl = QLabel(
            "Controlled Candidate Sharing: Candidates will ONLY be matched and shared with verified employers "
            "if explicit consent is granted. Recruiter access is logged in the immutable audit trail.",
            group
        )
        info_lbl.setStyleSheet("color: #0369A1; background-color: #F0F9FF; border: 1px solid #BAE6FD; border-radius: 6px; padding: 10px; font-size: 12px;")
        layout.addWidget(info_lbl)

        form = QFormLayout()
        form.setSpacing(12)

        self.combo_consent_status = QComboBox(group)
        self.combo_consent_status.addItems(["Not Asked", "Consented", "Declined", "Withdrawn"])
        form.addRow("Consent Status:", self.combo_consent_status)

        self.combo_consent_method = QComboBox(group)
        self.combo_consent_method.addItems(["In-Person Form", "Phone/SMS", "Digital Consent"])
        form.addRow("Consent Method:", self.combo_consent_method)

        self.edit_consent_notes = QLineEdit(group)
        self.edit_consent_notes.setPlaceholderText("e.g. Consented for verified Pernem / Mopa airport vacancies")
        form.addRow("Consent Notes:", self.edit_consent_notes)

        layout.addLayout(form)
        self.form_layout.addWidget(group)

    def _on_age_auto_calculated(self, age: int):
        self.edit_age.setValue(age)

    def _on_status_changed(self, status: str):
        self.panel_employed.setVisible(status == "EMPLOYED")
        self.panel_unemployed.setVisible(status == "UNEMPLOYED")
        self.panel_self_emp.setVisible(status == "SELF_EMPLOYED")
        self.panel_student.setVisible(status == "STUDENT")

    def _on_unemp_exp_changed(self, idx: int):
        self.box_unemp_exp_fields.setVisible(idx == 1)

    def _on_govt_applied_changed(self, idx: int):
        self.box_govt_fields.setVisible(idx == 1)

    def _on_save_clicked(self):
        """Validates intake form, performs duplicate check, and saves to SQLite."""
        status = self.status_selector.get_status()

        if status == "EMPLOYED":
            years_exp = self.edit_emp_years.value()
        elif status == "UNEMPLOYED":
            years_exp = self.edit_unemp_years.value() if self.combo_unemp_has_exp.currentIndex() == 1 else 0.0
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

        # 1. Validation
        is_valid, errors = validate_candidate_form(payload)
        if not is_valid:
            err_msg = "\n".join(f"• {msg}" for msg in errors.values())
            QMessageBox.warning(self, "Incomplete Details", f"Please check the required fields:\n\n{err_msg}")
            return

        # 2. Duplicate Detection
        duplicates = repository.check_duplicates(
            mobile=payload["mobile"],
            email=payload["email"],
            full_name=payload["full_name"],
            address=self.edit_address.toPlainText().strip()
        )
        if duplicates:
            dlg = DuplicateCandidateDialog(duplicates, self)
            if dlg.exec() != DuplicateCandidateDialog.Accepted:
                if dlg.selected_existing_id:
                    self.review_candidate_requested.emit(dlg.selected_existing_id)
                return

        # 3. Domain Model Construction
        cand = Candidate(
            full_name=payload["full_name"],
            dob=self.dob_picker.get_date_iso(),
            age=payload["age"],
            gender=self.combo_gender.currentText(),
            address=self.edit_address.toPlainText().strip(),
            village=payload["village"],
            taluka=self.edit_taluka.text().strip() or "Pernem",
            pincode=payload["pincode"],
            mobile=payload["mobile"],
            alternate_mobile=payload["alternate_mobile"],
            email=payload["email"],
            intake_office=self.combo_intake_office.currentData() or "Pernem"
        )

        # Attach granular Location details
        cand.location = CandidateLocation(
            candidate_id="",
            house_building=self.edit_house.text().strip(),
            vaddo=self.edit_vaddo.text().strip(),
            village=payload["village"],
            booth=self.edit_booth.text().strip(),
            taluka=self.edit_taluka.text().strip() or "Pernem",
            pincode=payload["pincode"],
            full_address_landmark=self.edit_address.toPlainText().strip()
        )

        # Attach Recruiter Consent
        c_status = self.combo_consent_status.currentText()
        cand.consent = CandidateConsent(
            candidate_id="",
            consent_status=c_status,
            consent_date=datetime.now().strftime("%Y-%m-%d") if c_status == "Consented" else "",
            consent_method=self.combo_consent_method.currentText() if c_status == "Consented" else "",
            consent_notes=self.edit_consent_notes.text().strip()
        )

        cand.education = Education(
            highest_qualification=self.combo_qual.currentText(),
            degree_course=self.edit_degree.text().strip(),
            specialisation=self.edit_specialisation.text().strip(),
            institution=self.edit_institution.text().strip(),
            passing_year=self.edit_passing_year.value() if self.edit_passing_year.value() > 0 else None,
            additional_qualifications=self.edit_add_qual.text().strip(),
            certifications=self.edit_certs.text().strip(),
            skills=self.edit_edu_skills.text().strip()
        )

        cand.employment = Employment(status=status)
        if status == "EMPLOYED":
            cand.employment.category = self.combo_emp_cat.currentText()
            cand.employment.department_company = self.edit_emp_org.text().strip()
            cand.employment.designation = self.edit_emp_role.text().strip()
            cand.employment.work_location = self.edit_emp_loc.text().strip()
            cand.employment.years_experience = self.edit_emp_years.value()
            cand.employment.previous_experience = self.edit_emp_prev.text().strip()
            cand.employment.current_salary = self.edit_emp_salary.value() if self.edit_emp_salary.value() > 0 else None
        elif status == "UNEMPLOYED":
            if self.combo_unemp_has_exp.currentIndex() == 1:
                cand.employment.years_experience = self.edit_unemp_years.value()
                cand.employment.previous_experience = self.edit_unemp_prev.text().strip()
            else:
                cand.employment.years_experience = 0.0
                cand.employment.previous_experience = ""

            applied = (self.combo_unemp_applied.currentIndex() == 1)
            cand.employment.govt_applied = applied
            if applied:
                cand.employment.govt_post_exam = self.edit_govt_post.text().strip()
                cand.employment.govt_department = self.edit_govt_dept.text().strip()
                cand.employment.govt_app_year = self.edit_govt_year.value()
                cand.employment.govt_result_status = self.combo_govt_status.currentText()
                cand.employment.govt_remarks = self.edit_govt_remarks.text().strip()
        elif status == "SELF_EMPLOYED":
            cand.employment.self_emp_business_nature = self.edit_self_nature.text().strip()
            cand.employment.self_emp_location = self.edit_self_loc.text().strip()
            cand.employment.self_emp_years_active = self.edit_self_years.value() if self.edit_self_years.value() > 0 else None
            cand.employment.self_emp_employees_count = self.edit_self_emp_count.value() if self.edit_self_emp_count.value() > 0 else None
            cand.employment.self_emp_monthly_income = self.edit_self_income.value() if self.edit_self_income.value() > 0 else None
        elif status == "STUDENT":
            cand.employment.student_current_course = self.edit_stud_course.text().strip()
            cand.employment.student_institution = self.edit_stud_inst.text().strip()
            cand.employment.student_expected_year = self.edit_stud_exp_year.value()
            cand.employment.student_interested_in_employment = (self.combo_stud_job.currentText() == "Yes")

        cand.preferences = EmploymentPreferences(
            preferred_sector=self.combo_pref_sector.currentText(),
            preferred_role=self.edit_pref_role.text().strip(),
            preferred_location=self.edit_pref_loc.text().strip(),
            willing_to_relocate=(self.combo_relocate.currentText() == "Yes"),
            preferred_employment_type=self.combo_pref_type.currentText(),
            languages_known=self.edit_languages.text().strip(),
            total_experience_years=self.edit_total_exp.value(),
            remarks=self.edit_remarks.toPlainText().strip()
        )

        # 4. Atomic Save into SQLite
        try:
            saved_candidate = repository.save_candidate(cand)
            new_id = saved_candidate.candidate_id

            # 5. Save Document Inventory
            docs_to_save = []
            for dt, widgets in self.doc_widgets.items():
                st = widgets["status"].currentText()
                notes = widgets["notes"].text().strip()
                cat = DocumentManager.get_category_for_type(dt)
                docs_to_save.append(CandidateDocument(
                    candidate_id=new_id,
                    document_type=dt,
                    document_category=cat,
                    status=st,
                    notes=notes
                ))
            if docs_to_save:
                repository.save_candidate_documents_bulk(new_id, docs_to_save)

            signals.candidate_saved.emit(new_id)
            self.reset_form()

            QMessageBox.information(
                self,
                "Candidate Registered Successfully",
                f"Candidate successfully saved to local database!\n\n"
                f"Candidate ID: {new_id}\n\n"
                f"Status: Safely stored locally (Pending background cloud sync)."
            )
        except Exception as e:
            logger.error("Failed to save candidate: %s", e)
            QMessageBox.critical(self, "Database Error", f"Failed to save candidate:\n{e}")

    def reset_form(self):
        """Clears all inputs to defaults."""
        default_off = config.get("default_office", "Pernem")
        idx = self.combo_intake_office.findData(default_off)
        self.combo_intake_office.setCurrentIndex(idx if idx >= 0 else 0)

        self.edit_name.clear()
        self.edit_mobile.clear()
        self.edit_alt_mobile.clear()
        self.edit_email.clear()
        self.combo_village.setCurrentIndex(0)
        self.dob_picker.clear()
        self.edit_age.setValue(0)
        self.combo_gender.setCurrentIndex(0)
        self.edit_house.clear()
        self.edit_address.clear()
        self.edit_vaddo.clear()
        self.edit_booth.clear()
        self.edit_pincode.clear()

        # Education
        self.combo_qual.setCurrentIndex(0)
        self.edit_degree.clear()
        self.edit_specialisation.clear()
        self.edit_institution.clear()
        self.edit_passing_year.setValue(0)
        self.edit_add_qual.clear()
        self.edit_certs.clear()
        self.edit_edu_skills.clear()

        # Employment
        self.status_selector.set_status("UNEMPLOYED")
        self.combo_unemp_has_exp.setCurrentIndex(0)
        self.box_unemp_exp_fields.hide()
        self.edit_unemp_years.setValue(0.0)
        self.edit_unemp_prev.clear()
        self.combo_unemp_applied.setCurrentIndex(0)
        self.box_govt_fields.hide()
        self.edit_govt_post.clear()
        self.edit_govt_dept.clear()
        self.edit_govt_remarks.clear()
        self.edit_emp_org.clear()
        self.edit_emp_role.clear()
        self.edit_emp_loc.clear()
        self.edit_emp_years.setValue(0.0)
        self.edit_emp_prev.clear()
        self.edit_emp_salary.setValue(0.0)
        self.edit_self_nature.clear()
        self.edit_self_loc.clear()
        self.edit_self_years.setValue(0.0)
        self.edit_self_emp_count.setValue(0)
        self.edit_self_income.setValue(0.0)
        self.edit_stud_course.clear()
        self.edit_stud_inst.clear()

        # Preferences
        self.combo_pref_sector.setCurrentIndex(0)
        self.edit_pref_role.clear()
        self.edit_pref_loc.clear()
        self.combo_relocate.setCurrentIndex(0)
        self.combo_pref_type.setCurrentIndex(0)
        self.edit_total_exp.setValue(0.0)
        self.edit_remarks.clear()

        # Documents & Consent
        if hasattr(self, "doc_widgets"):
            for widgets in self.doc_widgets.values():
                widgets["status"].setCurrentText("Missing")
                widgets["notes"].clear()
        if hasattr(self, "combo_consent_status"):
            self.combo_consent_status.setCurrentText("Not Asked")
            self.combo_consent_method.setCurrentIndex(0)
            self.edit_consent_notes.clear()
