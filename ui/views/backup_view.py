"""
Backup, Restore & On-Demand CSV Export View for Pedne Sewa Trust.
Provides complete local database backups, safe restoration, and UTF-8 CSV exports using Qt icons.
"""

import os
from datetime import datetime
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox, QFileDialog
)
from PySide6.QtCore import Qt
from app.config import config
from app.signals import signals
from export.backup_manager import backup_manager
from export.csv_exporter import csv_exporter
from sync.sync_worker import sync_worker
from ui.components.icons import AppIcons
from utils.logger import logger


class BackupView(QWidget):
    """Database backup, restore, and CSV dataset export controls."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self._connect_signals()
        self.refresh_backups()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 1. Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Backup, Restore & Data Exports", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        sub_lbl = QLabel("Create local database snapshots, restore historical archives, and export complete CSV datasets.", self)
        sub_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        layout.addLayout(title_box)

        # 2. Cards Row (3 Clean Cards)
        top_row = QHBoxLayout()
        top_row.setSpacing(14)

        # Card 1: Database Snapshot Card
        db_card = QFrame(self)
        db_card.setProperty("class", "ContentCard")
        db_layout = QVBoxLayout(db_card)
        db_layout.setSpacing(10)

        db_title = QLabel("Local Database Backups", db_card)
        db_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")

        db_desc = QLabel(
            "Backups are complete, timestamped SQLite database files containing all candidate records.\n"
            "An automatic snapshot is created each time the application launches (retaining last 30).",
            db_card
        )
        db_desc.setStyleSheet("color: #64748B; font-size: 12px;")
        db_desc.setWordWrap(True)

        db_btn_layout = QHBoxLayout()
        self.btn_backup_now = QPushButton("Backup Database Now", db_card)
        self.btn_backup_now.setProperty("class", "PrimaryButton")
        self.btn_backup_now.setIcon(AppIcons.backup())
        self.btn_backup_now.setCursor(Qt.PointingHandCursor)
        self.btn_backup_now.clicked.connect(self._on_backup_now)

        self.btn_restore = QPushButton("Restore Database...", db_card)
        self.btn_restore.setProperty("class", "SecondaryButton")
        self.btn_restore.setIcon(AppIcons.database())
        self.btn_restore.setCursor(Qt.PointingHandCursor)
        self.btn_restore.clicked.connect(self._on_restore_clicked)

        db_btn_layout.addWidget(self.btn_backup_now)
        db_btn_layout.addWidget(self.btn_restore)

        db_layout.addWidget(db_title)
        db_layout.addWidget(db_desc)
        db_layout.addLayout(db_btn_layout)
        db_layout.addStretch()
        top_row.addWidget(db_card, 1)

        # Card 2: Cloud Backup Card
        cloud_card = QFrame(self)
        cloud_card.setProperty("class", "ContentCard")
        cloud_layout = QVBoxLayout(cloud_card)
        cloud_layout.setSpacing(10)

        cloud_title = QLabel("Cloud Backup", cloud_card)
        cloud_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")

        cloud_desc = QLabel(
            "Synchronize candidate records with the secure cloud repository.\n"
            "Runs automatically in the background every 10 minutes. Click below to trigger immediately.",
            cloud_card
        )
        cloud_desc.setStyleSheet("color: #64748B; font-size: 12px;")
        cloud_desc.setWordWrap(True)

        self.btn_backup_cloud = QPushButton("Backup to Cloud", cloud_card)
        self.btn_backup_cloud.setProperty("class", "PrimaryButton")
        self.btn_backup_cloud.setIcon(AppIcons.backup())
        self.btn_backup_cloud.setCursor(Qt.PointingHandCursor)
        self.btn_backup_cloud.clicked.connect(self._on_backup_cloud)

        cloud_layout.addWidget(cloud_title)
        cloud_layout.addWidget(cloud_desc)
        cloud_layout.addWidget(self.btn_backup_cloud)
        cloud_layout.addStretch()
        top_row.addWidget(cloud_card, 1)

        # Card 3: Data Export Card
        csv_card = QFrame(self)
        csv_card.setProperty("class", "ContentCard")
        csv_layout = QVBoxLayout(csv_card)
        csv_layout.setSpacing(10)

        csv_title = QLabel("Data Exports", csv_card)
        csv_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")

        csv_desc = QLabel(
            "Export candidate records into standardized UTF-8 CSV files (Excel-ready).\n"
            "You choose where the exported file should be saved on your computer.",
            csv_card
        )
        csv_desc.setStyleSheet("color: #64748B; font-size: 12px;")
        csv_desc.setWordWrap(True)

        csv_btn_layout = QHBoxLayout()
        self.btn_export_all = QPushButton("Export All Candidates", csv_card)
        self.btn_export_all.setProperty("class", "SecondaryButton")
        self.btn_export_all.setIcon(AppIcons.export_file())
        self.btn_export_all.setCursor(Qt.PointingHandCursor)
        self.btn_export_all.clicked.connect(self._on_export_all_csv)

        self.btn_export_pending = QPushButton("Export Unsynced Records", csv_card)
        self.btn_export_pending.setProperty("class", "SecondaryButton")
        self.btn_export_pending.setIcon(AppIcons.export_file())
        self.btn_export_pending.setCursor(Qt.PointingHandCursor)
        self.btn_export_pending.clicked.connect(self._on_export_pending_csv)

        csv_btn_layout.addWidget(self.btn_export_all)
        csv_btn_layout.addWidget(self.btn_export_pending)

        csv_layout.addWidget(csv_title)
        csv_layout.addWidget(csv_desc)
        csv_layout.addLayout(csv_btn_layout)
        csv_layout.addStretch()
        top_row.addWidget(csv_card, 1)

        layout.addLayout(top_row)

        # 3. Table of Local Backups
        tbl_header_box = QHBoxLayout()
        tbl_title = QLabel("Local Database Historical Archives", self)
        tbl_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 15px; margin-top: 8px;")
        tbl_header_box.addWidget(tbl_title)
        tbl_header_box.addStretch()

        btn_open_folder = QPushButton("Open Backups Folder", self)
        btn_open_folder.setProperty("class", "SecondaryButton")
        btn_open_folder.setIcon(AppIcons.database())
        btn_open_folder.setCursor(Qt.PointingHandCursor)
        btn_open_folder.clicked.connect(self._open_backups_folder)
        tbl_header_box.addWidget(btn_open_folder)

        layout.addLayout(tbl_header_box)

        self.backup_table = QTableWidget(self)
        self.backup_table.setColumnCount(4)
        self.backup_table.setHorizontalHeaderLabels([
            "Backup Filename", "Type", "File Size", "Creation Date"
        ])
        self.backup_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.backup_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.backup_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.backup_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.backup_table.setAlternatingRowColors(True)
        layout.addWidget(self.backup_table)

    def _connect_signals(self):
        signals.database_backed_up.connect(lambda p: self.refresh_backups())
        signals.sync_completed.connect(self._on_sync_success)
        signals.sync_failed.connect(self._on_sync_failure)

    def _on_sync_success(self, info: dict):
        self.btn_backup_cloud.setEnabled(True)
        self.btn_backup_cloud.setText("Backup to Cloud")
        if getattr(self, "_manual_backup_active", False):
            self._manual_backup_active = False
            pushed = info.get("records_pushed", 0)
            QMessageBox.information(
                self,
                "Cloud Backup Complete",
                f"Cloud backup completed successfully.\n\n{pushed} candidate records synchronized with the cloud repository."
            )

    def _on_sync_failure(self, err_msg: str):
        self.btn_backup_cloud.setEnabled(True)
        self.btn_backup_cloud.setText("Backup to Cloud")
        if getattr(self, "_manual_backup_active", False):
            self._manual_backup_active = False
            QMessageBox.warning(
                self,
                "Cloud Backup Incomplete",
                f"Cloud synchronization could not be completed:\n\n{err_msg}\n\n"
                "Your records remain safely preserved on this computer and will be retried automatically."
            )

    def refresh_backups(self):
        backups = backup_manager.list_backups()
        self.backup_table.setRowCount(len(backups))
        for r_idx, b in enumerate(backups):
            self.backup_table.setItem(r_idx, 0, QTableWidgetItem(b["filename"]))
            b_type = "Automated Startup" if b["is_auto"] else "Manual User Backup"
            self.backup_table.setItem(r_idx, 1, QTableWidgetItem(b_type))
            item_size = QTableWidgetItem(b["size_display"])
            item_size.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.backup_table.setItem(r_idx, 2, item_size)
            self.backup_table.setItem(r_idx, 3, QTableWidgetItem(b["modified"]))

    def _on_backup_now(self):
        try:
            path = backup_manager.create_backup(is_automatic=False)
            signals.database_backed_up.emit(path)
            self.refresh_backups()
            QMessageBox.information(self, "Backup Complete", f"Database snapshot created successfully:\n\n{path}")
        except Exception as e:
            logger.error("Manual backup error: %s", e)
            QMessageBox.critical(self, "Backup Failed", f"Could not create database backup: {e}")

    def _on_restore_clicked(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Database Backup to Restore",
            str(backup_manager.backup_dir),
            "SQLite Database Backups (*.sqlite *.db *.bak);;All Files (*.*)"
        )
        if not file_path:
            return

        reply = QMessageBox.warning(
            self,
            "Confirm Database Restoration",
            "WARNING: Restoring will overwrite the active local database with the selected backup file.\n\n"
            "(A safety checkpoint of your current database will be saved automatically before restoration proceeds).\n\n"
            f"Are you sure you want to restore from:\n{os.path.basename(file_path)}?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                backup_manager.restore_backup(file_path)
                signals.database_restored.emit()
                self.refresh_backups()
                QMessageBox.information(self, "Restoration Complete", "Database has been successfully restored!")
            except Exception as e:
                logger.error("Restore failed: %s", e)
                QMessageBox.critical(self, "Restoration Error", f"Failed to restore database from backup:\n{e}")

    def _on_backup_cloud(self):
        """Triggers manual cloud backup cycle."""
        from sync.apps_script_client import apps_script_client
        if not apps_script_client.is_configured():
            QMessageBox.warning(
                self,
                "Cloud Backup Gateway Required",
                "Cloud backup gateway is not configured.\n\n"
                "Please configure the Gateway Web App URL and API Key in Settings before initiating cloud backup."
            )
            return

        try:
            self.btn_backup_cloud.setEnabled(False)
            self.btn_backup_cloud.setText("Syncing with Cloud...")
            self._manual_backup_active = True
            sync_worker.sync_now(is_manual=True)
        except Exception as e:
            self.btn_backup_cloud.setEnabled(True)
            self.btn_backup_cloud.setText("Backup to Cloud")
            self._manual_backup_active = False
            logger.error("Cloud backup initiation error: %s", e)
            QMessageBox.critical(self, "Backup Error", f"Could not initiate cloud backup: {e}")

    def _on_export_all_csv(self):
        default_filename = f"PST_All_Candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export All Candidates to CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            path = csv_exporter.export_all(target_filepath=file_path)
            QMessageBox.information(self, "Export Successful", f"All candidate records successfully exported to:\n\n{path}")
        except Exception as e:
            logger.error("Export all CSV failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Could not export CSV: {e}")

    def _on_export_pending_csv(self):
        default_filename = f"PST_Unsynced_Candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Unsynced Records to CSV",
            default_filename,
            "CSV Files (*.csv);;All Files (*.*)"
        )
        if not file_path:
            return

        try:
            path = csv_exporter.export_pending(target_filepath=file_path)
            QMessageBox.information(self, "Export Successful", f"Unsynced records successfully exported to:\n\n{path}")
        except Exception as e:
            logger.error("Export pending CSV failed: %s", e)
            QMessageBox.critical(self, "Export Error", f"Could not export CSV: {e}")

    def _open_backups_folder(self):
        folder = str(backup_manager.backup_dir)
        os.startfile(folder)
