@echo off
setlocal enabledelayedexpansion

:: Pedne Sewa Trust - Universal Updater Bridge
:: Intercepts legacy updater scripts (v2.0.0 - v2.0.3) and completes atomic binary replacement.

echo [Pedne Sewa Trust] Completing application update...
ping 127.0.0.1 -n 3 >nul 2>&1

set "APP_DIR=%~dp0"
set "SRC_DIR="

:: Locate the staged update directory in %TEMP%
for /f "delims=" %%D in ('dir "%TEMP%\pst_update_*" /b /ad /o-d 2^>nul') do (
    if exist "%TEMP%\%%D\extracted\PedneSewaTrustRegistry.exe" (
        set "SRC_DIR=%TEMP%\%%D\extracted"
        goto :apply_update
    )
    if exist "%TEMP%\%%D\PedneSewaTrustRegistry.exe" (
        set "SRC_DIR=%TEMP%\%%D"
        goto :apply_update
    )
)

:apply_update
if defined SRC_DIR (
    echo Copying updated files from !SRC_DIR! to !APP_DIR!...
    robocopy "!SRC_DIR!" "!APP_DIR!" /E /R:10 /W:1 /XF config.json *.db *.sqlite *.sqlite3 *.log *.pdf *.xlsx *.csv >nul 2>&1
    if !ERRORLEVEL! GEQ 8 (
        xcopy /E /Y /I /Q /H /R "!SRC_DIR!\*" "!APP_DIR!\" >nul 2>&1
    )
)

:: Launch updated executable if not already running
cd /D "!APP_DIR!"
tasklist /FI "IMAGENAME eq PedneSewaTrustRegistry.exe" 2>nul | find /I "PedneSewaTrustRegistry.exe" >nul
if errorlevel 1 (
    start "" "!APP_DIR!PedneSewaTrustRegistry.exe"
)

exit /b 0
