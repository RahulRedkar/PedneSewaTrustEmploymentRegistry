"""
Google Sheets Synchronisation & Cloud Backup View for Pedne Sewa Trust.
Manages OAuth connection, displays destination spreadsheet information,
triggers manual sync, and displays the sync history log using Qt icons.
"""

import webbrowser
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QGridLayout
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QColor

from app.config import config
from app.signals import signals
from database.repository import repository
from sync.oauth_manager import oauth_manager
from sync.sync_worker import sync_worker
from ui.components.icons import AppIcons
from utils.logger import logger


class SyncView(QWidget):
    """Google Sheets sync status, account connection, and audit log viewer."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
        self.refresh_view()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Google Sheets Cloud Backup & Synchronisation", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        sub_lbl = QLabel("Online backup and sync layer. SQLite remains your authoritative local database.", self)
        sub_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        layout.addLayout(title_box)

        # 2. Top Cards Grid (Destination Info + Account Status + Quick Sync)
        grid = QGridLayout()
        grid.setSpacing(14)

        # Card 1: Destination Sheet
        dest_card = QFrame(self)
        dest_card.setProperty("class", "ContentCard")
        d_layout = QVBoxLayout(dest_card)
        d_title = QLabel("DESTINATION SPREADSHEET", dest_card)
        d_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 12px;")
        d_layout.addWidget(d_title)

        sheet_id = config.get("spreadsheet_id", "1DC9TY2D2_mJgyJJ_hM3a91UsSOuqssWiBuMKhaxoW_0")
        self.lbl_sheet_id = QLabel(f"Spreadsheet ID: <code>{sheet_id[:16]}...</code>", dest_card)
        self.lbl_sheet_tab = QLabel(f"Worksheet Tab: <b>{config.get('worksheet_name', 'Candidates')}</b>", dest_card)
        self.lbl_sheet_privacy = QLabel("Security: <b>Private / Restricted</b> (OAuth required)", dest_card)

        for l in (self.lbl_sheet_id, self.lbl_sheet_tab, self.lbl_sheet_privacy):
            l.setStyleSheet("color: #475569; font-size: 12px; padding: 2px 0;")
            d_layout.addWidget(l)

        btn_open_sheet = QPushButton("Open Spreadsheet in Browser", dest_card)
        btn_open_sheet.setProperty("class", "SecondaryButton")
        btn_open_sheet.setIcon(AppIcons.database())
        btn_open_sheet.setCursor(Qt.PointingHandCursor)
        btn_open_sheet.clicked.connect(self._open_sheet_url)
        d_layout.addWidget(btn_open_sheet)
        d_layout.addStretch()
        grid.addWidget(dest_card, 0, 0)

        # Card 2: Google Account Connection
        auth_card = QFrame(self)
        auth_card.setProperty("class", "ContentCard")
        a_layout = QVBoxLayout(auth_card)
        a_title = QLabel("GOOGLE OAUTH AUTHORISATION", auth_card)
        a_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 12px;")
        a_layout.addWidget(a_title)

        self.lbl_auth_status = QLabel("Status: Checking...", auth_card)
        self.lbl_auth_account = QLabel("Account: None", auth_card)

        for l in (self.lbl_auth_status, self.lbl_auth_account):
            l.setStyleSheet("color: #475569; font-size: 12px; padding: 2px 0;")
            a_layout.addWidget(l)

        btn_auth_layout = QHBoxLayout()
        self.btn_connect = QPushButton("Connect Google Account", auth_card)
        self.btn_connect.setProperty("class", "PrimaryButton")
        self.btn_connect.setIcon(AppIcons.settings())
        self.btn_connect.setCursor(Qt.PointingHandCursor)
        self.btn_connect.clicked.connect(self._on_connect_clicked)

        self.btn_disconnect = QPushButton("Disconnect", auth_card)
        self.btn_disconnect.setProperty("class", "SecondaryButton")
        self.btn_disconnect.setIcon(AppIcons.cancel())
        self.btn_disconnect.setCursor(Qt.PointingHandCursor)
        self.btn_disconnect.clicked.connect(self._on_disconnect_clicked)

        btn_auth_layout.addWidget(self.btn_connect)
        btn_auth_layout.addWidget(self.btn_disconnect)
        a_layout.addLayout(btn_auth_layout)
        a_layout.addStretch()
        grid.addWidget(auth_card, 0, 1)

        # Card 3: Live Sync Counters & Trigger
        sync_stats_card = QFrame(self)
        sync_stats_card.setProperty("class", "ContentCard")
        s_layout = QVBoxLayout(sync_stats_card)
        s_title = QLabel("BACKUP STATUS & CONTROLS", sync_stats_card)
        s_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 12px;")
        s_layout.addWidget(s_title)

        self.lbl_stats_synced = QLabel("Successfully Backed Up: <b>0</b>", sync_stats_card)
        self.lbl_stats_pending = QLabel("Pending Cloud Sync: <b>0</b>", sync_stats_card)
        self.lbl_stats_last = QLabel("Last Successful: <i>Never</i>", sync_stats_card)

        for l in (self.lbl_stats_synced, self.lbl_stats_pending, self.lbl_stats_last):
            l.setStyleSheet("color: #475569; font-size: 12px; padding: 2px 0;")
            s_layout.addWidget(l)

        self.btn_sync_now = QPushButton("Sync Now (Background)", sync_stats_card)
        self.btn_sync_now.setProperty("class", "PrimaryButton")
        self.btn_sync_now.setIcon(AppIcons.sync())
        self.btn_sync_now.setCursor(Qt.PointingHandCursor)
        self.btn_sync_now.clicked.connect(self._on_sync_now_clicked)
        s_layout.addWidget(self.btn_sync_now)
        s_layout.addStretch()
        grid.addWidget(sync_stats_card, 0, 2)

        layout.addLayout(grid)

        # 3. Sync Log Audit Table
        log_title = QLabel("Synchronisation Audit Log", self)
        log_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 15px; margin-top: 8px;")
        layout.addWidget(log_title)

        self.log_table = QTableWidget(self)
        self.log_table.setColumnCount(5)
        self.log_table.setHorizontalHeaderLabels([
            "Timestamp", "Status", "Records Pushed", "Records Failed", "Outcome / Details"
        ])
        self.log_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.log_table.horizontalHeader().setSectionResizeMode(4, QHeaderView.Stretch)
        self.log_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.log_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.log_table.setAlternatingRowColors(True)
        layout.addWidget(self.log_table)

    def _connect_signals(self):
        signals.sync_completed.connect(lambda stats: self.refresh_view())
        signals.sync_failed.connect(lambda msg: self.refresh_view())
        signals.candidate_saved.connect(lambda cid: self.refresh_view())
        signals.candidate_updated.connect(lambda cid: self.refresh_view())
        signals.settings_updated.connect(self.refresh_view)

    def refresh_view(self):
        is_auth = oauth_manager.is_authenticated()
        if is_auth:
            self.lbl_auth_status.setText("Status: <b style='color: #15803D;'>● Connected</b>")
            self.lbl_auth_account.setText(f"Account: <b>{oauth_manager.get_connected_account()}</b>")
            self.btn_connect.setEnabled(False)
            self.btn_disconnect.setEnabled(True)
        else:
            self.lbl_auth_status.setText("Status: <b style='color: #64748B;'>○ Not Connected</b>")
            self.lbl_auth_account.setText("Account: Authorization required for private sheet")
            self.btn_connect.setEnabled(True)
            self.btn_disconnect.setEnabled(False)

        stats = repository.get_sync_statistics()
        self.lbl_stats_synced.setText(f"Successfully Backed Up: <b style='color: #15803D;'>{stats['synced_count']}</b>")
        self.lbl_stats_pending.setText(f"Pending Cloud Sync: <b style='color: #D97706;'>{stats['pending_count']}</b>")
        last_success = stats['last_successful_sync']
        self.lbl_stats_last.setText(f"Last Successful: <i>{last_success[:19].replace('T', ' ') if last_success else 'Never'}</i>")

        logs = repository.get_sync_logs(limit=30)
        self.log_table.setRowCount(len(logs))
        for r_idx, l in enumerate(logs):
            self.log_table.setItem(r_idx, 0, QTableWidgetItem(l["timestamp"][:19].replace("T", " ")))

            status_item = QTableWidgetItem(l["status"])
            status_item.setTextAlignment(Qt.AlignCenter)
            if l["status"] == "SUCCESS":
                status_item.setForeground(QColor("#15803D"))
            else:
                status_item.setForeground(QColor("#DC2626"))
            self.log_table.setItem(r_idx, 1, status_item)

            item_pushed = QTableWidgetItem(str(l["records_pushed"]))
            item_pushed.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.log_table.setItem(r_idx, 2, item_pushed)

            item_failed = QTableWidgetItem(str(l["records_failed"]))
            item_failed.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.log_table.setItem(r_idx, 3, item_failed)

            self.log_table.setItem(r_idx, 4, QTableWidgetItem(l["details"] or l["error_message"] or "—"))

    def _on_connect_clicked(self):
        self.lbl_auth_status.setText("Status: Opening browser for Google authorization...")
        success, msg = oauth_manager.authorize_desktop_flow()
        if success:
            QMessageBox.information(self, "Authorization Successful", msg)
        else:
            QMessageBox.warning(self, "Authorization Needed", f"{msg}\n\nNote: Place your Google Cloud Desktop credentials.json in the application directory or configure in Settings.")
        self.refresh_view()

    def _on_disconnect_clicked(self):
        reply = QMessageBox.question(
            self,
            "Disconnect Google Account",
            "Are you sure you want to disconnect Google Sheets cloud backup?\n\n"
            "Your local candidate records will remain safely saved in SQLite on this computer.",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            oauth_manager.disconnect()
            self.refresh_view()

    def _on_sync_now_clicked(self):
        self.btn_sync_now.setEnabled(False)
        self.btn_sync_now.setText("Syncing...")
        sync_worker.sync_now(is_manual=True)
        from PySide6.QtCore import QTimer
        QTimer.singleShot(2500, lambda: (
            self.btn_sync_now.setEnabled(True),
            self.btn_sync_now.setText("Sync Now (Background)"),
            self.refresh_view()
        ))

    def _open_sheet_url(self):
        sid = config.get("spreadsheet_id", "1DC9TY2D2_mJgyJJ_hM3a91UsSOuqssWiBuMKhaxoW_0")
        url = f"https://docs.google.com/spreadsheets/d/{sid}"
        webbrowser.open(url)
