@echo off
setlocal enabledelayedexpansion
title Pedne Sewa Trust - 1-Click Update Helper

echo ==============================================================================
echo   Pedne Sewa Trust - Employment and Candidate Registry Update Helper
echo ==============================================================================
echo.

set "APP_DIR=%~dp0"
cd /D "%APP_DIR%"

echo [1/4] Closing any running application instances...
taskkill /F /IM "PedneSewaTrustRegistry.exe" >nul 2>&1
ping 127.0.0.1 -n 3 >nul 2>&1

echo [2/4] Downloading latest release from GitHub...
powershell -NoProfile -Command ^
    "$ErrorActionPreference = 'Stop';" ^
    "Write-Host 'Checking latest release...';" ^
    "$rel = Invoke-RestMethod -Uri 'https://api.github.com/repos/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases/latest' -Headers @{'User-Agent'='PowerShell'};" ^
    "$tag = $rel.tag_name;" ^
    "Write-Host \"Latest release tag: $tag\";" ^
    "$asset = $rel.assets | Where-Object { $_.name -like '*Windows.zip' } | Select-Object -First 1;" ^
    "if (-not $asset) { throw 'No Windows distribution zip found in latest release.'; }" ^
    "$zipPath = Join-Path $env:TEMP 'PedneSewaTrustRegistry-Latest.zip';" ^
    "Write-Host \"Downloading $($asset.name)...\";" ^
    "Invoke-WebRequest -Uri $asset.browser_download_url -OutFile $zipPath -UseBasicParsing;" ^
    "$extractDir = Join-Path $env:TEMP 'pst_latest_extracted';" ^
    "if (Test-Path $extractDir) { Remove-Item $extractDir -Recurse -Force | Out-Null; }" ^
    "Write-Host 'Extracting update package...';" ^
    "Expand-Archive -Path $zipPath -DestinationPath $extractDir -Force;" ^
    "Write-Host 'Download and extraction complete.'"

if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [ERROR] Could not download update automatically. Please check your internet connection.
    pause
    exit /b 1
)

echo [3/4] Installing updated files...
set "EXTRACT_DIR=%TEMP%\pst_latest_extracted"
if exist "%EXTRACT_DIR%\PedneSewaTrustRegistry\PedneSewaTrustRegistry.exe" (
    set "SRC_DIR=%EXTRACT_DIR%\PedneSewaTrustRegistry"
) else (
    set "SRC_DIR=%EXTRACT_DIR%"
)

robocopy "%SRC_DIR%" "%APP_DIR%" /E /R:10 /W:1 /XF config.json *.db *.sqlite *.sqlite3 *.log *.pdf *.xlsx *.csv *.bak /XD backups exports logs >nul 2>&1
if %ERRORLEVEL% GEQ 8 (
    xcopy /E /Y /I /Q /H /R "%SRC_DIR%\*" "%APP_DIR%\" >nul 2>&1
)

echo [4/4] Starting Pedne Sewa Trust Registry...
start "" "%APP_DIR%PedneSewaTrustRegistry.exe"
echo.
echo Update completed successfully!
ping 127.0.0.1 -n 3 >nul 2>&1
exit /b 0
