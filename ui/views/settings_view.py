"""
Settings & System Configuration View for Pedne Sewa Trust - Employment Registry.
Manages organisation branding, logo overrides, Google Sheets destination,
sync intervals, and local storage directories using Qt icons.
"""

import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QLineEdit,
    QPushButton, QFormLayout, QFrame, QSpinBox, QFileDialog,
    QMessageBox, QScrollArea
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from app.config import config
from app.version import APP_VERSION, GITHUB_REPO_SLUG
from app.signals import signals
from sync.sync_worker import sync_worker
from ui.components.icons import AppIcons
from utils.logger import logger


class SettingsView(QWidget):
    """Administrator configuration interface."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._init_ui()
        self.load_settings()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 20, 24, 20)
        main_layout.setSpacing(14)

        # 1. Header Title
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_lbl = QLabel("Application Settings & Configuration", self)
        title_lbl.setStyleSheet("font-size: 22px; font-weight: 800; color: #0F172A;")

        sub_lbl = QLabel("Manage organisation identity, Trust branding, and local storage directories.", self)
        sub_lbl.setStyleSheet("font-size: 13px; color: #64748B;")
        title_box.addWidget(title_lbl)
        title_box.addWidget(sub_lbl)
        main_layout.addLayout(title_box)

        # 2. Scroll container
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content_widget = QWidget()
        layout = QVBoxLayout(content_widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        # Card 1: Organisation & Branding
        org_card = QFrame(self)
        org_card.setProperty("class", "ContentCard")
        f_org = QFormLayout(org_card)
        f_org.setSpacing(12)

        org_title = QLabel("Organisation & Branding", org_card)
        org_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")
        f_org.addRow(org_title)

        self.edit_org_name = QLineEdit(org_card)
        f_org.addRow("Organisation Name:", self.edit_org_name)

        # Logo display & file picker
        logo_box = QHBoxLayout()
        self.logo_preview = QLabel(org_card)
        self.logo_preview.setFixedSize(48, 48)
        self.logo_preview.setScaledContents(True)

        self.edit_logo_path = QLineEdit(org_card)
        self.edit_logo_path.setPlaceholderText("Leave blank to auto-detect from project root / bundled assets")

        btn_browse_logo = QPushButton("Browse...", org_card)
        btn_browse_logo.setProperty("class", "SecondaryButton")
        btn_browse_logo.clicked.connect(self._on_browse_logo)

        logo_box.addWidget(self.logo_preview)
        logo_box.addWidget(self.edit_logo_path)
        logo_box.addWidget(btn_browse_logo)
        f_org.addRow("Trust Logo Image:", logo_box)

        layout.addWidget(org_card)

        # Card 2: Cloud Backup Gateway Configuration
        cloud_card = QFrame(self)
        cloud_card.setProperty("class", "ContentCard")
        f_cloud = QFormLayout(cloud_card)
        f_cloud.setSpacing(12)

        cloud_title = QLabel("Cloud Backup Gateway (Google Apps Script)", cloud_card)
        cloud_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")
        f_cloud.addRow(cloud_title)

        cloud_info = QLabel(
            "Configure the Google Apps Script Web App URL for automatic cloud backup.\n"
            "The desktop application communicates via secure HTTPS without requiring Google OAuth login or local token files.",
            cloud_card
        )
        cloud_info.setStyleSheet("color: #64748B; font-size: 12px;")
        cloud_info.setWordWrap(True)
        f_cloud.addRow(cloud_info)

        self.edit_apps_script_url = QLineEdit(cloud_card)
        self.edit_apps_script_url.setPlaceholderText("https://script.google.com/macros/s/AKfycb.../exec")
        f_cloud.addRow("Gateway Web App URL:", self.edit_apps_script_url)

        self.edit_api_key = QLineEdit(cloud_card)
        self.edit_api_key.setEchoMode(QLineEdit.Password)
        self.edit_api_key.setPlaceholderText("Enter BACKUP_API_KEY (confidential)")
        f_cloud.addRow("Gateway API Key:", self.edit_api_key)

        layout.addWidget(cloud_card)

        # Card 3: Demonstration & Test Data Controls
        demo_card = QFrame(self)
        demo_card.setProperty("class", "ContentCard")
        f_demo = QVBoxLayout(demo_card)
        f_demo.setSpacing(12)

        demo_title = QLabel("Demonstration & Test Data", demo_card)
        demo_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")
        f_demo.addWidget(demo_title)

        demo_info = QLabel(
            "Load 100 synthetic, realistic Pernem / Goa candidate profiles for training, system demonstration, "
            "and offline validation. Demo records are strictly flagged (is_demo = 1) and can be purged at any time "
            "without disturbing genuine candidate records.",
            demo_card
        )
        demo_info.setStyleSheet("color: #64748B; font-size: 12px;")
        demo_info.setWordWrap(True)
        f_demo.addWidget(demo_info)

        demo_action_box = QHBoxLayout()
        demo_action_box.setSpacing(12)

        self.lbl_demo_count = QLabel("Demo Candidates Loaded: 0", demo_card)
        self.lbl_demo_count.setStyleSheet("font-weight: 600; color: #0F172A; font-size: 13px;")
        demo_action_box.addWidget(self.lbl_demo_count)
        demo_action_box.addStretch()

        self.btn_load_demo = QPushButton("Load 100 Demo Candidates", demo_card)
        self.btn_load_demo.setProperty("class", "SecondaryButton")
        self.btn_load_demo.setIcon(AppIcons.add_candidate())
        self.btn_load_demo.setCursor(Qt.PointingHandCursor)
        self.btn_load_demo.clicked.connect(self._on_load_demo_data)
        demo_action_box.addWidget(self.btn_load_demo)

        self.btn_remove_demo = QPushButton("Remove Demo Data", demo_card)
        self.btn_remove_demo.setProperty("class", "SecondaryButton")
        self.btn_remove_demo.setIcon(AppIcons.trash())
        self.btn_remove_demo.setCursor(Qt.PointingHandCursor)
        self.btn_remove_demo.clicked.connect(self._on_remove_demo_data)
        demo_action_box.addWidget(self.btn_remove_demo)

        f_demo.addLayout(demo_action_box)
        layout.addWidget(demo_card)

        # Card 4: Local Storage Directories
        dir_card = QFrame(self)
        dir_card.setProperty("class", "ContentCard")
        f_dir = QFormLayout(dir_card)
        f_dir.setSpacing(12)

        dir_title = QLabel("Local Storage Directories", dir_card)
        dir_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")
        f_dir.addRow(dir_title)

        self.edit_db_path = QLineEdit(dir_card)
        self.edit_db_path.setReadOnly(True)
        self.edit_db_path.setStyleSheet("background-color: #F1F5F9; color: #475569;")
        f_dir.addRow("Active SQLite Database:", self.edit_db_path)

        self.edit_backup_dir = QLineEdit(dir_card)
        self.edit_backup_dir.setReadOnly(True)
        self.edit_backup_dir.setStyleSheet("background-color: #F1F5F9; color: #475569;")
        f_dir.addRow("Database Backups Folder:", self.edit_backup_dir)

        layout.addWidget(dir_card)

        # Card 5: Software Updates & System Version
        update_card = QFrame(self)
        update_card.setProperty("class", "ContentCard")
        f_update = QFormLayout(update_card)
        f_update.setSpacing(12)

        update_title = QLabel("Software Updates & System Information", update_card)
        update_title.setStyleSheet("font-weight: 700; color: #0F172A; font-size: 13px;")
        f_update.addRow(update_title)

        app_name_label = QLabel("Pedne Sewa Trust Employment Registry", update_card)
        app_name_label.setStyleSheet("font-weight: 600; color: #0F172A; font-size: 13px;")
        f_update.addRow("Application:", app_name_label)

        ver_label = QLabel(f"Version {APP_VERSION}", update_card)
        ver_label.setStyleSheet("color: #15803D; font-weight: 700; font-size: 13px;")
        f_update.addRow("Version:", ver_label)

        repo_label = QLabel(f"<a href='https://github.com/{GITHUB_REPO_SLUG}'>github.com/{GITHUB_REPO_SLUG}</a>", update_card)
        repo_label.setOpenExternalLinks(True)
        repo_label.setStyleSheet("color: #0284C7; font-size: 13px;")
        f_update.addRow("GitHub Repository:", repo_label)

        update_action_box = QHBoxLayout()
        self.btn_check_update = QPushButton("Check for Updates", update_card)
        self.btn_check_update.setProperty("class", "SecondaryButton")
        self.btn_check_update.setIcon(AppIcons.sync())
        self.btn_check_update.setCursor(Qt.PointingHandCursor)
        self.btn_check_update.clicked.connect(self._on_check_updates)
        update_action_box.addWidget(self.btn_check_update)
        update_action_box.addStretch()
        f_update.addRow("Software Updates:", update_action_box)

        layout.addWidget(update_card)

        scroll.setWidget(content_widget)
        main_layout.addWidget(scroll)

        # 3. Footer Actions
        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        btn_save = QPushButton("Save Settings", self)
        btn_save.setProperty("class", "PrimaryButton")
        btn_save.setIcon(AppIcons.save())
        btn_save.setMinimumHeight(38)
        btn_save.clicked.connect(self._on_save_settings)
        btn_layout.addWidget(btn_save)

        main_layout.addLayout(btn_layout)

    def load_settings(self):
        self.edit_org_name.setText(config.get("organisation_name", "Pedne Sewa Trust"))
        self.edit_logo_path.setText(config.get("custom_logo_path", ""))
        self.edit_apps_script_url.setText(config.get("apps_script_url", ""))
        self.edit_api_key.setText(config.get("backup_api_key", ""))
        self.edit_db_path.setText(config.get("database_path", ""))
        self.edit_backup_dir.setText(config.get("backup_dir", ""))
        self._update_logo_preview()
        self._update_demo_count()

    def _update_demo_count(self):
        try:
            from database.repository import repository
            count = repository.count_demo_candidates()
            self.lbl_demo_count.setText(f"Demo Candidates Loaded: {count}")
        except Exception as e:
            logger.warning("Could not read demo candidate count: %s", e)

    def _update_logo_preview(self):
        logo_path = config.resolve_logo_path()
        if logo_path and os.path.exists(logo_path):
            pix = QPixmap(logo_path)
            if not pix.isNull():
                self.logo_preview.setPixmap(pix.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.logo_preview.setText("🏛️")

    def _on_browse_logo(self):
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Logo Image File",
            "",
            "Image Files (*.png *.jpg *.jpeg *.svg *.ico);;All Files (*.*)"
        )
        if file_path:
            self.edit_logo_path.setText(file_path)
            pix = QPixmap(file_path)
            if not pix.isNull():
                self.logo_preview.setPixmap(pix.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def _on_save_settings(self):
        config.set("organisation_name", self.edit_org_name.text().strip() or "Pedne Sewa Trust")
        config.set("custom_logo_path", self.edit_logo_path.text().strip())
        config.set("apps_script_url", self.edit_apps_script_url.text().strip())
        config.set("backup_api_key", self.edit_api_key.text().strip())
        signals.settings_updated.emit()
        self._update_logo_preview()
        QMessageBox.information(self, "Settings Saved", "Application configuration updated successfully!")

    def _on_load_demo_data(self):
        reply = QMessageBox.question(
            self,
            "Load Demonstration Data",
            "This will populate the database with 100 synthetic Pernem candidate profiles for testing.\n\n"
            "All demo records are clearly marked and segregated (is_demo = 1).\n\n"
            "Would you like to proceed?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.Yes
        )
        if reply == QMessageBox.Yes:
            try:
                from database.repository import repository
                from database.demo_data_generator import seed_demo_data
                count = seed_demo_data(repository)
                self._update_demo_count()
                signals.database_restored.emit()
                QMessageBox.information(
                    self,
                    "Demo Data Loaded",
                    f"Successfully loaded {count} demonstration candidates!\n\n"
                    "Dashboard metrics, candidate databases, and reports have been updated."
                )
            except Exception as e:
                logger.error("Failed to load demo data: %s", e)
                QMessageBox.critical(self, "Error", f"Failed to seed demo candidates: {e}")

    def _on_remove_demo_data(self):
        reply = QMessageBox.warning(
            self,
            "Remove Demonstration Data",
            "This will permanently delete all demonstration candidates (is_demo = 1) from the database.\n\n"
            "Genuine candidate registrations will NOT be affected.\n\n"
            "Are you sure you want to remove all demonstration data?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        if reply == QMessageBox.Yes:
            try:
                from database.repository import repository
                removed = repository.remove_demo_candidates()
                self._update_demo_count()
                signals.database_restored.emit()
                QMessageBox.information(
                    self,
                    "Demo Data Removed",
                    f"Successfully removed {removed} demonstration records.\n\n"
                    "All views and reports have been refreshed."
                )
            except Exception as e:
                logger.error("Failed to remove demo data: %s", e)
                QMessageBox.critical(self, "Error", f"Failed to remove demo candidates: {e}")

    def _on_check_updates(self):
        self.btn_check_update.setEnabled(False)
        self.btn_check_update.setText("Checking GitHub...")
        try:
            from app.updater import UpdateCheckThread
            self.update_thread = UpdateCheckThread(is_manual=True, parent=self)
            self.update_thread.update_available.connect(self._on_update_found)
            self.update_thread.update_not_available.connect(self._on_up_to_date)
            self.update_thread.check_failed.connect(self._on_update_failed)
            self.update_thread.start()
        except Exception as e:
            self._reset_update_btn()
            QMessageBox.warning(self, "Update Error", f"Could not initialize update check: {e}")

    def _reset_update_btn(self):
        self.btn_check_update.setEnabled(True)
        self.btn_check_update.setText("Check for Updates")

    def _on_update_found(self, latest_ver: str, notes: str, download_url: str, asset_name: str = "", checksum_url: str = ""):
        self._reset_update_btn()
        try:
            from app.updater import UpdateDialog
            dlg = UpdateDialog(latest_ver, notes, download_url, asset_name, checksum_url, self)
            dlg.exec()
        except Exception as e:
            QMessageBox.warning(self, "Update Dialog Error", f"Could not open update dialog: {e}")

    def _on_up_to_date(self, current_ver: str):
        self._reset_update_btn()
        QMessageBox.information(
            self,
            "Up to Date",
            f"You are running the latest version of Pedne Sewa Trust Registry (v{current_ver}). No updates are currently needed."
        )

    def _on_update_failed(self, err_msg: str):
        self._reset_update_btn()
        QMessageBox.warning(
            self,
            "Update Check",
            f"Could not connect to GitHub to check for updates:\n{err_msg}\n\nPlease check your internet connection or try again later."
        )


