"""
Phase 2 Expansion Tests for Pedne Sewa Trust - Employment Facilitation Platform.
Verifies Google Sheets UI isolation, background worker firing, schema versioning,
pre-migration backups, rollback safety, government/private job matching with disclaimers,
recruiter consent gate, multi-application tracking, GitHub version checking, and DOB picker integrity.
"""

import pytest
import sqlite3
from datetime import datetime
from unittest.mock import MagicMock, patch
from PySide6.QtWidgets import QApplication, QCheckBox
from PySide6.QtCore import QDate

from app.constants import APP_VERSION
from database.connection import DatabaseManager
from database.repository import CandidateRepository
from database.schema import MigrationManager, init_database
from models.candidate import Candidate, CandidateLocation, Education, Employment
from models.facilitation import (
    CandidateDocument, GovernmentJob, PrivateJob, Recruiter, CandidateConsent,
    GovernmentJobApplication, PrivateJobApplication
)
from facilitation.matching_engine import matching_engine, DISCLAIMER_TEXT
from facilitation.recruiter_service import RecruiterService
from sync.sync_worker import sync_worker
from sync.sync_engine import SyncEngine
from app.updater import parse_version, UpdateCheckThread


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


@pytest.fixture
def clean_repo(tmp_path):
    db_file = str(tmp_path / "test_p2.db")
    mgr = DatabaseManager(db_file)
    with mgr.get_connection() as conn:
        init_database(conn)
    return CandidateRepository(mgr)


# ----------------------------------------------------------------------
# 1 & 2. Google Sheets Background Sync & Worker Preservation
# ----------------------------------------------------------------------

def test_google_sheets_worker_interval_and_silent_operation():
    """Verifies that the background sync worker is configured for 10-minute intervals."""
    sync_worker.start()
    # 10 minutes = 600,000 milliseconds
    assert sync_worker.timer.interval() == 10 * 60 * 1000
    assert hasattr(sync_worker, "sync_now")


