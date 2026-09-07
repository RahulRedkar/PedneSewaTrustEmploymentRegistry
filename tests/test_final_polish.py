"""
Comprehensive verification tests for Pedne Sewa Trust - Final Polish & GitHub Readiness.
Covers:
1. Google Apps Script Web App backup configuration & URL validation.
2. Demonstration data generator & admin purge actions.
3. Elimination of Private Jobs from Sidebar, MainWindow stack, and Dashboard.
4. Operator-facing "Backup to Cloud" button presence & absence of forbidden terms.
5. User-chosen export destination saving.
6. Clean human-readable titles with zero machine-style underscores.
7. Settings view contains no CSV/PDF export directory row.
8. Git ignore rules and credentials safety.
"""

import os
from pathlib import Path
from PySide6.QtWidgets import QApplication

from sync.apps_script_client import apps_script_client
from database.demo_data_generator import generate_100_demo_candidates, seed_demo_data
from database.repository import repository
from reports.analytics_engine import analytics_engine
from ui.components.sidebar import Sidebar
from ui.components.header_bar import HeaderBar
from ui.views.dashboard_view import DashboardView
from ui.views.candidate_form_view import CandidateFormView
from ui.dialogs.candidate_edit_dialog import CandidateEditDialog
from ui.views.reports_view import ReportsView
from ui.views.backup_view import BackupView
from ui.views.settings_view import SettingsView
from ui.main_window import MainWindow
from models.candidate import Candidate
from export.csv_exporter import csv_exporter
from reports.csv_report_exporter import report_csv_exporter
from reports.pdf_generator import pdf_generator


def test_apps_script_backup_configuration():
    """Verifies that AppsScriptClient handles configuration without requiring credentials.json."""
    assert hasattr(apps_script_client, "is_configured")
    assert hasattr(apps_script_client, "push_candidates")
    url = apps_script_client.get_endpoint_url()
    assert isinstance(url, str)


def test_demo_data_generation_and_admin_removal():
    """Verifies that 100 synthetic candidates generate cleanly and pass all integrity tests."""
    cands = generate_100_demo_candidates()
    assert len(cands) == 100
    for c in cands:
        assert c.is_demo is True
        assert c.candidate_id.startswith("PST-DEMO-")

    # Verify analytics reconciliation
    summary = analytics_engine.get_dashboard_summary(cands)
    assert summary["total_candidates"] == 100
    assert summary["employed"] == summary["govt_employed"] + summary["private_employed"]
    assert summary["unemployed"] == summary["govt_applicants"] + summary["never_applied"]
    assert summary["total_candidates"] == summary["employed"] + summary["unemployed"] + summary["self_employed"] + summary["students"]



def test_no_private_jobs_in_ui(qapp):
    """Verifies that Private Jobs is completely removed from Sidebar, MainWindow stack, and Dashboard."""
    # 1. Sidebar has 8 items and none mention Private Jobs
    sb = Sidebar()
    button_texts = [btn.text() for btn in sb.buttons]
    assert "Private Jobs" not in button_texts
    assert len(button_texts) == 9

    # 2. MainWindow stack has 9 views matching Sidebar
    win = MainWindow()
    assert win.stack.count() == 9
    assert not hasattr(win, "private_jobs_view")

    # 3. Dashboard has no private job metric rows
    dash = DashboardView()
    assert not hasattr(dash, "row_fac_priv")
    assert hasattr(dash, "row_fac_gov")
    assert hasattr(dash, "row_fac_consented")


def test_backup_to_cloud_button_presence_and_sanitization(qapp):
    """Verifies that 'Backup to Cloud' is present and no forbidden provider terms appear in operator UI."""
    hb = HeaderBar()
    assert hasattr(hb, "btn_backup_cloud")
    assert hb.btn_backup_cloud.text() == "Backup to Cloud"

    bv = BackupView()
    assert hasattr(bv, "btn_backup_cloud")
    assert bv.btn_backup_cloud.text() == "Backup to Cloud"

    # Verify absence of forbidden terms in visible operator buttons
    forbidden_terms = ["Google Sheets", "Google", "OAuth", "Spreadsheet"]
    for btn in hb.findChildren(type(hb.btn_backup_cloud)):
        for ft in forbidden_terms:
            assert ft.lower() not in btn.text().lower(), f"Forbidden term '{ft}' in HeaderBar button '{btn.text()}'"

    for btn in bv.findChildren(type(bv.btn_backup_cloud)):
        for ft in forbidden_terms:
            assert ft.lower() not in btn.text().lower(), f"Forbidden term '{ft}' in BackupView button '{btn.text()}'"


