"""
Employment Status Segmented Selector for Pedne Sewa Trust - Employment Registry.
Presents visually distinct cards for EMPLOYED, UNEMPLOYED, SELF-EMPLOYED, and STUDENT.
"""

from PySide6.QtWidgets import QWidget, QHBoxLayout, QPushButton
from PySide6.QtCore import Qt, Signal


class EmploymentStatusSelector(QWidget):
    """Segmented status card selector."""

    status_changed = Signal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.buttons = {}
        self.current_status = "UNEMPLOYED"
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        options = [
            ("UNEMPLOYED", "Unemployed"),
            ("EMPLOYED", "Employed"),
            ("SELF_EMPLOYED", "Self-Employed"),
            ("STUDENT", "Student")
        ]

        for code, label in options:
            btn = QPushButton(label, self)
            btn.setCheckable(True)
            btn.setCursor(Qt.PointingHandCursor)
            btn.setMinimumHeight(38)
            btn.clicked.connect(lambda checked, c=code: self.set_status(c))
            self.buttons[code] = btn
            layout.addWidget(btn)

        self.set_status("UNEMPLOYED")

    def set_status(self, code: str):
        """Activates the given status and updates button styles."""
        self.current_status = code
        for c, btn in self.buttons.items():
            is_active = (c == code)
            btn.setChecked(is_active)
            if is_active:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #F0FDF4;
                        color: #15803D;
                        border: 2px solid #15803D;
                        border-radius: 6px;
                        font-weight: 700;
                        font-size: 13px;
                        padding: 8px 14px;
                    }
                """)
            else:
                btn.setStyleSheet("""
                    QPushButton {
                        background-color: #FFFFFF;
                        color: #475569;
                        border: 1px solid #E2E8F0;
                        border-radius: 6px;
                        font-weight: 600;
                        font-size: 13px;
                        padding: 8px 14px;
                    }
                    QPushButton:hover {
                        background-color: #F8FAFC;
                        color: #0F172A;
                        border-color: #CBD5E1;
                    }
                """)
        self.status_changed.emit(code)

    def get_status(self) -> str:
        return self.current_status
