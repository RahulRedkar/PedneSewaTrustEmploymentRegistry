"""
Date of Birth input control for Pedne Sewa Trust - Employment Registry.
Simplified direct input: [ DD/MM/YYYY 📅 ] with native calendar popup and Clear button.
No checkbox. Blank allows manual age entry; selected date auto-calculates age.
"""

from typing import Optional
from PySide6.QtWidgets import QWidget, QHBoxLayout, QDateEdit, QPushButton
from PySide6.QtCore import Qt, QDate, Signal
from utils.validators import calculate_age_from_dob
from ui.components.icons import AppIcons


class DateOfBirthPicker(QWidget):
    """
    Direct Date of Birth picker:
    - Clean [ DD/MM/YYYY 📅 ] input with native calendar popup.
    - Zero checkbox controls.
    - Special value text for blank/optional state.
    - Clear button resets to blank.
    - Range: 1920-01-01 to today.
    - Emits ISO string and auto-calculates age.
    """

    date_changed = Signal(str)      # Emits ISO string "YYYY-MM-DD" or ""
    age_calculated = Signal(int)     # Emits calculated age in years

    def __init__(self, parent=None):
        super().__init__(parent)
        self._blank_date = QDate(1919, 12, 31)
        self._min_valid_date = QDate(1920, 1, 1)
        self._is_set: bool = False
        self._init_ui()

    def _init_ui(self):
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(8)

        # Native QDateEdit
        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("dd/MM/yyyy")
        self.date_edit.setSpecialValueText("DD/MM/YYYY (Optional)")

        # Range: 1919-12-31 (sentinel blank) to today
        today = QDate.currentDate()
        self.date_edit.setMinimumDate(self._blank_date)
        self.date_edit.setMaximumDate(today)

        # Start in blank state
        self.date_edit.setDate(self._blank_date)
        self.date_edit.dateChanged.connect(self._on_date_changed)
        layout.addWidget(self.date_edit, 1)

        # Clear Button
        self.btn_clear = QPushButton("Clear", self)
        self.btn_clear.setProperty("class", "SecondaryButton")
        self.btn_clear.setIcon(AppIcons.clear())
        self.btn_clear.setToolTip("Clear Date of Birth (leave blank)")
        self.btn_clear.setCursor(Qt.PointingHandCursor)
        self.btn_clear.clicked.connect(self.clear)
        self.btn_clear.setEnabled(False)
        layout.addWidget(self.btn_clear)

    def _on_date_changed(self, qdate: QDate):
        if qdate <= self._blank_date or not qdate.isValid():
            self._is_set = False
            self.btn_clear.setEnabled(False)
            self.date_changed.emit("")
        else:
            self._is_set = True
            self.btn_clear.setEnabled(True)
            iso_str = qdate.toString("yyyy-MM-dd")
            self.date_changed.emit(iso_str)
            age = calculate_age_from_dob(iso_str)
            if age is not None:
                self.age_calculated.emit(age)

    def get_date_iso(self) -> Optional[str]:
        """Returns ISO string 'YYYY-MM-DD' if set, else None."""
        if not self._is_set or self.date_edit.date() < self._min_valid_date:
            return None
        return self.date_edit.date().toString("yyyy-MM-dd")

    def set_date_iso(self, iso_str: Optional[str]):
        """Sets date from ISO string. If None or empty, resets to blank."""
        if not iso_str:
            self.clear()
            return

        qd = QDate.fromString(iso_str[:10], "yyyy-MM-dd")
        if qd.isValid() and qd >= self._min_valid_date:
            self.date_edit.setDate(qd)
        else:
            self.clear()

    def clear(self):
        """Resets to blank/unspecified."""
        self._is_set = False
        self.date_edit.setDate(self._blank_date)
        self.btn_clear.setEnabled(False)
        self.date_changed.emit("")
