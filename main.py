"""
Entry point for Pedne Sewa Trust — Employment & Candidate Registry.
Production-ready Windows Desktop Application using PySide6 and SQLite.
"""

import sys
import os
from pathlib import Path
from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon

from app.config import config
from app.version import APP_VERSION, APP_NAME, APP_ORGANISATION
from database.connection import db_manager
from database.schema import init_database
from ui.main_window import MainWindow
from utils.logger import logger


def load_stylesheet(app: QApplication):
    """Loads and applies the application stylesheet from assets."""
    style_path = config.base_dir / "assets" / "styles.qss"
    if style_path.exists():
        try:
            with open(style_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.info("Application stylesheet loaded successfully.")
        except Exception as e:
            logger.warning("Could not apply stylesheet: %s", e)


def exception_hook(exctype, value, traceback_obj):
    """Global uncaught exception handler to prevent silent crashes."""
    import traceback
    err_str = "".join(traceback.format_exception(exctype, value, traceback_obj))
    logger.critical("Uncaught exception:\n%s", err_str)
    # Output to standard stderr
    sys.__excepthook__(exctype, value, traceback_obj)


def get_app_icon() -> QIcon:
    """
    Finds and returns the best multi-resolution Windows application icon.
    Checks frozen executable directory, PyInstaller bundle (_MEIPASS),
    and development root.
    """
    candidate_paths = []

    # 1. Next to running executable (production frozen EXE)
    exe_dir = Path(sys.executable).resolve().parent
    candidate_paths.append(exe_dir / "assets" / "icon.ico")
    candidate_paths.append(exe_dir / "icon.ico")
    candidate_paths.append(exe_dir / "assets" / "logo.png")

    # 2. Inside PyInstaller bundle (_MEIPASS)
    if hasattr(sys, "_MEIPASS"):
        meipass_dir = Path(sys._MEIPASS)
        candidate_paths.append(meipass_dir / "assets" / "icon.ico")
        candidate_paths.append(meipass_dir / "assets" / "logo.png")

    # 3. Project root / config base_dir (development & installed)
    base_dir = Path(__file__).resolve().parent
    candidate_paths.append(base_dir / "assets" / "icon.ico")
    candidate_paths.append(base_dir / "assets" / "logo.png")
    candidate_paths.append(config.base_dir / "assets" / "icon.ico")
    candidate_paths.append(config.base_dir / "assets" / "logo.png")

    for path in candidate_paths:
        if path.exists() and os.path.isfile(path):
            icon = QIcon(str(path))
            if not icon.isNull():
                return icon

    # Fallback to resolve_logo_path
    logo = config.resolve_logo_path()
    if logo and os.path.exists(logo):
        return QIcon(logo)

    return QIcon()


def main():
    # Set exception hook
    sys.excepthook = exception_hook

    # Ensure Windows taskbar displays the Trust logo instead of generic python icon
    if sys.platform == "win32":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(f"PedneSewaTrust.EmploymentRegistry.{APP_VERSION}")
        except Exception as e:
            logger.warning("Could not set Windows AppUserModelID: %s", e)

    # Qt Application setup
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANISATION)

    # Set App Icon (Multi-resolution Windows ICO containing 16, 24, 32, 48, 64, 128, 256px)
    app_icon = get_app_icon()
    if not app_icon.isNull():
        app.setWindowIcon(app_icon)

    # Set Fusion style and force crisp Light Palette (prevents Windows Dark Mode leaking dark artifacts)
    app.setStyle("Fusion")
    from PySide6.QtGui import QPalette, QColor
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor("#F8FAFC"))
    palette.setColor(QPalette.WindowText, QColor("#0F172A"))
    palette.setColor(QPalette.Base, QColor("#FFFFFF"))
    palette.setColor(QPalette.AlternateBase, QColor("#F1F5F9"))
    palette.setColor(QPalette.ToolTipBase, QColor("#FFFFFF"))
    palette.setColor(QPalette.ToolTipText, QColor("#0F172A"))
    palette.setColor(QPalette.Text, QColor("#0F172A"))
    palette.setColor(QPalette.Button, QColor("#FFFFFF"))
    palette.setColor(QPalette.ButtonText, QColor("#0F172A"))
    palette.setColor(QPalette.BrightText, QColor("#DC2626"))
    palette.setColor(QPalette.Link, QColor("#15803D"))
    palette.setColor(QPalette.Highlight, QColor("#15803D"))
    palette.setColor(QPalette.HighlightedText, QColor("#FFFFFF"))
    app.setPalette(palette)

    # Apply styling
    load_stylesheet(app)

    # Initialize SQLite database
    try:
        with db_manager.get_connection() as conn:
            init_database(conn)
    except Exception as e:
        logger.critical("Failed to initialize database schema: %s", e)
        QMessageBox.critical(None, "Database Error", f"Fatal: Could not initialize local SQLite database:\n{e}")
        return 1

    # Launch Main Window
    window = MainWindow()
    window.show()

    logger.info("Pedne Sewa Trust desktop application launched successfully.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
