"""
Domain models for Pedne Sewa Trust - Employment Facilitation Platform.
Defines entity dataclasses for location, document inventory, government jobs,
private jobs, recruiters, consent, multi-application history, and audit logging.
"""

from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any
from datetime import datetime


@dataclass
class CandidateLocation:
    candidate_id: str
    house_building: str = ""
    vaddo: str = ""
    village: str = ""
    booth: str = ""
    taluka: str = "Pernem"
    pincode: str = ""
    full_address_landmark: str = ""


@dataclass
class CandidateDocument:
    id: Optional[int] = None
    candidate_id: str = ""
    document_type: str = ""
    document_category: str = ""
    status: str = "Missing"  # Available, Missing, Applied/Awaiting, Expired, Needs Renewal, Needs Verification, Not Applicable
    issue_date: str = ""
    expiry_date: str = ""
    application_date: str = ""
    reference_number: str = ""
    expected_availability_date: str = ""
    verification_status: str = "Not Checked"  # Not Checked, Verified, Needs Verification
    notes: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class GovernmentJob:
    job_id: str = ""
    source: str = "GSSC"  # GSSC, GPSC, Govt of Goa Recruitment
    advertisement_number: str = ""
    department: str = ""
    post_name: str = ""
    vacancies_count: int = 1
    employment_type: str = "Regular / Permanent"
    pay_level_salary: str = ""
    minimum_qualification: str = ""
    preferred_qualification: str = ""
    experience_requirement_years: float = 0.0
    age_limit_min: int = 18
    age_limit_max: int = 45
    gender_requirement: str = "Any"
    category_reservation: str = ""
    konkani_marathi_required: str = "Konkani Essential, Marathi Desirable"
    required_documents: List[str] = field(default_factory=list)
    application_start_date: str = ""
    application_closing_date: str = ""
    application_method: str = "Online"
    official_ad_url: str = ""
    official_apply_url: str = ""
    ad_pdf_url: str = ""
    last_checked_at: str = field(default_factory=lambda: datetime.now().isoformat())
    source_last_updated_at: str = ""
    status: str = "OPEN"  # OPEN, CLOSING SOON, CLOSED, UPCOMING, UNKNOWN


@dataclass
class PrivateJob:
    job_id: str = ""
    employer: str = ""
    job_title: str = ""
    department: str = ""
    job_description: str = ""
    required_qualification: str = ""
    required_skills: str = ""
    required_experience_years: float = 0.0
    required_documents: str = ""
    location: str = "Pernem"
    salary_range: str = ""
    employment_type: str = "Full-Time"
    work_mode: str = "On-Site"
    application_deadline: str = ""
    source: str = "Curated"
    source_url: str = ""
    application_url: str = ""
    contact_person: str = ""
    contact_email: str = ""
    contact_phone: str = ""
    date_added: str = field(default_factory=lambda: datetime.now().isoformat())
    last_verified_at: str = ""
    verification_status: str = "VERIFIED"
    status: str = "ACTIVE"  # ACTIVE, CLOSING SOON, CLOSED, FILLED, UNVERIFIED


@dataclass
class Recruiter:
    recruiter_id: str = ""
    company: str = ""
    contact_person: str = ""
    designation: str = ""
    email: str = ""
    phone: str = ""
    industry: str = ""
    location: str = ""
    website: str = ""
    verification_status: str = "UNVERIFIED"  # UNVERIFIED, VERIFIED, BLOCKED
    date_added: str = field(default_factory=lambda: datetime.now().isoformat())
    last_contact_at: str = ""
    candidates_shared_count: int = 0
    notes: str = ""


@dataclass
class CandidateConsent:
    candidate_id: str = ""
    consent_status: str = "Not Asked"  # Not Asked, Consented, Declined, Withdrawn
    consent_date: str = ""
    consent_method: str = ""  # In-Person Form, Phone/SMS, Digital Consent
    consent_notes: str = ""
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class RecruiterCandidateShare:
    id: Optional[int] = None
    recruiter_id: str = ""
    candidate_id: str = ""
    job_id: Optional[str] = None
    shared_date: str = field(default_factory=lambda: datetime.now().isoformat())
    export_mode: str = "Level 1 Shortlist"  # Level 1 Shortlist, Level 2 Profile
    consent_status_at_sharing: str = ""
    shared_by: str = ""
    notes: str = ""


@dataclass
class GovernmentJobApplication:
    application_id: Optional[int] = None
    candidate_id: str = ""
    job_id: Optional[str] = None
    advertisement_number: str = ""
    post_name: str = ""
    department: str = ""
    application_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    application_status: str = "APPLIED"  # APPLIED, ADMIT_CARD_ISSUED, EXAM_ATTENDED, SELECTED, REJECTED, WITHDRAWN
    exam_date: str = ""
    result_details: str = ""
    notes: str = ""


@dataclass
class PrivateJobApplication:
    application_id: Optional[int] = None
    candidate_id: str = ""
    job_id: Optional[str] = None
    company_employer: str = ""
    job_title: str = ""
    application_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    application_method: str = "Direct"
    application_status: str = "APPLIED"  # APPLIED, SHORTLISTED, INTERVIEW_SCHEDULED, OFFER_EXTENDED, HIRED, REJECTED, WITHDRAWN
    interview_date: str = ""
    notes: str = ""


@dataclass
class AuditEntry:
    id: Optional[int] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    user_action: str = ""
    entity_type: str = ""  # Candidate, Recruiter, Job, Consent, Share
    entity_id: str = ""
    action: str = ""  # CREATE, UPDATE, DELETE, CONSENT_CHANGE, RECRUITER_VERIFIED, SHARE_EXPORT
    old_value: str = ""
    new_value: str = ""
    notes: str = ""


@dataclass
class JobMatchResult:
    job_id: str
    candidate_id: str
    job_title: str
    organization: str
    job_type: str  # Government / Private
    match_tier: str  # HIGH MATCH, MEDIUM MATCH, LOW MATCH, NOT ENOUGH INFORMATION
    score: float  # 0.0 - 100.0
    matched_criteria: List[str] = field(default_factory=list)
    missing_criteria: List[str] = field(default_factory=list)
    document_gaps: List[str] = field(default_factory=list)
    disclaimer: str = "Potential Match — Verify Eligibility Against Official Advertisement"
