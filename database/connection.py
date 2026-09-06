"""
SQLite database connection factory with WAL mode for Pedne Sewa Trust.
Ensures thread-safe reads/writes, transactional atomicity, and robust data integrity.
"""

import sqlite3
import os
from contextlib import contextmanager
from pathlib import Path
from typing import Generator
from app.config import config
from utils.logger import logger


class DatabaseManager:
    """Manages SQLite database connections, WAL mode configuration, and transactions."""

    def __init__(self, db_path: str = None):
        self.db_path = db_path or config.get("database_path")
        self._ensure_dir()
        self._init_pragmas()

    def _ensure_dir(self):
        parent = Path(self.db_path).parent
        parent.mkdir(parents=True, exist_ok=True)

    def get_connection(self) -> sqlite3.Connection:
        """Returns a new SQLite connection configured with WAL mode and row factory."""
        conn = sqlite3.connect(self.db_path, timeout=10.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA synchronous = NORMAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        return conn

    def _init_pragmas(self):
        try:
            with self.get_connection() as conn:
                conn.execute("PRAGMA journal_mode = WAL;")
        except Exception as e:
            logger.warning("Could not set initial WAL pragma: %s", e)

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Transactional context manager. Automatically commits on success or rolls back on error."""
        conn = self.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE TRANSACTION;")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error("Transaction rolled back due to error: %s", e)
            raise e
        finally:
            conn.close()


db_manager = DatabaseManager()
