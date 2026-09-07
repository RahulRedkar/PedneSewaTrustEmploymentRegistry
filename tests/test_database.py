"""
Unit tests for SQLite database repository, sequential Candidate ID generation,
transactions, and duplicate detection.
"""

import os
import tempfile
import pytest
from database.connection import DatabaseManager
from database.repository import CandidateRepository
from models.candidate import Candidate, Education, Employment, EmploymentPreferences


@pytest.fixture
def repo():
    # Use isolated temporary database for each test
    temp_dir = tempfile.mkdtemp()
    db_path = os.path.join(temp_dir, "test.db")
    test_mgr = DatabaseManager(db_path)
    r = CandidateRepository(db_manager_instance=test_mgr)
    yield r
    # No strict file delete needed, OS cleans temp dir


def test_sequential_id_generation(repo):
    c1 = Candidate(full_name="Candidate One", mobile="9822000001", village="Mandrem", employment=Employment(status="EMPLOYED"))
    c1 = repo.save_candidate(c1)
    assert c1.candidate_id == "PST-000001"
    assert c1.sync_status == "PENDING"

    c2 = Candidate(full_name="Candidate Two", mobile="9822000002", village="Arambol", employment=Employment(status="UNEMPLOYED"))
    c2 = repo.save_candidate(c2)
    assert c2.candidate_id == "PST-000002"
    assert c2.sync_status == "PENDING"


def test_candidate_retrieval(repo):
    c = Candidate(
        full_name="Sunil Gawande",
        mobile="9822334455",
        village="Pernem (Town)",
        education=Education(highest_qualification="Graduate - B.E. / B.Tech", degree_course="Computer Engineering"),
        employment=Employment(status="EMPLOYED", category="Private", department_company="Tech Solutions", designation="Developer", years_experience=3.5),
        preferences=EmploymentPreferences(preferred_sector="IT", willing_to_relocate=True)
    )
    saved = repo.save_candidate(c)
    fetched = repo.get_candidate(saved.candidate_id)

    assert fetched is not None
    assert fetched.candidate_id == "PST-000001"
    assert fetched.full_name == "Sunil Gawande"
    assert fetched.education.highest_qualification == "Graduate - B.E. / B.Tech"
    assert fetched.employment.department_company == "Tech Solutions"
    assert fetched.employment.years_experience == 3.5
    assert fetched.preferences.willing_to_relocate is True


def test_duplicate_detection(repo):
    c1 = Candidate(
        full_name="Amit Naik",
        mobile="9822998877",
        email="amit@example.com",
        village="Tuem",
        address="House 45, Near School",
        employment=Employment(status="SELF_EMPLOYED")
    )
    repo.save_candidate(c1)

    # 1. Exact mobile duplicate
    dups1 = repo.check_duplicates(mobile="9822998877")
    assert len(dups1) == 1
    assert dups1[0]["candidate_id"] == "PST-000001"
    assert "Exact Mobile Number match" in dups1[0]["reasons"]

    # 2. Email duplicate
    dups2 = repo.check_duplicates(mobile="9800000000", email="amit@example.com")
    assert len(dups2) == 1
    assert "Exact Email match" in dups2[0]["reasons"]

    # 3. Name + Address duplicate
    dups3 = repo.check_duplicates(mobile="9811111111", full_name="Amit Naik", address="House 45, Near School")
    assert len(dups3) == 1
    assert "Same Full Name & Address" in dups3[0]["reasons"]

    # 4. No duplicate for new person
    dups4 = repo.check_duplicates(mobile="9700000000", full_name="Suresh Parab")
    assert len(dups4) == 0


def test_candidate_update_re_marks_pending(repo):
    c = Candidate(full_name="Pooja Pednekar", mobile="9822123456", village="Morjim", employment=Employment(status="STUDENT"))
    c = repo.save_candidate(c)
    assert c.sync_status == "PENDING"

    # Simulate it was synced
    repo.mark_candidates_synced([c.candidate_id], "2026-09-04T12:00:00")
    synced_c = repo.get_candidate(c.candidate_id)
    assert synced_c.sync_status == "SYNCED"

    # Now edit candidate locally
    synced_c.full_name = "Pooja P. Pednekar"
    synced_c.employment.status = "EMPLOYED"
    synced_c.employment.category = "Government"
    repo.update_candidate(synced_c)

    updated_c = repo.get_candidate(c.candidate_id)
    assert updated_c.full_name == "Pooja P. Pednekar"
    assert updated_c.employment.category == "Government"
    assert updated_c.sync_status == "PENDING"  # Must be re-marked PENDING!


