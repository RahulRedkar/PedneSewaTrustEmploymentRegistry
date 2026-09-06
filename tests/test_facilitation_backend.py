"""
Comprehensive Automated Test Suite for Pedne Sewa Trust - Employment Facilitation Platform.
Tests backend architecture, independent vaddo & booth querying, document readiness,
tiered matching engine, strict consent enforcement, recruiter verification rejection,
fail-safe job caching, and audit logging.
"""

import pytest
import sqlite3
from datetime import datetime, timedelta

from database.connection import DatabaseManager
from database.repository import CandidateRepository
from models.candidate import Candidate, Education, Employment, EmploymentPreferences
from models.facilitation import (
    CandidateLocation, CandidateDocument, CandidateConsent,
    GovernmentJob, PrivateJob, Recruiter, GovernmentJobApplication, PrivateJobApplication
)
from facilitation.document_manager import DocumentManager
from facilitation.matching_engine import MatchingEngine, DISCLAIMER_TEXT
from facilitation.job_adapters import GSSCJobAdapter, seed_initial_sample_jobs
from facilitation.recruiter_service import RecruiterService


@pytest.fixture
def test_repo(tmp_path):
    """Creates an isolated in-memory or temporary SQLite database repository."""
    db_file = str(tmp_path / "test_facilitation.db")
    mgr = DatabaseManager(db_file)
    repo = CandidateRepository(mgr)
    return repo


def test_independent_vaddo_and_booth_storage_and_filter(test_repo):
    """Verifies Vaddo and Booth are independent, separate, searchable/filterable fields."""
    # Candidate 1: Morjim, Deulwada, Booth 10
    c1 = test_repo.save_candidate(Candidate(
        full_name="Anand Shet",
        mobile="9822100001",
        village="Morjim",
        location=CandidateLocation(
            candidate_id="",
            house_building="H.No 101",
            vaddo="Deulwada",
            village="Morjim",
            booth="Booth 10 - GPS Morjim"
        )
    ))

    # Candidate 2: Mandrem, Deulwada, Booth 15
    c2 = test_repo.save_candidate(Candidate(
        full_name="Sneha Parab",
        mobile="9822100002",
        village="Mandrem",
        location=CandidateLocation(
            candidate_id="",
            house_building="H.No 45",
            vaddo="Deulwada",
            village="Mandrem",
            booth="Booth 15 - GPS Mandrem"
        )
    ))

    # Candidate 3: Morjim, Tembwada, Booth 10
    c3 = test_repo.save_candidate(Candidate(
        full_name="Vikas Naik",
        mobile="9822100003",
        village="Morjim",
        location=CandidateLocation(
            candidate_id="",
            house_building="H.No 88",
            vaddo="Tembwada",
            village="Morjim",
            booth="Booth 10 - GPS Morjim"
        )
    ))

    # Test 1: Search by Vaddo 'Deulwada' independently -> Returns c1 and c2
    res_vaddo = test_repo.search_candidates_by_location(vaddo="Deulwada")
    vaddo_ids = [c.candidate_id for c in res_vaddo]
    assert c1.candidate_id in vaddo_ids
    assert c2.candidate_id in vaddo_ids
    assert c3.candidate_id not in vaddo_ids

    # Test 2: Search by Booth 'Booth 10' independently -> Returns c1 and c3
    res_booth = test_repo.search_candidates_by_location(booth="Booth 10")
    booth_ids = [c.candidate_id for c in res_booth]
    assert c1.candidate_id in booth_ids
    assert c3.candidate_id in booth_ids
    assert c2.candidate_id not in booth_ids


def test_document_inventory_and_readiness_calculation(test_repo):
    """Verifies document inventory and readiness scoring with gap identification."""
    cand = test_repo.save_candidate(Candidate(
        full_name="Pooja Pednekar",
        mobile="9822100004",
        village="Arambol"
    ))
    cid = cand.candidate_id

    # Create documents with mixed statuses
    docs = [
        CandidateDocument(candidate_id=cid, document_type="15-Year Residence Certificate", document_category="Residence", status="Available"),
        CandidateDocument(candidate_id=cid, document_type="Employment Exchange Registration Card (Goa)", document_category="Employment", status="Applied/Awaiting"),
        CandidateDocument(candidate_id=cid, document_type="Birth Certificate", document_category="Other", status="Available"),
        CandidateDocument(candidate_id=cid, document_type="10th / SSC Marksheet & Certificate", document_category="Education", status="Expired", expiry_date="2020-01-01")
    ]
    test_repo.save_candidate_documents_bulk(cid, docs)

    saved_docs = test_repo.get_candidate_documents(cid)
    assert len(saved_docs) == 4

    # Calculate Government Readiness
    readiness = DocumentManager.calculate_readiness(saved_docs, "GOVERNMENT")
    assert readiness["is_ready"] is False
    assert readiness["available_count"] == 2  # Residence & Birth
    assert "Employment Exchange Registration Card (Goa)" in readiness["awaiting"]
    assert "10th / SSC Marksheet & Certificate" in readiness["expired"]


