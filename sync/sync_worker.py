"""
Background QThread worker for periodic and on-demand Google Sheets synchronisation.
Ensures zero GUI blocking and handles timer scheduling.
"""

from typing import Optional
from PySide6.QtCore import QThread, QTimer, Signal, QObject
from app.config import config
from sync.sync_engine import sync_engine
from utils.logger import logger


class SyncTaskThread(QThread):
    """Worker thread running a single sync execution cycle."""

    finished_signal = Signal(dict)

    def __init__(self, is_manual: bool = False):
        super().__init__()
        self.is_manual = is_manual

    def run(self):
        try:
            res = sync_engine.run_sync(is_manual=self.is_manual)
            self.finished_signal.emit(res)
        except Exception as e:
            logger.error("Error in sync worker thread: %s", e)
            from app.signals import signals
            signals.sync_failed.emit(str(e))
            self.finished_signal.emit({"status": "FAILURE", "error": str(e)})


class BackgroundSyncManager(QObject):
    """Manages periodic 10-minute sync timers and manual sync invocations."""

    def __init__(self):
        super().__init__()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.trigger_background_sync)
        self._active_thread: Optional[SyncTaskThread] = None

    def start(self):
        """Starts periodic sync timer based on configured interval."""
        minutes = config.get("sync_interval_minutes", 10)
        ms = max(1, minutes) * 60 * 1000
        self.timer.start(ms)
        logger.info("Background sync timer started (interval: %d minutes)", minutes)

    def stop(self):
        """Stops periodic sync timer."""
        self.timer.stop()
        logger.info("Background sync timer stopped.")

    def trigger_background_sync(self):
        """Timer callback triggering non-blocking sync."""
        self.sync_now(is_manual=False)

    def sync_now(self, is_manual: bool = True):
        """Triggers an immediate sync cycle in background thread."""
        if self._active_thread and self._active_thread.isRunning():
            logger.info("Sync already in progress, skipping duplicate trigger.")
            return

        self._active_thread = SyncTaskThread(is_manual=is_manual)
        self._active_thread.finished_signal.connect(self._on_sync_finished)
        self._active_thread.start()

    def _on_sync_finished(self, result: dict):
        logger.info("Sync worker finished with result: %s", result.get("status"))


sync_worker = BackgroundSyncManager()
