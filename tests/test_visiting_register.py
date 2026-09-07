"""
Unit and Integration Tests for Visiting Register Feature.
Validates VisitorRecord domain model, database CRUD, sequential Sr No generation,
CSV and Excel import with fuzzy matching, CSV export, and dual cloud backup synchronization.
"""

import os
import tempfile
import csv
import openpyxl
from datetime import datetime
import pytest

from database.connection import DatabaseManager
from database.repository import CandidateRepository
from models.visitor import VisitorRecord
from export.importer import FileImporter
from export.csv_exporter import CSVExporter
from app.constants import SYNC_STATUS_PENDING, SYNC_STATUS_SYNCED, VISITING_REGISTER_COLUMNS


@pytest.fixture
def repo():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_visiting.db")
    test_mgr = DatabaseManager(db_path)
    r = CandidateRepository(db_manager_instance=test_mgr)
    yield r


def test_visitor_model_methods():
    vis = VisitorRecord(
        sr_no=1,
        visit_date="2026-09-07",
        visit_time="10:30 AM",
        candidate_name="Rahul Redkar",
        village="Corgao",
        mobile="9822112233",
        purpose="Candidate Intake"
    )
    d = vis.to_dict()
    assert d["sr_no"] == 1
    assert d["candidate_name"] == "Rahul Redkar"
    assert d["sync_status"] == "PENDING"

    backup_d = vis.to_backup_dict()
    assert "sr_no" in backup_d
    assert "candidate_name" in backup_d
    assert "id" not in backup_d  # flat backup payload

    row = vis.to_row_list()
    assert row[0] == "1"
    assert row[1] == "Pernem"
    assert row[4] == "Rahul Redkar"


def test_sequential_visitor_sr_no(repo):
    v1 = VisitorRecord(candidate_name="Visitor One", village="Mandrem", mobile="9822000001", purpose="Inquiry")
    id1 = repo.save_visitor(v1)
    assert id1 is not None
    assert v1.sr_no == 1

    v2 = VisitorRecord(candidate_name="Visitor Two", village="Arambol", mobile="9822000002", purpose="Document Verification")
    id2 = repo.save_visitor(v2)
    assert id2 is not None
    assert v2.sr_no == 2

    loaded_v1 = repo.get_visitor_by_id(id1)
    assert loaded_v1 is not None
    assert loaded_v1.candidate_name == "Visitor One"
    assert loaded_v1.sr_no == 1
    assert loaded_v1.sync_status == SYNC_STATUS_PENDING


def test_visitor_update_and_soft_delete(repo):
    v = VisitorRecord(candidate_name="Original Name", village="Morjim", mobile="9822000003", purpose="General")
    v_id = repo.save_visitor(v)

    loaded = repo.get_visitor_by_id(v_id)
    loaded.candidate_name = "Updated Name"
    loaded.purpose = "Interview"
    updated = repo.update_visitor(loaded)
    assert updated is True

    check = repo.get_visitor_by_id(v_id)
    assert check.candidate_name == "Updated Name"
    assert check.purpose == "Interview"

    # Soft delete
    deleted = repo.delete_visitor(v_id)
    assert deleted is True

    all_active = repo.get_all_visitors(include_deleted=False)
    assert len(all_active) == 0

    all_with_deleted = repo.get_all_visitors(include_deleted=True)
    assert len(all_with_deleted) == 1
    assert all_with_deleted[0].is_deleted == 1


def test_visitor_search_and_filters(repo):
    repo.save_visitor(VisitorRecord(candidate_name="Sunil Gawande", village="Corgao", mobile="9822111111", purpose="Registration", visit_date="2026-09-07"))
    repo.save_visitor(VisitorRecord(candidate_name="Pooja Naik", village="Mandrem", mobile="9822222222", purpose="Interview", visit_date="2026-09-07"))
    repo.save_visitor(VisitorRecord(candidate_name="Ramesh Corgaonkar", village="Corgao", mobile="9822333333", purpose="Inquiry", visit_date="2026-09-06"))

    # Search by name
    res_name = repo.search_visitors(query="Sunil")
    assert len(res_name) == 1
    assert res_name[0].candidate_name == "Sunil Gawande"

    # Search by village
    res_village = repo.search_visitors(village_filter="Corgao")
    assert len(res_village) == 2

    # Search by date
    res_date = repo.search_visitors(date_filter="2026-09-07")
    assert len(res_date) == 2

    # Search by query across mobile
    res_mob = repo.search_visitors(query="9822222222")
    assert len(res_mob) == 1
    assert res_mob[0].candidate_name == "Pooja Naik"


