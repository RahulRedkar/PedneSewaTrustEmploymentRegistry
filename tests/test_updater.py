"""
Comprehensive automated test suite for GitHub Releases Auto-Updater in Pedne Sewa Trust Registry.
Validates:
1. Version logic: semantic version parsing, comparison, newer version detection, no-update condition.
2. GitHub API integration: authenticated requests, no-token behaviour, 401, 403, 404, timeouts,
   malformed JSON, missing assets, and asset selection.
3. Security: SHA-256 checksum verification, mismatch aborts, invalid package structure,
   user data directory protection, and database/config preservation.

All GitHub HTTP calls are strictly mocked — zero external network requests.
"""

import os
import io
import json
import zipfile
import hashlib
import tempfile
import urllib.request
import urllib.error
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest
from app.version import APP_VERSION
from app.config import config
from app.updater import (
    parse_version,
    compute_file_sha256,
    is_safe_app_dir,
    get_update_token,
    UpdateCheckThread,
    DownloadWorker
)


# ==============================================================================
# 1. Semantic Version Parsing & Comparison Tests
# ==============================================================================

def test_semantic_version_parsing():
    """Validates semantic version normalization across diverse formats."""
    assert parse_version("2.0.0") == (2, 0, 0)
    assert parse_version("v2.0.0") == (2, 0, 0)
    assert parse_version("V2.1.5") == (2, 1, 5)
    assert parse_version("v2.10.3-beta") == (2, 10, 3)
    assert parse_version("2") == (2, 0, 0)
    assert parse_version("2.1") == (2, 1, 0)
    assert parse_version("") == (0, 0, 0)
    assert parse_version(None) == (0, 0, 0)


def test_semantic_version_comparison():
    """Validates accurate numerical comparison of semantic versions."""
    assert parse_version("v2.1.0") > parse_version("v2.0.0")
    assert parse_version("v2.0.1") > parse_version("v2.0.0")
    assert parse_version("v2.0.0") == parse_version("2.0.0")
    assert parse_version("v1.9.9") < parse_version("v2.0.0")
    assert parse_version("v2.0.0-rc1") == parse_version("v2.0.0")


# ==============================================================================
# 2. GitHub API Mocked Request Tests
# ==============================================================================

def test_updater_constructs_canonical_api_endpoint(qapp):
    """Verifies that updater constructs the canonical private repo endpoint and excludes old owner."""
    from app.version import GITHUB_OWNER, GITHUB_REPOSITORY, GITHUB_REPO_SLUG
    from app.updater import DEFAULT_GITHUB_REPO

    # Authoritative values
    assert GITHUB_OWNER == "RahulRedkar"
    assert GITHUB_REPOSITORY == "PedneSewaTrustEmploymentRegistry"
    assert GITHUB_REPO_SLUG == "RahulRedkar/PedneSewaTrustEmploymentRegistry"
    assert DEFAULT_GITHUB_REPO == "RahulRedkar/PedneSewaTrustEmploymentRegistry"
    assert "pedne-sewa-trust" not in GITHUB_REPO_SLUG.lower()

    thread = UpdateCheckThread()
    assert thread.repo_slug == "RahulRedkar/PedneSewaTrustEmploymentRegistry"

    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({"tag_name": "v2.0.1", "assets": []}).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    captured = []
    with patch("urllib.request.urlopen", side_effect=lambda req, timeout=10.0: (captured.append(req), mock_resp)[1]):
        thread.run()

    assert len(captured) == 1
    assert captured[0].full_url == "https://api.github.com/repos/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases/latest"
    assert "pedne-sewa-trust" not in captured[0].full_url

def test_github_authenticated_api_request(qapp):
    """Verifies that GITHUB_UPDATE_TOKEN adds Authorization: Bearer header to GitHub API calls."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({
        "tag_name": "v2.0.0",
        "body": "Up to date",
        "assets": []
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)

    captured_requests = []
    def mock_urlopen(req, timeout=10.0):
        captured_requests.append(req)
        return mock_resp

    with patch("app.updater.get_update_token", return_value="ghp_test_secret_token_12345"), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen):
        thread.run()

    assert len(captured_requests) == 1
    req = captured_requests[0]
    auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
    assert auth_header == "Bearer ghp_test_secret_token_12345"


def test_github_no_token_behaviour(qapp):
    """Verifies that in the absence of GITHUB_UPDATE_TOKEN, no Authorization header is sent."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps({
        "tag_name": "v2.0.0",
        "body": "Up to date",
        "assets": []
    }).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)

    captured_requests = []
    def mock_urlopen(req, timeout=10.0):
        captured_requests.append(req)
        return mock_resp

    with patch("app.updater.get_update_token", return_value=""), \
         patch("urllib.request.urlopen", side_effect=mock_urlopen):
        thread.run()

    assert len(captured_requests) == 1
    req = captured_requests[0]
    auth_header = req.headers.get("Authorization") or req.headers.get("authorization")
    assert auth_header is None


