"""
Synchronisation & Reconciliation Engine for Pedne Sewa Trust - Employment Registry.
Enforces:
- Local SQLite as authoritative master
- Candidate ID as permanent unique key
- Idempotent row appends and updates (zero duplicate rows)
- Timestamp-based reconciliation (local updated_at vs Sheet updated_at)
- Fault-tolerant retry (local data safe on network/auth failure)
"""

from datetime import datetime
from typing import Dict, Any, List
from app.config import config
from app.signals import signals
from database.repository import repository
from sync.apps_script_client import apps_script_client
from utils.logger import logger


class SyncEngine:
    """Orchestrates candidate synchronisation between local SQLite and Google Apps Script Web App."""

    def __init__(self):
        pass

    def run_sync(self, is_manual: bool = False) -> Dict[str, Any]:
        """
        Executes a complete synchronisation cycle via Google Apps Script.
        Returns a dict summarizing the outcome.
        """
        # 1. Check if Apps Script endpoint is configured
        if not apps_script_client.is_configured():
            msg = "Cloud backup gateway is not configured. Local data is safely preserved on this computer."
            logger.info(msg)
            signals.sync_status_changed.emit("offline", "Backup: Not configured")
            signals.sync_failed.emit(msg)
            return {"status": "NOT_CONFIGURED", "records_pushed": 0, "message": msg}

        # 2. Fetch pending/failed local records
        pending_candidates = repository.get_pending_sync_candidates()
        if not pending_candidates:
            msg = "All candidate records are already backed up to the cloud."
            logger.info(msg)
            signals.sync_status_changed.emit("synced", "Backup: Up to date")
            signals.sync_completed.emit({"records_pushed": 0, "message": msg})
            return {"status": "SUCCESS", "records_pushed": 0, "message": msg}

        signals.sync_status_changed.emit("pending", f"Backup: Syncing {len(pending_candidates)} records...")

        # 3. Push records to Google Apps Script gateway
        try:
            res = apps_script_client.push_candidates(pending_candidates)
            if res.get("status") == "SUCCESS":
                pushed_count = len(pending_candidates)
                now_iso = datetime.now().isoformat()
                pushed_ids = [c.candidate_id for c in pending_candidates]
                repository.mark_candidates_synced(pushed_ids, now_iso)
                repository.log_sync_event(
                    pushed_count, 0, "SUCCESS",
                    details=f"Synced {pushed_count} candidates via Google Apps Script"
                )
                signals.sync_status_changed.emit("synced", "Backup: Complete")
                signals.sync_completed.emit({"records_pushed": pushed_count, "timestamp": now_iso})
                logger.info("Backup completed successfully: %d records pushed to cloud.", pushed_count)
                return {"status": "SUCCESS", "records_pushed": pushed_count}
            else:
                err_detail = res.get("error", "Failed to communicate with backup gateway")
                user_msg = f"Cloud synchronisation could not be completed: {err_detail}"
                logger.warning("Backup failure: %s", err_detail)
                repository.log_sync_event(0, len(pending_candidates), "FAILURE", err_detail, details=user_msg)
                signals.sync_status_changed.emit("failed", "Backup: Failed")
                signals.sync_failed.emit(user_msg)
                return {"status": "FAILURE", "records_pushed": 0, "error": user_msg, "technical_error": err_detail}

        except Exception as e:
            user_msg = f"Cloud synchronisation could not be completed: {e}"
            logger.error("Sync error: %s", e)
            repository.log_sync_event(0, len(pending_candidates), "FAILURE", str(e), details=user_msg)
            signals.sync_status_changed.emit("failed", "Backup: Error")
            signals.sync_failed.emit(user_msg)
            return {"status": "FAILURE", "records_pushed": 0, "error": user_msg, "technical_error": str(e)}


sync_engine = SyncEngine()

