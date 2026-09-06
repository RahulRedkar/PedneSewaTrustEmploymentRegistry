"""
Dashboard View for Pedne Sewa Trust - Employment Registry.
Presents real-time KPI metrics, category breakdowns, village distribution,
and strict data-integrity reconciliation against local SQLite storage.
"""

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QGridLayout,
    QFrame, QPushButton, QTableWidget, QTableWidgetItem,
    QHeaderView, QScrollArea
)
from PySide6.QtCore import Qt, Signal
from app.signals import signals
from database.repository import repository
from reports.analytics_engine import analytics_engine
from ui.components.metric_card import MetricCard
from ui.components.icons import AppIcons
from sync.sync_worker import sync_worker
from utils.logger import logger


class DashboardView(QWidget):
    """Modern executive dashboard with clean typography and real-time statistics."""

    navigate_requested = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
        self.refresh_data()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(18)

        # 1. Dashboard Title Area (Clean executive header)
        title_bar = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        b_title = QLabel("Taluka Employment Overview", self)
        b_title.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        b_sub = QLabel("Live community candidate statistics for Pernem Taluka, Goa", self)
        b_sub.setStyleSheet("font-size: 13px; color: #64748B;")

        title_box.addWidget(b_title)
        title_box.addWidget(b_sub)
        title_bar.addLayout(title_box)

        title_bar.addStretch()

        btn_add = QPushButton("Register Candidate", self)
        btn_add.setProperty("class", "PrimaryButton")
        btn_add.setIcon(AppIcons.add_candidate())
        btn_add.setCursor(Qt.PointingHandCursor)
        btn_add.clicked.connect(lambda: self.navigate_requested.emit(1))

        title_bar.addWidget(btn_add)
        main_layout.addLayout(title_bar)

        # 2. Scroll Area for Dashboard Content
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        scroll_layout = QVBoxLayout(content_widget)
        scroll_layout.setContentsMargins(0, 0, 0, 0)
        scroll_layout.setSpacing(20)

        # 3. 5 Summary KPI Metric Cards (Single horizontal row)
        self.kpi_layout = QHBoxLayout()
        self.kpi_layout.setSpacing(12)

        self.card_total = MetricCard("REGISTERED CANDIDATES", "0", "All Candidates", "#0284C7")
        self.card_employed = MetricCard("EMPLOYED", "0", "Govt & Private", "#16A34A")
        self.card_unemployed = MetricCard("UNEMPLOYED", "0", "Seeking Opportunities", "#DC2626")
        self.card_self_emp = MetricCard("SELF-EMPLOYED", "0", "Local Businesses", "#EA580C")
        self.card_emp_rate = MetricCard("EMPLOYMENT RATE", "0%", "Pernem Taluka", "#0D9488")
        # Hidden/compatible reference in case external callers expect card_students
        self.card_students = MetricCard("STUDENTS", "0", "Aspirants / Batch", "#2563EB")
        self.card_students.hide()

        self.kpi_layout.addWidget(self.card_total)
        self.kpi_layout.addWidget(self.card_employed)
        self.kpi_layout.addWidget(self.card_unemployed)
        self.kpi_layout.addWidget(self.card_self_emp)
        self.kpi_layout.addWidget(self.card_emp_rate)

        scroll_layout.addLayout(self.kpi_layout)

        # 4. 4 Facilitation Cards Section
        fac_header_box = QHBoxLayout()
        fac_title = QLabel("Employment Facilitation & Readiness", self)
        fac_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 15px;")
        fac_header_box.addWidget(fac_title)
        fac_header_box.addStretch()
        scroll_layout.addLayout(fac_header_box)

        self.fac_grid = QGridLayout()
        self.fac_grid.setSpacing(14)

        # Facilitation Card 1: Government Opportunities
        self.card_fac_gov = QFrame(self)
        self.card_fac_gov.setProperty("class", "ContentCard")
        self.card_fac_gov.setStyleSheet("""
            QFrame.ContentCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 3px solid #2563EB;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        g_layout = QVBoxLayout(self.card_fac_gov)
        g_layout.setSpacing(8)
        g_title = QLabel("Government Opportunities", self.card_fac_gov)
        g_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 14px;")
        g_layout.addWidget(g_title)

        self.row_fac_gov = self._create_metric_row("Open Government Jobs", "0", val_color="#2563EB")
        self.row_govt_apps = self._create_metric_row("Active Applicants", "0", val_color="#475569")
        self.row_govt_emp = self._create_metric_row("Currently Employed", "0", val_color="#16A34A")

        g_layout.addLayout(self.row_fac_gov["layout"])
        g_layout.addLayout(self.row_govt_apps["layout"])
        g_layout.addLayout(self.row_govt_emp["layout"])
        g_layout.addStretch()
        self.fac_grid.addWidget(self.card_fac_gov, 0, 0)

        # Facilitation Card 2: Potential Matches & Employers
        self.card_fac_rec = QFrame(self)
        self.card_fac_rec.setProperty("class", "ContentCard")
        self.card_fac_rec.setStyleSheet("""
            QFrame.ContentCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 3px solid #0D9488;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        r_layout = QVBoxLayout(self.card_fac_rec)
        r_layout.setSpacing(8)
        r_title = QLabel("Potential Matches", self.card_fac_rec)
        r_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 14px;")
        r_layout.addWidget(r_title)

        self.row_fac_rec = self._create_metric_row("Verified Employers", "0", val_color="#0D9488")
        self.row_fac_matches = self._create_metric_row("Active Match Pipeline", "Available", val_color="#0D9488")
        self.row_fac_partners = self._create_metric_row("Local Partner Network", "Pernem", val_color="#475569")

        r_layout.addLayout(self.row_fac_rec["layout"])
        r_layout.addLayout(self.row_fac_matches["layout"])
        r_layout.addLayout(self.row_fac_partners["layout"])
        r_layout.addStretch()
        self.fac_grid.addWidget(self.card_fac_rec, 0, 1)

        # Facilitation Card 3: Candidates Ready for Facilitation
        self.card_fac_cand = QFrame(self)
        self.card_fac_cand.setProperty("class", "ContentCard")
        self.card_fac_cand.setStyleSheet("""
            QFrame.ContentCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 3px solid #16A34A;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        c_layout = QVBoxLayout(self.card_fac_cand)
        c_layout.setSpacing(8)
        c_title = QLabel("Candidates Ready for Facilitation", self.card_fac_cand)
        c_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 14px;")
        c_layout.addWidget(c_title)

        self.row_fac_consented = self._create_metric_row("Recruiter-Ready Candidates", "0", val_color="#16A34A")
        self.row_never_app = self._create_metric_row("Direct Job Seekers", "0", val_color="#475569")
        self.row_fac_pool = self._create_metric_row("Placement Readiness", "Active", val_color="#16A34A")

        c_layout.addLayout(self.row_fac_consented["layout"])
        c_layout.addLayout(self.row_never_app["layout"])
        c_layout.addLayout(self.row_fac_pool["layout"])
        c_layout.addStretch()
        self.fac_grid.addWidget(self.card_fac_cand, 0, 2)

        # Facilitation Card 4: Document Readiness
        self.card_fac_doc = QFrame(self)
        self.card_fac_doc.setProperty("class", "ContentCard")
        self.card_fac_doc.setStyleSheet("""
            QFrame.ContentCard {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-top: 3px solid #6366F1;
                border-radius: 8px;
                padding: 14px;
            }
        """)
        d_layout = QVBoxLayout(self.card_fac_doc)
        d_layout.setSpacing(8)
        d_title = QLabel("Document Readiness", self.card_fac_doc)
        d_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 14px;")
        d_layout.addWidget(d_title)

        self.row_docs_avail = self._create_metric_row("Available Documents", "0", val_color="#15803D")
        self.row_docs_awaiting = self._create_metric_row("Applied / Awaiting", "0", val_color="#D97706")
        self.row_docs_missing = self._create_metric_row("Missing Documents", "0", val_color="#DC2626")

        d_layout.addLayout(self.row_docs_avail["layout"])
        d_layout.addLayout(self.row_docs_awaiting["layout"])
        d_layout.addLayout(self.row_docs_missing["layout"])
        d_layout.addStretch()
        self.fac_grid.addWidget(self.card_fac_doc, 0, 3)

        scroll_layout.addLayout(self.fac_grid)

        # 5. Bottom Section: Restyled Village Distribution Table
        v_header_box = QHBoxLayout()
        v_title = QLabel("Candidate Distribution by Village", self)
        v_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 15px; margin-top: 4px;")
        v_header_box.addWidget(v_title)
        v_header_box.addStretch()
        scroll_layout.addLayout(v_header_box)

        self.village_table = QTableWidget(self)
        self.village_table.setColumnCount(6)
        self.village_table.setHorizontalHeaderLabels([
            "Village", "Total Candidates", "Employed", "Unemployed", "Self-Employed", "Employment Rate"
        ])
        self.village_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        for c in range(1, 6):
            self.village_table.horizontalHeader().setSectionResizeMode(c, QHeaderView.ResizeToContents)
        self.village_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.village_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.village_table.setAlternatingRowColors(True)
        self.village_table.setMinimumHeight(280)
        self.village_table.setStyleSheet("""
            QTableWidget {
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                background-color: #FFFFFF;
                gridline-color: #F1F5F9;
            }
            QHeaderView::section {
                background-color: #F8FAFC;
                color: #334155;
                font-weight: 700;
                font-size: 12px;
                padding: 8px 10px;
                border-bottom: 2px solid #E2E8F0;
            }
            QTableWidget::item {
                padding: 6px 12px;
                font-size: 13px;
            }
        """)
        scroll_layout.addWidget(self.village_table)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

    def _create_metric_row(self, label: str, initial_val: str = "0", val_color: str = "#0F172A"):
        h = QHBoxLayout()
        lbl = QLabel(label, self)
        lbl.setStyleSheet("color: #475569; font-size: 13px;")

        val = QLabel(initial_val, self)
        val.setStyleSheet(f"color: {val_color}; font-size: 14px; font-weight: 700;")

        h.addWidget(lbl)
        h.addStretch()
        h.addWidget(val)
        return {"layout": h, "label": lbl, "value": val}

    def _connect_signals(self):
        signals.candidate_saved.connect(lambda cid: self.refresh_data())
        signals.candidate_updated.connect(lambda cid: self.refresh_data())
        signals.candidate_deleted.connect(lambda cid: self.refresh_data())
        signals.sync_completed.connect(lambda stats: self.refresh_data())
        signals.database_restored.connect(self.refresh_data)

    def refresh_data(self):
        """
        Re-queries SQLite and updates all metric cards and tables.
        Performs strict data-integrity check to verify all breakdowns reconcile.
        """
        candidates = repository.get_all_candidates(include_deleted=False)
        summary = analytics_engine.get_dashboard_summary(candidates)

        # Strict Data-Integrity Check:
        # 1. Employed must reconcile with Govt + Private
        reconciled_employed = summary["govt_employed"] + summary["private_employed"]
        assert summary["employed"] == reconciled_employed, (
            f"Integrity Error: Employed ({summary['employed']}) != Govt ({summary['govt_employed']}) + Private ({summary['private_employed']})"
        )

        # 2. Unemployed must reconcile with Govt Applicants + Never Applied
        reconciled_unemployed = summary["govt_applicants"] + summary["never_applied"]
        assert summary["unemployed"] == reconciled_unemployed, (
            f"Integrity Error: Unemployed ({summary['unemployed']}) != Applicants ({summary['govt_applicants']}) + Never Applied ({summary['never_applied']})"
        )

        # 3. Total candidates must match sum of statuses
        reconciled_total = summary["employed"] + summary["unemployed"] + summary["self_employed"] + summary["students"]
        assert summary["total_candidates"] == reconciled_total, (
            f"Integrity Error: Total ({summary['total_candidates']}) != sum of status categories ({reconciled_total})"
        )

        logger.info(
            "Dashboard data integrity verified: Total=%d (Employed=%d, Unemployed=%d, Self-Employed=%d, Students=%d)",
            summary["total_candidates"], summary["employed"], summary["unemployed"], summary["self_employed"], summary["students"]
        )

        # Update KPI Cards
        self.card_total.update_value(summary["total_candidates"])
        self.card_employed.update_value(
            summary["employed"],
            f"Govt: {summary['govt_employed']} | Private: {summary['private_employed']}"
        )
        self.card_unemployed.update_value(
            summary["unemployed"],
            f"Govt Applicants: {summary['govt_applicants']} | Other: {summary['never_applied']}"
        )
        self.card_self_emp.update_value(summary["self_employed"], "Local Businesses")
        if hasattr(self, "card_students") and self.card_students:
            self.card_students.update_value(summary["students"], "Education & Training")
        self.card_emp_rate.update_value(f"{summary['employment_rate']}%", "Overall Pernem")

        # Update Govt Breakdown rows
        self.row_govt_emp["value"].setText(str(summary["govt_employed"]))
        self.row_govt_apps["value"].setText(str(summary["govt_applicants"]))
        self.row_never_app["value"].setText(str(summary["never_applied"]))

        # Update Document Readiness Card
        try:
            with repository.db.get_connection() as conn:
                cur = conn.cursor()
                cur.execute("SELECT COUNT(*) FROM candidate_documents WHERE status = 'Available'")
                cnt_avail = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM candidate_documents WHERE status = 'Applied / Awaiting'")
                cnt_awaiting = cur.fetchone()[0]
                cur.execute("SELECT COUNT(*) FROM candidate_documents WHERE status = 'Missing'")
                cnt_missing = cur.fetchone()[0]
                self.row_docs_avail["value"].setText(str(cnt_avail))
                self.row_docs_awaiting["value"].setText(str(cnt_awaiting))
                self.row_docs_missing["value"].setText(str(cnt_missing))
        except Exception as e:
            logger.warning("Could not refresh document stats: %s", e)

        # Update Facilitation Metrics
        try:
            gov_jobs = repository.get_all_government_jobs(status_filter="OPEN")
            consented_count = len(repository.get_consented_candidates())
            rec_count = len(repository.get_all_recruiters(status_filter="VERIFIED"))
            self.row_fac_gov["value"].setText(str(len(gov_jobs)))
            self.row_fac_consented["value"].setText(str(consented_count))
            self.row_fac_rec["value"].setText(str(rec_count))
        except Exception as e:
            logger.warning("Could not refresh facilitation metrics: %s", e)

        # Update Village Table
        village_rows = analytics_engine.generate_village_report(candidates)
        self.village_table.setRowCount(len(village_rows))
        for r_idx, vr in enumerate(village_rows):
            # Left aligned village name with clean font
            item_v = QTableWidgetItem(vr["village"])
            item_v.setTextAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self.village_table.setItem(r_idx, 0, item_v)

            # Right aligned numbers
            for col_idx, key in enumerate(["total", "employed", "unemployed", "self_employed"], start=1):
                item_num = QTableWidgetItem(str(vr[key]))
                item_num.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                self.village_table.setItem(r_idx, col_idx, item_num)

            # Employment rate with clean percentage badge styling
            rate_val = vr["employment_rate"]
            item_rate = QTableWidgetItem(str(rate_val))
            item_rate.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.village_table.setItem(r_idx, 5, item_rate)
