"""
Integration tests verifying Scenarios A, B, C, and D as requested in user specification:
- Scenario A: Offline creation of 10 candidates -> 10 pending -> online reconnect -> 10 synced.
- Scenario B: Edit candidate -> updates existing Google Sheets row without creating duplicate.
- Scenario C: API failure -> local candidates remain intact, status remains pending.
- Scenario D: Application restart -> unsynced records persist across reboot and sync after reopen.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from database.connection import DatabaseManager
from database.repository import CandidateRepository
from models.candidate import Candidate, Employment
from sync.sync_engine import SyncEngine


@pytest.fixture
def env():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "scenarios.db")
    mgr = DatabaseManager(db_path)
    repo = CandidateRepository(db_manager_instance=mgr)
    engine = SyncEngine()
    return mgr, repo, engine


def test_scenario_a_offline_intake_then_reconnect_sync(env):
    """Scenario A: Create 10 candidates while offline -> 10 pending -> reconnect -> 10 synced."""
    mgr, repo, engine = env

    # 1. Offline: Create 10 candidates
    created_ids = []
    for i in range(1, 11):
        c = Candidate(
            full_name=f"Candidate {i}",
            mobile=f"98220000{i:02d}",
            village="Mandrem",
            employment=Employment(status="EMPLOYED" if i % 2 == 0 else "UNEMPLOYED")
        )
        saved = repo.save_candidate(c)
        created_ids.append(saved.candidate_id)

    # Verify all 10 are locally stored and PENDING
    pending = repo.get_pending_sync_candidates()
    assert len(pending) == 10
    for p in pending:
        assert p.sync_status == "PENDING"

    # 2. Reconnect: Mock Apps Script Web App becoming available
    with patch("sync.sync_engine.repository", repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates") as mock_push:

        mock_push.return_value = {"status": "SUCCESS", "records_pushed": 10}

        result = engine.run_sync()

        assert result["status"] == "SUCCESS"
        assert result["records_pushed"] == 10
        mock_push.assert_called_once()

        # Verify all 10 are now SYNCED in local database
        for cid in created_ids:
            cand = repo.get_candidate(cid)
            assert cand.sync_status == "SYNCED"
            assert cand.last_synced_at is not None

        # Pending count should now be 0
        assert len(repo.get_pending_sync_candidates()) == 0


def test_scenario_b_candidate_edit_updates_row_without_duplication(env):
    """Scenario B: Edit candidate -> existing candidate is re-pushed with updated fields, marked synced."""
    mgr, repo, engine = env

    # Create and sync candidate
    c = Candidate(full_name="Ramesh Chodankar", mobile="9822991122", village="Corgao", employment=Employment(status="UNEMPLOYED"))
    c = repo.save_candidate(c)
    cid = c.candidate_id
    repo.mark_candidates_synced([cid], "2026-09-04T10:00:00")

    # Edit candidate locally
    cand_to_edit = repo.get_candidate(cid)
    cand_to_edit.full_name = "Ramesh S. Chodankar"
    cand_to_edit.employment.status = "EMPLOYED"
    cand_to_edit.employment.category = "Private"
    cand_to_edit.employment.department_company = "Goa Shipyard Ltd"
    repo.update_candidate(cand_to_edit)

    # Candidate should now be re-marked PENDING
    re_edited = repo.get_candidate(cid)
    assert re_edited.sync_status == "PENDING"

    # Sync: Push updated candidate payload to Apps Script gateway
    with patch("sync.sync_engine.repository", repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates") as mock_push:

        mock_push.return_value = {"status": "SUCCESS", "records_pushed": 1}

        res = engine.run_sync()

        assert res["status"] == "SUCCESS"
        assert res["records_pushed"] == 1
        mock_push.assert_called_once()
        pushed_cands = mock_push.call_args[0][0]
        assert len(pushed_cands) == 1
        assert pushed_cands[0].candidate_id == cid
        assert pushed_cands[0].full_name == "Ramesh S. Chodankar"

        updated_in_db = repo.get_candidate(cid)
        assert updated_in_db.sync_status == "SYNCED"


def test_scenario_c_api_unavailable_preserves_local_data(env):
    """Scenario C: Backup gateway unavailable -> local candidate remains intact, pending."""
    mgr, repo, engine = env

    c = Candidate(full_name="Pravin Naik", mobile="9822338800", village="Tuem", employment=Employment(status="SELF_EMPLOYED"))
    c = repo.save_candidate(c)

    # API failure simulation
    with patch("sync.sync_engine.repository", repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates", side_effect=Exception("503 Service Unavailable")):

        res = engine.run_sync()
        assert res["status"] == "FAILURE"

        # Local database candidate MUST be completely intact and still PENDING
        persisted = repo.get_candidate(c.candidate_id)
        assert persisted is not None
        assert persisted.full_name == "Pravin Naik"
        assert persisted.sync_status == "PENDING"


def test_scenario_d_application_restart_preserves_pending(env):
    """Scenario D: Close and reopen application before sync -> pending records persist and sync."""
    mgr, repo, engine = env
    db_file = mgr.db_path

    # Session 1: Add 2 candidates while offline
    c1 = repo.save_candidate(Candidate(full_name="User Alpha", mobile="9822110011", village="Arambol", employment=Employment(status="STUDENT")))
    c2 = repo.save_candidate(Candidate(full_name="User Beta", mobile="9822110022", village="Morjim", employment=Employment(status="EMPLOYED")))

    # Simulate Application Close (mgr closed)
    del repo
    del mgr

    # Session 2: Application Restart (new manager pointing to same SQLite db file)
    new_mgr = DatabaseManager(db_file)
    new_repo = CandidateRepository(db_manager_instance=new_mgr)

    # Verify pending records persisted across restart
    pending_after_restart = new_repo.get_pending_sync_candidates()
    assert len(pending_after_restart) == 2
    assert {p.candidate_id for p in pending_after_restart} == {c1.candidate_id, c2.candidate_id}

    # Now sync after reopen
    with patch("sync.sync_engine.repository", new_repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates") as mock_push:

        mock_push.return_value = {"status": "SUCCESS", "records_pushed": 2}

        res = engine.run_sync()
        assert res["status"] == "SUCCESS"
        assert res["records_pushed"] == 2

        # Verify both are now SYNCED
        assert new_repo.get_candidate(c1.candidate_id).sync_status == "SYNCED"
        assert new_repo.get_candidate(c2.candidate_id).sync_status == "SYNCED"
