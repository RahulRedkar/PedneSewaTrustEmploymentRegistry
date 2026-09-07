"""
Log Walk-in Visit Dialog for Pedne Sewa Trust - Visiting Register.
Enables quick entry and editing of walk-in candidate visits with auto-assigned Sr No,
date/time defaults, candidate autocomplete, village selection, and purpose presets.
"""

from datetime import datetime
from typing import Optional, List
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QFormLayout, QLabel,
    QLineEdit, QComboBox, QDateEdit, QTimeEdit, QPushButton,
    QFrame, QMessageBox, QCompleter
)
from PySide6.QtCore import Qt, QDate, QTime, QStringListModel

from models.visitor import VisitorRecord
from database.repository import repository
from app.constants import PERNEM_VILLAGES, VISIT_PURPOSES
from ui.components.icons import AppIcons
from utils.validators import clean_mobile
from utils.logger import logger


class LogVisitDialog(QDialog):
    """Dialog to record or edit a visitor walk-in entry."""

    def __init__(self, visitor: Optional[VisitorRecord] = None, parent=None):
        super().__init__(parent)
        self.visitor = visitor
        self.is_edit = visitor is not None and visitor.id is not None
        self.saved_record: Optional[VisitorRecord] = None

        self._candidates_lookup = {}
        self._init_ui()
        self._load_candidate_autocomplete()
        if self.is_edit and self.visitor:
            self._populate_existing()
        else:
            self._set_defaults()

    def _init_ui(self):
        title = "Edit Visit Record" if self.is_edit else "Log New Walk-in Visit"
        self.setWindowTitle(f"📝 {title} - Visiting Register")
        self.setMinimumWidth(520)
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # Header card
        header_card = QFrame(self)
        header_card.setStyleSheet("""
            QFrame {
                background-color: #F8FAFC;
                border: 1px solid #E2E8F0;
                border-radius: 8px;
                padding: 10px 14px;
            }
        """)
        h_layout = QVBoxLayout(header_card)
        h_layout.setContentsMargins(0, 0, 0, 0)
        h_layout.setSpacing(2)

        title_text = "Edit Walk-in Visitor Record" if self.is_edit else "New Walk-in Visit Entry"
        h_title = QLabel(title_text, header_card)
        h_title.setStyleSheet("font-size: 16px; font-weight: 800; color: #0F172A;")
        h_desc = QLabel("Enter visitor particulars. Sr No., date, and time are automatically managed.", header_card)
        h_desc.setStyleSheet("font-size: 12px; color: #64748B;")
        h_layout.addWidget(h_title)
        h_layout.addWidget(h_desc)
        layout.addWidget(header_card)

        # Form
        form_layout = QFormLayout()
        form_layout.setSpacing(12)
        form_layout.setLabelAlignment(Qt.AlignRight | Qt.AlignVCenter)

        # 1. Sr No.
        sr_layout = QHBoxLayout()
        self.sr_no_edit = QLineEdit(self)
        self.sr_no_edit.setReadOnly(True)
        self.sr_no_edit.setStyleSheet("background-color: #F1F5F9; color: #475569; font-weight: 700;")
        self.sr_no_edit.setFixedWidth(100)
        sr_desc = QLabel("(Auto-assigned sequential number)", self)
        sr_desc.setStyleSheet("font-size: 11px; color: #94A3B8;")
        sr_layout.addWidget(self.sr_no_edit)
        sr_layout.addWidget(sr_desc)
        sr_layout.addStretch()
        form_layout.addRow("Sr No.:", sr_layout)

        # 2. Visit Date
        self.date_edit = QDateEdit(self)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.setDisplayFormat("yyyy-MM-dd")
        self.date_edit.setDate(QDate.currentDate())
        form_layout.addRow("Visit Date *:", self.date_edit)

        # 3. Visit Time
        self.time_edit = QTimeEdit(self)
        self.time_edit.setDisplayFormat("hh:mm AP")
        self.time_edit.setTime(QTime.currentTime())
        form_layout.addRow("Visit Time *:", self.time_edit)

        # 4. Name of Candidate
        self.name_edit = QLineEdit(self)
        self.name_edit.setPlaceholderText("Full Name of candidate / visitor")
        self.name_edit.setClearButtonEnabled(True)
        form_layout.addRow("Candidate Name *:", self.name_edit)

        # 5. Address (Village)
        self.village_combo = QComboBox(self)
        self.village_combo.setEditable(True)
        self.village_combo.addItem("")  # Blank default
        self.village_combo.addItems(PERNEM_VILLAGES)
        self.village_combo.setPlaceholderText("Select or type village")
        form_layout.addRow("Address (Village):", self.village_combo)

        # 6. Mobile Number
        self.mobile_edit = QLineEdit(self)
        self.mobile_edit.setPlaceholderText("10-digit mobile number")
        self.mobile_edit.setMaxLength(15)
        self.mobile_edit.setClearButtonEnabled(True)
        form_layout.addRow("Mobile No.:", self.mobile_edit)

        # 7. Purpose of Visit
        self.purpose_combo = QComboBox(self)
        self.purpose_combo.setEditable(True)
        self.purpose_combo.addItems(VISIT_PURPOSES)
        form_layout.addRow("Purpose of Visit *:", self.purpose_combo)

        layout.addLayout(form_layout)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(10)

        self.btn_cancel = QPushButton("Cancel", self)
        self.btn_cancel.setProperty("class", "SecondaryButton")
        self.btn_cancel.setIcon(AppIcons.cancel())
        self.btn_cancel.clicked.connect(self.reject)

        save_label = "Update Visit" if self.is_edit else "Save Visit Record"
        self.btn_save = QPushButton(save_label, self)
        self.btn_save.setProperty("class", "PrimaryButton")
        self.btn_save.setIcon(AppIcons.save())
        self.btn_save.setStyleSheet("""
            QPushButton {
                background-color: #2563EB;
                color: white;
                font-weight: 700;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #1D4ED8;
            }
        """)
        self.btn_save.clicked.connect(self._on_save)

        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_save)
        layout.addLayout(btn_layout)

    def _set_defaults(self):
        next_sr = repository.get_next_visitor_sr_no()
        self.sr_no_edit.setText(str(next_sr))
        self.date_edit.setDate(QDate.currentDate())
        self.time_edit.setTime(QTime.currentTime())

    def _load_candidate_autocomplete(self):
        """Loads candidate names into autocomplete for quick lookup."""
        try:
            candidates = repository.get_all_candidates(include_deleted=False)
            names = []
            for c in candidates:
                if c.full_name:
                    name_clean = c.full_name.strip()
                    names.append(name_clean)
                    self._candidates_lookup[name_clean.lower()] = c

            completer = QCompleter(names, self)
            completer.setCaseSensitivity(Qt.CaseInsensitive)
            completer.setFilterMode(Qt.MatchContains)
            self.name_edit.setCompleter(completer)
            completer.activated.connect(self._on_candidate_selected)
        except Exception as e:
            logger.warning("Could not setup candidate autocomplete for visiting register: %s", e)

    def _on_candidate_selected(self, text: str):
        """Auto-populates village and mobile if a registered candidate is selected."""
        c = self._candidates_lookup.get(text.strip().lower())
        if c:
            if c.village and (not self.village_combo.currentText().strip() or self.village_combo.currentText() == ""):
                idx = self.village_combo.findText(c.village, Qt.MatchFixedString)
                if idx >= 0:
                    self.village_combo.setCurrentIndex(idx)
                else:
                    self.village_combo.setCurrentText(c.village)
            if c.mobile and not self.mobile_edit.text().strip():
                self.mobile_edit.setText(c.mobile)

    def _populate_existing(self):
        v = self.visitor
        if not v:
            return
        self.sr_no_edit.setText(str(v.sr_no))
        if v.visit_date:
            d = QDate.fromString(v.visit_date, "yyyy-MM-dd")
            if d.isValid():
                self.date_edit.setDate(d)
        if v.visit_time:
            t = QTime.fromString(v.visit_time, "hh:mm AP")
            if not t.isValid():
                t = QTime.fromString(v.visit_time, "hh:mm")
            if t.isValid():
                self.time_edit.setTime(t)

        self.name_edit.setText(v.candidate_name)

        if v.village:
            idx = self.village_combo.findText(v.village, Qt.MatchFixedString)
            if idx >= 0:
                self.village_combo.setCurrentIndex(idx)
            else:
                self.village_combo.setCurrentText(v.village)

        self.mobile_edit.setText(v.mobile)

        if v.purpose:
            p_idx = self.purpose_combo.findText(v.purpose, Qt.MatchFixedString)
            if p_idx >= 0:
                self.purpose_combo.setCurrentIndex(p_idx)
            else:
                self.purpose_combo.setCurrentText(v.purpose)

    def _on_save(self):
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Validation Error", "Please enter the candidate / visitor name.")
            self.name_edit.setFocus()
            return

        mobile = self.mobile_edit.text().strip()
        if mobile:
            cleaned_mob = clean_mobile(mobile)
            if len(cleaned_mob) != 10:
                reply = QMessageBox.question(
                    self,
                    "Mobile Number Check",
                    f"The entered mobile number '{mobile}' does not look like a 10-digit number.\nDo you want to save anyway?",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    self.mobile_edit.setFocus()
                    return
                saved_mobile = mobile
            else:
                saved_mobile = cleaned_mob
        else:
            saved_mobile = ""

        purpose = self.purpose_combo.currentText().strip()
        if not purpose:
            purpose = "General Inquiry"

        visit_date = self.date_edit.date().toString("yyyy-MM-dd")
        visit_time = self.time_edit.time().toString("hh:mm AP")
        village = self.village_combo.currentText().strip()

        try:
            sr_no = int(self.sr_no_edit.text().strip())
        except (ValueError, TypeError):
            sr_no = repository.get_next_visitor_sr_no()

        if self.is_edit and self.visitor:
            self.visitor.visit_date = visit_date
            self.visitor.visit_time = visit_time
            self.visitor.candidate_name = name
            self.visitor.village = village
            self.visitor.mobile = saved_mobile
            self.visitor.purpose = purpose
            repository.update_visitor(self.visitor)
            self.saved_record = self.visitor
            logger.info("Updated visitor Sr No. %d in database", self.visitor.sr_no)
        else:
            new_record = VisitorRecord(
                sr_no=sr_no,
                visit_date=visit_date,
                visit_time=visit_time,
                candidate_name=name,
                village=village,
                mobile=saved_mobile,
                purpose=purpose
            )
            rec_id = repository.save_visitor(new_record)
            new_record.id = rec_id
            self.saved_record = new_record
            logger.info("Created new visitor Sr No. %d in database", new_record.sr_no)

        self.accept()