def test_visitors_summary_counts(repo):
    today_str = datetime.now().strftime("%Y-%m-%d")
    repo.save_visitor(VisitorRecord(candidate_name="Visitor Today 1", visit_date=today_str, village="Mandrem", mobile="9822000010", purpose="Walk-in"))
    repo.save_visitor(VisitorRecord(candidate_name="Visitor Today 2", visit_date=today_str, village="Arambol", mobile="9822000011", purpose="Walk-in"))

    counts = repo.get_visitors_summary_counts()
    assert counts["today"] == 2
    assert counts["total"] == 2
    assert counts["pending_sync"] == 2


def test_csv_export_visitors(repo):
    repo.save_visitor(VisitorRecord(candidate_name="Anita Deshmukh", village="Dargalim", mobile="9822444444", purpose="Job Application"))
    visitors = repo.get_all_visitors()

    temp_dir = tempfile.mkdtemp()
    target_csv = os.path.join(temp_dir, "test_visitors_export.csv")
    exporter = CSVExporter(export_dir=temp_dir)
    exporter.export_visitors(visitors, target_filepath=target_csv)

    assert os.path.exists(target_csv)
    with open(target_csv, "r", encoding="utf-8-sig") as f:
        reader = list(csv.reader(f))
        assert len(reader) >= 2  # header + 1 row
        assert reader[0] == VISITING_REGISTER_COLUMNS
        assert reader[1][1] == "Pernem"
        assert reader[1][4] == "Anita Deshmukh"


def test_excel_and_csv_import():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_import.db")
    test_mgr = DatabaseManager(db_path)
    r = CandidateRepository(db_manager_instance=test_mgr)
    importer = FileImporter(repo=r)

    # 1. Test CSV Import
    csv_path = os.path.join(temp_dir, "sample_visitors.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Sr No.", "Date", "Time", "Name of candidate", "Address (village)", "Mobile No.", "Purpose of visit"])
        writer.writerow(["", "2026-09-07", "11:00 AM", "Kiran Parab", "Alorna", "9822555555", "Intake"])
        writer.writerow(["", "2026-09-07", "11:30 AM", "Amit Raut", "Chopdem", "9822666666", "Meeting"])

    result_csv = importer.import_visiting_register(csv_path)
    assert result_csv["inserted"] == 2
    assert result_csv["skipped"] == 0

    all_imported = r.get_all_visitors()
    assert len(all_imported) == 2
    names = [v.candidate_name for v in all_imported]
    assert "Kiran Parab" in names
    assert "Amit Raut" in names

    # 2. Test Excel (.xlsx) Import with fuzzy header names
    xlsx_path = os.path.join(temp_dir, "sample_visitors.xlsx")
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Visiting Register"
    ws.append(["S.No", "Visit Date", "Time", "Candidate Name", "Village", "Mobile", "Purpose"])
    ws.append([10, "2026-09-07", "02:15 PM", "Deepak Sawant", "Mandrem", "9822777777", "Verification"])
    wb.save(xlsx_path)

    result_xlsx = importer.import_visiting_register(xlsx_path)
    assert result_xlsx["inserted"] == 1

    final_visitors = r.get_all_visitors()
    assert len(final_visitors) == 3
    deepak = [v for v in final_visitors if v.candidate_name == "Deepak Sawant"][0]
    assert deepak.village == "Mandrem"
    assert deepak.mobile == "9822777777"


