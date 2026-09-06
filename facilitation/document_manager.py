"""
Document Manager for Pedne Sewa Trust - Employment Facilitation Platform.
Maintains canonical document catalog, calculates document readiness scores,
and ensures strict data privacy (never exposes sensitive ID numbers).
"""

from typing import List, Dict, Any, Optional
from datetime import datetime
from models.facilitation import CandidateDocument

# Canonical Document Categories & Types
DOCUMENT_CATALOG = {
    "Identity": [
        "Aadhaar Card",
        "PAN Card",
        "Voter ID (EPIC)",
        "Passport",
        "Driving Licence"
    ],
    "Residence": [
        "15-Year Residence Certificate",
        "Domicile Certificate"
    ],
    "Education": [
        "10th / SSC Marksheet & Certificate",
        "12th / HSSC Marksheet & Certificate",
        "ITI Certificate",
        "Diploma Certificate",
        "Degree Marksheet & Certificate",
        "Post-Graduate Degree / Marksheet",
        "Other Educational / Vocational Certificate"
    ],
    "Employment": [
        "Employment Exchange Registration Card (Goa)",
        "Experience Certificates",
        "Relieving Letter",
        "Salary Slips"
    ],
    "Government & Reservation": [
        "Caste Certificate (SC/ST/OBC)",
        "EWS Certificate",
        "PwD / Disability Certificate",
        "Ex-Servicemen Certificate"
    ],
    "Other": [
        "Birth Certificate",
        "Character Certificate",
        "Police Clearance Certificate",
        "Passport Size Photos",
        "Resume / Biodata"
    ]
}

DOCUMENT_STATUSES = [
    "Available",
    "Missing",
    "Applied/Awaiting",
    "Expired",
    "Needs Renewal",
    "Needs Verification",
    "Not Applicable"
]

# Essential documents required for Government jobs in Goa
GOVT_ESSENTIAL_DOCUMENTS = [
    "15-Year Residence Certificate",
    "Employment Exchange Registration Card (Goa)",
    "Birth Certificate",
    "10th / SSC Marksheet & Certificate"
]

# Essential documents for Private sector jobs
PRIVATE_ESSENTIAL_DOCUMENTS = [
    "Resume / Biodata",
    "10th / SSC Marksheet & Certificate",
    "Passport Size Photos"
]


class DocumentManager:
    """Manages document inventory, verification, readiness scoring, and privacy."""

    @staticmethod
    def get_catalog() -> Dict[str, List[str]]:
        """Returns the full catalog of supported documents by category."""
        return DOCUMENT_CATALOG

    @staticmethod
    def get_all_document_types() -> List[str]:
        """Returns flat list of all document types."""
        types = []
        for cat, items in DOCUMENT_CATALOG.items():
            types.extend(items)
        return types

    @staticmethod
    def get_category_for_type(doc_type: str) -> str:
        """Finds category for a given document type."""
        for cat, items in DOCUMENT_CATALOG.items():
            if doc_type in items:
                return cat
        return "Other"

    @staticmethod
    def calculate_readiness(
        documents: List[CandidateDocument],
        target_sector: str = "GOVERNMENT"
    ) -> Dict[str, Any]:
        """
        Calculates document readiness score and gap analysis.
        Distinguishes 'document exists' from 'document is valid and available'.
        """
        doc_map = {d.document_type: d for d in documents}

        required = (
            GOVT_ESSENTIAL_DOCUMENTS
            if target_sector.upper() == "GOVERNMENT"
            else PRIVATE_ESSENTIAL_DOCUMENTS
        )

        available_count = 0
        missing = []
        awaiting = []
        expired = []
        needs_renewal = []

        for req in required:
            doc = doc_map.get(req)
            if not doc:
                missing.append(req)
                continue

            status = doc.status.strip().title()
            if status == "Available":
                # Check if expired by date
                if doc.expiry_date:
                    try:
                        exp_dt = datetime.fromisoformat(doc.expiry_date[:10])
                        if exp_dt < datetime.now():
                            expired.append(req)
                            continue
                    except Exception:
                        pass
                available_count += 1
            elif status in ("Applied/Awaiting", "Awaiting"):
                awaiting.append(req)
            elif status == "Expired":
                expired.append(req)
            elif status == "Needs Renewal":
                needs_renewal.append(req)
            elif status == "Not Applicable":
                # Skip from required denominator
                pass
            else:
                missing.append(req)

        total_req = len(required)
        score = (available_count / total_req * 100.0) if total_req > 0 else 0.0

        is_ready = (available_count == total_req)

        return {
            "target_sector": target_sector,
            "readiness_score": round(score, 1),
            "is_ready": is_ready,
            "available_count": available_count,
            "total_required": total_req,
            "missing": missing,
            "awaiting": awaiting,
            "expired": expired,
            "needs_renewal": needs_renewal
        }

    @staticmethod
    def check_job_document_eligibility(
        candidate_documents: List[CandidateDocument],
        required_job_documents: List[str]
    ) -> Dict[str, Any]:
        """
        Evaluates candidate's document inventory against a specific job's requirements.
        Returns matched documents and blocking gaps.
        """
        doc_map = {d.document_type: d for d in candidate_documents}
        matched = []
        gaps = []

        for req in required_job_documents:
            doc = doc_map.get(req)
            if not doc:
                gaps.append(f"Missing {req}")
                continue

            status = doc.status.strip().title()
            if status == "Available":
                if doc.expiry_date:
                    try:
                        if datetime.fromisoformat(doc.expiry_date[:10]) < datetime.now():
                            gaps.append(f"{req} is Expired")
                            continue
                    except Exception:
                        pass
                matched.append(req)
            elif status in ("Applied/Awaiting", "Awaiting"):
                gaps.append(f"{req} Applied/Awaiting (not yet available)")
            elif status == "Expired":
                gaps.append(f"{req} is Expired")
            elif status == "Needs Renewal":
                gaps.append(f"{req} Needs Renewal")
            elif status == "Needs Verification":
                gaps.append(f"{req} Needs Verification")
            else:
                gaps.append(f"Missing {req}")

        has_all_documents = len(gaps) == 0
        return {
            "has_all_documents": has_all_documents,
            "matched_documents": matched,
            "document_gaps": gaps
        }


document_manager = DocumentManager()
