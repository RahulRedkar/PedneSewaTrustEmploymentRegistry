"""
Unit tests for analytics calculations and PDF generation.
"""

import os
import tempfile
import pytest
from reports.analytics_engine import AnalyticsEngine
from reports.pdf_generator import PDFReportGenerator
from models.candidate import Candidate, Education, Employment, EmploymentPreferences


def test_analytics_dashboard_summary():
    engine = AnalyticsEngine()

    c1 = Candidate(full_name="A", mobile="9822111111", village="Mandrem", employment=Employment(status="EMPLOYED", category="Government"))
    c2 = Candidate(full_name="B", mobile="9822222222", village="Arambol", employment=Employment(status="EMPLOYED", category="Private"))
    c3 = Candidate(full_name="C", mobile="9822333333", village="Corgao", employment=Employment(status="UNEMPLOYED", govt_applied=True))
    c4 = Candidate(full_name="D", mobile="9822444444", village="Tuem", employment=Employment(status="UNEMPLOYED", govt_applied=False))
    c5 = Candidate(full_name="E", mobile="9822555555", village="Morjim", employment=Employment(status="SELF_EMPLOYED"))

    candidates = [c1, c2, c3, c4, c5]
    summary = engine.get_dashboard_summary(candidates)

    assert summary["total_candidates"] == 5
    assert summary["employed"] == 2
    assert summary["govt_employed"] == 1
    assert summary["private_employed"] == 1
    assert summary["unemployed"] == 2
    assert summary["govt_applicants"] == 1
    assert summary["never_applied"] == 1
    assert summary["self_employed"] == 1
    assert summary["employment_rate"] == 40.0


def test_pdf_report_generation():
    temp_dir = tempfile.mkdtemp()
    gen = PDFReportGenerator(output_dir=temp_dir)

    headers = ["Category", "Count", "Percentage"]
    rows = [
        ["Employed", "45", "45.0%"],
        ["Unemployed", "30", "30.0%"],
        ["Self-Employed", "15", "15.0%"],
        ["Students", "10", "10.0%"]
    ]

    out_pdf = os.path.join(temp_dir, "test_report.pdf")
    gen.generate_report("Employment Test Summary", headers, rows, target_filepath=out_pdf)

    assert os.path.exists(out_pdf)
    assert os.path.getsize(out_pdf) > 1000  # Generated valid PDF
