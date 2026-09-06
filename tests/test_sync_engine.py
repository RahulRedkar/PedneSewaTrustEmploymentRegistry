"""
Unit tests for Google Apps Script Web App synchronization & reconciliation engine.
Tests configuration detection, payload generation, idempotent batch push, and local data preservation.
"""

import os
import tempfile
from unittest.mock import MagicMock, patch
import pytest
from database.connection import DatabaseManager
from database.repository import CandidateRepository
from models.candidate import Candidate, Employment, Education
from models.facilitation import CandidateLocation, CandidateConsent
from sync.sync_engine import SyncEngine
from sync.apps_script_client import apps_script_client


@pytest.fixture
def sync_setup():
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "sync_test.db")
    test_mgr = DatabaseManager(db_path)
    repo = CandidateRepository(db_manager_instance=test_mgr)
    engine = SyncEngine()
    return repo, engine


def test_apps_script_client_url_validation():
    """Verifies that AppsScriptClient correctly validates configured endpoints and API keys."""
    # Placeholder or empty -> not configured
    with patch.object(apps_script_client, "get_endpoint_url", return_value="https://script.google.com/macros/s/YOUR_DEPLOYMENT_ID/exec"), \
         patch.object(apps_script_client, "get_api_key", return_value="pst_secret_key"):
        assert not apps_script_client.is_configured()

    with patch.object(apps_script_client, "get_endpoint_url", return_value=""), \
         patch.object(apps_script_client, "get_api_key", return_value="pst_secret_key"):
        assert not apps_script_client.is_configured()

    # Missing API key -> not configured
    with patch.object(apps_script_client, "get_endpoint_url", return_value="https://script.google.com/macros/s/AKfycbz_1234567890/exec"), \
         patch.object(apps_script_client, "get_api_key", return_value=""):
        assert not apps_script_client.is_configured()

    # Valid deployment URL and API key -> configured
    with patch.object(apps_script_client, "get_endpoint_url", return_value="https://script.google.com/macros/s/AKfycbz_1234567890/exec"), \
         patch.object(apps_script_client, "get_api_key", return_value="pst_secret_key"):
        assert apps_script_client.is_configured()


def test_push_candidates_contract_and_security():
    """Verifies exact JSON contract: sends api_key, no spreadsheet_id, and handles HTML/redirects safely."""
    cand = Candidate(full_name="Pooja Parab", mobile="9822334455", village="Arambol", employment=Employment(status="EMPLOYED"))

    # 1. Successful push verifies payload contract
    with patch.object(apps_script_client, "get_endpoint_url", return_value="https://script.google.com/macros/s/AKfycbz_test/exec"), \
         patch.object(apps_script_client, "get_api_key", return_value="pst_test_key_xyz"), \
         patch("requests.post") as mock_post:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://script.googleusercontent.com/macros/echo"
        mock_resp.history = []
        mock_resp.headers = {"Content-Type": "application/json"}
        mock_resp.text = '{"status": "SUCCESS", "records_processed": 1}'
        mock_resp.json.return_value = {"status": "SUCCESS", "records_processed": 1}
        mock_post.return_value = mock_resp

        res = apps_script_client.push_candidates([cand])
        assert res["status"] == "SUCCESS"

        # Check payload contract
        sent_json = mock_post.call_args[1]["json"]
        assert sent_json["api_key"] == "pst_test_key_xyz"
        assert "candidates" in sent_json
        assert len(sent_json["candidates"]) == 1
        assert "spreadsheet_id" not in sent_json
        assert "worksheet_name" not in sent_json

        # Ensure no row_values or data wrapper columns
        cand_payload = sent_json["candidates"][0]
        assert "row_values" not in cand_payload
        assert "data" not in cand_payload
        assert "candidate_id" in cand_payload
        assert "full_name" in cand_payload
        assert "village" in cand_payload
        assert "mobile" in cand_payload
        assert "highest_qualification" in cand_payload
        assert "employment_status" in cand_payload
        assert "aadhaar" not in str(cand_payload).lower()
        assert "pan_number" not in str(cand_payload).lower()

    # 2. HTML response (e.g. Apps script crashed or returned HTML error page) MUST NOT be marked SUCCESS
    with patch.object(apps_script_client, "get_endpoint_url", return_value="https://script.google.com/macros/s/AKfycbz_test/exec"), \
         patch.object(apps_script_client, "get_api_key", return_value="pst_test_key_xyz"), \
         patch("requests.post") as mock_post:

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://script.googleusercontent.com/macros/echo"
        mock_resp.history = []
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = "<html><body>Error: Script error</body></html>"
        mock_post.return_value = mock_resp

        res = apps_script_client.push_candidates([cand])
        assert res["status"] == "FAILURE"
        assert "HTML" in res["error"]

    # 3. Google Login redirect MUST be flagged as configuration error
    with patch.object(apps_script_client, "get_endpoint_url", return_value="https://script.google.com/macros/s/AKfycbz_test/exec"), \
         patch.object(apps_script_client, "get_api_key", return_value="pst_test_key_xyz"), \
         patch("requests.post") as mock_post:

        redirect_item = MagicMock()
        redirect_item.url = "https://accounts.google.com/ServiceLogin"
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.url = "https://accounts.google.com/ServiceLogin"
        mock_resp.history = [redirect_item]
        mock_resp.headers = {"Content-Type": "text/html"}
        mock_resp.text = "<html>Login</html>"
        mock_post.return_value = mock_resp

        res = apps_script_client.push_candidates([cand])
        assert res["status"] == "FAILURE"
        assert "Anyone" in res["error"]



