"""
Main Application Window for Pedne Sewa Trust - Employment & Candidate Registry.
Orchestrates sidebar navigation, header status, view stack, and background jobs.
"""

import os
from PySide6.QtWidgets import QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QStackedWidget
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtCore import Qt, QTimer

from app.config import config
from app.signals import signals
from export.backup_manager import backup_manager
from sync.sync_worker import sync_worker
from ui.components.header_bar import HeaderBar
from ui.components.sidebar import Sidebar
from ui.components.toast import ToastNotification
from ui.views.dashboard_view import DashboardView
from ui.views.candidate_form_view import CandidateFormView
from ui.views.candidate_list_view import CandidateListView
from ui.views.government_jobs_view import GovernmentJobsView
from ui.views.recruiters_view import RecruitersView
from ui.views.reports_view import ReportsView
from ui.views.backup_view import BackupView
from ui.views.settings_view import SettingsView
from utils.logger import logger


class MainWindow(QMainWindow):
    """Main Application Window."""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Pedne Sewa Trust — Employment & Candidate Registry")
        self.setMinimumSize(1120, 720)
        self.resize(1200, 800)

        self._set_app_icon()
        self._init_ui()
        self._connect_signals()
        self._init_startup_tasks()

    def _set_app_icon(self):
        """Sets application window and taskbar icon."""
        try:
            from main import get_app_icon
            icon = get_app_icon()
            if not icon.isNull():
                self.setWindowIcon(icon)
                return
        except Exception:
            pass

        icon_path = config.base_dir / "assets" / "icon.ico"
        if not icon_path.exists():
            icon_path = config.resolve_logo_path()
        if icon_path and os.path.exists(str(icon_path)):
            self.setWindowIcon(QIcon(str(icon_path)))

    def _init_ui(self):
        central_widget = QWidget(self)
        central_widget.setObjectName("CentralWidget")
        self.setCentralWidget(central_widget)

        root_layout = QVBoxLayout(central_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # 1. Header Bar
        self.header = HeaderBar(self)
        root_layout.addWidget(self.header)

        # 2. Body (Sidebar + View Stack)
        body_layout = QHBoxLayout()
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)

        self.sidebar = Sidebar(self)
        body_layout.addWidget(self.sidebar)

        # View Stack
        self.stack = QStackedWidget(self)

        self.dashboard_view = DashboardView(self)
        self.form_view = CandidateFormView(self)
        self.list_view = CandidateListView(self)
        self.gov_jobs_view = GovernmentJobsView(self)
        self.recruiters_view = RecruitersView(self)
        self.reports_view = ReportsView(self)
        self.backup_view = BackupView(self)
        self.settings_view = SettingsView(self)

        self.stack.addWidget(self.dashboard_view)   # 0
        self.stack.addWidget(self.form_view)        # 1
        self.stack.addWidget(self.list_view)        # 2
        self.stack.addWidget(self.gov_jobs_view)    # 3
        self.stack.addWidget(self.recruiters_view)  # 4
        self.stack.addWidget(self.reports_view)     # 5
        self.stack.addWidget(self.backup_view)      # 6
        self.stack.addWidget(self.settings_view)    # 7

        body_layout.addWidget(self.stack, 1)
        root_layout.addLayout(body_layout)

        # Toast notification overlay
        self.toast = ToastNotification(self)

    def _connect_signals(self):
        self.sidebar.page_changed.connect(self.stack.setCurrentIndex)
        self.dashboard_view.navigate_requested.connect(self.sidebar.set_active_index)

        # If candidate intake duplicate review is clicked, switch to table and focus candidate
        self.form_view.review_candidate_requested.connect(self._on_review_candidate_requested)

        # Clean, operator-facing toasts (no cloud sync mentions)
        signals.candidate_saved.connect(
            lambda cid: self.toast.show_toast(f"Candidate {cid} registered successfully", "success")
        )
        signals.candidate_updated.connect(
            lambda cid: self.toast.show_toast(f"Candidate {cid} updated successfully", "info")
        )

    def _on_review_candidate_requested(self, candidate_id: str):
        self.sidebar.set_active_index(2)  # Switch to Candidate Database
        self.list_view.select_and_view_candidate(candidate_id)

    def _init_startup_tasks(self):
        """Runs automatic startup backup and starts the 10-minute periodic sync worker."""
        # 1. Automatic startup backup
        try:
            backup_manager.create_backup(is_automatic=True)
        except Exception as e:
            logger.error("Automatic startup database backup error: %s", e)

        # 2. Start background sync timer
        sync_worker.start()

        # 3. Initial sync attempt after 3 seconds in background thread
        QTimer.singleShot(3000, lambda: sync_worker.sync_now(is_manual=False))

        # 4. Non-blocking GitHub update check after 5 seconds
        QTimer.singleShot(5000, self._check_software_updates)

    def _check_software_updates(self):
        """Launches non-blocking background thread to check GitHub Releases."""
        try:
            from app.updater import UpdateCheckThread
            self.update_thread = UpdateCheckThread(parent=self)
            self.update_thread.update_available.connect(self._on_update_available)
            self.update_thread.start()
        except Exception as e:
            logger.debug("Could not initialize update check thread: %s", e)

    def _on_update_available(self, latest_ver: str, release_notes: str, download_url: str, asset_name: str = "", checksum_url: str = ""):
        try:
            from app.updater import UpdateDialog
            dlg = UpdateDialog(latest_ver, release_notes, download_url, asset_name, checksum_url, self)
            dlg.exec()
        except Exception as e:
            logger.warning("Could not display update dialog: %s", e)
