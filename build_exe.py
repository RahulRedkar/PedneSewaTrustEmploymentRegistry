"""
PyInstaller packaging build script for Pedne Sewa Trust - Employment Registry.
Packages the application into a standalone Windows executable.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path
from app.version import APP_VERSION, APP_NAME


def build_executable():
    root_dir = Path(__file__).resolve().parent
    icon_path = root_dir / "assets" / "icon.ico"
    logo_path = root_dir / "assets" / "logo.png"
    styles_path = root_dir / "assets" / "styles.qss"

    print("==================================================================")
    print(f"  Building {APP_NAME} v{APP_VERSION}")
    print("==================================================================")

    # PyInstaller arguments
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--onedir",  # Clean onedir build for fast startup and easy asset inspection
        "--windowed", # No black console window
        f"--name=PedneSewaTrustRegistry",
        f"--icon={icon_path}",
        # Assets
        f"--add-data={logo_path};assets",
        f"--add-data={icon_path};assets",
        f"--add-data={styles_path};assets",
        # Hidden imports
        "--hidden-import=app.version",
        "--hidden-import=requests",
        "--hidden-import=sync.apps_script_client",
        "--hidden-import=database.demo_data_generator",
        "--hidden-import=reportlab",
        "--hidden-import=reportlab.lib",
        "--hidden-import=reportlab.lib.pagesizes",
        "--hidden-import=reportlab.lib.colors",
        "--hidden-import=reportlab.platypus",
        "--hidden-import=reportlab.pdfgen",
        "--hidden-import=PySide6.QtCore",
        "--hidden-import=PySide6.QtGui",
        "--hidden-import=PySide6.QtWidgets",
        "--hidden-import=sqlite3",
        "--hidden-import=models.facilitation",
        "--hidden-import=models.candidate",
        "--hidden-import=models.visitor",
        "--hidden-import=export.importer",
        "--hidden-import=openpyxl",
        "--hidden-import=ui.views.visiting_register_view",
        "--hidden-import=ui.dialogs.log_visit_dialog",
        "--hidden-import=facilitation.job_adapters",
        "--hidden-import=facilitation.matching_engine",
        "--hidden-import=facilitation.recruiter_service",
        "--hidden-import=facilitation.document_manager",
        "--hidden-import=app.updater",
        # Entrypoint
        str(root_dir / "main.py")
    ]

    print(f"Running command: {' '.join(cmd)}")
    res = subprocess.run(cmd, cwd=str(root_dir))
    if res.returncode == 0:
        print("\n[SUCCESS] Build completed successfully!")
        dist_dir = root_dir / "dist" / "PedneSewaTrustRegistry"
        exe_path = dist_dir / "PedneSewaTrustRegistry.exe"
        # Ensure assets folder exists directly adjacent to the EXE as well
        dist_assets = dist_dir / "assets"
        dist_assets.mkdir(parents=True, exist_ok=True)
        for item in ["icon.ico", "logo.png", "styles.qss"]:
            src = root_dir / "assets" / item
            if src.exists():
                shutil.copy2(src, dist_assets / item)
                print(f"Copied {item} to {dist_assets / item}")
        print(f"Standalone executable located at:\n{exe_path}")
    else:
        print(f"\n[ERROR] Build failed with exit code {res.returncode}")
        sys.exit(res.returncode)


if __name__ == "__main__":
    build_executable()
