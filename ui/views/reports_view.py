"""
Reports & Analytics View for Pedne Sewa Trust - Employment Registry.
Provides multi-category demographic analysis, interactive filtering,
CSV report exports, and publication-ready PDF report generation using Qt icons.
"""

from datetime import datetime
from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QComboBox,
    QPushButton, QTabWidget, QTableWidget, QTableWidgetItem,
    QHeaderView, QFrame, QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from models.candidate import Candidate
from database.repository import repository
from facilitation.document_manager import DocumentManager
from reports.analytics_engine import analytics_engine
from reports.csv_report_exporter import report_csv_exporter
from reports.pdf_generator import pdf_generator
from app.constants import PERNEM_VILLAGES, QUALIFICATION_LEVELS, EMPLOYMENT_STATUSES
from app.signals import signals
from ui.components.icons import AppIcons
from utils.logger import logger


class ReportsView(QWidget):
    """Analytical reporting suite with multi-dimensional filtering."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.all_candidates: List[Candidate] = []
        self.filtered_candidates: List[Candidate] = []
        self._init_ui()
        self._connect_signals()
        self.reload_reports()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Reports & Community Analytics", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        sub_lbl = QLabel("Generate demographic, geographic, and sectoral insights for Pernem Taluka.", self)
        sub_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        main_layout.addLayout(title_box)

        # 2. Filter Card
        filter_card = QFrame(self)
        filter_card.setProperty("class", "ContentCard")
        f_layout = QHBoxLayout(filter_card)
        f_layout.setContentsMargins(14, 12, 14, 12)
        f_layout.setSpacing(12)

        self.combo_village = QComboBox(filter_card)
        self.combo_village.setMinimumWidth(160)
        self.combo_village.view().setTextElideMode(Qt.ElideNone)
        self.combo_village.addItems(["All Villages"] + PERNEM_VILLAGES)
        self.combo_village.currentIndexChanged.connect(self.apply_report_filters)

        self.combo_status = QComboBox(filter_card)
        self.combo_status.setMinimumWidth(160)
        self.combo_status.view().setTextElideMode(Qt.ElideNone)
        self.combo_status.addItems(["All Statuses"] + EMPLOYMENT_STATUSES)
        self.combo_status.currentIndexChanged.connect(self.apply_report_filters)

        self.combo_qual = QComboBox(filter_card)
        self.combo_qual.setMinimumWidth(180)
        self.combo_qual.view().setTextElideMode(Qt.ElideNone)
        self.combo_qual.addItems(["All Qualifications"] + QUALIFICATION_LEVELS)
        self.combo_qual.currentIndexChanged.connect(self.apply_report_filters)

        btn_reset = QPushButton("Reset Filters", filter_card)
        btn_reset.setProperty("class", "SecondaryButton")
        btn_reset.setIcon(AppIcons.clear())
        btn_reset.clicked.connect(self._reset_filters)

        lbl_v = QLabel("Village:", filter_card); lbl_v.setStyleSheet("color: #64748B; font-weight: 600;")
        lbl_s = QLabel("Status:", filter_card); lbl_s.setStyleSheet("color: #64748B; font-weight: 600;")
        lbl_q = QLabel("Qualification:", filter_card); lbl_q.setStyleSheet("color: #64748B; font-weight: 600;")

        f_layout.addWidget(lbl_v)
        f_layout.addWidget(self.combo_village)
        f_layout.addWidget(lbl_s)
        f_layout.addWidget(self.combo_status)
        f_layout.addWidget(lbl_q)
        f_layout.addWidget(self.combo_qual)
        f_layout.addWidget(btn_reset)
        f_layout.addStretch()

        main_layout.addWidget(filter_card)

        # 3. Report Tabs
        self.tabs = QTabWidget(self)

        # Tab 1: Employment Summary
        self.tab_emp = self._create_report_tab(
            "Employment Summary Report",
            headers=["Employment Classification", "Candidate Count", "Percentage Share"],
            export_csv_fn=self._export_employment_csv,
            export_pdf_fn=self._export_employment_pdf
        )
        self.tabs.addTab(self.tab_emp["widget"], "1. Employment Summary")

        # Tab 2: Village Breakdown
        self.tab_village = self._create_report_tab(
            "Village Employment Report",
            headers=["Village", "Total Candidates", "Employed", "Unemployed", "Govt", "Private", "Self-Employed", "Emp Rate"],
            export_csv_fn=self._export_village_csv,
            export_pdf_fn=self._export_village_pdf
        )
        self.tabs.addTab(self.tab_village["widget"], "2. Village Distribution")

        # Tab 3: Qualifications
        self.tab_qual = self._create_report_tab(
            "Qualification Report",
            headers=["Highest Qualification Level", "Candidate Count", "Percentage Share"],
            export_csv_fn=self._export_qual_csv,
            export_pdf_fn=self._export_qual_pdf
        )
        self.tabs.addTab(self.tab_qual["widget"], "3. Qualifications")

        # Tab 4: Experience Bands
        self.tab_exp = self._create_report_tab(
            "Experience Report",
            headers=["Work Experience Band", "Candidate Count", "Percentage Share"],
            export_csv_fn=self._export_exp_csv,
            export_pdf_fn=self._export_exp_pdf
        )
        self.tabs.addTab(self.tab_exp["widget"], "4. Experience Distribution")

        # Tab 5: Government Sector & Aspirants
        self.tab_govt = self._create_report_tab(
            "Government Employment & Aspirants Report",
            headers=["Aspiration / Selection Category", "Candidate Count"],
            export_csv_fn=self._export_govt_csv,
            export_pdf_fn=self._export_govt_pdf
        )
        self.tabs.addTab(self.tab_govt["widget"], "5. Government Jobs")

        # Tab 6: Job Preferences & Demand
        self.tab_pref = self._create_report_tab(
            "Job Preferences & Skills Demand Report",
            headers=["Demand Category", "Top Requests / Skills", "Frequency"],
            export_csv_fn=self._export_pref_csv,
            export_pdf_fn=self._export_pref_pdf
        )
        self.tabs.addTab(self.tab_pref["widget"], "6. Preferences & Skills")

        # Tab 7: Document Readiness
        self.tab_docs = self._create_report_tab(
            "Candidate Document Readiness Report",
            headers=["Candidate ID", "Full Name", "Village", "Govt Readiness", "General Readiness", "Document Status Summary"],
            export_csv_fn=self._export_docs_csv,
            export_pdf_fn=self._export_docs_pdf
        )
        self.tabs.addTab(self.tab_docs["widget"], "7. Document Readiness")

        # Tab 8: Recruiter-Ready Candidates
        self.tab_recruiter = self._create_report_tab(
            "Recruiter-Ready Consented Candidates Report",
            headers=["Candidate ID", "Full Name", "Village", "Qualification", "Skills", "Consent Status", "Consent Date"],
            export_csv_fn=self._export_recruiter_csv,
            export_pdf_fn=self._export_recruiter_pdf
        )
        self.tabs.addTab(self.tab_recruiter["widget"], "8. Recruiter-Ready Candidates")

        main_layout.addWidget(self.tabs)

    def _create_report_tab(self, title: str, headers: List[str], export_csv_fn, export_pdf_fn) -> Dict[str, Any]:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        # Action bar
        act_bar = QHBoxLayout()
        report_lbl = QLabel(title)
        report_lbl.setStyleSheet("font-size: 15px; font-weight: 700; color: #0F172A;")
        act_bar.addWidget(report_lbl)
        act_bar.addStretch()

        btn_csv = QPushButton("Export CSV", w)
        btn_csv.setProperty("class", "SecondaryButton")
        btn_csv.setIcon(AppIcons.export_file())
        btn_csv.clicked.connect(export_csv_fn)

        btn_pdf = QPushButton("Export Official PDF", w)
        btn_pdf.setProperty("class", "PrimaryButton")
        btn_pdf.setIcon(AppIcons.export_file())
        btn_pdf.clicked.connect(export_pdf_fn)

        act_bar.addWidget(btn_csv)
        act_bar.addWidget(btn_pdf)
        layout.addLayout(act_bar)

        # Table
        table = QTableWidget(w)
        table.setColumnCount(len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        table.setSelectionBehavior(QTableWidget.SelectRows)
        table.setAlternatingRowColors(True)
        layout.addWidget(table)

        return {"widget": w, "table": table, "headers": headers, "title": title}

    def _connect_signals(self):
        signals.candidate_saved.connect(lambda cid: self.reload_reports())
        signals.candidate_updated.connect(lambda cid: self.reload_reports())
        signals.candidate_deleted.connect(lambda cid: self.reload_reports())
        signals.database_restored.connect(self.reload_reports)

    def _reset_filters(self):
        self.combo_village.setCurrentIndex(0)
        self.combo_status.setCurrentIndex(0)
        self.combo_qual.setCurrentIndex(0)

    def reload_reports(self):
        self.all_candidates = repository.get_all_candidates(include_deleted=False)
        self.apply_report_filters()

    def apply_report_filters(self):
        v = self.combo_village.currentText()
        s = self.combo_status.currentText()
        q = self.combo_qual.currentText()

        self.filtered_candidates = analytics_engine.filter_candidates(
            self.all_candidates,
            village=None if v == "All Villages" else v,
            status=None if s == "All Statuses" else s,
            qualification=None if q == "All Qualifications" else q
        )

        self._populate_employment_report()
        self._populate_village_report()
        self._populate_qualification_report()
        self._populate_experience_report()
        self._populate_govt_report()
        self._populate_preference_report()
        self._populate_doc_readiness_report()
        self._populate_recruiter_report()

    def _populate_employment_report(self):
        rep = analytics_engine.generate_employment_report(self.filtered_candidates)
        table = self.tab_emp["table"]
        rows = rep["rows"]
        table.setRowCount(len(rows))
        for r_idx, (cat, count, pct) in enumerate(rows):
            item_cat = QTableWidgetItem(str(cat))
            item_cat.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_cnt = QTableWidgetItem(str(count))
            item_cnt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_pct = QTableWidgetItem(str(pct))
            item_pct.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            table.setItem(r_idx, 0, item_cat)
            table.setItem(r_idx, 1, item_cnt)
            table.setItem(r_idx, 2, item_pct)

    def _populate_village_report(self):
        rows = analytics_engine.generate_village_report(self.filtered_candidates)
        table = self.tab_village["table"]
        table.setRowCount(len(rows))
        for r_idx, vr in enumerate(rows):
            item_v = QTableWidgetItem(vr["village"])
            item_v.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            table.setItem(r_idx, 0, item_v)

            for col_idx, key in enumerate(["total", "employed", "unemployed", "govt_employed", "private_employed", "self_employed", "employment_rate"], start=1):
                item_val = QTableWidgetItem(str(vr[key]))
                item_val.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                table.setItem(r_idx, col_idx, item_val)

    def _populate_qualification_report(self):
        rows = analytics_engine.generate_qualification_report(self.filtered_candidates)
        table = self.tab_qual["table"]
        table.setRowCount(len(rows))
        for r_idx, qr in enumerate(rows):
            item_q = QTableWidgetItem(qr["qualification"])
            item_q.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_c = QTableWidgetItem(str(qr["count"]))
            item_c.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_p = QTableWidgetItem(qr["percentage"])
            item_p.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            table.setItem(r_idx, 0, item_q)
            table.setItem(r_idx, 1, item_c)
            table.setItem(r_idx, 2, item_p)

    def _populate_experience_report(self):
        rows = analytics_engine.generate_experience_report(self.filtered_candidates)
        table = self.tab_exp["table"]
        table.setRowCount(len(rows))
        for r_idx, er in enumerate(rows):
            item_b = QTableWidgetItem(er["experience_range"])
            item_b.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_c = QTableWidgetItem(str(er["count"]))
            item_c.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            item_p = QTableWidgetItem(er["percentage"])
            item_p.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            table.setItem(r_idx, 0, item_b)
            table.setItem(r_idx, 1, item_c)
            table.setItem(r_idx, 2, item_p)

    def _populate_govt_report(self):
        rep = analytics_engine.generate_govt_employment_report(self.filtered_candidates)
        table = self.tab_govt["table"]
        table_data = [
            ("Currently Employed in Government", str(rep["govt_employed_count"])),
            ("Total Active Government Job Applicants", str(rep["govt_applicants_count"])),
            ("Candidates Who Have Never Applied for Govt", str(rep["never_applied_count"]))
        ]
        for item in rep["result_status_breakdown"]:
            table_data.append((f"Result Status: {item['status']}", str(item["count"])))

        table.setRowCount(len(table_data))
        for r_idx, (cat, cnt) in enumerate(table_data):
            item_c = QTableWidgetItem(cat)
            item_c.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_v = QTableWidgetItem(cnt)
            item_v.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            table.setItem(r_idx, 0, item_c)
            table.setItem(r_idx, 1, item_v)

    def _populate_preference_report(self):
        rep = analytics_engine.generate_job_preference_and_skills_report(self.filtered_candidates)
        table = self.tab_pref["table"]
        rows = []
        for s, count in rep["top_sectors"]:
            rows.append(("Preferred Sector", s, str(count)))
        for r, count in rep["top_roles"]:
            rows.append(("Preferred Role", r, str(count)))
        for loc, count in rep["top_locations"]:
            rows.append(("Preferred Location", loc, str(count)))
        for sk, count in rep["top_skills"]:
            rows.append(("High-Demand Skill", sk, str(count)))

        table.setRowCount(len(rows))
        for r_idx, (cat, name, cnt) in enumerate(rows):
            item_cat = QTableWidgetItem(cat)
            item_cat.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_name = QTableWidgetItem(name)
            item_name.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            item_cnt = QTableWidgetItem(cnt)
            item_cnt.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

            table.setItem(r_idx, 0, item_cat)
            table.setItem(r_idx, 1, item_name)
            table.setItem(r_idx, 2, item_cnt)

    def _extract_table_data(self, table: QTableWidget) -> List[List[str]]:
        rows = []
        for r in range(table.rowCount()):
            row_vals = []
            for c in range(table.columnCount()):
                item = table.item(r, c)
                row_vals.append(item.text() if item else "")
            rows.append(row_vals)
        return rows

    def _export_generic_csv(self, tab_dict):
        table = tab_dict["table"]
        title = tab_dict["title"]
        headers = tab_dict["headers"]
        rows = self._extract_table_data(table)

        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        default_filename = f"PST_Report_{clean_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {title} to CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            out = report_csv_exporter.export_report_table(title, headers, rows, target_filepath=file_path)
            QMessageBox.information(self, "Export Successful", f"Report successfully exported to:\n\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error", f"Failed to export report CSV: {e}")

    def _export_generic_pdf(self, tab_dict):
        table = tab_dict["table"]
        title = tab_dict["title"]
        headers = tab_dict["headers"]
        rows = self._extract_table_data(table)
        v = self.combo_village.currentText()
        s = self.combo_status.currentText()
        q = self.combo_qual.currentText()
        filter_str = f"Village: {v} | Status: {s} | Qual: {q}"

        clean_title = "".join(c for c in title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
        default_filename = f"PST_Report_{clean_title}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            f"Export {title} to PDF",
            default_filename,
            "PDF Files (*.pdf);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            out = pdf_generator.generate_report(title, headers, rows, filter_summary=filter_str, target_filepath=file_path)
            QMessageBox.information(self, "Export Successful", f"Official branded PDF report generated:\n\n{out}")
        except Exception as e:
            QMessageBox.critical(self, "PDF Export Error", f"Failed to generate PDF report: {e}")

    def _export_employment_csv(self): self._export_generic_csv(self.tab_emp)
    def _export_employment_pdf(self): self._export_generic_pdf(self.tab_emp)
    def _export_village_csv(self): self._export_generic_csv(self.tab_village)
    def _export_village_pdf(self): self._export_generic_pdf(self.tab_village)
    def _export_qual_csv(self): self._export_generic_csv(self.tab_qual)
    def _export_qual_pdf(self): self._export_generic_pdf(self.tab_qual)
    def _export_exp_csv(self): self._export_generic_csv(self.tab_exp)
    def _export_exp_pdf(self): self._export_generic_pdf(self.tab_exp)
    def _export_govt_csv(self): self._export_generic_csv(self.tab_govt)
    def _export_govt_pdf(self): self._export_generic_pdf(self.tab_govt)
    def _export_pref_csv(self): self._export_generic_csv(self.tab_pref)
    def _export_pref_pdf(self): self._export_generic_pdf(self.tab_pref)
    def _export_docs_csv(self): self._export_generic_csv(self.tab_docs)
    def _export_docs_pdf(self): self._export_generic_pdf(self.tab_docs)
    def _export_recruiter_csv(self): self._export_generic_csv(self.tab_recruiter)
    def _export_recruiter_pdf(self): self._export_generic_pdf(self.tab_recruiter)

    def _populate_doc_readiness_report(self):
        table = self.tab_docs["table"]
        rows = []
        for c in self.filtered_candidates:
            docs = repository.get_candidate_documents(c.candidate_id)
            gov_r = DocumentManager.calculate_readiness(docs, "GOVERNMENT")
            priv_r = DocumentManager.calculate_readiness(docs, "PRIVATE")
            status_summary = f"Missing: {len(gov_r.get('missing_documents', []))} | Expired: {len(gov_r.get('expired_documents', []))}"
            rows.append((
                c.candidate_id,
                c.full_name,
                c.village,
                f"{gov_r.get('readiness_score', 0)}%",
                f"{priv_r.get('readiness_score', 0)}%",
                status_summary
            ))
        table.setRowCount(len(rows))
        for r_idx, (cid, name, vil, gr, pr, sm) in enumerate(rows):
            table.setItem(r_idx, 0, QTableWidgetItem(cid))
            table.setItem(r_idx, 1, QTableWidgetItem(name))
            table.setItem(r_idx, 2, QTableWidgetItem(vil))
            item_gr = QTableWidgetItem(gr); item_gr.setTextAlignment(Qt.AlignCenter)
            item_pr = QTableWidgetItem(pr); item_pr.setTextAlignment(Qt.AlignCenter)
            table.setItem(r_idx, 3, item_gr)
            table.setItem(r_idx, 4, item_pr)
            table.setItem(r_idx, 5, QTableWidgetItem(sm))

    def _populate_recruiter_report(self):
        table = self.tab_recruiter["table"]
        rows = []
        for c in self.filtered_candidates:
            consent = repository.get_candidate_consent(c.candidate_id)
            if consent and consent.consent_status == "Consented":
                rows.append((
                    c.candidate_id,
                    c.full_name,
                    c.village,
                    c.education.highest_qualification or "—",
                    c.education.skills or c.preferences.skills_list or "—",
                    consent.consent_status,
                    consent.consent_date or "—"
                ))
        table.setRowCount(len(rows))
        for r_idx, (cid, name, vil, qual, sk, st, dt) in enumerate(rows):
            table.setItem(r_idx, 0, QTableWidgetItem(cid))
            table.setItem(r_idx, 1, QTableWidgetItem(name))
            table.setItem(r_idx, 2, QTableWidgetItem(vil))
            table.setItem(r_idx, 3, QTableWidgetItem(qual))
            table.setItem(r_idx, 4, QTableWidgetItem(sk))
            item_st = QTableWidgetItem(st); item_st.setTextAlignment(Qt.AlignCenter)
            table.setItem(r_idx, 5, item_st)
            table.setItem(r_idx, 6, QTableWidgetItem(dt))
