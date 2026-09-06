# Pedne Sewa Trust — Employment Facilitation Platform

[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue.svg)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)](https://python.org)
[![GUI](https://img.shields.io/badge/GUI-PySide6%20%28Qt%206%29-green.svg)](https://qt.io)
[![Database](https://img.shields.io/badge/database-SQLite3%20%28WAL%20mode%29-lightgrey.svg)](https://sqlite.org)
[![Release](https://img.shields.io/badge/version-2.0.0-emerald.svg)](https://github.com/RahulRedkar/PedneSewaTrustEmploymentRegistry/releases)
[![License](https://img.shields.io/badge/license-Proprietary%20%2F%20NGO-orange.svg)]()

A professional, production-grade Windows desktop application built for **Pedne Sewa Trust** to record, manage, analyze, and actively facilitate employment opportunities for jobseekers across Pernem (Pedne) Taluka, Goa.

---

## 🏛️ Project Purpose & Scope

The **Pedne Sewa Trust Employment Facilitation Platform** transforms grassroots candidate intake into an organized employment facilitation pipeline for North Goa. Tailored specifically for the 26+ villages of Pernem Taluka, the application provides local operators and Trust administrators with an offline-resilient registry, candidate profiling, document verification tracking, recruiter consent governance, and automated off-site cloud disaster recovery.

---

## 🏗️ Architecture Overview

The system is designed with a **local-first, privacy-preserving, zero-credential desktop architecture**:

```
┌─────────────────────────────────────────────────────────────┐
│                 Desktop Client (PySide6 / Qt6)              │
│                                                             │
│  ┌───────────────────────┐       ┌───────────────────────┐  │
│  │   Operator Workflow   │       │  Candidate Profiling  │  │
│  │   (Intake & Search)   │       │ (Location & Documents)│  │
│  └───────────┬───────────┘       └───────────┬───────────┘  │
│              │                               │              │
│              ▼                               ▼              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │      Authoritative Local SQLite Database (WAL Mode)   │  │
│  │       Stored in %USERPROFILE%\.pedne_sewa_trust\       │  │
│  └───────────────────────────┬───────────────────────────┘  │
│                              │                              │
│                Automatic Rolling Daily Backups               │
│                              │                              │
│                              ▼                              │
│  ┌───────────────────────────────────────────────────────┐  │
│  │          Background Cloud Sync Worker (10 min)        │  │
│  │          HTTPS Client (Zero Local Google OAuth)       │  │
│  └───────────────────────────┬───────────────────────────┘  │
└──────────────────────────────┼──────────────────────────────┘
                               │ HTTPS POST (API Key Auth)
                               ▼
┌─────────────────────────────────────────────────────────────┐
│       Serverless Gateway (Google Apps Script Web App)       │
│         - Enforces Script Property BACKUP_API_KEY           │
│         - Authoritative for Google Sheet & Worksheet        │
└──────────────────────────────┬──────────────────────────────┘
                               │ Server-side SpreadsheetApp API
                               ▼
┌─────────────────────────────────────────────────────────────┐
│           Private Organization Google Spreadsheet           │
│           42-Column Tabular Schema (Row per Candidate)      │
└─────────────────────────────────────────────────────────────┘
```

### Key Architectural Pillars:
1. **Local-First & Offline-Resilient**: The local SQLite database is the primary source of truth. All registration, searching, editing, and reporting operate with zero latency, even with no internet connection.
2. **Serverless Cloud Backup**: Eliminates fragile desktop Google OAuth browser popups, client ID files (`credentials.json`), and expiring refresh tokens. Instead, a lightweight HTTPS POST delivers flat tabular candidate records to a private Google Apps Script endpoint authenticated via an API key.
3. **Silent Background Synchronization**: An asynchronous background worker synchronizes pending records every 10 minutes without freezing the user interface or interrupting data entry operators.
4. **Data Isolation**: Local user database, configuration, and automatic database backups are preserved strictly in `%USERPROFILE%\.pedne_sewa_trust\` and are never modified during software binary updates.

---

## ✨ Key Capabilities & Modules

| Module | Features & Capabilities |
| :--- | :--- |
| **Candidate Intake & Search** | Full intake recording Personal Details, Contact Numbers, Address, Village, Independent Vaddo/Ward, Electoral Polling Booth, Education, Skills, and Current Employment Classification. Real-time duplicate detection on Mobile number and Name. |
| **Government Job Tracking** | Tracks candidate applications for Goa State (GSSC, GPSC, Directorate vacancies). Local curation of official recruitment notifications with match evaluation enforcing the legal disclaimer: *"Potential Match — Verify Eligibility Against Official Advertisement"*. |
| **Local Job Vacancies** | Curated catalog of local government and private employer vacancies in Pernem, Mopa Airport, Tuem IDC, and greater Goa. |
| **Rule-Based Matching** | Automated matching engine comparing candidate qualification, age limits, driving license, and village location against active job requirements. |
| **Document Readiness Engine** | Tracks 6 essential documents: 15-Year Residence Certificate, Employment Exchange Registration Card, Educational Marksheets, Degree/Diploma Certificate, Birth Certificate, and Driving Licence across 7 discrete readiness states with readiness scoring (0–100%). |
| **Recruiter Consent Gate** | Strict privacy enforcement ensuring candidate contact info is only shared with verified employers when explicit candidate consent has been logged. Enforces 3 privacy tiers. |
| **Facilitation & Interaction Logs** | Complete audit logging of employer outreach, candidate submissions, interview invites, and placement outcomes. |
| **Reports & Analytics** | Real-time interactive demographic charts, village distributions, educational breakdowns, and instant export to CSV or publication-ready branded PDF reports. |
| **Sample Demo Data Seeding** | Instant generation of 100 synthetic, segregated Pernem candidate profiles (`is_demo = 1`) for demonstration and training, with one-click cleanup. |
| **Local Backup Management** | Automated rolling database snapshots on application startup (with 30-day retention) plus on-demand local backup creation and restoration. |
| **Tabular Cloud Backup** | 42-column tabular backup where every candidate field occupies its own spreadsheet column with automatic duplicate prevention and in-place row updates. |
| **GitHub Releases Updater** | Non-blocking background update checks against GitHub Releases with release notes display, SHA-256 cryptographic verification, and detached binary replacement. |

---

## 📋 Prerequisites

* **Operating System**: Windows 10 or Windows 11 (64-bit recommended)
* **Python**: Python 3.10, 3.11, 3.12, or 3.13
* **Package Manager**: `pip` (standard with Python)

---

## 💻 Local Development Setup

### 1. Clone the Repository
```powershell
git clone https://github.com/RahulRedkar/PedneSewaTrustEmploymentRegistry.git
cd PedneSewaTrustEmploymentRegistry
```

### 2. Create and Activate a Virtual Environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the Automated Test Suite
```powershell
python -m pytest tests/ -v
```

### 5. Launch Application in Development Mode
```powershell
python main.py
```

---

## 🔒 Production Deployment: Google Apps Script Backup Gateway

To enable cloud backups to a private Google Spreadsheet without desktop OAuth:

### Step 1: Open Target Google Sheet & Apps Script
1. Open your designated Google Spreadsheet in your web browser.
2. In the menu, click **Extensions** > **Apps Script**.

### Step 2: Paste Gateway Script
1. Replace any boilerplate code in `Code.gs` with the entire contents of [`sync/google_apps_script.js`](file:///E:/Pedne%20Sewa%20Trust%20Employment%20Related%20Data/sync/google_apps_script.js).
2. Click **Save** (`Ctrl+S`).

### Step 3: Configure Script Properties (Server-Side Secrets)
1. In the Apps Script left sidebar, click the **Project Settings** (gear icon ⚙️).
2. Scroll down to **Script Properties** and click **Add script property**.
3. Add the following properties:
   * `SHEET_ID`: The ID of your Google Sheet (from the sheet URL: `https://docs.google.com/spreadsheets/d/<SHEET_ID>/edit`).
   * `BACKUP_API_KEY`: A strong, private random secret key (e.g. `YOUR_GENERATED_SECRET_KEY`).
4. Click **Save script properties**.

### Step 4: Deploy as Web App
1. Click the blue **Deploy** button (top right) > **New deployment**.
2. Select type: **Web app** (gear icon).
3. Configuration:
   * **Description**: `Pedne Sewa Trust Cloud Backup Gateway v2`
   * **Execute as**: `Me (your_google_account@gmail.com)`
   * **Who has access**: `Anyone` *(Note: The endpoint strictly enforces the `BACKUP_API_KEY` for authentication; unauthorized calls are rejected).*
4. Click **Deploy** and authorize the script permissions.
5. Copy the resulting **Web App URL** (e.g. `https://script.google.com/macros/s/AKfycb.../exec`).

### Step 5: Configure Desktop Client
Configure the desktop application using either **Environment Variables** or the **Settings UI / config.json**:

#### Option A: Environment Variables (Recommended for secure administration)
Set these variables in your Windows environment:
```powershell
[System.Environment]::SetEnvironmentVariable('GOOGLE_APPS_SCRIPT_URL', 'https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec', 'User')
[System.Environment]::SetEnvironmentVariable('BACKUP_API_KEY', 'YOUR_STRONG_SECRET_KEY', 'User')
```

#### Option B: Settings Interface
1. Launch the application and open **Settings** from the sidebar.
2. Under **Cloud Backup Gateway**, paste:
   * **Apps Script Web App URL**: `https://script.google.com/macros/s/<DEPLOYMENT_ID>/exec`
   * **Backup API Key**: `YOUR_STRONG_SECRET_KEY`
3. Click **Save Settings**.

---

## 📦 Building the Standalone Windows Executable

The application compiles into a standalone, portable Windows application using PyInstaller:

```powershell
python build_exe.py
```

The compiled standalone executable and bundled assets are generated in:
```
dist\PedneSewaTrustRegistry\
├── PedneSewaTrustRegistry.exe
├── assets\
│   ├── icon.ico
│   ├── logo.png
│   └── styles.qss
└── _internal\
```

---

## 🔄 GitHub Releases Distribution & Update Flow

This repository includes a continuous integration workflow [`.github/workflows/release.yml`](file:///E:/Pedne%20Sewa%20Trust%20Employment%20Related%20Data/.github/workflows/release.yml):

1. **Tag Push**: Whenever a release tag is pushed (e.g. `git tag v2.0.0 && git push origin v2.0.0`), GitHub Actions:
   - Sets up a clean Windows runner.
   - Runs the full 67+ automated test suite.
   - Compiles the executable via `python build_exe.py`.
   - Packages the release archive `PedneSewaTrustRegistry-v<VERSION>-Windows.zip`.
   - Computes SHA-256 cryptographic hashes and publishes `SHA256SUMS.txt`.
   - Publishes an official GitHub Release with release notes.

2. **In-App Auto-Update (Private Repository Support)**:
   - On startup, the desktop client checks the private GitHub Releases API asynchronously using the configured `GITHUB_UPDATE_TOKEN` (via environment variable `GITHUB_UPDATE_TOKEN` or local `config.json`).
   - When a newer version is detected, operators see release notes with an **Update Now** button.
   - The updater streams the release package, verifies the SHA-256 checksum against `SHA256SUMS.txt`, and spawns a detached updater script.
   - The detached script waits for the current instance to exit, replaces the binaries in the install directory, and relaunches the application.
   - **User Data Isolation Guarantee**: The updater operates solely on application binaries. The user database (`pst_registry.db`), local backups, and configuration in `%USERPROFILE%\.pedne_sewa_trust\` are completely isolated and never modified.

3. **Separation of Concerns: API Keys & Tokens**:
   - `BACKUP_API_KEY`: Used exclusively to authenticate HTTPS POST payloads with the private Google Apps Script Web App backup gateway.
   - `GITHUB_UPDATE_TOKEN`: Used exclusively to query the private GitHub Releases API and stream release assets.
   - These two credentials serve completely independent purposes and are managed separately.

---

## 🛡️ Security, Privacy & Compliance

- **No Secrets in Source Control**: Production API keys, GitHub tokens, `config.json`, `.env`, and local database files are strictly gitignored. Only safe templates (`config.example.json`) are committed.
- **Private Repository Desktop Security Notice**: A token supplied to a desktop client cannot be considered completely confidential from a user who has administrative control over that physical machine. Therefore, `GITHUB_UPDATE_TOKEN` must always be restricted to the absolute minimum **read-only** repository permissions (`contents: read`). Never assign write or administrative permissions to desktop update tokens.
- **No Aadhaar or PAN Storage**: In strict compliance with Indian data protection norms, national identification numbers (Aadhaar, PAN) are neither captured nor synchronized to cloud backups.
- **Explicit Recruiter Consent**: Candidate records cannot be exported or shared with third-party employers without explicit, audited candidate consent.
- **Server-Side Authorization**: The destination Google Spreadsheet ID is maintained server-side in Apps Script properties; desktop clients cannot alter or redirect backup destinations.
- **Cryptographic Verification**: Release updates are verified via SHA-256 checksums against `SHA256SUMS.txt` before unpackaging.

---

## 🏛️ Pedne Sewa Trust
*Pernem (Pedne) Taluka, Goa, India*  
*Empowering local youth through structured employment facilitation and grassroots skill mapping.*
