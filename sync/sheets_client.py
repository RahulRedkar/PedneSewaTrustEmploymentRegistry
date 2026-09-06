"""
Google Sheets API v4 client for Pedne Sewa Trust - Employment Registry.
Implements batch queries, worksheet verification, header initialization,
and row index mapping.
"""

from typing import List, Dict, Any, Tuple, Optional
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from app.constants import GOOGLE_SHEETS_COLUMNS
from sync.oauth_manager import oauth_manager
from utils.logger import logger


class GoogleSheetsClient:
    """Encapsulates official Google Sheets API v4 operations."""

    def __init__(self):
        self._service = None

    def get_service(self):
        """Returns authenticated Google Sheets API service resource."""
        creds = oauth_manager.get_credentials()
        if not creds:
            raise PermissionError("Google Account is not authorized. Please connect via Settings.")
        if not self._service or not creds.valid:
            self._service = build("sheets", "v4", credentials=creds, cache_discovery=False)
        return self._service

    def ensure_worksheet_and_headers(self, spreadsheet_id: str, worksheet_name: str):
        """
        Verifies the target spreadsheet and worksheet tab exist.
        Creates the tab and writes the 42-column canonical header if missing.
        """
        service = self.get_service()
        # 1. Fetch spreadsheet metadata to check if tab exists
        meta = service.spreadsheets().get(spreadsheetId=spreadsheet_id).execute()
        sheets = meta.get("sheets", [])
        tab_names = [s.get("properties", {}).get("title") for s in sheets]

        if worksheet_name not in tab_names:
            logger.info("Worksheet tab '%s' not found, creating...", worksheet_name)
            req = {
                "addSheet": {
                    "properties": {
                        "title": worksheet_name,
                        "gridProperties": {
                            "rowCount": 1000,
                            "columnCount": len(GOOGLE_SHEETS_COLUMNS) + 2
                        }
                    }
                }
            }
            service.spreadsheets().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body={"requests": [req]}
            ).execute()

        # 2. Check if row 1 contains headers
        header_range = f"{worksheet_name}!A1:AP1"
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=header_range
        ).execute()
        rows = res.get("values", [])

        if not rows or len(rows[0]) == 0:
            logger.info("Initializing 42 canonical headers on worksheet '%s'...", worksheet_name)
            service.spreadsheets().values().update(
                spreadsheetId=spreadsheet_id,
                range=header_range,
                valueInputOption="USER_ENTERED",
                body={"values": [GOOGLE_SHEETS_COLUMNS]}
            ).execute()

    def fetch_candidate_index(self, spreadsheet_id: str, worksheet_name: str) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
        """
        Reads existing sheet rows to build an index mapping:
        candidate_id -> {"row": row_number, "sheet_updated_at": timestamp}
        Also detects and flags any existing duplicate Candidate IDs found in the Sheet.
        """
        service = self.get_service()
        # Fetch Column A (Candidate ID) and Column AO (Updated At, 41st col)
        # Fetching A to AO so we have all columns safely
        sheet_range = f"{worksheet_name}!A:AO"
        res = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=sheet_range
        ).execute()

        rows = res.get("values", [])
        index_map: Dict[str, Dict[str, Any]] = {}
        duplicates_in_sheet: List[str] = []

        # Row 1 is header, data starts at row 2 (1-based index)
        for row_idx, row in enumerate(rows[1:], start=2):
            if not row:
                continue
            cid = str(row[0]).strip() if len(row) > 0 else ""
            if not cid:
                continue

            updated_at = ""
            if len(row) >= 41:
                updated_at = str(row[40]).strip()

            if cid in index_map:
                duplicates_in_sheet.append(cid)
                logger.warning("Duplicate Candidate ID '%s' found in Google Sheet at row %d!", cid, row_idx)
            else:
                index_map[cid] = {
                    "row": row_idx,
                    "sheet_updated_at": updated_at
                }

        return index_map, duplicates_in_sheet

    def append_rows(self, spreadsheet_id: str, worksheet_name: str, rows: List[List[Any]]) -> int:
        """Appends new candidate rows to the bottom of the worksheet."""
        if not rows:
            return 0
        service = self.get_service()
        append_range = f"{worksheet_name}!A1"
        res = service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=append_range,
            valueInputOption="USER_ENTERED",
            insertDataOption="INSERT_ROWS",
            body={"values": rows}
        ).execute()
        updated_rows = res.get("updates", {}).get("updatedRows", len(rows))
        return updated_rows

    def batch_update_rows(self, spreadsheet_id: str, worksheet_name: str, updates: List[Tuple[int, List[Any]]]) -> int:
        """
        Batch updates existing rows using spreadsheets.values.batchUpdate.
        updates: list of (row_number, row_values)
        """
        if not updates:
            return 0
        service = self.get_service()
        data = []
        for row_num, row_vals in updates:
            data.append({
                "range": f"{worksheet_name}!A{row_num}:AP{row_num}",
                "values": [row_vals]
            })

        body = {
            "valueInputOption": "USER_ENTERED",
            "data": data
        }
        res = service.spreadsheets().values().batchUpdate(
            spreadsheetId=spreadsheet_id,
            body=body
        ).execute()
        return len(data)


sheets_client = GoogleSheetsClient()
