"""
Database backup and restore manager for Pedne Sewa Trust - Employment Registry.
Provides:
- Automatic startup / daily rolling backups (retains last 30 snapshots)
- Manual user-triggered timestamped backups
- Safe atomic restoration with automatic pre-restore safety checkpoint
"""

import os
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional
from app.config import config
from database.connection import db_manager
from utils.logger import logger


class BackupManager:
    """Manages SQLite online backups, rotations, and safe restoration."""

    def __init__(self, backup_dir: Optional[str] = None):
        self.backup_dir = Path(backup_dir or config.get("backup_dir"))
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def create_backup(self, custom_dest_dir: Optional[str] = None, is_automatic: bool = False) -> str:
        """
        Creates an online atomic SQLite database backup using sqlite3.backup API.
        Safe to run even while database is actively being read.
        """
        target_dir = Path(custom_dest_dir) if custom_dest_dir else self.backup_dir
        target_dir.mkdir(parents=True, exist_ok=True)

        prefix = "pst_registry_auto" if is_automatic else "pst_registry_backup"
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_filename = f"{prefix}_{timestamp}.sqlite"
        backup_filepath = target_dir / backup_filename

        src_conn = db_manager.get_connection()
        try:
            # Checkpoint WAL to flush all transactions into primary database file
            src_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")

            dest_conn = sqlite3.connect(str(backup_filepath))
            with dest_conn:
                src_conn.backup(dest_conn, pages=100)
            dest_conn.close()

            logger.info("Successfully created database backup: %s", backup_filepath)

            if is_automatic:
                self.prune_automatic_backups()

            return str(backup_filepath)
        except Exception as e:
            logger.error("Failed to create database backup: %s", e)
            raise e
        finally:
            src_conn.close()

    def prune_automatic_backups(self, keep_count: int = 30):
        """
        Rotates automatic backups, preserving only the most recent keep_count.
        Never removes manual backups or the active operational database!
        """
        try:
            auto_backups = sorted(
                list(self.backup_dir.glob("pst_registry_auto_*.sqlite")),
                key=lambda p: p.stat().st_mtime,
                reverse=True
            )
            if len(auto_backups) > keep_count:
                to_delete = auto_backups[keep_count:]
                for f in to_delete:
                    try:
                        f.unlink()
                        logger.info("Pruned old automatic backup: %s", f.name)
                    except Exception as err:
                        logger.warning("Could not prune backup %s: %s", f.name, err)
        except Exception as e:
            logger.error("Error during automatic backup pruning: %s", e)

    def list_backups(self) -> List[dict]:
        """Returns sorted list of available backup files with size and timestamp."""
        backups = []
        if not self.backup_dir.exists():
            return backups

        for f in sorted(self.backup_dir.glob("*.sqlite"), key=lambda p: p.stat().st_mtime, reverse=True):
            stat = f.stat()
            backups.append({
                "filename": f.name,
                "filepath": str(f),
                "size_bytes": stat.st_size,
                "size_display": f"{stat.st_size / 1024:.1f} KB",
                "modified": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
                "is_auto": "auto" in f.name
            })
        return backups

    def restore_backup(self, backup_filepath: str) -> bool:
        """
        Safely restores database from backup:
        1. Validates backup file.
        2. Automatically creates pre-restore safety checkpoint of current database.
        3. Restores data using SQLite backup API.
        """
        b_path = Path(backup_filepath)
        if not b_path.exists() or not b_path.is_file():
            raise FileNotFoundError(f"Backup file not found: {backup_filepath}")

        # 1. Test opening backup
        test_conn = sqlite3.connect(str(b_path))
        try:
            cursor = test_conn.cursor()
            cursor.execute("SELECT count(*) FROM sqlite_master WHERE type='table' AND name='candidates'")
            if cursor.fetchone()[0] == 0:
                raise ValueError("Selected file is not a valid Pedne Sewa Trust database backup.")
        finally:
            test_conn.close()

        # 2. Safety checkpoint of current operational DB
        logger.info("Creating pre-restore safety snapshot before restore...")
        self.create_backup(is_automatic=False)

        # 3. Restore using online backup API from backup into operational DB
        src_conn = sqlite3.connect(str(b_path))
        dest_conn = db_manager.get_connection()
        try:
            with dest_conn:
                src_conn.backup(dest_conn, pages=100)
            dest_conn.execute("PRAGMA wal_checkpoint(TRUNCATE);")
            logger.info("Successfully restored database from: %s", backup_filepath)
            return True
        except Exception as e:
            logger.error("Failed to restore database from backup: %s", e)
            raise e
        finally:
            src_conn.close()
            dest_conn.close()


backup_manager = BackupManager()
