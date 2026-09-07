"""
VisitorRecord domain model for Pedne Sewa Trust - Visiting Register.
Represents candidate / visitor walk-in records with auto-assigned sequential Sr No,
date, time, contact information, and visit purpose.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
import sqlite3


@dataclass
class VisitorRecord:
    """Represents an individual entry in the Visiting Register."""

    id: Optional[int] = None
    sr_no: int = 0
    visit_date: str = field(default_factory=lambda: datetime.now().strftime("%Y-%m-%d"))
    visit_time: str = field(default_factory=lambda: datetime.now().strftime("%I:%M %p"))
    candidate_name: str = ""
    village: str = ""
    mobile: str = ""
    purpose: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    sync_status: str = "PENDING"
    last_synced_at: Optional[str] = None
    is_deleted: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Converts record to dictionary for SQLite persistence and serialization."""
        return {
            "id": self.id,
            "sr_no": self.sr_no,
            "visit_date": self.visit_date,
            "visit_time": self.visit_time,
            "candidate_name": self.candidate_name,
            "village": self.village,
            "mobile": self.mobile,
            "purpose": self.purpose,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "sync_status": self.sync_status,
            "last_synced_at": self.last_synced_at,
            "is_deleted": self.is_deleted,
        }

    def to_backup_dict(self) -> Dict[str, Any]:
        """
        Converts record to flat dictionary for Google Apps Script cloud backup.
        Matches the columns of the 'Visiting Register' Google Sheet.
        """
        return {
            "sr_no": self.sr_no,
            "visit_date": self.visit_date,
            "visit_time": self.visit_time,
            "candidate_name": self.candidate_name,
            "village": self.village,
            "mobile": self.mobile,
            "purpose": self.purpose,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def to_row_list(self) -> List[str]:
        """Returns row list aligned with export and table display columns."""
        return [
            str(self.sr_no),
            self.visit_date,
            self.visit_time,
            self.candidate_name,
            self.village,
            self.mobile,
            self.purpose,
            self.created_at,
            self.updated_at,
        ]

    @classmethod
    def from_row(cls, row: Any) -> "VisitorRecord":
        """Builds a VisitorRecord from a SQLite row or mapping."""
        keys = row.keys() if hasattr(row, "keys") else []
        return cls(
            id=row["id"] if "id" in keys else None,
            sr_no=int(row["sr_no"]) if row["sr_no"] is not None else 0,
            visit_date=row["visit_date"] or "",
            visit_time=row["visit_time"] or "",
            candidate_name=row["candidate_name"] or "",
            village=row["village"] or "",
            mobile=row["mobile"] or "",
            purpose=row["purpose"] or "",
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"] or "",
            sync_status=row["sync_status"] or "PENDING",
            last_synced_at=row["last_synced_at"],
            is_deleted=int(row["is_deleted"]) if row["is_deleted"] is not None else 0,
        )
