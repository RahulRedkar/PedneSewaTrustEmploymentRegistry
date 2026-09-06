"""
On-Demand CSV Export utility for Pedne Sewa Trust - Employment Registry.
Generates RFC 4180 compliant UTF-8 CSV files with full escaping for commas,
quotes, linebreaks, and Indian Unicode names/addresses.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from app.constants import GOOGLE_SHEETS_COLUMNS, SYNC_STATUS_PENDING, SYNC_STATUS_FAILED
from app.config import config
from database.repository import repository
from models.candidate import Candidate
from utils.logger import logger


class CSVExporter:
    """Handles on-demand exports of candidate datasets to UTF-8 CSV."""

    def __init__(self, export_dir: Optional[str] = None):
        self.export_dir = Path(export_dir or config.get("export_dir"))
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_candidates(
        self,
        candidates: List[Candidate],
        target_filepath: Optional[str] = None,
        export_label: str = "candidates"
    ) -> str:
        """
        Exports a given list of candidates to a clean UTF-8 CSV file.
        Uses utf-8-sig (with BOM) so Microsoft Excel on Windows opens Indian characters cleanly!
        """
        if not target_filepath:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"PST_{export_label}_{timestamp}.csv"
            target_filepath = str(self.export_dir / filename)

        try:
            with open(target_filepath, mode="w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f, quoting=csv.QUOTE_MINIMAL)
                # Write 42 canonical column headers
                writer.writerow(GOOGLE_SHEETS_COLUMNS)

                for cand in candidates:
                    writer.writerow(cand.to_row_list())

            logger.info("Successfully exported %d candidates to %s", len(candidates), target_filepath)
            return target_filepath
        except Exception as e:
            logger.error("Failed to export candidates to CSV: %s", e)
            raise e

    def export_all(self, target_filepath: Optional[str] = None) -> str:
        """Exports all active candidates in local SQLite database."""
        candidates = repository.get_all_candidates(include_deleted=False)
        return self.export_candidates(candidates, target_filepath, export_label="all")

    def export_pending(self, target_filepath: Optional[str] = None) -> str:
        """Exports all candidates that have pending or failed cloud sync."""
        candidates = repository.get_pending_sync_candidates()
        return self.export_candidates(candidates, target_filepath, export_label="pending_sync")

    def export_filtered(self, candidates: List[Candidate], target_filepath: Optional[str] = None) -> str:
        """Exports the currently filtered candidate list from UI."""
        return self.export_candidates(candidates, target_filepath, export_label="filtered")


csv_exporter = CSVExporter()