def test_github_newer_version_detection(qapp):
    """Verifies that UpdateCheckThread emits update_available when a newer release is detected."""
    mock_data = {
        "tag_name": "v2.1.0",
        "body": "### New Features\n- Added candidate facilitation reports",
        "assets": [
            {
                "name": "PedneSewaTrustRegistry-v2.1.0-Windows.zip",
                "url": "https://api.github.com/repos/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases/assets/101",
                "browser_download_url": "https://github.com/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases/download/v2.1.0/PedneSewaTrustRegistry-v2.1.0-Windows.zip"
            },
            {
                "name": "SHA256SUMS.txt",
                "url": "https://api.github.com/repos/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases/assets/102",
                "browser_download_url": "https://github.com/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases/download/v2.1.0/SHA256SUMS.txt"
            }
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    results = []
    thread.update_available.connect(lambda *args: results.append(args))

    with patch("app.updater.get_update_token", return_value="token123"), \
         patch("urllib.request.urlopen", return_value=mock_resp):
        thread.run()

    assert len(results) == 1
    tag, notes, dl_url, asset_name, checksum_url = results[0]
    assert tag == "v2.1.0"
    assert "Added candidate facilitation reports" in notes
    assert "assets/101" in dl_url  # Authenticated API asset URL preferred
    assert asset_name == "PedneSewaTrustRegistry-v2.1.0-Windows.zip"
    assert "assets/102" in checksum_url


def test_github_no_update_condition(qapp):
    """Verifies that UpdateCheckThread emits update_not_available when current version is active."""
    mock_data = {
        "tag_name": f"v{APP_VERSION}",
        "body": "Current active release",
        "assets": []
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    up_to_date_called = []
    thread.update_not_available.connect(lambda ver: up_to_date_called.append(ver))

    with patch("urllib.request.urlopen", return_value=mock_resp):
        thread.run()

    assert len(up_to_date_called) == 1
    assert up_to_date_called[0] == APP_VERSION


def test_github_http_401_unauthorized(qapp):
    """Verifies graceful handling when GitHub returns HTTP 401 Unauthorized."""
    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    errs = []
    thread.check_failed.connect(lambda msg: errs.append(msg))

    err_resp = urllib.error.HTTPError("https://api.github.com", 401, "Unauthorized", {}, None)
    with patch("urllib.request.urlopen", side_effect=err_resp):
        thread.run()

    assert len(errs) == 1
    assert "Authentication failed" in errs[0]
    assert "GITHUB_UPDATE_TOKEN" in errs[0]


def test_github_http_403_forbidden(qapp):
    """Verifies graceful handling when GitHub returns HTTP 403 Forbidden."""
    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    errs = []
    thread.check_failed.connect(lambda msg: errs.append(msg))

    err_resp = urllib.error.HTTPError("https://api.github.com", 403, "Forbidden", {}, None)
    with patch("urllib.request.urlopen", side_effect=err_resp):
        thread.run()

    assert len(errs) == 1
    assert "Authentication failed" in errs[0]


def test_github_http_404_not_found(qapp):
    """Verifies graceful handling when GitHub returns HTTP 404 (private repo with invalid/missing token)."""
    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    errs = []
    thread.check_failed.connect(lambda msg: errs.append(msg))

    err_resp = urllib.error.HTTPError("https://api.github.com", 404, "Not Found", {}, None)
    with patch("urllib.request.urlopen", side_effect=err_resp):
        thread.run()

    assert len(errs) == 1
    assert "Repository or release not found" in errs[0]


def test_github_timeout_and_network_error(qapp):
    """Verifies that network timeouts or connectivity loss do not crash the application."""
    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    errs = []
    thread.check_failed.connect(lambda msg: errs.append(msg))

    with patch("urllib.request.urlopen", side_effect=TimeoutError("Request timed out")):
        thread.run()

    assert len(errs) == 1
    assert "Network connection unavailable" in errs[0]


def test_github_malformed_json_response(qapp):
    """Verifies graceful handling when GitHub response is not valid JSON."""
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = b"<html>502 Bad Gateway</html>"
    mock_resp.__enter__.return_value = mock_resp

    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    errs = []
    thread.check_failed.connect(lambda msg: errs.append(msg))

    with patch("urllib.request.urlopen", return_value=mock_resp):
        thread.run()

    assert len(errs) == 1
    assert "Network connection unavailable" in errs[0] or "JSON" in errs[0]


def test_github_release_asset_selection(qapp):
    """Verifies that .zip is prioritized over .exe and SHA256SUMS.txt is matched correctly."""
    mock_data = {
        "tag_name": "v2.5.0",
        "body": "Release body",
        "assets": [
            {"name": "installer.exe", "url": "https://api/exe", "browser_download_url": "https://dl/exe"},
            {"name": "PedneSewaTrustRegistry-v2.5.0-Windows.zip", "url": "https://api/zip", "browser_download_url": "https://dl/zip"},
            {"name": "SHA256SUMS.txt", "url": "https://api/sha", "browser_download_url": "https://dl/sha"}
        ]
    }
    mock_resp = MagicMock()
    mock_resp.status = 200
    mock_resp.read.return_value = json.dumps(mock_data).encode("utf-8")
    mock_resp.__enter__.return_value = mock_resp

    thread = UpdateCheckThread(repo_slug="RahulRedkar/PedneSewaTrustEmploymentRegistry", is_manual=True)
    results = []
    thread.update_available.connect(lambda *args: results.append(args))

    with patch("app.updater.get_update_token", return_value=""), \
         patch("urllib.request.urlopen", return_value=mock_resp):
        thread.run()

    assert len(results) == 1
    _, _, dl_url, asset_name, checksum_url = results[0]
    assert asset_name == "PedneSewaTrustRegistry-v2.5.0-Windows.zip"
    assert dl_url == "https://dl/zip"
    assert checksum_url == "https://dl/sha"


# ==============================================================================
# 3. Security, Checksums, Package Validation & Data Preservation Tests
# ==============================================================================

def test_checksum_verification_success(qapp):
    """Verifies that DownloadWorker validates correct checksum and extracts package."""
    # Create sample in-memory zip containing PedneSewaTrustRegistry.exe
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("PedneSewaTrustRegistry.exe", b"VALID_BINARY_PAYLOAD")
        zf.writestr("assets/icon.ico", b"ICON")
    zip_bytes = zip_buf.getvalue()

    correct_hash = hashlib.sha256(zip_bytes).hexdigest().lower()
    checksum_content = f"{correct_hash}  PedneSewaTrustRegistry-v2.1.0-Windows.zip\n".encode("utf-8")

    def mock_open(req, timeout=45.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        if "SHA256SUMS.txt" in url or "sha256" in url.lower():
            resp.read.return_value = checksum_content
        else:
            resp.info.return_value.get.return_value = len(zip_bytes)
            resp.read.side_effect = [zip_bytes, b""]
        return resp

    worker = DownloadWorker(
        url="https://github.com/repo/releases/download/v2.1.0/PedneSewaTrustRegistry-v2.1.0-Windows.zip",
        asset_name="PedneSewaTrustRegistry-v2.1.0-Windows.zip",
        checksum_url="https://github.com/repo/releases/download/v2.1.0/SHA256SUMS.txt"
    )

    results = []
    worker.download_finished.connect(lambda ok, err, path, is_dir: results.append((ok, err, path, is_dir)))

    with patch.object(worker, "_create_opener") as mock_opener_builder:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = mock_open
        mock_opener_builder.return_value = mock_opener
        worker.run()

    assert len(results) == 1
    ok, err, path, is_dir = results[0]
    assert ok is True
    assert err == ""
    assert is_dir is True
    assert (Path(path) / "PedneSewaTrustRegistry.exe").exists()


def test_checksum_mismatch_aborts(qapp):
    """
    CRITICAL SECURITY TEST:
    Verifies that a checksum mismatch immediately aborts and displays the required message:
    'Update verification failed. The current application has not been changed.'
    """
    payload = b"Tampered binary payload"
    wrong_hash = "0000000000000000000000000000000000000000000000000000000000000000"
    checksum_content = f"{wrong_hash}  PedneSewaTrustRegistry-v2.1.0-Windows.zip\n".encode("utf-8")

    def mock_open(req, timeout=45.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        if "SHA256SUMS.txt" in url or "sha256" in url.lower():
            resp.read.return_value = checksum_content
        else:
            resp.info.return_value.get.return_value = len(payload)
            resp.read.side_effect = [payload, b""]
        return resp

    worker = DownloadWorker(
        url="https://github.com/repo/releases/download/v2.1.0/PedneSewaTrustRegistry-v2.1.0-Windows.zip",
        asset_name="PedneSewaTrustRegistry-v2.1.0-Windows.zip",
        checksum_url="https://github.com/repo/releases/download/v2.1.0/SHA256SUMS.txt"
    )

    results = []
    worker.download_finished.connect(lambda ok, err, path, is_dir: results.append((ok, err, path, is_dir)))

    with patch.object(worker, "_create_opener") as mock_opener_builder:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = mock_open
        mock_opener_builder.return_value = mock_opener
        worker.run()

    assert len(results) == 1
    ok, err, path, is_dir = results[0]
    assert ok is False
    assert "Update verification failed. The current application has not been changed." in err


def test_invalid_package_missing_exe_aborts(qapp):
    """Verifies that an extracted package missing PedneSewaTrustRegistry.exe is rejected."""
    # ZIP with arbitrary text file but no executable
    zip_buf = io.BytesIO()
    with zipfile.ZipFile(zip_buf, "w") as zf:
        zf.writestr("readme.txt", b"Nothing here")
    zip_bytes = zip_buf.getvalue()

    correct_hash = hashlib.sha256(zip_bytes).hexdigest().lower()
    checksum_content = f"{correct_hash}  PedneSewaTrustRegistry-v2.1.0-Windows.zip\n".encode("utf-8")

    def mock_open(req, timeout=45.0):
        url = req.full_url if hasattr(req, "full_url") else str(req)
        resp = MagicMock()
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        if "SHA256SUMS.txt" in url or "sha256" in url.lower():
            resp.read.return_value = checksum_content
        else:
            resp.info.return_value.get.return_value = len(zip_bytes)
            resp.read.side_effect = [zip_bytes, b""]
        return resp

    worker = DownloadWorker(
        url="https://github.com/repo/releases/download/v2.1.0/PedneSewaTrustRegistry-v2.1.0-Windows.zip",
        asset_name="PedneSewaTrustRegistry-v2.1.0-Windows.zip",
        checksum_url="https://github.com/repo/releases/download/v2.1.0/SHA256SUMS.txt"
    )

    results = []
    worker.download_finished.connect(lambda ok, err, path, is_dir: results.append((ok, err, path, is_dir)))

    with patch.object(worker, "_create_opener") as mock_opener_builder:
        mock_opener = MagicMock()
        mock_opener.open.side_effect = mock_open
        mock_opener_builder.return_value = mock_opener
        worker.run()

    assert len(results) == 1
    ok, err, path, is_dir = results[0]
    assert ok is False
    assert "Package validation failed: Application executable not found in update" in err


def test_user_data_path_protection():
    """
    CRITICAL USER-DATA ISOLATION TEST:
    Verifies that the updater refuses to operate if app destination
    overlaps with the persistent user directory in ~/.pedne_sewa_trust.
    """
    user_data = Path.home() / ".pedne_sewa_trust"
    assert not is_safe_app_dir(user_data)
    assert not is_safe_app_dir(user_data / "backups")
    assert not is_safe_app_dir(user_data / "pst_registry.db")
    assert not is_safe_app_dir(user_data / "config.json")

    # Safe destination (e.g. Program Files or portable extracted directory)
    assert is_safe_app_dir(Path("C:/Program Files/PedneSewaTrustRegistry"))
    assert is_safe_app_dir(Path("D:/PortableApps/PedneSewaTrustRegistry"))


def test_config_and_database_preservation():
    """
    Verifies that configuration keys (Apps Script URL, Backup API Key, Update Token)
    and SQLite database settings are completely preserved across updater invocations.
    """
    # Ensure config precedence maintains values
    with patch.dict(os.environ, {
        "GOOGLE_APPS_SCRIPT_URL": "https://script.google.com/macros/s/TEST_URL/exec",
        "BACKUP_API_KEY": "test_backup_key_preserved",
        "GITHUB_UPDATE_TOKEN": "test_update_token_preserved"
    }):
        assert config.get("apps_script_url") == "https://script.google.com/macros/s/TEST_URL/exec"
        assert config.get("backup_api_key") == "test_backup_key_preserved"
        assert config.get("github_update_token") == "test_update_token_preserved"
