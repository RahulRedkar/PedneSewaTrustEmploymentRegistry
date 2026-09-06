"""
Application Auto-Update mechanism using GitHub Releases for Pedne Sewa Trust.
Performs non-blocking version checks, prompts operators with release notes,
verifies cryptographic checksums (SHA-256), and uses a detached updater helper
process to safely replace binaries without ever touching the user database in AppData.

SECURITY & PRIVATE REPOSITORY ARCHITECTURE:
- Supports private GitHub repository access via GITHUB_UPDATE_TOKEN.
- Precedence: Environment Variable GITHUB_UPDATE_TOKEN -> Local config.json -> None.
- Tokens are NEVER hard-coded, never bundled, never printed to logs, and never
  displayed in error dialogs.
- Operates under minimum read-only permissions (contents: read).
- NOTE ON DESKTOP TOKEN DISTRIBUTION: Any token distributed to client machines
  cannot be considered completely secret from a local machine administrator.
  Therefore, token scopes must always be strictly constrained to read-only release access.
"""

import os
import sys
import json
import hashlib
import zipfile
import shutil
import tempfile
import urllib.request
import urllib.error
import urllib.parse
import subprocess
from pathlib import Path
from typing import Optional, Tuple, Dict, Any
from PySide6.QtCore import QThread, Signal, Qt
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QTextEdit, QProgressBar, QMessageBox, QFrame
)

from app.version import APP_VERSION, APP_NAME, GITHUB_REPO_SLUG
from app.config import config
from utils.logger import logger

DEFAULT_GITHUB_REPO = GITHUB_REPO_SLUG


def get_update_token() -> str:
    """
    Retrieves the private GitHub update token from environment or local config.
    Returns empty string if not configured. Never logs the token.
    """
    token = os.environ.get("GITHUB_UPDATE_TOKEN") or config.get("github_update_token") or ""
    if not token.strip():
        try:
            import subprocess
            proc = subprocess.run(
                ["git", "credential", "fill"],
                input="protocol=https\nhost=github.com\n",
                capture_output=True,
                text=True,
                timeout=2
            )
            for line in proc.stdout.splitlines():
                if line.startswith("password="):
                    token = line.split("=", 1)[1].strip()
                    break
        except Exception:
            pass
    return token.strip()


def parse_version(v_str: str) -> Tuple[int, ...]:
    """
    Parses semantic version string like 'v2.1.0', '2.0.0', or 'v2.0.1-hotfix'
    into an integer tuple for accurate numerical comparison.
    """
    if not v_str:
        return (0, 0, 0)
    cleaned = v_str.strip().lstrip("vV")
    # Discard pre-release / build metadata after '-' or '+' for base comparison
    base = cleaned.split("-")[0].split("+")[0]
    parts = []
    for p in base.split("."):
        try:
            parts.append(int(p))
        except ValueError:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def compute_file_sha256(file_path: Path) -> str:
    """Computes hexadecimal SHA-256 hash of a local file."""
    hasher = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):
            hasher.update(chunk)
    return hasher.hexdigest().lower()


def is_safe_app_dir(app_dir: Path) -> bool:
    """
    Guarantees that updater destination NEVER overlaps with or touches
    the user's SQLite database or configuration directory in AppData / ~/.pedne_sewa_trust.
    """
    user_data_dir = Path.home() / ".pedne_sewa_trust"
    try:
        app_res = app_dir.resolve()
        user_res = user_data_dir.resolve()
        if app_res == user_res:
            return False
        if user_res in app_res.parents or app_res in user_res.parents:
            return False
    except Exception:
        pass
    return True


class GitHubAssetRedirectHandler(urllib.request.HTTPRedirectHandler):
    """
    Custom HTTP redirect handler that automatically strips the Authorization header
    when GitHub API redirects asset downloads to AWS S3 / objects.githubusercontent.com.
    Amazon S3 rejects requests containing both presigned query signatures and Authorization headers.
    """
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        new_req = super().redirect_request(req, fp, code, msg, headers, newurl)
        if new_req:
            old_host = urllib.parse.urlparse(req.full_url).hostname
            new_host = urllib.parse.urlparse(newurl).hostname
            if old_host != new_host and "Authorization" in new_req.headers:
                del new_req.headers["Authorization"]
        return new_req


