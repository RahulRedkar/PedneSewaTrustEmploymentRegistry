"""
Global Qt Signal Bus for reactive cross-widget updates in PySide6.
Ensures loose coupling between UI views, background sync, and database mutations.
"""

from PySide6.QtCore import QObject, Signal


class AppSignals(QObject):
    """Event bus singleton transmitting notifications across application components."""

    # Candidate Data Events
    candidate_saved = Signal(str)      # candidate_id
    candidate_updated = Signal(str)    # candidate_id
    candidate_deleted = Signal(str)    # candidate_id

    # Sync Lifecycle Events
    sync_started = Signal()
    sync_status_changed = Signal(str, str) # status, display_message (e.g. "SYNCED", "Synced 2m ago")
    sync_progress = Signal(int, int)       # current, total
    sync_completed = Signal(dict)          # summary stats dict
    sync_failed = Signal(str)              # user-friendly error message

    # System & Database Events
    database_backed_up = Signal(str)       # backup_filepath
    database_restored = Signal()           # trigger full refresh
    settings_updated = Signal()            # trigger settings reload
    toast_requested = Signal(str, str)     # message, level ("info", "success", "warning", "error")


signals = AppSignals()