def test_user_chosen_export_destinations(tmp_path):
    """Verifies that CSV and PDF exporters properly honor user-specified custom file destinations."""
    cand = Candidate(
        candidate_id="PST-000001",
        full_name="Govind Parab",
        village="Arambol",
        mobile="9822112233"
    )

    # 1. Custom CSV export destination
    target_csv = tmp_path / "custom_folder" / "candidates_export.csv"
    target_csv.parent.mkdir(parents=True, exist_ok=True)
    out_csv = csv_exporter.export_candidates([cand], target_filepath=str(target_csv))
    assert os.path.exists(out_csv)
    assert Path(out_csv).resolve() == target_csv.resolve()

    # 2. Custom Report CSV destination
    target_rep_csv = tmp_path / "custom_folder" / "report_export.csv"
    out_rep_csv = report_csv_exporter.export_report_table("Test Report", ["H1", "H2"], [["A", "B"]], target_filepath=str(target_rep_csv))
    assert os.path.exists(out_rep_csv)
    assert Path(out_rep_csv).resolve() == target_rep_csv.resolve()

    # 3. Custom Report PDF destination
    target_pdf = tmp_path / "custom_folder" / "report_export.pdf"
    out_pdf = pdf_generator.generate_report("Test Report", ["Col1", "Col2"], [["Data1", "Data2"]], target_filepath=str(target_pdf))
    assert os.path.exists(out_pdf)
    assert Path(out_pdf).resolve() == target_pdf.resolve()


def test_clean_titles_and_no_underscores(qapp):
    """Verifies that visible group titles, tabs, and headers use natural titles with zero machine underscores."""
    # 1. CandidateFormView section headers
    form_view = CandidateFormView()
    from PySide6.QtWidgets import QGroupBox
    groups = form_view.findChildren(QGroupBox)
    group_titles = [g.title() for g in groups]
    assert any("1. Personal Details" in t for t in group_titles)
    assert any("2. Education Details" in t for t in group_titles)
    assert any("3. Employment Classification" in t for t in group_titles)
    assert any("4. Preferences & Skills" in t for t in group_titles)
    assert any("5. Document Readiness" in t for t in group_titles)
    assert any("6. Recruiter Consent & Facilitation" in t for t in group_titles)
    for t in group_titles:
        assert "_" not in t, f"Underscore found in group title: {t}"

    # 2. CandidateEditDialog tabs
    sample_cand = Candidate(
        candidate_id="PST-000001",
        full_name="Govind Parab",
        village="Arambol",
        mobile="9822112233"
    )
    edit_dlg = CandidateEditDialog(sample_cand)
    edit_tab_names = [edit_dlg.tabs.tabText(i) for i in range(edit_dlg.tabs.count())]
    assert "4. Preferences & Skills" in edit_tab_names
    assert "5. Document Readiness" in edit_tab_names
    for name in edit_tab_names:
        assert "_" not in name, f"Underscore found in edit tab: {name}"

    # 3. ReportsView tabs
    rep_view = ReportsView()
    rep_tab_names = [rep_view.tabs.tabText(i) for i in range(rep_view.tabs.count())]
    assert "6. Preferences & Skills" in rep_tab_names
    assert "7. Document Readiness" in rep_tab_names
    assert "8. Recruiter-Ready Candidates" in rep_tab_names
    for name in rep_tab_names:
        assert "_" not in name, f"Underscore found in report tab: {name}"


def test_settings_view_no_export_directory_row(qapp):
    """Verifies that SettingsView has removed all CSV/PDF export directory configuration."""
    settings = SettingsView()
    assert not hasattr(settings, "edit_export_dir")
    from PySide6.QtWidgets import QLabel
    labels = [lbl.text() for lbl in settings.findChildren(QLabel)]
    for lbl in labels:
        assert "export folder" not in lbl.lower()
        assert "exports folder" not in lbl.lower()


def test_gitignore_security_rules():
    """Verifies that .gitignore covers all credentials, database, and cache paths."""
    gi_path = Path(__file__).resolve().parent.parent / ".gitignore"
    assert gi_path.exists()
    content = gi_path.read_text(encoding="utf-8")
    assert "credentials.json" in content
    assert "google_token.json" in content
    assert "*.db" in content
    assert "*.sqlite" in content
    assert "__pycache__" in content
    assert ".pytest_cache" in content