def test_sync_appends_new_candidate(sync_setup):
    repo, engine = sync_setup
    cand = Candidate(full_name="Anand Vengurlekar", mobile="9822445566", village="Querim", employment=Employment(status="EMPLOYED"))
    cand = repo.save_candidate(cand)
    assert cand.sync_status == "PENDING"

    # Mock Apps Script Client
    with patch("sync.sync_engine.repository", repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates") as mock_push:

        mock_push.return_value = {"status": "SUCCESS", "records_pushed": 1}

        result = engine.run_sync()

        assert result["status"] == "SUCCESS"
        assert result["records_pushed"] == 1
        mock_push.assert_called_once()

        # Verify candidate is now SYNCED in SQLite
        updated_cand = repo.get_candidate(cand.candidate_id)
        assert updated_cand.sync_status == "SYNCED"
        assert updated_cand.last_synced_at is not None


def test_sync_unconfigured_gateway_preserves_local_data(sync_setup):
    repo, engine = sync_setup
    cand = Candidate(full_name="Geeta Sawant", mobile="9822778899", village="Corgao", employment=Employment(status="EMPLOYED"))
    cand = repo.save_candidate(cand)

    with patch("sync.sync_engine.repository", repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=False):

        result = engine.run_sync()

        assert result["status"] == "NOT_CONFIGURED"
        assert result["records_pushed"] == 0

        # Local candidate remains safely in SQLite as PENDING
        updated_cand = repo.get_candidate(cand.candidate_id)
        assert updated_cand.sync_status == "PENDING"


def test_offline_failure_preserves_local_data_as_pending(sync_setup):
    repo, engine = sync_setup
    cand = Candidate(full_name="Deepak Malik", mobile="9822114477", village="Paliem", employment=Employment(status="UNEMPLOYED"))
    cand = repo.save_candidate(cand)
    assert cand.sync_status == "PENDING"

    # Simulate network failure during HTTPS POST to Apps Script
    with patch("sync.sync_engine.repository", repo), \
         patch("sync.sync_engine.apps_script_client.is_configured", return_value=True), \
         patch("sync.sync_engine.apps_script_client.push_candidates", return_value={"status": "FAILURE", "error": "Connection timed out"}):

        result = engine.run_sync()

        assert result["status"] == "FAILURE"
        # Candidate MUST still be safely stored locally as PENDING!
        cand_in_db = repo.get_candidate(cand.candidate_id)
        assert cand_in_db is not None
        assert cand_in_db.sync_status == "PENDING"


def test_candidate_to_backup_dict_tabular_structure():
    """Verifies that Candidate.to_backup_dict produces a clean tabular dictionary with dedicated fields."""
    c = Candidate(
        candidate_id="PST-000042",
        full_name="Nilesh Parsekar",
        dob="1995-08-12",
        age=30,
        gender="Male",
        address="House 45",
        village="Mandrem",
        taluka="Pernem",
        pincode="403527",
        mobile="9822112233",
        alternate_mobile="9822998877",
        email="nilesh@example.com",
        education=Education(
            highest_qualification="Graduate - B.Com",
            degree_course="Bachelor of Commerce",
            specialisation="Accounting",
            institution="DMC College",
            passing_year=2017,
            skills="Tally, GST, Excel"
        ),
        employment=Employment(
            status="EMPLOYED",
            category="Private",
            department_company="Local Logistics Pvt Ltd",
            designation="Senior Accountant",
            work_location="Tuem IDC",
            years_experience=5.5
        )
    )

    backup_dict = c.to_backup_dict()

    # 1. candidate_id is the first key
    keys = list(backup_dict.keys())
    assert keys[0] == "candidate_id"
    assert backup_dict["candidate_id"] == "PST-000042"

    # 2. No catch-all or serialized keys
    assert "row_values" not in backup_dict
    assert "data" not in backup_dict

    # 3. Dedicated fields are properly populated
    assert backup_dict["full_name"] == "Nilesh Parsekar"
    assert backup_dict["dob"] == "1995-08-12"
    assert backup_dict["age"] == 30
    assert backup_dict["gender"] == "Male"
    assert backup_dict["village"] == "Mandrem"
    assert backup_dict["taluka"] == "Pernem"
    assert backup_dict["mobile"] == "9822112233"
    assert backup_dict["highest_qualification"] == "Graduate - B.Com"
    assert backup_dict["course"] == "Bachelor of Commerce"
    assert backup_dict["specialisation"] == "Accounting"
    assert backup_dict["institution"] == "DMC College"
    assert backup_dict["passing_year"] == 2017
    assert backup_dict["skills"] == "Tally, GST, Excel"
    assert backup_dict["employment_status"] == "EMPLOYED"
    assert backup_dict["employment_category"] == "Private"
    assert backup_dict["organisation"] == "Local Logistics Pvt Ltd"
    assert backup_dict["designation"] == "Senior Accountant"

    # 4. Excludes sensitive ID documents
    assert "aadhaar" not in str(backup_dict).lower()
    assert "pan" not in str(backup_dict).lower()

    # 5. Every single value is a primitive (str, int, float, bool) — no nested dicts or lists
    for k, v in backup_dict.items():
        assert not isinstance(v, (dict, list)), f"Value for key '{k}' must not be a complex object (was {type(v)})"


def test_candidate_location_regression_and_defensive_serialization():
    """
    Regression test: Verifies Candidate.to_backup_dict() correctly maps real
    CandidateLocation fields (including 'booth' to 'polling_booth') and never
    raises AttributeError on missing or None location attributes.
    """
    # 1. Candidate with actual CandidateLocation instance
    c1 = Candidate(
        candidate_id="PST-000101",
        full_name="Deepa Parsekar",
        village="Corgao",
        location=CandidateLocation(
            candidate_id="PST-000101",
            vaddo="Gauravaddo",
            village="Corgao",
            booth="Polling Booth 22"
        ),
        consent=CandidateConsent(
            candidate_id="PST-000101",
            consent_status="Consented",
            consent_date="2026-09-07"
        )
    )

    d1 = c1.to_backup_dict()
    assert d1["candidate_id"] == "PST-000101"
    assert d1["vaddo"] == "Gauravaddo"
    assert d1["polling_booth"] == "Polling Booth 22"
    assert d1["recruiter_consent_status"] == "Consented"
    assert d1["recruiter_consent_date"] == "2026-09-07"

    # 2. Candidate with CandidateLocation having None / empty fields
    c2 = Candidate(
        candidate_id="PST-000102",
        full_name="Rajesh Sawant",
        village="Arambol",
        location=CandidateLocation(
            candidate_id="PST-000102",
            vaddo="",
            village="Arambol",
            booth=""
        )
    )

    d2 = c2.to_backup_dict()
    assert d2["candidate_id"] == "PST-000102"
    assert d2["vaddo"] == ""
    assert d2["polling_booth"] == ""

    # 3. Candidate with location=None
    c3 = Candidate(
        candidate_id="PST-000103",
        full_name="Sanjay Naik",
        village="Querim",
        location=None,
        consent=None
    )

    d3 = c3.to_backup_dict()
    assert d3["candidate_id"] == "PST-000103"
    assert d3["vaddo"] == ""
    assert d3["polling_booth"] == ""
    assert d3["recruiter_consent_status"] == ""
    assert d3["recruiter_consent_date"] == ""



