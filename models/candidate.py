"""
Domain models for Pedne Sewa Trust - Employment Registry.
Defines entity dataclasses for Candidates, Education, Employment, Preferences,
and serialization helpers for SQLite, CSV, and Google Sheets flat 42-column format.
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, Dict, Any, List
from datetime import datetime
from models.facilitation import CandidateLocation, CandidateConsent


@dataclass
class Education:
    highest_qualification: str = ""
    degree_course: str = ""
    specialisation: str = ""
    institution: str = ""
    passing_year: Optional[int] = None
    additional_qualifications: str = ""
    certifications: str = ""
    skills: str = ""


@dataclass
class Employment:
    status: str = "UNEMPLOYED"  # EMPLOYED, UNEMPLOYED, SELF_EMPLOYED, STUDENT
    category: str = ""          # Government, Private
    department_company: str = ""
    designation: str = ""
    work_location: str = ""
    years_experience: float = 0.0
    previous_experience: str = ""
    current_salary: Optional[float] = None

    # Unemployed - Govt Application details
    govt_applied: bool = False
    govt_post_exam: str = ""
    govt_department: str = ""
    govt_app_year: Optional[int] = None
    govt_result_status: str = ""
    govt_remarks: str = ""

    # Self-Employed details
    self_emp_business_nature: str = ""
    self_emp_location: str = ""
    self_emp_years_active: Optional[float] = None
    self_emp_employees_count: Optional[int] = None
    self_emp_monthly_income: Optional[float] = None

    # Student details
    student_current_course: str = ""
    student_institution: str = ""
    student_expected_year: Optional[int] = None
    student_interested_in_employment: bool = True


@dataclass
class EmploymentPreferences:
    preferred_sector: str = ""
    preferred_role: str = ""
    preferred_location: str = ""
    willing_to_relocate: bool = False
    preferred_employment_type: str = "Full-Time"
    languages_known: str = ""
    skills_list: str = ""
    certifications_list: str = ""
    total_experience_years: float = 0.0
    previous_employers: str = ""
    remarks: str = ""


@dataclass
class Candidate:
    candidate_id: str = ""
    full_name: str = ""
    dob: str = ""            # ISO YYYY-MM-DD
    age: Optional[int] = None
    gender: str = ""
    address: str = ""
    village: str = ""
    taluka: str = "Pernem"
    pincode: str = ""
    mobile: str = ""
    alternate_mobile: str = ""
    email: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sync_status: str = "PENDING"  # PENDING, SYNCED, FAILED
    last_synced_at: Optional[str] = None
    is_deleted: bool = False
    is_demo: bool = False

    education: Education = field(default_factory=Education)
    employment: Employment = field(default_factory=Employment)
    preferences: EmploymentPreferences = field(default_factory=EmploymentPreferences)
    location: Optional[CandidateLocation] = None
    consent: Optional[CandidateConsent] = None

    def to_flat_dict(self) -> Dict[str, Any]:
        """Flattens complete candidate object into a single dictionary matching the 42-column schema."""
        reg_date = self.created_at[:10] if self.created_at else ""

        # Self-employment details combined string for sheets
        self_emp_summary = ""
        if self.employment.status == "SELF_EMPLOYED":
            parts = []
            if self.employment.self_emp_business_nature:
                parts.append(f"Nature: {self.employment.self_emp_business_nature}")
            if self.employment.self_emp_location:
                parts.append(f"Loc: {self.employment.self_emp_location}")
            if self.employment.self_emp_years_active is not None:
                parts.append(f"Active: {self.employment.self_emp_years_active}y")
            if self.employment.self_emp_monthly_income is not None:
                parts.append(f"Income: ₹{self.employment.self_emp_monthly_income:.0f}")
            self_emp_summary = "; ".join(parts)
        elif self.employment.status == "STUDENT":
            parts = []
            if self.employment.student_current_course:
                parts.append(f"Course: {self.employment.student_current_course}")
            if self.employment.student_institution:
                parts.append(f"Inst: {self.employment.student_institution}")
            if self.employment.student_expected_year:
                parts.append(f"Batch: {self.employment.student_expected_year}")
            parts.append(f"Job Interested: {'Yes' if self.employment.student_interested_in_employment else 'No'}")
            self_emp_summary = "; ".join(parts)

        # Combined skills and certs
        all_skills = ", ".join(filter(None, [self.education.skills, self.preferences.skills_list]))
        all_certs = ", ".join(filter(None, [self.education.certifications, self.preferences.certifications_list]))

        return {
            "Candidate ID": self.candidate_id,
            "Registration Date": reg_date,
            "Full Name": self.full_name,
            "DOB": self.dob or "",
            "Age": self.age if self.age is not None else "",
            "Gender": self.gender or "",
            "Address": self.address or "",
            "Village": self.village,
            "Taluka": self.taluka,
            "Pincode": self.pincode or "",
            "Mobile": self.mobile,
            "Alternate Mobile": self.alternate_mobile or "",
            "Email": self.email or "",
            "Highest Qualification": self.education.highest_qualification or "",
            "Course": self.education.degree_course or "",
            "Specialisation": self.education.specialisation or "",
            "Institution": self.education.institution or "",
            "Passing Year": self.education.passing_year or "",
            "Skills": all_skills,
            "Certifications": all_certs,
            "Employment Status": self.employment.status,
            "Employment Category": self.employment.category or "",
            "Organisation": self.employment.department_company or "",
            "Designation": self.employment.designation or "",
            "Work Location": self.employment.work_location or "",
            "Years Experience": self.employment.years_experience if self.employment.years_experience else "",
            "Previous Experience": self.employment.previous_experience or "",
            "Applied Government Job": "Yes" if self.employment.govt_applied else "No",
            "Government Application/Post": self.employment.govt_post_exam or "",
            "Government Application Year": self.employment.govt_app_year or "",
            "Government Result Status": self.employment.govt_result_status or "",
            "Self Employment Details": self_emp_summary,
            "Preferred Sector": self.preferences.preferred_sector or "",
            "Preferred Role": self.preferences.preferred_role or "",
            "Preferred Location": self.preferences.preferred_location or "",
            "Willing To Relocate": "Yes" if self.preferences.willing_to_relocate else "No",
            "Preferred Employment Type": self.preferences.preferred_employment_type or "",
            "Languages": self.preferences.languages_known or "",
            "Remarks": self.preferences.remarks or self.employment.govt_remarks or "",
            "Created At": self.created_at,
            "Updated At": self.updated_at,
            "Sync Status": self.sync_status
        }

    def to_backup_dict(self) -> Dict[str, Any]:
        """
        Returns a clean, flattened dictionary for Google Sheets cloud backup.
        Every candidate field has its own dedicated property with no serialization
        or nested wrapper objects. Sensitive Aadhaar and PAN numbers are excluded.
        """
        reg_date = self.created_at[:10] if self.created_at else ""

        # Self-employment / Student summary
        self_emp_summary = ""
        if self.employment.status == "SELF_EMPLOYED":
            parts = []
            if self.employment.self_emp_business_nature:
                parts.append(f"Nature: {self.employment.self_emp_business_nature}")
            if self.employment.self_emp_location:
                parts.append(f"Loc: {self.employment.self_emp_location}")
            if self.employment.self_emp_years_active is not None:
                parts.append(f"Active: {self.employment.self_emp_years_active}y")
            if self.employment.self_emp_monthly_income is not None:
                parts.append(f"Income: ₹{self.employment.self_emp_monthly_income:.0f}")
            self_emp_summary = "; ".join(parts)
        elif self.employment.status == "STUDENT":
            parts = []
            if self.employment.student_current_course:
                parts.append(f"Course: {self.employment.student_current_course}")
            if self.employment.student_institution:
                parts.append(f"Inst: {self.employment.student_institution}")
            if self.employment.student_expected_year:
                parts.append(f"Batch: {self.employment.student_expected_year}")
            parts.append(f"Job Interested: {'Yes' if self.employment.student_interested_in_employment else 'No'}")
            self_emp_summary = "; ".join(parts)

        all_skills = ", ".join(filter(None, [self.education.skills, self.preferences.skills_list]))
        all_certs = ", ".join(filter(None, [self.education.certifications, self.preferences.certifications_list]))

        # Safely extract optional CandidateLocation fields (canonical field in CandidateLocation is 'booth')
        loc_vaddo = ""
        loc_booth = ""
        if self.location:
            v_val = getattr(self.location, "vaddo", "")
            loc_vaddo = str(v_val).strip() if v_val is not None else ""
            b_val = getattr(self.location, "booth", None)
            if b_val is None:
                b_val = getattr(self.location, "polling_booth", "")
            loc_booth = str(b_val).strip() if b_val is not None else ""

        # Safely extract optional CandidateConsent fields
        con_status = ""
        con_date = ""
        if self.consent:
            s_val = getattr(self.consent, "consent_status", "")
            con_status = str(s_val).strip() if s_val is not None else ""
            d_val = getattr(self.consent, "consent_date", "")
            con_date = str(d_val).strip() if d_val is not None else ""

        return {
            "candidate_id": self.candidate_id,
            "registration_date": reg_date,
            "full_name": self.full_name,
            "dob": self.dob or "",
            "age": self.age if self.age is not None else "",
            "gender": self.gender or "",
            "address": self.address or "",
            "village": self.village or "",
            "vaddo": loc_vaddo,
            "polling_booth": loc_booth,
            "taluka": self.taluka or "Pernem",
            "pincode": self.pincode or "",
            "mobile": self.mobile or "",
            "alternate_mobile": self.alternate_mobile or "",
            "email": self.email or "",
            "highest_qualification": self.education.highest_qualification or "",
            "course": self.education.degree_course or "",
            "specialisation": self.education.specialisation or "",
            "institution": self.education.institution or "",
            "passing_year": self.education.passing_year or "",
            "skills": all_skills,
            "certifications": all_certs,
            "employment_status": self.employment.status or "",
            "employment_category": self.employment.category or "",
            "organisation": self.employment.department_company or "",
            "designation": self.employment.designation or "",
            "work_location": self.employment.work_location or "",
            "years_experience": self.employment.years_experience if self.employment.years_experience else "",
            "previous_experience": self.employment.previous_experience or "",
            "applied_government_job": "Yes" if self.employment.govt_applied else "No",
            "government_post": self.employment.govt_post_exam or "",
            "government_app_year": self.employment.govt_app_year or "",
            "government_result_status": self.employment.govt_result_status or "",
            "self_employment_details": self_emp_summary,
            "preferred_sector": self.preferences.preferred_sector or "",
            "preferred_role": self.preferences.preferred_role or "",
            "preferred_location": self.preferences.preferred_location or "",
            "willing_to_relocate": "Yes" if self.preferences.willing_to_relocate else "No",
            "preferred_employment_type": self.preferences.preferred_employment_type or "",
            "languages": self.preferences.languages_known or "",
            "recruiter_consent_status": con_status,
            "recruiter_consent_date": con_date,
            "remarks": self.preferences.remarks or self.employment.govt_remarks or "",
            "created_at": self.created_at or "",
            "updated_at": self.updated_at or ""
        }

    def to_row_list(self) -> List[Any]:
        """Returns 42 values in exact canonical order for Google Sheets and CSV."""
        flat = self.to_flat_dict()
        from app.constants import GOOGLE_SHEETS_COLUMNS
        return [flat.get(col, "") for col in GOOGLE_SHEETS_COLUMNS]