def test_dual_cloud_sync_candidates_and_visitors():
    from unittest.mock import MagicMock, patch
    from models.candidate import Candidate
    from sync.sync_engine import SyncEngine

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_dual_sync.db")
    test_mgr = DatabaseManager(db_path)
    r = CandidateRepository(db_manager_instance=test_mgr)
    engine = SyncEngine()

    c = r.save_candidate(Candidate(full_name="Sync Candidate", mobile="9822119988", village="Corgao"))
    v_id = r.save_visitor(VisitorRecord(candidate_name="Sync Visitor", mobile="9822119977", village="Mandrem", purpose="Registration"))

    assert c.sync_status == "PENDING"
    v = r.get_visitor_by_id(v_id)
    assert v.sync_status == "PENDING"

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.push_backup.return_value = {"status": "SUCCESS", "records_pushed": 2}

    with patch("sync.sync_engine.repository", r), \
         patch("sync.sync_engine.apps_script_client", mock_client):

        res = engine.run_sync()
        assert res["status"] == "SUCCESS"
        assert res["records_pushed"] == 2

        # Verify both candidate and visitor marked as SYNCED
        updated_c = r.get_candidate(c.candidate_id)
        assert updated_c.sync_status == "SYNCED"

        updated_v = r.get_visitor_by_id(v_id)
        assert updated_v.sync_status == "SYNCED"

        # Verify dual payload sent
        mock_client.push_backup.assert_called_once()
        _, kwargs = mock_client.push_backup.call_args
        assert len(kwargs["candidates"]) == 1
        assert len(kwargs["visitors"]) == 1


def test_visitor_remarks_support(repo):
    """Verifies that remarks are properly saved, retrieved, updated, and searched."""
    v = VisitorRecord(
        candidate_name="Praveen Vernekar",
        village="Pernem",
        mobile="9822998877",
        purpose="Other",
        remarks="Passport verification and trust documentation inquiry"
    )
    v_id = repo.save_visitor(v)
    assert v_id is not None

    loaded = repo.get_visitor_by_id(v_id)
    assert loaded.purpose == "Other"
    assert loaded.remarks == "Passport verification and trust documentation inquiry"

    # Search by remarks substring
    search_res = repo.search_visitors(query="Passport")
    assert len(search_res) == 1
    assert search_res[0].candidate_name == "Praveen Vernekar"

    # Update remarks
    loaded.remarks = "Updated: completed verification"
    repo.update_visitor(loaded)
    reloaded = repo.get_visitor_by_id(v_id)
    assert reloaded.remarks == "Updated: completed verification"


def test_manual_full_backup_when_zero_pending():
    """Verifies that is_manual=True triggers full candidate + visitor push when 0 pending."""
    from unittest.mock import MagicMock, patch
    from models.candidate import Candidate
    from sync.sync_engine import SyncEngine

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_manual_sync.db")
    test_mgr = DatabaseManager(db_path)
    r = CandidateRepository(db_manager_instance=test_mgr)
    engine = SyncEngine()

    c = r.save_candidate(Candidate(full_name="Already Synced Cand", mobile="9822119988", village="Corgao"))
    v_id = r.save_visitor(VisitorRecord(candidate_name="Already Synced Vis", mobile="9822119977", village="Mandrem", purpose="Registration"))

    # Mark both as SYNCED initially
    r.mark_candidates_synced([c.candidate_id], datetime.now().isoformat())
    r.mark_visitors_synced([v_id], datetime.now().isoformat())

    # Pending count is 0
    assert len(r.get_pending_sync_candidates()) == 0
    assert len(r.get_pending_sync_visitors()) == 0

    mock_client = MagicMock()
    mock_client.is_configured.return_value = True
    mock_client.push_backup.return_value = {"status": "SUCCESS", "records_pushed": 2}

    with patch("sync.sync_engine.repository", r), \
         patch("sync.sync_engine.apps_script_client", mock_client):

        # Automatic sync (is_manual=False) should do nothing
        res_auto = engine.run_sync(is_manual=False)
        assert res_auto["records_pushed"] == 0
        mock_client.push_backup.assert_not_called()

        # Manual sync (is_manual=True) should fetch all active records and push
        res_manual = engine.run_sync(is_manual=True)
        assert res_manual["status"] == "SUCCESS"
        assert res_manual["records_pushed"] == 2
        assert res_manual["candidates_pushed"] == 1
        assert res_manual["visitors_pushed"] == 1

        mock_client.push_backup.assert_called_once()
        _, kwargs = mock_client.push_backup.call_args
        assert len(kwargs["candidates"]) == 1
        assert len(kwargs["visitors"]) == 1


