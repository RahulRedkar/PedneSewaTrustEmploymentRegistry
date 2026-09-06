"""
Top Application Header Bar for Pedne Sewa Trust - Employment Registry.
Displays Trust branding, logo, and real-time Cloud Backup status pill.
"""

import os
from PySide6.QtWidgets import QWidget, QHBoxLayout, QVBoxLayout, QLabel, QPushButton
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt
from app.config import config
from app.signals import signals
from sync.sync_worker import sync_worker
from ui.components.icons import AppIcons


class HeaderBar(QWidget):
    """Header bar with clean NGO branding and Cloud Backup status pill."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("HeaderBar")
        self.setFixedHeight(68)
        self._init_ui()
        self._connect_signals()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 0, 20, 0)
        layout.setSpacing(14)

        # 1. Logo Display (clean aspect ratio)
        self.logo_label = QLabel(self)
        self.logo_label.setFixedSize(48, 48)
        self.logo_label.setScaledContents(True)
        self.reload_logo()
        layout.addWidget(self.logo_label)

        # 2. Title & Subtitle
        title_box = QVBoxLayout()
        title_box.setSpacing(2)
        title_box.setAlignment(Qt.AlignVCenter)

        org_name = config.get("organisation_name", "Pedne Sewa Trust")
        self.title_label = QLabel(org_name.upper(), self)
        self.title_label.setObjectName("HeaderTitle")

        self.sub_label = QLabel("Employment & Candidate Registry — Pernem, Goa", self)
        self.sub_label.setObjectName("HeaderSubtitle")

        title_box.addWidget(self.title_label)
        title_box.addWidget(self.sub_label)
        layout.addLayout(title_box)

        layout.addStretch()

        # Operator-facing "Backup to Cloud" action button & Trust badge
        action_box = QHBoxLayout()
        action_box.setSpacing(12)

        self.btn_backup_cloud = QPushButton("Backup to Cloud", self)
        self.btn_backup_cloud.setProperty("class", "SecondaryButton")
        self.btn_backup_cloud.setIcon(AppIcons.backup())
        self.btn_backup_cloud.setCursor(Qt.PointingHandCursor)
        self.btn_backup_cloud.setToolTip("Manually synchronize local records with the cloud backup repository")
        self.btn_backup_cloud.clicked.connect(self._on_backup_cloud_clicked)
        action_box.addWidget(self.btn_backup_cloud)

        badge_lbl = QLabel("Pernem Taluka Employment Registry", self)
        badge_lbl.setStyleSheet("color: #64748B; font-size: 12px; font-weight: 600; padding: 5px 12px; background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px;")
        action_box.addWidget(badge_lbl)

        layout.addLayout(action_box)

    def _on_backup_cloud_clicked(self):
        """Triggers manual background sync cycle with feedback."""
        from sync.apps_script_client import apps_script_client
        from PySide6.QtWidgets import QMessageBox
        if not apps_script_client.is_configured():
            QMessageBox.warning(
                self,
                "Cloud Backup Gateway Required",
                "Cloud backup gateway is not configured.\n\n"
                "Please configure the Gateway Web App URL and API Key in Settings before initiating cloud backup."
            )
            return
        self.btn_backup_cloud.setEnabled(False)
        self.btn_backup_cloud.setText("Syncing...")
        sync_worker.sync_now(is_manual=True)

    def reload_logo(self):
        """Reloads logo preserving aspect ratio."""
        logo_path = config.resolve_logo_path()
        if logo_path and os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                self.logo_label.setPixmap(pixmap.scaled(48, 48, Qt.KeepAspectRatio, Qt.SmoothTransformation))
                return
        self.logo_label.setText("🏛️")

    def _connect_signals(self):
        signals.settings_updated.connect(self._on_settings_updated)
        signals.sync_completed.connect(lambda info: self._reset_backup_btn())
        signals.sync_failed.connect(lambda err: self._reset_backup_btn())

    def _reset_backup_btn(self):
        self.btn_backup_cloud.setEnabled(True)
        self.btn_backup_cloud.setText("Backup to Cloud")

    def update_cloud_status(self, status: str, message: str):
        """Silent status handler to preserve signal interface without UI exposure."""
        pass

    def _on_settings_updated(self):
        self.title_label.setText(config.get("organisation_name", "Pedne Sewa Trust").upper())
        self.reload_logo()
