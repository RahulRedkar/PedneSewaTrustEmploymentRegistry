"""
Recruiter Service for Pedne Sewa Trust - Employment Facilitation Platform.
Enforces strict service-layer data protection:
1. Only VERIFIED recruiters can receive candidate data (UNVERIFIED/BLOCKED rejected with audit event).
2. Only candidates with explicit 'Consented' status can be exported (Declined/Withdrawn/Not Asked strictly blocked).
3. 3-Tier exports (Level 1 Anonymised Shortlist vs Level 2 Recruiter Profile; Level 3 Sensitive documents strictly blocked).
4. Full audit logging of all export and sharing events.
"""

import csv
import io
from typing import List, Dict, Any, Optional
from datetime import datetime
from models.candidate import Candidate
from models.facilitation import Recruiter, RecruiterCandidateShare
from database.repository import repository
from utils.logger import logger


class RecruiterService:
    """Service layer for recruiter interactions, verification enforcement, and controlled exports."""

    def __init__(self, repo=None):
        self.repo = repo or repository

    def export_candidates_for_recruiter(
        self,
        recruiter_id: str,
        candidate_ids: List[str],
        export_mode: str = "Level 1 Shortlist",  # "Level 1 Shortlist" or "Level 2 Profile"
        job_id: Optional[str] = None,
        actor: str = "Operator",
        notes: str = ""
    ) -> Dict[str, Any]:
        """
        Executes controlled recruiter export with strict verification and consent checks.
        Raises PermissionError if recruiter is not VERIFIED.
        Filters out candidates lacking explicit 'Consented' status.
        Logs all actions to audit_log.
        """
        # 1. Verify Recruiter
        recruiter = self.repo.get_recruiter(recruiter_id)
        if not recruiter:
            self.repo.log_audit(
                "Recruiter", recruiter_id, "EXPORT_BLOCKED",
                "", "", actor, "Recruiter not found"
            )
            raise ValueError(f"Recruiter '{recruiter_id}' does not exist.")

        if recruiter.verification_status != "VERIFIED":
            self.repo.log_audit(
                "Recruiter", recruiter_id, "EXPORT_BLOCKED",
                recruiter.verification_status, "REJECTED", actor,
                f"Export attempt blocked: recruiter is {recruiter.verification_status}"
            )
            raise PermissionError(
                f"Access Denied: Recruiter '{recruiter.company}' is {recruiter.verification_status}. "
                "Only VERIFIED recruiters can receive candidate profiles."
            )

        # 2. Filter Candidates by Explicit Consent
        consented_candidates: List[Candidate] = []
        excluded_candidates: List[Dict[str, str]] = []

        for cid in candidate_ids:
            cand = self.repo.get_candidate(cid)
            if not cand or cand.is_deleted:
                continue

            consent = self.repo.get_candidate_consent(cid)
            consent_status = consent.consent_status if consent else (cand.consent.consent_status if cand.consent else "Not Asked")

            if consent_status == "Consented":
                consented_candidates.append(cand)
            else:
                excluded_candidates.append({
                    "candidate_id": cid,
                    "full_name": cand.full_name,
                    "reason": f"Consent status is '{consent_status}' (Requires 'Consented')"
                })
                self.repo.log_audit(
                    "Candidate", cid, "EXPORT_EXCLUDED_NO_CONSENT",
                    consent_status, "EXCLUDED", actor,
                    f"Candidate excluded from export to {recruiter.company} due to non-consented status"
                )

        if not consented_candidates:
            return {
                "success": False,
                "message": "No candidates eligible for export. All selected candidates lacked 'Consented' status.",
                "exported_count": 0,
                "consented_candidates": [],
                "excluded_candidates": excluded_candidates,
                "csv_data": "",
                "records": []
            }

        # 3. Generate Tiered Export Data
        records = []
        now = datetime.now().isoformat()

        for cand in consented_candidates:
            loc = cand.location
            vaddo = loc.vaddo if loc else ""
            village = cand.village or (loc.village if loc else "")

            if export_mode == "Level 1 Shortlist":
                # Level 1: Anonymised Shortlist (No direct contact, no full address)
                records.append({
                    "Reference ID": cand.candidate_id,
                    "Age": cand.age if cand.age is not None else "",
                    "Gender": cand.gender or "",
                    "Village": village,
                    "Vaddo": vaddo,
                    "Highest Qualification": cand.education.highest_qualification or "",
                    "Course / Degree": cand.education.degree_course or "",
                    "Specialisation": cand.education.specialisation or "",
                    "Skills": ", ".join(filter(None, [cand.education.skills, cand.preferences.skills_list])),
                    "Total Experience (Years)": cand.employment.years_experience or cand.preferences.total_experience_years or 0.0,
                    "Current Status": cand.employment.status,
                    "Preferred Role": cand.preferences.preferred_role or "",
                    "Preferred Location": cand.preferences.preferred_location or "",
                    "Notice / Availability": cand.preferences.preferred_employment_type or "Full-Time"
                })
            else:
                # Level 2: Recruiter Profile (Contact details included for verified recruiters)
                # Sensitive Level 3 items (Aadhaar, PAN, Bank info) are strictly excluded!
                records.append({
                    "Candidate ID": cand.candidate_id,
                    "Full Name": cand.full_name,
                    "Mobile": cand.mobile,
                    "Alternate Mobile": cand.alternate_mobile or "",
                    "Email": cand.email or "",
                    "Village": village,
                    "Vaddo": vaddo,
                    "Age": cand.age if cand.age is not None else "",
                    "Gender": cand.gender or "",
                    "Highest Qualification": cand.education.highest_qualification or "",
                    "Degree / Course": cand.education.degree_course or "",
                    "Institution": cand.education.institution or "",
                    "Passing Year": cand.education.passing_year or "",
                    "Skills": ", ".join(filter(None, [cand.education.skills, cand.preferences.skills_list])),
                    "Certifications": ", ".join(filter(None, [cand.education.certifications, cand.preferences.certifications_list])),
                    "Employment Status": cand.employment.status,
                    "Years Experience": cand.employment.years_experience or cand.preferences.total_experience_years or 0.0,
                    "Previous Experience": cand.employment.previous_experience or cand.preferences.previous_employers or "",
                    "Preferred Role": cand.preferences.preferred_role or "",
                    "Preferred Location": cand.preferences.preferred_location or "",
                    "Languages Known": cand.preferences.languages_known or ""
                })

            # 4. Record share and audit trail
            share = RecruiterCandidateShare(
                recruiter_id=recruiter_id,
                candidate_id=cand.candidate_id,
                job_id=job_id,
                shared_date=now,
                export_mode=export_mode,
                consent_status_at_sharing="Consented",
                shared_by=actor,
                notes=notes
            )
            self.repo.record_candidate_share(share)

        # 5. Format CSV
        csv_buffer = io.StringIO()
        if records:
            writer = csv.DictWriter(csv_buffer, fieldnames=list(records[0].keys()))
            writer.writeheader()
            writer.writerows(records)

        return {
            "success": True,
            "message": f"Successfully exported {len(records)} candidate(s) under '{export_mode}'.",
            "recruiter_company": recruiter.company,
            "export_mode": export_mode,
            "exported_count": len(records),
            "consented_candidates": [c.candidate_id for c in consented_candidates],
            "excluded_candidates": excluded_candidates,
            "csv_data": csv_buffer.getvalue(),
            "records": records
        }


recruiter_service = RecruiterService()