def test_visitor_intake_office(repo):
    """Tests intake office assignment, retrieval, and search filtering."""
    v_pernem = VisitorRecord(
        candidate_name="Pernem Visitor",
        village="Pernem",
        mobile="9822110001",
        purpose="Registration",
        intake_office="Pernem"
    )
    v_korgao = VisitorRecord(
        candidate_name="Korgao Visitor",
        village="Corgao",
        mobile="9822110002",
        purpose="Inquiry",
        intake_office="Korgao"
    )

    id_p = repo.save_visitor(v_pernem)
    id_k = repo.save_visitor(v_korgao)

    loaded_p = repo.get_visitor_by_id(id_p)
    assert loaded_p.intake_office == "Pernem"

    loaded_k = repo.get_visitor_by_id(id_k)
    assert loaded_k.intake_office == "Korgao"

    # Search with office filter
    korgao_res = repo.search_visitors(office_filter="Korgao")
    assert len(korgao_res) == 1
    assert korgao_res[0].candidate_name == "Korgao Visitor"

    pernem_res = repo.search_visitors(office_filter="Pernem")
    assert len(pernem_res) == 1
    assert pernem_res[0].candidate_name == "Pernem Visitor"


def test_visiting_register_migration_v7():
    """Verifies Migration v7 safely adds intake_office column to older schemas."""
    import sqlite3
    from database.schema import MigrationManager

    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test_migration_v7.db")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create v6 schema (with remarks, without intake_office)
    cursor.execute("""
        CREATE TABLE visiting_register (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sr_no INTEGER NOT NULL UNIQUE,
            visit_date TEXT NOT NULL,
            visit_time TEXT NOT NULL,
            candidate_name TEXT NOT NULL,
            village TEXT NOT NULL,
            mobile TEXT NOT NULL,
            purpose TEXT NOT NULL,
            remarks TEXT DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            sync_status TEXT NOT NULL DEFAULT 'PENDING',
            last_synced_at TEXT,
            is_deleted INTEGER NOT NULL DEFAULT 0
        );
    """)
    cursor.execute("CREATE TABLE schema_version (version INTEGER PRIMARY KEY, applied_at TEXT, description TEXT);")
    cursor.execute("INSERT INTO schema_version VALUES (6, '2026-09-07', 'v6');")
    cursor.execute("""
        INSERT INTO visiting_register (sr_no, visit_date, visit_time, candidate_name, village, mobile, purpose, remarks, created_at, updated_at)
        VALUES (1, '2026-09-07', '10:00 AM', 'Pre-migration Vis', 'Arambol', '9822119955', 'Inquiry', '', '2026-09-07', '2026-09-07');
    """)
    conn.commit()

    # Apply migrations up to v7
    MigrationManager.apply_migrations(conn)

    assert MigrationManager.get_current_version(conn) == 7

    cursor.execute("PRAGMA table_info(visiting_register);")
    cols = [c[1] for c in cursor.fetchall()]
    assert "intake_office" in cols

    # Verify existing record has default 'Pernem'
    cursor.execute("SELECT intake_office FROM visiting_register WHERE sr_no = 1;")
    row = cursor.fetchone()
    assert row[0] == "Pernem"
    conn.close()


def test_import_with_intake_office(repo):
    """Tests CSV import with Intake Office column."""
    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, "visiting_with_office.csv")

    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["Sr No.", "Intake Office", "Date", "Time", "Name of Candidate", "Address (Village)", "Mobile No.", "Purpose of Visit", "Remarks"])
        writer.writerow(["", "Korgao", "2026-09-07", "11:00 AM", "Korgao Walkin", "Corgao", "9822000088", "Job Search", "Referred by friend"])
        writer.writerow(["", "Pernem", "2026-09-07", "11:30 AM", "Pernem Walkin", "Mandrem", "9822000089", "Inquiry", ""])

    importer = FileImporter(repo=repo)
    res = importer.import_visiting_register(csv_path)
    assert res["success"] is True
    assert res["inserted"] == 2

    k_vis = repo.search_visitors(query="Korgao Walkin")
    assert len(k_vis) == 1
    assert k_vis[0].intake_office == "Korgao"

    p_vis = repo.search_visitors(query="Pernem Walkin")
    assert len(p_vis) == 1
    assert p_vis[0].intake_office == "Pernem"