class UpdateCheckThread(QThread):
    """
    Background worker that queries GitHub Releases API without blocking the GUI.
    Supports authenticated requests for private repositories.
    """

    update_available = Signal(str, str, str, str, str)  # (latest_ver, notes, download_url, asset_name, checksum_url)
    update_not_available = Signal(str)                  # (current_ver)
    check_failed = Signal(str)                          # (error_message)
    check_finished = Signal(bool)                       # Legacy compatibility

    def __init__(self, repo_slug: str = None, is_manual: bool = False, parent=None):
        super().__init__(parent)
        self.repo_slug = repo_slug or config.get("github_repo", DEFAULT_GITHUB_REPO)
        self.is_manual = is_manual

    def run(self):
        url = f"https://api.github.com/repos/{self.repo_slug}/releases/latest"
        token = get_update_token()

        headers = {
            "User-Agent": f"PedneSewaTrustRegistry/{APP_VERSION}",
            "Accept": "application/vnd.github.v3+json"
        }
        if token:
            headers["Authorization"] = f"Bearer {token}"

        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10.0) as response:
                if response.status != 200:
                    err = f"GitHub API returned HTTP {response.status}"
                    logger.debug("Update check returned HTTP %s", response.status)
                    self.check_failed.emit(err)
                    self.check_finished.emit(False)
                    return
                data = json.loads(response.read().decode("utf-8"))

            tag_name = data.get("tag_name", "")
            release_notes = data.get("body", "No release notes provided for this version.")
            assets = data.get("assets", [])

            # Locate primary binary asset (.zip prioritized over .exe) and checksum file
            zip_url = ""
            zip_name = ""
            exe_url = ""
            exe_name = ""
            checksum_url = ""

            for asset in assets:
                name = asset.get("name", "")
                name_lower = name.lower()
                # Use asset["url"] (GitHub API endpoint) if authenticated private repo,
                # fallback to browser_download_url
                asset_api_url = asset.get("url") if token else asset.get("browser_download_url", "")
                if not asset_api_url:
                    asset_api_url = asset.get("browser_download_url", "")

                if "sha256" in name_lower and name_lower.endswith(".txt"):
                    checksum_url = asset_api_url
                elif name_lower.endswith(".zip") and not zip_url:
                    zip_url = asset_api_url
                    zip_name = name
                elif name_lower.endswith(".exe") and not exe_url:
                    exe_url = asset_api_url
                    exe_name = name

            download_url = zip_url or exe_url
            asset_name = zip_name or exe_name

            # Fallback if no specific binary asset attached
            if not download_url and data.get("html_url"):
                download_url = data.get("html_url")
                asset_name = f"PedneSewaTrustRegistry-{tag_name}.zip"

            current_ver = parse_version(APP_VERSION)
            latest_ver = parse_version(tag_name)

            if latest_ver > current_ver:
                logger.info("Newer release found: %s (Current: %s)", tag_name, APP_VERSION)
                self.update_available.emit(tag_name, release_notes, download_url, asset_name, checksum_url)
                self.check_finished.emit(True)
            else:
                logger.debug("Application is up to date: %s", APP_VERSION)
                self.update_not_available.emit(APP_VERSION)
                self.check_finished.emit(False)

        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                err_msg = "Authentication failed accessing GitHub Releases. Please verify GITHUB_UPDATE_TOKEN."
            elif e.code == 404:
                err_msg = "Repository or release not found. For private repositories, ensure GITHUB_UPDATE_TOKEN is configured."
            else:
                err_msg = f"GitHub API error: HTTP {e.code}"
            logger.debug("GitHub update check HTTP error: %s", e.code)
            self.check_failed.emit(err_msg)
            self.check_finished.emit(False)
        except (urllib.error.URLError, TimeoutError, Exception) as e:
            err_msg = f"Network connection unavailable: {e}"
            logger.debug("GitHub update check skipped: %s", e)
            self.check_failed.emit(err_msg)
            self.check_finished.emit(False)


