"""
Unit tests verifying UI component behavior, DateOfBirthPicker, and Dashboard data integrity.
"""

import pytest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QDate

from ui.components.dob_picker import DateOfBirthPicker
from reports.analytics_engine import analytics_engine
from models.candidate import Candidate, Employment


@pytest.fixture(scope="session")
def qapp():
    app = QApplication.instance()
    if not app:
        app = QApplication([])
    return app


def test_dob_picker_initialization_and_range(qapp):
    """Verifies native calendar DOB picker initialization, allowed range, and blank support."""
    picker = DateOfBirthPicker()

    # Allowed range: 1920 to today
    today = QDate.currentDate()
    assert picker.date_edit.maximumDate() == today

    # Initial state: blank/optional (get_date_iso returns None)
    assert picker.get_date_iso() is None
    assert picker.btn_clear.isEnabled() is False

    # Check calendarPopup is enabled
    assert picker.date_edit.calendarPopup() is True

    # Check display format is dd/MM/yyyy
    assert picker.date_edit.displayFormat() == "dd/MM/yyyy"

    # Setting valid date produces valid ISO and enables clear button
    sample_date = today.addYears(-22)
    picker.set_date_iso(sample_date.toString("yyyy-MM-dd"))
    assert picker.get_date_iso() == sample_date.toString("yyyy-MM-dd")
    assert picker.btn_clear.isEnabled() is True

    # Clear button resets to blank
    picker.clear()
    assert picker.get_date_iso() is None
    assert picker.btn_clear.isEnabled() is False



def test_dashboard_data_integrity_reconciliation():
    """
    Verifies that every KPI total and its displayed breakdown reconcile strictly
    against the underlying candidate records:
    - Employed = Govt Employed + Private Employed
    - Unemployed = Govt Applicants + Never Applied
    - Total = Employed + Unemployed + Self-Employed + Students
    """
    candidates = [
        Candidate(full_name="Candidate A", mobile="9822111101", village="Mandrem", employment=Employment(status="EMPLOYED", category="Government")),
        Candidate(full_name="Candidate B", mobile="9822111102", village="Corgao", employment=Employment(status="EMPLOYED", category="Private")),
        Candidate(full_name="Candidate C", mobile="9822111103", village="Tuem", employment=Employment(status="EMPLOYED")), # unspecified category -> reconciles as Private
        Candidate(full_name="Candidate D", mobile="9822111104", village="Arambol", employment=Employment(status="UNEMPLOYED", govt_applied=True)),
        Candidate(full_name="Candidate E", mobile="9822111105", village="Morjim", employment=Employment(status="UNEMPLOYED", govt_applied=False)),
        Candidate(full_name="Candidate F", mobile="9822111106", village="Dargalim", employment=Employment(status="SELF_EMPLOYED")),
        Candidate(full_name="Candidate G", mobile="9822111107", village="Pernem", employment=Employment(status="STUDENT")),
    ]

    summary = analytics_engine.get_dashboard_summary(candidates)

    # 1. Total count
    assert summary["total_candidates"] == 7

    # 2. Employed reconciliation
    assert summary["employed"] == 3
    assert summary["govt_employed"] == 1
    assert summary["private_employed"] == 2
    assert summary["employed"] == summary["govt_employed"] + summary["private_employed"]

    # 3. Unemployed reconciliation
    assert summary["unemployed"] == 2
    assert summary["govt_applicants"] == 1
    assert summary["never_applied"] == 1
    assert summary["unemployed"] == summary["govt_applicants"] + summary["never_applied"]

    # 4. Total sum reconciliation
    assert summary["total_candidates"] == (
        summary["employed"] + summary["unemployed"] + summary["self_employed"] + summary["students"]
    )


def test_phase2_views_instantiation_and_components(qapp):
    """Verifies that all Phase 2 views and dialogs instantiate cleanly with new components."""
    from ui.views.candidate_form_view import CandidateFormView
    from ui.dialogs.candidate_edit_dialog import CandidateEditDialog
    from ui.dialogs.candidate_details_dialog import CandidateDetailsDialog
    from ui.views.government_jobs_view import GovernmentJobsView
    from ui.views.recruiters_view import RecruitersView
    from ui.views.dashboard_view import DashboardView
    from ui.views.reports_view import ReportsView

    # 1. CandidateFormView has house, vaddo, booth, document and consent sections
    form_view = CandidateFormView()
    assert hasattr(form_view, "edit_house")
    assert hasattr(form_view, "edit_vaddo")
    assert hasattr(form_view, "edit_booth")
    assert hasattr(form_view, "doc_widgets")
    assert hasattr(form_view, "combo_consent_status")
    assert len(form_view.doc_widgets) >= 8

    # 2. GovernmentJobsView
    gov_view = GovernmentJobsView()
    assert hasattr(gov_view, "table")
    assert hasattr(gov_view, "txt_search")
    assert hasattr(gov_view, "cmb_status")

    # 4. RecruitersView
    rec_view = RecruitersView()
    assert hasattr(rec_view, "tabs")
    assert hasattr(rec_view, "table_recruiters")
    assert hasattr(rec_view, "table_audit")
    assert rec_view.tabs.count() == 2

    # 5. CandidateEditDialog & DetailsDialog
    sample_cand = Candidate(
        candidate_id="PST-TEST-001",
        full_name="Rohan Parab",
        village="Mandrem",
        mobile="9822112233"
    )
    edit_dlg = CandidateEditDialog(sample_cand)
    assert edit_dlg.tabs.count() == 6
    assert hasattr(edit_dlg, "edit_house")
    assert hasattr(edit_dlg, "edit_vaddo")
    assert hasattr(edit_dlg, "edit_booth")
    assert hasattr(edit_dlg, "doc_widgets")
    assert hasattr(edit_dlg, "combo_consent_status")

    det_dlg = CandidateDetailsDialog(sample_cand)
    # Check that it has Document Readiness and Facilitation tabs
    tab_titles = [det_dlg.findChildren(type(edit_dlg.tabs))[0].tabText(i) for i in range(det_dlg.findChildren(type(edit_dlg.tabs))[0].count())]
    assert "Document Readiness" in tab_titles
    assert "Facilitation & Applications" in tab_titles

    # 6. DashboardView has Facilitation metrics
    dash = DashboardView()
    assert hasattr(dash, "row_fac_gov")
    assert hasattr(dash, "row_fac_consented")
    assert hasattr(dash, "row_fac_rec")

    # 7. ReportsView has 8 tabs
    rep = ReportsView()
    assert rep.tabs.count() == 8