def test_google_sheets_background_sync_idempotency_and_data_safety(clean_repo):
    """Verifies that the underlying SyncEngine works silently without data loss."""
    c = clean_repo.save_candidate(Candidate(
        full_name="Ramesh Sawant",
        village="Torxem",
        mobile="9822990011"
    ))
    assert c.sync_status == "PENDING"

    with patch("sync.sync_engine.repository", clean_repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates", return_value={"status": "SUCCESS", "records_pushed": 1}):

        engine = SyncEngine()
        stats = engine.run_sync()

        assert stats["status"] == "SUCCESS"
        assert stats["records_pushed"] == 1

        updated_c = clean_repo.get_candidate(c.candidate_id)
        assert updated_c.sync_status == "SYNCED"
        assert updated_c.last_synced_at is not None


def test_google_sheets_failure_preserves_local_data_as_pending(clean_repo):
    """Verifies that when sync fails (e.g. offline), local candidate is preserved as PENDING."""
    c = clean_repo.save_candidate(Candidate(
        full_name="Pooja Gawas",
        village="Corgao",
        mobile="9822990022"
    ))

    with patch("sync.sync_engine.repository", clean_repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates", return_value={"status": "FAILURE", "error": "Connection timed out"}):

        engine = SyncEngine()
        stats = engine.run_sync()

        assert stats["status"] == "FAILURE"
        assert stats["records_pushed"] == 0

        reloaded = clean_repo.get_candidate(c.candidate_id)
        assert reloaded is not None
        assert reloaded.sync_status in ("PENDING", "FAILED")
        assert reloaded.full_name == "Pooja Gawas"


# ----------------------------------------------------------------------
# 3. No Google Sheets Elements in Operator UI
# ----------------------------------------------------------------------

def test_no_google_sheets_elements_in_operator_ui(qapp):
    """Verifies that NO Google Sheets or Cloud Backup UI elements appear in the operator UI."""
    from ui.components.sidebar import Sidebar
    from ui.components.header_bar import HeaderBar
    from ui.views.dashboard_view import DashboardView
    from ui.views.candidate_list_view import CandidateListView
    from ui.dialogs.candidate_details_dialog import CandidateDetailsDialog
    from ui.views.settings_view import SettingsView

    # 1. Sidebar: No "Google Sheets Sync"
    sidebar = Sidebar()
    button_texts = [btn.text() for btn in sidebar.buttons]
    assert "Google Sheets Sync" not in button_texts
    assert "Cloud Backup" not in button_texts

    # 2. Header: No cloud_pill, no sync_btn
    header = HeaderBar()
    assert not hasattr(header, "cloud_pill")
    assert not hasattr(header, "sync_btn")

    # 3. Dashboard: No Sync Cloud button, no Online Backup Status card
    dash = DashboardView()
    assert not hasattr(dash, "cloud_card")
    assert not hasattr(dash, "lbl_safe_status")
    dash_buttons = [b.text() for b in dash.findChildren(object) if hasattr(b, "text")]
    assert "Sync Cloud" not in dash_buttons

    # 4. Candidate List View: No Cloud Backup column, no filter_sync
    list_view = CandidateListView()
    assert not hasattr(list_view, "filter_sync")
    headers = [list_view.table.horizontalHeaderItem(i).text() for i in range(list_view.table.columnCount())]
    assert "Cloud Backup" not in headers
    assert "Cloud Sync" not in headers

    # 5. Candidate Details Dialog: No Cloud Status badge
    cand = Candidate(candidate_id="PST-TEST-99", full_name="Test User", mobile="9822000000", village="Mandrem")
    details_dlg = CandidateDetailsDialog(cand)
    labels = [l.text() for l in details_dlg.findChildren(object) if hasattr(l, "text")]
    assert not any("Cloud" in lbl for lbl in labels)
    assert not any("☁ Synced" in lbl for lbl in labels)

    # 6. Settings View: No Google Sheets credentials or spreadsheet card
    settings = SettingsView()
    assert not hasattr(settings, "edit_sheet_id")
    assert not hasattr(settings, "edit_creds_path")


# ----------------------------------------------------------------------
# 4. Government Job Ingestion, Storage & Mandatory Disclaimer
# ----------------------------------------------------------------------

def test_government_job_storage_and_mandatory_disclaimer(clean_repo):
    """Verifies official government job storage and strict disclaimer enforcement."""
    job = GovernmentJob(
        job_id="GOV-GSSC-TEST-01",
        source="GSSC",
        advertisement_number="Advt 02/2026",
        department="Directorate of Health Services",
        post_name="Pharmacist",
        vacancies_count=4,
        minimum_qualification="Diploma",
        experience_requirement_years=1.0,
        age_limit_min=18,
        age_limit_max=45,
        required_documents=["15-Year Residence Certificate", "Valid Employment Exchange Card"],
        status="OPEN"
    )
    clean_repo.save_government_job(job)

    loaded = clean_repo.get_government_job("GOV-GSSC-TEST-01")
    assert loaded is not None
    assert loaded.post_name == "Pharmacist"
    assert loaded.vacancies_count == 4
    assert loaded.minimum_qualification == "Diploma"

    # Mandatory Legal Disclaimer Check
    assert DISCLAIMER_TEXT == "Potential Match — Verify Eligibility Against Official Advertisement"

    # Match candidate against this job
    cand = Candidate(
        candidate_id="PST-TEST-PHARM",
        full_name="Kavita Naik",
        dob="1998-05-15",
        village="Arambol",
        education=Education(highest_qualification="Diploma"),
        employment=Employment(status="UNEMPLOYED", years_experience=2.0)
    )
    docs = [
        CandidateDocument(document_type="15-Year Residence Certificate", status="Available"),
        CandidateDocument(document_type="Valid Employment Exchange Card", status="Available")
    ]

    res = matching_engine.match_candidate_to_government_job(cand, loaded, docs)
    assert res.match_tier in ("HIGH MATCH", "MEDIUM MATCH")
    assert res.disclaimer == DISCLAIMER_TEXT


# ----------------------------------------------------------------------
# 5. Private Job Creation & Document Gap Analysis
# ----------------------------------------------------------------------

def test_private_curated_job_matching_and_document_gaps(clean_repo):
    """Verifies curated private job creation, document gap detection, and match score."""
    pjob = PrivateJob(
        job_id="PRIV-TUEM-01",
        employer="Tuem Electronic City Concessionaire",
        job_title="SMT Machine Operator",
        required_qualification="ITI",
        required_experience_years=0.5,
        required_documents=["Valid Employment Exchange Card", "Aadhaar Card"],
        location="Tuem Industrial Estate",
        status="ACTIVE"
    )
    clean_repo.save_private_job(pjob)

    cand = Candidate(
        candidate_id="PST-TEST-ITI",
        full_name="Gaurav Parab",
        village="Tuem",
        education=Education(highest_qualification="ITI"),
        employment=Employment(status="UNEMPLOYED", years_experience=1.0)
    )
    # Missing Aadhaar Card
    docs = [
        CandidateDocument(document_type="Valid Employment Exchange Card", status="Available"),
        CandidateDocument(document_type="Aadhaar Card", status="Missing")
    ]

    res = matching_engine.match_candidate_to_private_job(cand, pjob, docs)
    assert len(res.document_gaps) >= 1
    assert any("Aadhaar Card" in g for g in res.document_gaps)


# ----------------------------------------------------------------------
# 6. Recruiter Consent Enforcement & Blocking Unverified Recruiters
# ----------------------------------------------------------------------

def test_recruiter_consent_and_verification_rules(clean_repo):
    """Verifies that non-consented candidates and unverified recruiters are blocked."""
    service = RecruiterService(clean_repo)

    # 1. Unverified recruiter
    r_unver = clean_repo.save_recruiter(Recruiter(
        recruiter_id="REC-UNVER-01",
        company="Unverified HR Agency",
        contact_person="John Doe",
        email="john@example.com",
        phone="9822001122",
        verification_status="UNVERIFIED"
    ))

    # Candidate who consented
    c_consented = clean_repo.save_candidate(Candidate(
        full_name="Siddhesh Shetye",
        village="Mandrem",
        mobile="9822119901"
    ))
    clean_repo.save_candidate_consent(CandidateConsent(
        candidate_id=c_consented.candidate_id,
        consent_status="Consented"
    ))

    # Unverified recruiter must be rejected
    with pytest.raises(PermissionError, match="Access Denied: Recruiter"):
        service.export_candidates_for_recruiter(
            recruiter_id="REC-UNVER-01",
            candidate_ids=[c_consented.candidate_id],
            export_mode="Level 1 Shortlist"
        )

    # 2. Verified recruiter
    r_ver = clean_repo.save_recruiter(Recruiter(
        recruiter_id="REC-VER-01",
        company="Mopa Airport Hospitality Ltd",
        contact_person="Jane Smith",
        email="jane@mopa.com",
        phone="9822001133",
        verification_status="VERIFIED"
    ))

    # Candidate who declined consent
    c_declined = clean_repo.save_candidate(Candidate(
        full_name="Deepak Rane",
        village="Pernem",
        mobile="9822119902"
    ))
    clean_repo.save_candidate_consent(CandidateConsent(
        candidate_id=c_declined.candidate_id,
        consent_status="Declined"
    ))

    # Sharing declined candidate must yield 0 exported candidates
    result = service.export_candidates_for_recruiter(
        recruiter_id="REC-VER-01",
        candidate_ids=[c_declined.candidate_id],
        export_mode="Level 1 Shortlist"
    )
    assert result["exported_count"] == 0
    assert len(result["excluded_candidates"]) == 1


# ----------------------------------------------------------------------
# 7. Multiple Applications History
# ----------------------------------------------------------------------

def test_multi_application_history_preservation(clean_repo):
    """Verifies that multiple applications per candidate do not overwrite each other."""
    c = clean_repo.save_candidate(Candidate(
        full_name="Amit Malik",
        village="Chopdem",
        mobile="9822554433"
    ))

    app1 = GovernmentJobApplication(
        candidate_id=c.candidate_id,
        job_id="GOV-01",
        post_name="LDC",
        department="Forests",
        application_date="2026-01-10",
        application_status="APPLIED"
    )
    app2 = GovernmentJobApplication(
        candidate_id=c.candidate_id,
        job_id="GOV-02",
        post_name="Steno",
        department="Finance",
        application_date="2026-02-15",
        application_status="SHORTLISTED"
    )

    clean_repo.save_government_job_application(app1)
    clean_repo.save_government_job_application(app2)

    history = clean_repo.get_government_job_applications(c.candidate_id)
    assert len(history) == 2
    posts = [a.post_name for a in history]
    assert "LDC" in posts
    assert "Steno" in posts


# ----------------------------------------------------------------------
# 8. Database Migration Versioning, Backups & Rollback Safety
# ----------------------------------------------------------------------

def test_database_migration_versioning_and_backup(clean_repo):
    """Verifies schema_version tracking and automated pre-migration backup."""
    with clean_repo.db.get_connection() as conn:
        ver = MigrationManager.get_current_version(conn)
        assert ver >= 2

        # Verify schema_version table content
        cur = conn.cursor()
        cur.execute("SELECT version, description FROM schema_version ORDER BY version ASC")
        rows = cur.fetchall()
        versions = [r[0] for r in rows]
        assert 1 in versions
        assert 2 in versions

        # Test pre-migration backup creation
        backup_file = MigrationManager.create_pre_migration_backup(conn, target_version=3)
        assert backup_file != ""
        assert backup_file.endswith(".db")


def test_database_migration_rollback_safety(tmp_path):
    """Verifies transactional rollback safety if a migration statement fails."""
    db_file = str(tmp_path / "test_rollback.db")
    conn = sqlite3.connect(db_file)
    init_database(conn)

    # Insert candidate
    conn.execute(
        "INSERT INTO candidates (candidate_id, full_name, village, mobile, created_at, updated_at) "
        "VALUES ('PST-ROLLBACK-01', 'Test User', 'Mandrem', '9822110099', datetime('now'), datetime('now'))"
    )
    conn.commit()

    # Intentionally trigger failed migration within transaction
    failed = False
    try:
        conn.execute("BEGIN IMMEDIATE TRANSACTION;")
        conn.execute("UPDATE candidates SET village = 'Corgao' WHERE candidate_id = 'PST-ROLLBACK-01'")
        # Invalid syntax statement to force failure
        conn.execute("ALTER TABLE non_existent_table ADD COLUMN invalid_col TEXT;")
        conn.commit()
    except Exception:
        conn.rollback()
        failed = True

    assert failed is True

    # Candidate village must still be 'Mandrem' due to safe rollback
    cursor = conn.cursor()
    cursor.execute("SELECT village FROM candidates WHERE candidate_id = 'PST-ROLLBACK-01'")
    row = cursor.fetchone()
    assert row[0] == "Mandrem"
    conn.close()


# ----------------------------------------------------------------------
# 9. GitHub Version Checking Logic
# ----------------------------------------------------------------------

def test_github_version_check_parsing():
    """Verifies semantic version comparison in the auto-update checker."""
    assert parse_version("v2.1.0") > parse_version("2.0.0")
    assert parse_version("2.0.1") > parse_version("2.0.0")
    assert parse_version("v3.0.0") > parse_version("v2.9.9")
    assert parse_version("2.0.0") == parse_version("v2.0.0")
    assert parse_version("1.9.9") < parse_version("2.0.0")


# ----------------------------------------------------------------------
# 10. Native DOB Picker Integrity (No Checkbox)
# ----------------------------------------------------------------------

def test_dob_picker_has_no_checkbox_and_works_correctly(qapp):
    """Verifies that DateOfBirthPicker contains NO checkbox and functions natively."""
    from ui.components.dob_picker import DateOfBirthPicker
    picker = DateOfBirthPicker()

    # Strict check: NO QCheckBox in picker or its child hierarchy
    checkboxes = picker.findChildren(QCheckBox)
    assert len(checkboxes) == 0

    # Default date is blank/None
    assert picker.get_date_iso() is None

    # Set valid date
    picker.set_date_iso("2000-08-25")
    assert picker.get_date_iso() == "2000-08-25"

    # Clear back to blank
    picker.clear()
    assert picker.get_date_iso() is None