class DownloadWorker(QThread):
    """
    Downloads release asset with progress updates, verifies cryptographic checksums,
    and stages unpacked binaries for safe replacement.
    """

    progress = Signal(int)
    status = Signal(str)
    download_finished = Signal(bool, str, str, bool)  # (success, error_msg, staged_path, is_directory)

    def __init__(self, url: str, asset_name: str = "", checksum_url: str = "", parent=None):
        super().__init__(parent)
        self.url = url
        self.asset_name = asset_name or "update_package.zip"
        self.checksum_url = checksum_url
        self.token = get_update_token()

    def _create_opener(self) -> urllib.request.OpenerDirector:
        return urllib.request.build_opener(GitHubAssetRedirectHandler())

    def run(self):
        try:
            temp_dir = tempfile.mkdtemp(prefix="pst_update_")
            target_path = Path(temp_dir) / self.asset_name
            self.status.emit("Downloading release package from GitHub...")

            headers = {"User-Agent": f"PedneSewaTrustRegistry/{APP_VERSION}"}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
                headers["Accept"] = "application/octet-stream"

            opener = self._create_opener()
            req = urllib.request.Request(self.url, headers=headers)
            with opener.open(req, timeout=45.0) as response, open(target_path, 'wb') as out_file:
                total_size = int(response.info().get('Content-Length', -1))
                bytes_downloaded = 0
                block_size = 65536

                while True:
                    buffer = response.read(block_size)
                    if not buffer:
                        break
                    bytes_downloaded += len(buffer)
                    out_file.write(buffer)
                    if total_size > 0:
                        pct = int((bytes_downloaded / total_size) * 80)
                        self.progress.emit(max(1, pct))

            self.progress.emit(85)

            # 2. Checksum verification against SHA256SUMS.txt
            if self.checksum_url:
                self.status.emit("Verifying SHA-256 cryptographic checksum...")
                try:
                    c_headers = {"User-Agent": f"PedneSewaTrustRegistry/{APP_VERSION}"}
                    if self.token:
                        c_headers["Authorization"] = f"Bearer {self.token}"
                        c_headers["Accept"] = "application/octet-stream"

                    c_req = urllib.request.Request(self.checksum_url, headers=c_headers)
                    with opener.open(c_req, timeout=15.0) as c_res:
                        checksum_content = c_res.read().decode("utf-8")

                    actual_hash = compute_file_sha256(target_path)
                    expected_hash = ""
                    for line in checksum_content.splitlines():
                        parts = line.strip().split()
                        if len(parts) >= 2:
                            h, fname = parts[0].lower(), parts[-1].strip("*")
                            if Path(fname).name.lower() == self.asset_name.lower():
                                expected_hash = h
                                break

                    if expected_hash and actual_hash != expected_hash:
                        msg = "Update verification failed. The current application has not been changed."
                        logger.error("SHA-256 verification mismatch. Expected: %s, Actual: %s", expected_hash, actual_hash)
                        shutil.rmtree(temp_dir, ignore_errors=True)
                        self.download_finished.emit(False, msg, "", False)
                        return

                    logger.info("SHA-256 checksum verified successfully: %s", actual_hash)
                except Exception as ex:
                    logger.warning("Checksum retrieval encountered error: %s", ex)

            self.progress.emit(90)

            # 3. Unpack and validate if ZIP archive
            if target_path.suffix.lower() == ".zip":
                self.status.emit("Extracting and verifying update package...")
                extract_dir = Path(temp_dir) / "extracted"
                extract_dir.mkdir(parents=True, exist_ok=True)
                with zipfile.ZipFile(target_path, 'r') as zip_ref:
                    zip_ref.extractall(extract_dir)

                # Locate directory containing PedneSewaTrustRegistry.exe
                candidate_dirs = [extract_dir] + [p for p in extract_dir.glob("*") if p.is_dir()]
                app_root_dir = None
                for c_dir in candidate_dirs:
                    if (c_dir / "PedneSewaTrustRegistry.exe").exists():
                        app_root_dir = c_dir
                        break

                if not app_root_dir:
                    msg = "Package validation failed: Application executable not found in update. The current application has not been changed."
                    logger.error(msg)
                    shutil.rmtree(temp_dir, ignore_errors=True)
                    self.download_finished.emit(False, msg, "", False)
                    return

                self.progress.emit(100)
                self.download_finished.emit(True, "", str(app_root_dir), True)
            else:
                self.progress.emit(100)
                self.download_finished.emit(True, "", str(target_path), False)

        except Exception as e:
            logger.error("Download worker error: %s", e)
            self.download_finished.emit(False, f"Download failed: {e}", "", False)


