"""
CSV exporter specifically formatted for analytical and demographic report tables.
"""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any, Optional
from app.config import config
from utils.logger import logger


class ReportCSVExporter:
    """Exports structured report tables into readable CSV files."""

    def __init__(self, export_dir: Optional[str] = None):
        self.export_dir = Path(export_dir or config.get("export_dir") or (config.app_data_dir / "exports"))
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_report_table(
        self,
        report_title: str,
        headers: List[str],
        rows: List[List[Any]],
        target_filepath: Optional[str] = None
    ) -> str:
        """Exports report matrix with title header and UTF-8 BOM encoding."""
        if not target_filepath:
            clean_title = "".join(c for c in report_title if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            target_filepath = str(self.export_dir / f"Report_{clean_title}_{ts}.csv")

        try:
            with open(target_filepath, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow([report_title])
                writer.writerow([f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
                writer.writerow([])
                writer.writerow(headers)
                for r in rows:
                    writer.writerow(r)

            logger.info("Exported report table to %s", target_filepath)
            return target_filepath
        except Exception as e:
            logger.error("Failed to export report CSV: %s", e)
            raise e


report_csv_exporter = ReportCSVExporter()