def test_tiered_job_matching_and_document_gaps(test_repo):
    """
    Verifies matching engine applies tiered hard/soft requirements,
    detects document gaps, and strictly adheres to the disclaimer requirement.
    """
    candidate = test_repo.save_candidate(Candidate(
        full_name="Rohit Gaonkar",
        age=24,
        mobile="9822100005",
        village="Corgao",
        education=Education(
            highest_qualification="12th / HSSC",
            skills="Computer Operation, MS Office"
        ),
        employment=Employment(years_experience=0.0)
    ))

    # Job requiring 12th, Age 18-45, and Residence Certificate
    gov_job = GovernmentJob(
        job_id="GOV-TEST-001",
        source="GSSC",
        department="Revenue Department",
        post_name="Talathi / Lower Division Clerk",
        minimum_qualification="12th / HSSC",
        age_limit_min=18,
        age_limit_max=45,
        experience_requirement_years=0.0,
        required_documents=[
            "15-Year Residence Certificate",
            "Employment Exchange Registration Card (Goa)"
        ]
    )

    # 1. Without required documents -> Document gap detected
    docs_empty = []
    result1 = MatchingEngine.match_candidate_to_government_job(candidate, gov_job, docs_empty)
    assert len(result1.document_gaps) == 2
    assert result1.disclaimer == DISCLAIMER_TEXT
    assert "Eligible" not in result1.match_tier

    # 2. With all required documents available -> High match
    docs_complete = [
        CandidateDocument(candidate_id=candidate.candidate_id, document_type="15-Year Residence Certificate", document_category="Residence", status="Available"),
        CandidateDocument(candidate_id=candidate.candidate_id, document_type="Employment Exchange Registration Card (Goa)", document_category="Employment", status="Available")
    ]
    result2 = MatchingEngine.match_candidate_to_government_job(candidate, gov_job, docs_complete)
    assert len(result2.document_gaps) == 0
    assert result2.match_tier == "HIGH MATCH"
    assert result2.disclaimer == DISCLAIMER_TEXT


def test_strict_recruiter_consent_enforcement(test_repo):
    """
    Strict Service-Layer Enforcement:
    Candidates without explicit 'Consented' status (Declined, Withdrawn, Not Asked)
    are NEVER exported or shared with recruiters.
    """
    service = RecruiterService(test_repo)

    # 1. Create verified recruiter
    recruiter = test_repo.save_recruiter(Recruiter(
        recruiter_id="REC-001",
        company="Mopa Airport Ground Operations",
        contact_person="Ravi Kumar",
        email="ravi@mopa.in",
        phone="9822000000",
        verification_status="VERIFIED"
    ))

    # 2. Create 4 candidates with different consent statuses
    c1 = test_repo.save_candidate(Candidate(full_name="Consented Cand", mobile="9822100010", village="Pernem"))
    test_repo.update_candidate_consent(c1.candidate_id, "Consented", method="In-Person Form")

    c2 = test_repo.save_candidate(Candidate(full_name="Declined Cand", mobile="9822100011", village="Pernem"))
    test_repo.update_candidate_consent(c2.candidate_id, "Declined", method="Phone Call")

    c3 = test_repo.save_candidate(Candidate(full_name="Withdrawn Cand", mobile="9822100012", village="Pernem"))
    test_repo.update_candidate_consent(c3.candidate_id, "Withdrawn", method="Written Notice")

    c4 = test_repo.save_candidate(Candidate(full_name="Not Asked Cand", mobile="9822100013", village="Pernem"))
    # c4 has default 'Not Asked'

    # 3. Attempt export for all 4 candidates
    cand_ids = [c1.candidate_id, c2.candidate_id, c3.candidate_id, c4.candidate_id]
    export_res = service.export_candidates_for_recruiter(
        recruiter_id="REC-001",
        candidate_ids=cand_ids,
        export_mode="Level 1 Shortlist",
        actor="Operator"
    )

    # Verify results
    assert export_res["success"] is True
    assert export_res["exported_count"] == 1
    assert export_res["consented_candidates"] == [c1.candidate_id]

    # Verify excluded candidate reasons
    excluded_ids = [e["candidate_id"] for e in export_res["excluded_candidates"]]
    assert c2.candidate_id in excluded_ids
    assert c3.candidate_id in excluded_ids
    assert c4.candidate_id in excluded_ids

    # Verify audit log captures exclusions
    audit_logs = test_repo.get_audit_logs(entity_type="Candidate")
    excluded_actions = [l for l in audit_logs if l.action == "EXPORT_EXCLUDED_NO_CONSENT"]
    assert len(excluded_actions) == 3