def test_delete_candidate(repo):
    c = Candidate(full_name="To Delete", mobile="9822556677", village="Torxem", employment=Employment(status="UNEMPLOYED"))
    c = repo.save_candidate(c)
    assert repo.get_candidate(c.candidate_id) is not None

    repo.delete_candidate(c.candidate_id)
    assert repo.get_candidate(c.candidate_id) is None


def test_unemployed_candidate_with_previous_experience(repo):
    c = Candidate(
        full_name="Santosh Parab",
        mobile="9822998877",
        village="Mandrem",
        employment=Employment(
            status="UNEMPLOYED",
            years_experience=3.5,
            previous_experience="Accountant at ABC Logistics",
            govt_applied=True,
            govt_post_exam="Junior Assistant",
            govt_department="Directorate of Accounts",
            govt_result_status="Awaiting Result"
        )
    )
    saved = repo.save_candidate(c)
    assert saved.candidate_id.startswith("PST-")

    retrieved = repo.get_candidate(saved.candidate_id)
    assert retrieved is not None
    assert retrieved.employment.status == "UNEMPLOYED"
    assert retrieved.employment.years_experience == 3.5
    assert retrieved.employment.previous_experience == "Accountant at ABC Logistics"
    assert retrieved.employment.govt_applied is True
    assert retrieved.employment.govt_post_exam == "Junior Assistant"

    # Test update
    retrieved.employment.years_experience = 4.0
    retrieved.employment.previous_experience = "Senior Accountant at ABC Logistics"
    repo.update_candidate(retrieved)

    updated = repo.get_candidate(saved.candidate_id)
    assert updated.employment.years_experience == 4.0
    assert updated.employment.previous_experience == "Senior Accountant at ABC Logistics"


def test_office_id_generation_and_segregation(repo):
    # 1. Korgao Candidates (Prefix KPST)
    k1 = Candidate(full_name="Korgao Candidate 1", mobile="9822000011", village="Corgao", intake_office="Korgao")
    k1 = repo.save_candidate(k1)
    assert k1.candidate_id == "KPST-000001"
    assert k1.intake_office == "Korgao"

    k2 = Candidate(full_name="Korgao Candidate 2", mobile="9822000012", village="Corgao", intake_office="Korgao")
    k2 = repo.save_candidate(k2)
    assert k2.candidate_id == "KPST-000002"
    assert k2.intake_office == "Korgao"

    # 2. Pernem Candidates (Prefix PST)
    p1 = Candidate(full_name="Pernem Candidate 1", mobile="9822000021", village="Pernem (Town)", intake_office="Pernem")
    p1 = repo.save_candidate(p1)
    assert p1.candidate_id == "PST-000001"
    assert p1.intake_office == "Pernem"

    p2 = Candidate(full_name="Pernem Candidate 2", mobile="9822000022", village="Mandrem", intake_office="Pernem")
    p2 = repo.save_candidate(p2)
    assert p2.candidate_id == "PST-000002"
    assert p2.intake_office == "Pernem"

    # 3. Third Korgao candidate increments independently
    k3 = Candidate(full_name="Korgao Candidate 3", mobile="9822000013", village="Corgao", intake_office="Korgao")
    k3 = repo.save_candidate(k3)
    assert k3.candidate_id == "KPST-000003"

    # 4. Verification of database retrieval
    ret_k1 = repo.get_candidate("KPST-000001")
    assert ret_k1 is not None
    assert ret_k1.intake_office == "Korgao"
    assert ret_k1.full_name == "Korgao Candidate 1"

    ret_p1 = repo.get_candidate("PST-000001")
    assert ret_p1 is not None
    assert ret_p1.intake_office == "Pernem"
    assert ret_p1.full_name == "Pernem Candidate 1"

    # 5. Verification of get_all_candidates
    all_cands = repo.get_all_candidates()
    assert len(all_cands) == 5
    offices = {c.candidate_id: c.intake_office for c in all_cands}
    assert offices["KPST-000001"] == "Korgao"
    assert offices["KPST-000002"] == "Korgao"
    assert offices["KPST-000003"] == "Korgao"
    assert offices["PST-000001"] == "Pernem"
    assert offices["PST-000002"] == "Pernem"


