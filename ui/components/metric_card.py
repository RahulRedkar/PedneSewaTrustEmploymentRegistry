"""
Reusable KPI metric card widget for Dashboard and analytical reports.
Clean white card with subtle border and semantic coloured accent.
"""

from typing import Any
from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel
from PySide6.QtCore import Qt


class MetricCard(QFrame):
    """Clean white KPI card displaying title, primary number, and secondary description."""

    def __init__(self, title: str, value: str = "0", subtitle: str = "", accent_color: str = "#15803D", parent=None):
        super().__init__(parent)
        self.setProperty("class", "MetricCard")
        self.accent_color = accent_color
        self.setStyleSheet(f"""
            QFrame.MetricCard {{
                background-color: #FFFFFF;
                border: 1px solid #E2E8F0;
                border-left: 4px solid {accent_color};
                border-radius: 8px;
                padding: 14px 16px;
            }}
        """)
        self._init_ui(title, value, subtitle)

    def _init_ui(self, title: str, value: str, subtitle: str):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.label_title = QLabel(title.upper(), self)
        self.label_title.setStyleSheet("color: #64748B; font-size: 11px; font-weight: 700; letter-spacing: 0.5px;")

        self.label_val = QLabel(str(value), self)
        self.label_val.setStyleSheet("color: #0F172A; font-size: 28px; font-weight: 800; padding: 2px 0;")

        self.label_sub = QLabel(subtitle, self)
        self.label_sub.setStyleSheet("color: #64748B; font-size: 12px;")
        if not subtitle:
            self.label_sub.hide()

        layout.addWidget(self.label_title)
        layout.addWidget(self.label_val)
        layout.addWidget(self.label_sub)

    def update_value(self, value: Any, subtitle: str = None):
        self.label_val.setText(str(value))
        if subtitle is not None:
            self.label_sub.setText(subtitle)
            self.label_sub.setVisible(bool(subtitle))