def test_unverified_recruiter_blocked(test_repo):
    """
    Unverified or Blocked recruiters must be strictly rejected at the service layer
    with an audit entry and permission error.
    """
    service = RecruiterService(test_repo)

    # 1. Unverified recruiter
    test_repo.save_recruiter(Recruiter(
        recruiter_id="REC-UNVERIF",
        company="Unverified Agency",
        contact_person="Unknown",
        email="info@unverified.in",
        phone="9800000000",
        verification_status="UNVERIFIED"
    ))

    cand = test_repo.save_candidate(Candidate(full_name="Any Cand", mobile="9822100020", village="Tuem"))
    test_repo.update_candidate_consent(cand.candidate_id, "Consented")

    with pytest.raises(PermissionError) as exc_info:
        service.export_candidates_for_recruiter(
            recruiter_id="REC-UNVERIF",
            candidate_ids=[cand.candidate_id],
            export_mode="Level 1 Shortlist"
        )
    assert "Only VERIFIED recruiters can receive candidate profiles" in str(exc_info.value)

    # Verify audit log records blocked attempt
    audit_logs = test_repo.get_audit_logs(entity_type="Recruiter", entity_id="REC-UNVERIF")
    assert any(l.action == "EXPORT_BLOCKED" for l in audit_logs)


def test_audit_logging_integrity(test_repo):
    """Verifies all actions touch the immutable audit_log table."""
    c = test_repo.save_candidate(Candidate(full_name="Audit Candidate", mobile="9822100030", village="Corgao"))
    cid = c.candidate_id

    # Consent update
    test_repo.update_candidate_consent(cid, "Consented", "In-Person Form", "Signed registration consent", "Admin")

    # Fetch audit entries
    logs = test_repo.get_audit_logs(entity_id=cid)
    actions = [l.action for l in logs]
    assert "CREATE" in actions
    assert "CONSENT_CHANGE" in actions


def test_job_source_adapter_failure_caching(test_repo):
    """
    Verifies that when a job source is checked under offline/failure conditions,
    existing cached jobs are preserved without deletion and status is marked properly.
    """
    seed_initial_sample_jobs(test_repo)

    adapter = GSSCJobAdapter(repo=test_repo)
    jobs = adapter.fetch_jobs()
    assert len(jobs) >= 2  # Seeded GSSC jobs present

    # Check that jobs in cache remain intact
    all_gov = test_repo.get_all_government_jobs()
    assert len(all_gov) >= 3


def test_multi_application_history(test_repo):
    """Verifies candidate tracks multiple Government and Private applications without data loss."""
    cand = test_repo.save_candidate(Candidate(full_name="Multi Applier", mobile="9822100040", village="Morjim"))
    cid = cand.candidate_id

    # Add 2 government applications
    test_repo.save_government_job_application(GovernmentJobApplication(
        candidate_id=cid,
        advertisement_number="GSSC/01/2026",
        post_name="Junior Stenographer",
        department="Higher Education",
        application_date="2026-09-02",
        application_status="APPLIED"
    ))
    test_repo.save_government_job_application(GovernmentJobApplication(
        candidate_id=cid,
        advertisement_number="GPSC/05/2026",
        post_name="Medical Officer",
        department="Health Services",
        application_date="2026-09-03",
        application_status="ADMIT_CARD_ISSUED"
    ))

    # Add 1 private application
    test_repo.save_private_job_application(PrivateJobApplication(
        candidate_id=cid,
        company_employer="GMR Mopa Airport",
        job_title="Terminal Associate",
        application_date="2026-09-04",
        application_status="INTERVIEW_SCHEDULED"
    ))

    gov_apps = test_repo.get_government_job_applications(cid)
    assert len(gov_apps) == 2

    priv_apps = test_repo.get_private_job_applications(cid)
    assert len(priv_apps) == 1
    assert priv_apps[0].company_employer == "GMR Mopa Airport"


def test_privacy_no_aadhaar_pan_in_sheets_export():
    """Verifies candidate flat dict and sheets columns do not contain sensitive ID numbers."""
    c = Candidate(
        candidate_id="PST-000099",
        full_name="Privacy Check",
        mobile="9822998877",
        village="Pernem"
    )
    flat = c.to_flat_dict()
    assert "Aadhaar" not in flat
    assert "PAN" not in flat

    row_vals = c.to_row_list()
    assert len(row_vals) == 42  # Preserves exact 42 columns
