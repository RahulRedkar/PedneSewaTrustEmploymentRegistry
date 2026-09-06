"""
Duplicate Candidate Warning Dialog for Pedne Sewa Trust - Employment Registry.
Warns operator when a matching mobile, email, or name+address already exists.
"""

from typing import List, Dict, Any
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTableWidget, QTableWidgetItem, QHeaderView, QFrame
)
from PySide6.QtCore import Qt


class DuplicateCandidateDialog(QDialog):
    """Presents existing matching candidates with 'Review' or 'Continue' choices."""

    def __init__(self, duplicates: List[Dict[str, Any]], parent=None):
        super().__init__(parent)
        self.setWindowTitle("⚠️ Potential Duplicate Candidate Detected")
        self.setMinimumSize(680, 420)
        self.setModal(True)
        self.should_continue = False
        self.selected_existing_id = None
        self._init_ui(duplicates)

    def _init_ui(self, duplicates: List[Dict[str, Any]]):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        # Warning Banner
        banner = QFrame(self)
        banner.setStyleSheet("""
            QFrame {
                background-color: #FEF3C7;
                border: 1.5px solid #F59E0B;
                border-radius: 8px;
                padding: 12px;
            }
        """)
        banner_layout = QVBoxLayout(banner)
        banner_title = QLabel("⚠️ Duplicate Warning: Similar candidate records found", banner)
        banner_title.setStyleSheet("color: #92400E; font-weight: 800; font-size: 14px;")
        banner_desc = QLabel(
            "One or more records in the database share the same mobile number, email, or name+address.\n"
            "Please review the existing candidate(s) below to prevent accidental duplicate registrations.",
            banner
        )
        banner_desc.setStyleSheet("color: #78350F; font-size: 12px;")
        banner_desc.setWordWrap(True)

        banner_layout.addWidget(banner_title)
        banner_layout.addWidget(banner_desc)
        layout.addWidget(banner)

        # Table of matches
        self.table = QTableWidget(self)
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(["Candidate ID", "Full Name", "Mobile", "Village", "Match Reason"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        self.table.setRowCount(len(duplicates))
        for r_idx, d in enumerate(duplicates):
            self.table.setItem(r_idx, 0, QTableWidgetItem(d.get("candidate_id", "")))
            self.table.setItem(r_idx, 1, QTableWidgetItem(d.get("full_name", "")))
            self.table.setItem(r_idx, 2, QTableWidgetItem(d.get("mobile", "")))
            self.table.setItem(r_idx, 3, QTableWidgetItem(d.get("village", "")))
            self.table.setItem(r_idx, 4, QTableWidgetItem(", ".join(d.get("reasons", []))))

        layout.addWidget(self.table)

        # Buttons
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(12)

        self.btn_cancel = QPushButton("Cancel (Don't Save)", self)
        self.btn_cancel.setProperty("class", "SecondaryButton")
        self.btn_cancel.clicked.connect(self.reject)

        self.btn_review = QPushButton("🔍 Review Selected Existing", self)
        self.btn_review.setProperty("class", "SecondaryButton")
        self.btn_review.clicked.connect(self._on_review)

        self.btn_proceed = QPushButton("Continue Saving Anyway", self)
        self.btn_proceed.setStyleSheet("""
            QPushButton {
                background-color: #D97706;
                color: white;
                font-weight: 700;
                padding: 8px 18px;
                border-radius: 6px;
                border: none;
            }
            QPushButton:hover {
                background-color: #B45309;
            }
        """)
        self.btn_proceed.clicked.connect(self._on_proceed)

        btn_layout.addWidget(self.btn_cancel)
        btn_layout.addWidget(self.btn_review)
        btn_layout.addStretch()
        btn_layout.addWidget(self.btn_proceed)

        layout.addLayout(btn_layout)

    def _on_proceed(self):
        self.should_continue = True
        self.accept()

    def _on_review(self):
        selected = self.table.selectedItems()
        if selected:
            row = selected[0].row()
            self.selected_existing_id = self.table.item(row, 0).text()
        elif self.table.rowCount() > 0:
            self.selected_existing_id = self.table.item(0, 0).text()
        self.reject()