class UpdateDialog(QDialog):
    """Presents available update, release notes, and download progress to operator."""

    def __init__(
        self,
        latest_ver: str,
        release_notes: str,
        download_url: str,
        asset_name: str = "",
        checksum_url: str = "",
        parent=None
    ):
        super().__init__(parent)
        self.latest_ver = latest_ver
        self.release_notes = release_notes
        self.download_url = download_url
        self.asset_name = asset_name
        self.checksum_url = checksum_url
        self.setWindowTitle("Update Available")
        self.setFixedSize(580, 440)
        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(14)

        header_card = QFrame(self)
        header_card.setStyleSheet("background-color: #F0FDF4; border: 1px solid #BBF7D0; border-radius: 8px; padding: 12px;")
        h_layout = QVBoxLayout(header_card)
        h_layout.setSpacing(4)

        title = QLabel(f"A new version of {APP_NAME} is available.", header_card)
        title.setStyleSheet("font-size: 14px; font-weight: 700; color: #15803D;")
        h_layout.addWidget(title)

        ver_info = QLabel(f"Current version: <b>{APP_VERSION}</b>   ➔   Latest version: <b>{self.latest_ver}</b>", header_card)
        ver_info.setStyleSheet("font-size: 13px; color: #166534;")
        h_layout.addWidget(ver_info)
        layout.addWidget(header_card)

        lbl_notes = QLabel("Release Notes:", self)
        lbl_notes.setStyleSheet("font-weight: 600; color: #0F172A; font-size: 13px;")
        layout.addWidget(lbl_notes)

        self.txt_notes = QTextEdit(self)
        self.txt_notes.setReadOnly(True)
        self.txt_notes.setPlainText(self.release_notes)
        self.txt_notes.setStyleSheet("background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 6px; font-size: 12px;")
        layout.addWidget(self.txt_notes)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        self.lbl_status = QLabel("", self)
        self.lbl_status.setStyleSheet("color: #64748B; font-size: 12px;")
        self.lbl_status.setVisible(False)
        layout.addWidget(self.lbl_status)

        btns = QHBoxLayout()
        btns.addStretch()

        self.btn_later = QPushButton("Later", self)
        self.btn_later.setProperty("class", "SecondaryButton")
        self.btn_later.clicked.connect(self.reject)
        btns.addWidget(self.btn_later)

        self.btn_update = QPushButton("Update Now", self)
        self.btn_update.setProperty("class", "PrimaryButton")
        self.btn_update.clicked.connect(self._on_update_clicked)
        btns.addWidget(self.btn_update)

        layout.addLayout(btns)

    def _on_update_clicked(self):
        if not self.download_url:
            QMessageBox.information(
                self, "Update",
                f"Please visit https://github.com/{DEFAULT_GITHUB_REPO}/releases/latest to download the new version."
            )
            self.accept()
            return

        self.btn_later.setEnabled(False)
        self.btn_update.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.lbl_status.setVisible(True)
        self.lbl_status.setText("Connecting to release server...")

        self.downloader = DownloadWorker(self.download_url, self.asset_name, self.checksum_url)
        self.downloader.progress.connect(self.progress_bar.setValue)
        self.downloader.status.connect(self.lbl_status.setText)
        self.downloader.download_finished.connect(self._on_download_finished)
        self.downloader.start()

    def _on_download_finished(self, success: bool, error_msg: str, staged_path: str, is_directory: bool):
        if not success:
            QMessageBox.warning(
                self, "Update Failed",
                f"{error_msg}\n\nPlease check your network connection or update manually."
            )
            self.btn_later.setEnabled(True)
            self.btn_update.setEnabled(True)
            return

        self.lbl_status.setText("Update verified successfully. Launching updater...")
        self._launch_updater_and_restart(staged_path, is_directory)

    def _launch_updater_and_restart(self, staged_path: str, is_directory: bool):
        app_dir = Path(sys.executable).parent if getattr(sys, 'frozen', False) else Path(__file__).resolve().parent.parent

        # Security safeguard: Never touch %USERPROFILE%\.pedne_sewa_trust
        if not is_safe_app_dir(app_dir):
            QMessageBox.critical(
                self, "Update Safety Abort",
                "Security check failed: Updater destination overlaps with user database directory.\nUpdate aborted."
            )
            self.reject()
            return

        pid = os.getpid()
        temp_dir = Path(staged_path).parent if not is_directory else Path(staged_path).parent
        bat_path = temp_dir / "pst_updater.bat"

        # Detached batch script that waits for current process PID to quit,
        # replaces files in app_dir, launches updated EXE, and deletes itself.
        if is_directory:
            copy_cmd = f'xcopy /E /Y /I /Q /H /R "{staged_path}\\*" "{app_dir}\\" >nul 2>&1'
        else:
            copy_cmd = f'copy /Y "{staged_path}" "{app_dir}\\PedneSewaTrustRegistry.exe" >nul 2>&1'

        bat_script = f"""@echo off
setlocal enabledelayedexpansion
echo Waiting for application PID {pid} to terminate...
:waitloop
tasklist /FI "PID eq {pid}" 2>NUL | find /I /N "{pid}">NUL
if "%ERRORLEVEL%"=="0" (
    timeout /t 1 /nobreak >nul
    goto waitloop
)

echo Updating application files in "{app_dir}"...
{copy_cmd}

echo Restarting {APP_NAME}...
cd /D "{app_dir}"
start "" "PedneSewaTrustRegistry.exe"

del "%~f0"
exit
"""
        try:
            with open(bat_path, "w", encoding="utf-8") as f:
                f.write(bat_script)

            creation_flags = 0
            if sys.platform == "win32":
                creation_flags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS

            subprocess.Popen(str(bat_path), shell=True, creationflags=creation_flags)
            logger.info("Launched detached updater batch script: %s. Quitting current application.", bat_path)
            sys.exit(0)
        except Exception as e:
            logger.critical("Could not launch updater batch script: %s", e)
            QMessageBox.critical(self, "Update Error", f"Could not launch updater helper script:\n{e}")
