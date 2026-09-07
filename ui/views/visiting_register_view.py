"""
Visiting Register View for Pedne Sewa Trust - Employment Registry.
Provides dedicated sidebar section for daily walk-in tracking, visitor log management,
real-time multi-filter searching, Excel / CSV batch importing, CSV exporting,
and integrated cloud backup tracking.
"""

from datetime import datetime, date, timedelta
from typing import List, Optional
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit, QComboBox,
    QPushButton, QTableWidget, QTableWidgetItem, QHeaderView,
    QFrame, QMessageBox, QFileDialog, QDateEdit
)
from PySide6.QtCore import Qt, QDate
from PySide6.QtGui import QColor

from models.visitor import VisitorRecord
from database.repository import repository
from export.importer import file_importer
from export.csv_exporter import csv_exporter
from app.constants import (
    PERNEM_VILLAGES,
    VISIT_PURPOSES,
    SYNC_STATUS_SYNCED,
    SYNC_STATUS_PENDING,
    SYNC_STATUS_FAILED
)
from app.signals import signals
from ui.components.icons import AppIcons
from ui.dialogs.log_visit_dialog import LogVisitDialog
from utils.logger import logger


class VisitingRegisterView(QWidget):
    """Dedicated management view for the Pedne Sewa Trust Visiting Register."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.visitors_cache: List[VisitorRecord] = []
        self.displayed_visitors: List[VisitorRecord] = []
        self._init_ui()
        self._connect_signals()
        self.refresh_data()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(14)

        # 1. Top Header Bar
        header_layout = QHBoxLayout()
        title_box = QVBoxLayout()
        title_box.setSpacing(2)

        title_lbl = QLabel("Visiting Register", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        self.count_lbl = QLabel("Showing 0 visitor entries", self)
        self.count_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(self.count_lbl)
        header_layout.addLayout(title_box)

        header_layout.addStretch()

        # Action Buttons
        btn_log = QPushButton("+ Log New Visit", self)
        btn_log.setIcon(AppIcons.add_candidate())
        btn_log.setCursor(Qt.PointingHandCursor)
        btn_log.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: 700;
                font-size: 13px;
                padding: 7px 16px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        btn_log.clicked.connect(self._on_log_new_visit)

        btn_import = QPushButton("Import Excel / CSV", self)
        btn_import.setProperty("class", "SecondaryButton")
        btn_import.setIcon(AppIcons.import_file())
        btn_import.setCursor(Qt.PointingHandCursor)
        btn_import.setToolTip("Import visiting register data from .xlsx or .csv")
        btn_import.clicked.connect(self._on_import_file)

        btn_export = QPushButton("Export CSV", self)
        btn_export.setProperty("class", "SecondaryButton")
        btn_export.setIcon(AppIcons.export_file())
        btn_export.setCursor(Qt.PointingHandCursor)
        btn_export.clicked.connect(self._on_export_csv)

        btn_refresh = QPushButton("Refresh", self)
        btn_refresh.setProperty("class", "SecondaryButton")
        btn_refresh.setIcon(AppIcons.refresh())
        btn_refresh.setCursor(Qt.PointingHandCursor)
        btn_refresh.clicked.connect(self.refresh_data)

        header_layout.addWidget(btn_log)
        header_layout.addWidget(btn_import)
        header_layout.addWidget(btn_export)
        header_layout.addWidget(btn_refresh)
        layout.addLayout(header_layout)

        # 2. KPI Summary Cards
        kpi_layout = QHBoxLayout()
        kpi_layout.setSpacing(12)

        self.card_today = self._create_kpi_card("Today's Visits", "0", "#2563EB", "#EFF6FF")
        self.card_month = self._create_kpi_card("This Month", "0", "#0D9488", "#F0FDFA")
        self.card_total = self._create_kpi_card("Total Registered", "0", "#4F46E5", "#EEF2FF")
        self.card_sync = self._create_kpi_card("Pending Cloud Sync", "0", "#D97706", "#FFFBEB")

        kpi_layout.addWidget(self.card_today)
        kpi_layout.addWidget(self.card_month)
        kpi_layout.addWidget(self.card_total)
        kpi_layout.addWidget(self.card_sync)
        layout.addLayout(kpi_layout)

        # 3. Search & Filters Card
        filter_card = QFrame(self)
        filter_card.setProperty("class", "ContentCard")
        filter_card.setStyleSheet("""
            QFrame {
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 8px 12px;
            }
        """)
        f_layout = QVBoxLayout(filter_card)
        f_layout.setContentsMargins(10, 8, 10, 8)
        f_layout.setSpacing(8)

        # Search Bar
        self.search_input = QLineEdit(filter_card)
        self.search_input.setPlaceholderText("Search by Candidate Name, Sr No., Mobile, Village, or Visit Purpose...")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_filters)
        f_layout.addWidget(self.search_input)

        # Filter Dropdowns Row
        filter_row = QHBoxLayout()
        filter_row.setSpacing(10)

        # Date preset filter
        self.date_preset_combo = QComboBox(filter_card)
        self.date_preset_combo.addItems([
            "All Dates",
            "Today",
            "Yesterday",
            "This Month",
            "Custom Date..."
        ])
        self.date_preset_combo.currentTextChanged.connect(self._on_date_preset_changed)

        # Custom date picker (hidden by default unless "Custom Date..." is picked)
        self.custom_date_edit = QDateEdit(filter_card)
        self.custom_date_edit.setCalendarPopup(True)
        self.custom_date_edit.setDisplayFormat("yyyy-MM-dd")
        self.custom_date_edit.setDate(QDate.currentDate())
        self.custom_date_edit.setVisible(False)
        self.custom_date_edit.dateChanged.connect(lambda: self.apply_filters())

        # Village Filter
        self.village_combo = QComboBox(filter_card)
        self.village_combo.addItem("All Villages")
        self.village_combo.addItems(PERNEM_VILLAGES)
        self.village_combo.currentTextChanged.connect(self.apply_filters)

        # Purpose Filter
        self.purpose_combo = QComboBox(filter_card)
        self.purpose_combo.addItem("All Purposes")
        self.purpose_combo.addItems(VISIT_PURPOSES)
        self.purpose_combo.currentTextChanged.connect(self.apply_filters)

        # Office Filter
        self.office_combo = QComboBox(filter_card)
        self.office_combo.addItem("All Offices", "")
        self.office_combo.addItem("Pedne (Pernem)", "Pernem")
        self.office_combo.addItem("Korgao", "Korgao")
        self.office_combo.currentIndexChanged.connect(lambda _: self.apply_filters())

        # Reset Filters button
        btn_reset = QPushButton("Clear Filters", filter_card)
        btn_reset.setProperty("class", "SecondaryButton")
        btn_reset.setIcon(AppIcons.clear())
        btn_reset.clicked.connect(self.reset_filters)

        filter_row.addWidget(QLabel("Office:", filter_card))
        filter_row.addWidget(self.office_combo)
        filter_row.addWidget(QLabel("Date:", filter_card))
        filter_row.addWidget(self.date_preset_combo)
        filter_row.addWidget(self.custom_date_edit)
        filter_row.addWidget(QLabel("Village:", filter_card))
        filter_row.addWidget(self.village_combo)
        filter_row.addWidget(QLabel("Purpose:", filter_card))
        filter_row.addWidget(self.purpose_combo)
        filter_row.addStretch()
        filter_row.addWidget(btn_reset)
        f_layout.addLayout(filter_row)

        layout.addWidget(filter_card)

        # 4. Data Table
        self.table = QTableWidget(self)
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Sr No.",
            "Office",
            "Date",
            "Time",
            "Name of Candidate",
            "Address (Village)",
            "Mobile No.",
            "Purpose of Visit",
            "Remarks",
            "Cloud Backup",
            "Actions"
        ])

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # Sr No
        header.setSectionResizeMode(1, QHeaderView.ResizeToContents)  # Office
        header.setSectionResizeMode(2, QHeaderView.ResizeToContents)  # Date
        header.setSectionResizeMode(3, QHeaderView.ResizeToContents)  # Time
        header.setSectionResizeMode(4, QHeaderView.Stretch)           # Name
        header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # Village
        header.setSectionResizeMode(6, QHeaderView.ResizeToContents)  # Mobile
        header.setSectionResizeMode(7, QHeaderView.ResizeToContents)  # Purpose
        header.setSectionResizeMode(8, QHeaderView.Stretch)           # Remarks
        header.setSectionResizeMode(9, QHeaderView.ResizeToContents)  # Cloud Backup
        header.setSectionResizeMode(10, QHeaderView.ResizeToContents) # Actions

        self.table.verticalHeader().setVisible(False)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.doubleClicked.connect(self._on_table_double_click)

        layout.addWidget(self.table)

    def _create_kpi_card(self, title: str, val: str, text_color: str, bg_color: str) -> QFrame:
        card = QFrame(self)
        card.setStyleSheet(f"""
            QFrame {{
                background-color: {bg_color};
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px 14px;
            }}
        """)
        c_layout = QVBoxLayout(card)
        c_layout.setContentsMargins(4, 4, 4, 4)
        c_layout.setSpacing(2)

        lbl_title = QLabel(title, card)
        lbl_title.setStyleSheet("font-size: 11px; font-weight: 600; color: #64748B; text-transform: uppercase;")

        lbl_val = QLabel(val, card)
        lbl_val.setStyleSheet(f"font-size: 20px; font-weight: 800; color: {text_color};")
        card.lbl_val = lbl_val  # Store handle for metric updates

        c_layout.addWidget(lbl_title)
        c_layout.addWidget(lbl_val)
        return card

    def _connect_signals(self):
        signals.sync_completed.connect(lambda _: self._update_sync_badges())
        signals.candidate_saved.connect(lambda _: self.refresh_data())

    def refresh_data(self):
        """Reloads all visitor entries and updates metric counters."""
        try:
            self.visitors_cache = repository.get_all_visitors(include_deleted=False)
            self._update_kpi_metrics()
            self.apply_filters()
        except Exception as e:
            logger.error("Failed to refresh Visiting Register: %s", e)

    def _update_kpi_metrics(self):
        try:
            counts = repository.get_visitors_summary_counts()
            self.card_today.lbl_val.setText(str(counts.get("today", 0)))
            self.card_month.lbl_val.setText(str(counts.get("this_month", 0)))
            self.card_total.lbl_val.setText(str(counts.get("total", 0)))
            self.card_sync.lbl_val.setText(str(counts.get("pending_sync", 0)))
        except Exception as e:
            logger.warning("Could not update visiting register metrics: %s", e)

    def _on_date_preset_changed(self, text: str):
        self.custom_date_edit.setVisible(text == "Custom Date...")
        self.apply_filters()

    def apply_filters(self):
        """Applies search text, date, village, purpose, and intake office filters."""
        query = self.search_input.text().strip().lower()
        office_filter = self.office_combo.currentData()
        village_filter = self.village_combo.currentText()
        purpose_filter = self.purpose_combo.currentText()
        date_preset = self.date_preset_combo.currentText()

        today_str = date.today().strftime("%Y-%m-%d")
        yesterday_str = (date.today() - timedelta(days=1)).strftime("%Y-%m-%d")
        month_prefix = date.today().strftime("%Y-%m")
        custom_date_str = self.custom_date_edit.date().toString("yyyy-MM-dd")

        filtered = []
        for v in self.visitors_cache:
            # 1. Query filter
            if query:
                match_query = (
                    query in v.candidate_name.lower() or
                    query in v.mobile.lower() or
                    query in v.village.lower() or
                    query in v.purpose.lower() or
                    query in (v.remarks or "").lower() or
                    query in getattr(v, "intake_office", "").lower() or
                    query in str(v.sr_no)
                )
                if not match_query:
                    continue

            # 2. Office filter
            if office_filter and getattr(v, "intake_office", "Pernem") != office_filter:
                continue

            # 3. Village filter
            if village_filter != "All Villages" and v.village != village_filter:
                continue

            # 4. Purpose filter
            if purpose_filter != "All Purposes" and v.purpose != purpose_filter:
                continue

            # 5. Date filter
            if date_preset == "Today" and v.visit_date != today_str:
                continue
            elif date_preset == "Yesterday" and v.visit_date != yesterday_str:
                continue
            elif date_preset == "This Month" and not v.visit_date.startswith(month_prefix):
                continue
            elif date_preset == "Custom Date..." and v.visit_date != custom_date_str:
                continue

            filtered.append(v)

        self.displayed_visitors = filtered
        self._populate_table(filtered)
        self.count_lbl.setText(f"Showing {len(filtered)} of {len(self.visitors_cache)} visitor entries")

    def reset_filters(self):
        """Resets all filter inputs to default."""
        self.search_input.clear()
        self.office_combo.setCurrentIndex(0)
        self.date_preset_combo.setCurrentIndex(0)
        self.village_combo.setCurrentIndex(0)
        self.purpose_combo.setCurrentIndex(0)
        self.apply_filters()

    def _populate_table(self, visitors: List[VisitorRecord]):
        self.table.setRowCount(len(visitors))

        for row_idx, v in enumerate(visitors):
            # 0: Sr No.
            sr_item = QTableWidgetItem(str(v.sr_no))
            sr_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 0, sr_item)

            # 1: Office
            off_str = "Korgao" if getattr(v, "intake_office", "Pernem") == "Korgao" else "Pedne"
            off_item = QTableWidgetItem(off_str)
            off_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 1, off_item)

            # 2: Date
            date_item = QTableWidgetItem(v.visit_date)
            date_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 2, date_item)

            # 3: Time
            time_item = QTableWidgetItem(v.visit_time)
            time_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 3, time_item)

            # 4: Candidate Name
            name_item = QTableWidgetItem(v.candidate_name)
            self.table.setItem(row_idx, 4, name_item)

            # 5: Village
            village_item = QTableWidgetItem(v.village or "—")
            self.table.setItem(row_idx, 5, village_item)

            # 6: Mobile No.
            mob_item = QTableWidgetItem(v.mobile or "—")
            mob_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(row_idx, 6, mob_item)

            # 7: Purpose
            purpose_item = QTableWidgetItem(v.purpose or "—")
            self.table.setItem(row_idx, 7, purpose_item)

            # 8: Remarks
            remarks_item = QTableWidgetItem(v.remarks or "—")
            self.table.setItem(row_idx, 8, remarks_item)

            # 9: Cloud Backup Status Badge
            badge_item = self._create_cloud_badge_item(v)
            self.table.setItem(row_idx, 9, badge_item)

            # 10: Action Buttons (Edit, Delete)
            actions_widget = self._create_actions_widget(v)
            self.table.setCellWidget(row_idx, 10, actions_widget)

    def _create_cloud_badge_item(self, v: VisitorRecord) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setTextAlignment(Qt.AlignCenter)

        if v.sync_status == SYNC_STATUS_SYNCED:
            item.setText("☁ Synced")
            item.setForeground(QColor("#15803D"))
            tip = f"Backed up to Google Sheets: {v.last_synced_at or 'Recently'}"
        elif v.sync_status == SYNC_STATUS_PENDING:
            item.setText("⏳ Pending")
            item.setForeground(QColor("#B45309"))
            tip = "Safely stored in local SQLite database. Awaiting next background sync."
        else:
            item.setText("⚠ Failed")
            item.setForeground(QColor("#DC2626"))
            tip = "Sync pending retry."

        item.setToolTip(tip)
        return item

    def _create_actions_widget(self, visitor: VisitorRecord) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background-color: transparent;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(6)

        btn_edit = QPushButton(w)
        btn_edit.setIcon(AppIcons.edit())
        btn_edit.setToolTip("Edit visitor entry")
        btn_edit.setFixedSize(30, 26)
        btn_edit.setProperty("class", "SecondaryButton")
        btn_edit.setCursor(Qt.PointingHandCursor)
        btn_edit.clicked.connect(lambda: self._on_edit_visit(visitor))

        btn_delete = QPushButton(w)
        btn_delete.setIcon(AppIcons.delete())
        btn_delete.setToolTip("Delete visitor entry")
        btn_delete.setFixedSize(30, 26)
        btn_delete.setProperty("class", "SecondaryButton")
        btn_delete.setCursor(Qt.PointingHandCursor)
        btn_delete.clicked.connect(lambda: self._on_delete_visit(visitor))

        layout.addWidget(btn_edit)
        layout.addWidget(btn_delete)
        return w

    def _on_log_new_visit(self):
        """Opens dialog to log a new walk-in visit."""
        dlg = LogVisitDialog(parent=self)
        if dlg.exec():
            self.refresh_data()
            signals.show_toast.emit("Visit logged successfully!")

    def _on_edit_visit(self, visitor: VisitorRecord):
        """Opens dialog to edit an existing visit record."""
        dlg = LogVisitDialog(visitor=visitor, parent=self)
        if dlg.exec():
            self.refresh_data()
            signals.show_toast.emit(f"Visit record Sr No. {visitor.sr_no} updated!")

    def _on_delete_visit(self, visitor: VisitorRecord):
        """Prompts confirmation and soft-deletes the visitor entry."""
        reply = QMessageBox.question(
            self,
            "Confirm Delete",
            f"Are you sure you want to delete visitor entry Sr No. {visitor.sr_no} ({visitor.candidate_name})?\n"
            "This entry will be marked deleted and removed from the active register.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes and visitor.id:
            repository.delete_visitor(visitor.id)
            self.refresh_data()
            signals.show_toast.emit(f"Visitor record Sr No. {visitor.sr_no} deleted.")

    def _on_table_double_click(self, index):
        row = index.row()
        if 0 <= row < len(self.displayed_visitors):
            self._on_edit_visit(self.displayed_visitors[row])

    def _on_import_file(self):
        """Handles on-demand loading and batch importing of Excel or CSV files."""
        filepath, _ = QFileDialog.getOpenFileName(
            self,
            "Select Visiting Register Sheet to Import",
            "",
            "Spreadsheet Files (*.xlsx *.xls *.csv);;Excel Files (*.xlsx *.xls);;CSV Files (*.csv);;All Files (*.*)"
        )
        if not filepath:
            return

        try:
            result = file_importer.import_visiting_register(filepath)
            inserted = result.get("inserted", 0)
            skipped = result.get("skipped", 0)

            msg = f"Import completed successfully!\n\n• {inserted} new visit records imported\n• {skipped} rows skipped (empty name or header)"
            QMessageBox.information(self, "Import Successful", msg)
            self.refresh_data()
            signals.show_toast.emit(f"Imported {inserted} visitor records!")
        except Exception as e:
            logger.error("Visiting register file import failed: %s", e)
            QMessageBox.critical(
                self,
                "Import Error",
                f"Failed to import file:\n\n{str(e)}\n\nPlease ensure the file contains valid columns (Name, Date, Village, etc.)."
            )

    def _on_export_csv(self):
        """Exports currently displayed visitor records to UTF-8 CSV with BOM."""
        if not self.displayed_visitors:
            QMessageBox.warning(self, "Export Empty", "There are no visitor entries to export under current filters.")
            return

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        default_filename = f"PST_Visiting_Register_{timestamp}.csv"

        filepath, _ = QFileDialog.getSaveFileName(
            self,
            "Save Visiting Register CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not filepath:
            return

        try:
            csv_exporter.export_visitors(self.displayed_visitors, target_filepath=filepath)
            QMessageBox.information(
                self,
                "Export Complete",
                f"Successfully exported {len(self.displayed_visitors)} visitor entries to:\n{filepath}"
            )
        except Exception as e:
            logger.error("Failed to export visiting register to CSV: %s", e)
            QMessageBox.critical(self, "Export Error", f"Could not export CSV file:\n{str(e)}")

    def _update_sync_badges(self):
        """Refreshes table data to update sync status badges after cloud backup."""
        self.refresh_data()
