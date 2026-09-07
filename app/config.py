"""
Configuration manager for Pedne Sewa Trust - Employment Registry.
Persists configuration in JSON file in User AppData or local project directory.
"""

import json
import os
import sys
from pathlib import Path
from typing import Any, Dict
from app.constants import (
    APP_ORGANISATION,
    DEFAULT_SPREADSHEET_ID,
    DEFAULT_WORKSHEET_NAME,
    DEFAULT_SYNC_INTERVAL_MINUTES,
    DEFAULT_APPS_SCRIPT_URL,
    OFFICE_PERNEM
)
from app.version import GITHUB_REPO_SLUG
from utils.logger import logger


class AppConfig:
    """Singleton application configuration manager."""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(AppConfig, cls).__new__(cls)
            cls._instance._init()
        return cls._instance

    def _init(self):
        # Base application directory in user home / local
        self.base_dir = Path(__file__).resolve().parent.parent
        self.app_data_dir = Path(os.path.expanduser("~")) / ".pedne_sewa_trust"
        self.app_data_dir.mkdir(parents=True, exist_ok=True)
        self.config_path = self.app_data_dir / "config.json"

        # Default directories
        self.default_db_path = self.app_data_dir / "pst_registry.db"
        self.default_backup_dir = self.app_data_dir / "backups"
        self.default_backup_dir.mkdir(parents=True, exist_ok=True)
        self.default_export_dir = self.app_data_dir / "exports"
        self.default_export_dir.mkdir(parents=True, exist_ok=True)

        self._data = self._get_defaults()
        self.load()

    def _get_defaults(self) -> Dict[str, Any]:
        return {
            "organisation_name": APP_ORGANISATION,
            "custom_logo_path": "",
            "spreadsheet_id": DEFAULT_SPREADSHEET_ID,
            "worksheet_name": DEFAULT_WORKSHEET_NAME,
            "sync_interval_minutes": DEFAULT_SYNC_INTERVAL_MINUTES,
            "apps_script_url": DEFAULT_APPS_SCRIPT_URL,
            "backup_api_key": "",
            "github_update_token": "",
            "github_repo": GITHUB_REPO_SLUG,
            "database_path": str(self.default_db_path),
            "backup_dir": str(self.default_backup_dir),
            "export_dir": str(self.default_export_dir),
            "backup_retention_days": 30,
            "default_office": OFFICE_PERNEM,
            "first_run_completed": False
        }

    def load(self):
        """Loads configuration from JSON file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    self._data.update(saved)
                logger.info("Configuration loaded from %s", self.config_path)
            except Exception as e:
                logger.error("Error loading config, using defaults: %s", e)
        else:
            self.save()

    def save(self):
        """Saves current configuration to JSON file."""
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2)
            logger.info("Configuration saved to %s", self.config_path)
        except Exception as e:
            logger.error("Error saving config: %s", e)

    def get(self, key: str, default: Any = None) -> Any:
        # Precedence 1: Environment Variables
        if key == "apps_script_url" and os.environ.get("GOOGLE_APPS_SCRIPT_URL"):
            return os.environ.get("GOOGLE_APPS_SCRIPT_URL").strip()
        if key in ("backup_api_key", "api_key") and os.environ.get("BACKUP_API_KEY"):
            return os.environ.get("BACKUP_API_KEY").strip()
        if key in ("github_update_token", "github_token") and os.environ.get("GITHUB_UPDATE_TOKEN"):
            return os.environ.get("GITHUB_UPDATE_TOKEN").strip()

        # Precedence 2: Local config.json, Precedence 3: Application defaults
        return self._data.get(key, default)

    def set(self, key: str, value: Any):
        self._data[key] = value
        self.save()

    def resolve_logo_path(self) -> str:
        """
        Dynamically finds the best available logo:
        1. Custom configured logo path
        2. Image in the workspace root directory (e.g. logo.png, logo.jpg)
        3. Bundled asset in /assets/logo.png
        """
        # 1. Check custom path if configured
        custom = self.get("custom_logo_path", "")
        if custom and os.path.exists(custom):
            return custom

        # 2. Check workspace root folder for any logo file
        root = self.base_dir
        for ext in ("png", "jpg", "jpeg", "svg", "ico"):
            for candidate_name in ("logo", "pst_logo", "pedne_sewa_trust_logo", "icon"):
                cand = root / f"{candidate_name}.{ext}"
                if cand.exists():
                    return str(cand)

        # Also scan root directly for any .png or .jpg with 'logo' in name
        try:
            for item in root.glob("*.*"):
                if item.is_file() and item.suffix.lower() in (".png", ".jpg", ".jpeg", ".svg", ".ico"):
                    if "logo" in item.stem.lower() or "pedne" in item.stem.lower() or "pst" in item.stem.lower():
                        return str(item)
        except Exception:
            pass

        # 3. Fallback to bundled asset
        bundled = root / "assets" / "logo.png"
        if bundled.exists():
            return str(bundled)

        return ""


config = AppConfig()
