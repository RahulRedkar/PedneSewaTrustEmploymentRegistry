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
    assert row[3] == "Rahul Redkar"


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
        assert reader[1][3] == "Anita Deshmukh"


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

