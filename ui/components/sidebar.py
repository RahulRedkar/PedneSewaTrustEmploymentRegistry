"""
Sidebar Navigation component for Pedne Sewa Trust - Employment Registry.
Uses crisp Qt standard icons and highlights active navigation state.
"""

from PySide6.QtWidgets import QWidget, QVBoxLayout, QPushButton, QLabel
from PySide6.QtCore import Qt, Signal, QSize
from ui.components.icons import AppIcons


class Sidebar(QWidget):
    """Sidebar navigation menu with highlighted active state."""

    page_changed = Signal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("Sidebar")
        self.setFixedWidth(220)
        self.buttons = []
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 16, 8, 16)
        layout.setSpacing(6)

        nav_items = [
            ("Dashboard", AppIcons.dashboard(), 0),
            ("Add Candidate", AppIcons.add_candidate(), 1),
            ("Candidate Database", AppIcons.database(), 2),
            ("Government Jobs", AppIcons.gov_jobs(), 3),
            ("Recruiters", AppIcons.recruiters(), 4),
            ("Reports & Analytics", AppIcons.reports(), 5),
            ("Backup / Export", AppIcons.backup(), 6),
            ("Settings", AppIcons.settings(), 7)
        ]

        for text, icon, index in nav_items:
            btn = QPushButton(text, self)
            btn.setObjectName("NavButton")
            btn.setProperty("class", "NavButton")
            btn.setIcon(icon)
            btn.setIconSize(QSize(18, 18))
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.clicked.connect(lambda checked, idx=index: self.set_active_index(idx))
            self.buttons.append(btn)
            layout.addWidget(btn)

        layout.addStretch()

        # Footer info
        from app.constants import APP_VERSION
        ver_label = QLabel(f"v{APP_VERSION} (Goa Facilitation)", self)
        ver_label.setStyleSheet("color: #94A3B8; font-size: 11px; padding-left: 14px;")
        layout.addWidget(ver_label)

        # Set Dashboard active initially
        if self.buttons:
            self.set_active_index(0)

    def set_active_index(self, index: int):
        for i, btn in enumerate(self.buttons):
            is_active = (i == index)
            btn.setChecked(is_active)
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
        self.page_changed.emit(index)
