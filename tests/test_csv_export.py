"""
Unit tests for CSV export and database backup mechanisms.
"""

import os
import csv
import tempfile
import pytest
from export.csv_exporter import CSVExporter
from export.backup_manager import BackupManager
from models.candidate import Candidate, Education, Employment, EmploymentPreferences
from database.connection import DatabaseManager
from database.repository import CandidateRepository
from app.constants import GOOGLE_SHEETS_COLUMNS


def test_csv_export_format_and_encoding():
    temp_dir = tempfile.mkdtemp()
    exporter = CSVExporter(export_dir=temp_dir)

    cand = Candidate(
        candidate_id="PST-000001",
        full_name="सुनील परब (Sunil Parab)",  # Devanagari Unicode
        mobile="9822112233",
        village="Corgao",
        address="House No. 12, Near \"Temple\", Main Road",  # Quotes & Commas
        employment=Employment(status="EMPLOYED", category="Private", department_company="Acme Corp, Goa", designation="Senior \"Lead\" Engineer")
    )

    out_file = os.path.join(temp_dir, "test_export.csv")
    exporter.export_candidates([cand], target_filepath=out_file)

    assert os.path.exists(out_file)

    with open(out_file, mode="r", encoding="utf-8-sig") as f:
        reader = csv.reader(f)
        header = next(reader)
        assert header == GOOGLE_SHEETS_COLUMNS
        assert len(header) == 42

        row = next(reader)
        assert row[0] == "PST-000001"
        assert row[2] == "सुनील परब (Sunil Parab)"
        assert "House No. 12, Near \"Temple\", Main Road" in row[6]
        assert row[20] == "EMPLOYED"
        assert row[22] == "Acme Corp, Goa"


def test_automatic_backup_and_pruning():
    temp_dir = tempfile.mkdtemp()
    mgr = BackupManager(backup_dir=temp_dir)

    # Create 3 automatic backups
    b1 = mgr.create_backup(is_automatic=True)
    assert os.path.exists(b1)

    # Pruning keeps last N
    mgr.prune_automatic_backups(keep_count=1)
    backups = mgr.list_backups()
    assert len(backups) <= 1
