"""
SQLite schema definitions and migrations for Pedne Sewa Trust - Employment Registry.
"""

import sqlite3
from utils.logger import logger

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS candidates (
    candidate_id TEXT PRIMARY KEY,
    full_name TEXT NOT NULL,
    dob TEXT,
    age INTEGER,
    gender TEXT,
    address TEXT,
    village TEXT NOT NULL,
    taluka TEXT NOT NULL DEFAULT 'Pernem',
    pincode TEXT,
    mobile TEXT NOT NULL,
    alternate_mobile TEXT,
    email TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    sync_status TEXT NOT NULL DEFAULT 'PENDING',
    last_synced_at TEXT,
    is_deleted INTEGER NOT NULL DEFAULT 0,
    is_demo INTEGER NOT NULL DEFAULT 0,
    intake_office TEXT NOT NULL DEFAULT 'Pernem'
);

CREATE TABLE IF NOT EXISTS education (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL UNIQUE,
    highest_qualification TEXT,
    degree_course TEXT,
    specialisation TEXT,
    institution TEXT,
    passing_year INTEGER,
    additional_qualifications TEXT,
    certifications TEXT,
    skills TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employment (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    category TEXT,
    department_company TEXT,
    designation TEXT,
    work_location TEXT,
    years_experience REAL DEFAULT 0.0,
    previous_experience TEXT,
    current_salary REAL,
    govt_applied INTEGER DEFAULT 0,
    govt_post_exam TEXT,
    govt_department TEXT,
    govt_app_year INTEGER,
    govt_result_status TEXT,
    govt_remarks TEXT,
    self_emp_business_nature TEXT,
    self_emp_location TEXT,
    self_emp_years_active REAL,
    self_emp_employees_count INTEGER,
    self_emp_monthly_income REAL,
    student_current_course TEXT,
    student_institution TEXT,
    student_expected_year INTEGER,
    student_interested_in_employment INTEGER DEFAULT 1,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS employment_preferences (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL UNIQUE,
    preferred_sector TEXT,
    preferred_role TEXT,
    preferred_location TEXT,
    willing_to_relocate INTEGER DEFAULT 0,
    preferred_employment_type TEXT,
    languages_known TEXT,
    skills_list TEXT,
    certifications_list TEXT,
    total_experience_years REAL DEFAULT 0.0,
    previous_employers TEXT,
    remarks TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS synchronisation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    records_pushed INTEGER NOT NULL DEFAULT 0,
    records_failed INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL,
    error_message TEXT,
    details TEXT
);

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    user_action TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    action TEXT NOT NULL,
    old_value TEXT,
    new_value TEXT,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS candidate_locations (
    candidate_id TEXT PRIMARY KEY,
    house_building TEXT,
    vaddo TEXT NOT NULL DEFAULT '',
    village TEXT NOT NULL,
    booth TEXT DEFAULT '',
    taluka TEXT NOT NULL DEFAULT 'Pernem',
    pincode TEXT DEFAULT '',
    full_address_landmark TEXT DEFAULT '',
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS candidate_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    document_type TEXT NOT NULL,
    document_category TEXT NOT NULL,
    status TEXT NOT NULL,
    issue_date TEXT,
    expiry_date TEXT,
    application_date TEXT,
    reference_number TEXT,
    expected_availability_date TEXT,
    verification_status TEXT NOT NULL DEFAULT 'Not Checked',
    notes TEXT,
    updated_at TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS government_jobs (
    job_id TEXT PRIMARY KEY,
    source TEXT NOT NULL,
    advertisement_number TEXT,
    department TEXT NOT NULL,
    post_name TEXT NOT NULL,
    vacancies_count INTEGER DEFAULT 1,
    employment_type TEXT DEFAULT 'Regular / Permanent',
    pay_level_salary TEXT,
    minimum_qualification TEXT,
    preferred_qualification TEXT,
    experience_requirement_years REAL DEFAULT 0.0,
    age_limit_min INTEGER DEFAULT 18,
    age_limit_max INTEGER DEFAULT 45,
    gender_requirement TEXT DEFAULT 'Any',
    category_reservation TEXT,
    konkani_marathi_required TEXT DEFAULT 'Konkani Essential, Marathi Desirable',
    required_documents TEXT,
    application_start_date TEXT,
    application_closing_date TEXT,
    application_method TEXT,
    official_ad_url TEXT,
    official_apply_url TEXT,
    ad_pdf_url TEXT,
    last_checked_at TEXT,
    source_last_updated_at TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN'
);

CREATE TABLE IF NOT EXISTS private_jobs (
    job_id TEXT PRIMARY KEY,
    employer TEXT NOT NULL,
    job_title TEXT NOT NULL,
    department TEXT,
    job_description TEXT,
    required_qualification TEXT,
    required_skills TEXT,
    required_experience_years REAL DEFAULT 0.0,
    required_documents TEXT,
    location TEXT NOT NULL,
    salary_range TEXT,
    employment_type TEXT DEFAULT 'Full-Time',
    work_mode TEXT DEFAULT 'On-Site',
    application_deadline TEXT,
    source TEXT,
    source_url TEXT,
    application_url TEXT,
    contact_person TEXT,
    contact_email TEXT,
    contact_phone TEXT,
    date_added TEXT NOT NULL,
    last_verified_at TEXT,
    verification_status TEXT DEFAULT 'VERIFIED',
    status TEXT NOT NULL DEFAULT 'ACTIVE'
);

CREATE TABLE IF NOT EXISTS recruiters (
    recruiter_id TEXT PRIMARY KEY,
    company TEXT NOT NULL,
    contact_person TEXT NOT NULL,
    designation TEXT,
    email TEXT NOT NULL,
    phone TEXT NOT NULL,
    industry TEXT,
    location TEXT,
    website TEXT,
    verification_status TEXT NOT NULL DEFAULT 'UNVERIFIED',
    date_added TEXT NOT NULL,
    last_contact_at TEXT,
    candidates_shared_count INTEGER DEFAULT 0,
    notes TEXT
);

CREATE TABLE IF NOT EXISTS candidate_consent (
    candidate_id TEXT PRIMARY KEY,
    consent_status TEXT NOT NULL DEFAULT 'Not Asked',
    consent_date TEXT,
    consent_method TEXT,
    consent_notes TEXT,
    updated_at TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS recruiter_candidate_shares (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    recruiter_id TEXT NOT NULL,
    candidate_id TEXT NOT NULL,
    job_id TEXT,
    shared_date TEXT NOT NULL,
    export_mode TEXT NOT NULL,
    consent_status_at_sharing TEXT NOT NULL,
    shared_by TEXT,
    notes TEXT,
    FOREIGN KEY(recruiter_id) REFERENCES recruiters(recruiter_id) ON DELETE CASCADE,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS government_job_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    job_id TEXT,
    advertisement_number TEXT,
    post_name TEXT NOT NULL,
    department TEXT NOT NULL,
    application_date TEXT NOT NULL,
    application_status TEXT NOT NULL DEFAULT 'APPLIED',
    exam_date TEXT,
    result_details TEXT,
    notes TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS private_job_applications (
    application_id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    job_id TEXT,
    company_employer TEXT NOT NULL,
    job_title TEXT NOT NULL,
    application_date TEXT NOT NULL,
    application_method TEXT,
    application_status TEXT NOT NULL DEFAULT 'APPLIED',
    interview_date TEXT,
    notes TEXT,
    FOREIGN KEY(candidate_id) REFERENCES candidates(candidate_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL,
    description TEXT
);

CREATE INDEX IF NOT EXISTS idx_candidates_mobile ON candidates(mobile);
CREATE INDEX IF NOT EXISTS idx_candidates_village ON candidates(village);
CREATE INDEX IF NOT EXISTS idx_candidates_sync_status ON candidates(sync_status);
CREATE INDEX IF NOT EXISTS idx_employment_status ON employment(status);
CREATE INDEX IF NOT EXISTS idx_locations_vaddo ON candidate_locations(vaddo);
CREATE INDEX IF NOT EXISTS idx_locations_village ON candidate_locations(village);
CREATE INDEX IF NOT EXISTS idx_locations_booth ON candidate_locations(booth);
CREATE INDEX IF NOT EXISTS idx_candidate_docs_cand ON candidate_documents(candidate_id);
CREATE INDEX IF NOT EXISTS idx_candidate_docs_type ON candidate_documents(document_type);
CREATE INDEX IF NOT EXISTS idx_candidate_docs_status ON candidate_documents(status);
CREATE INDEX IF NOT EXISTS idx_gov_jobs_status ON government_jobs(status);
CREATE INDEX IF NOT EXISTS idx_gov_jobs_dept ON government_jobs(department);
CREATE INDEX IF NOT EXISTS idx_private_jobs_status ON private_jobs(status);
CREATE INDEX IF NOT EXISTS idx_recruiters_verif ON recruiters(verification_status);
CREATE INDEX IF NOT EXISTS idx_candidate_consent ON candidate_consent(consent_status);
CREATE INDEX IF NOT EXISTS idx_shares_recruiter ON recruiter_candidate_shares(recruiter_id);
CREATE INDEX IF NOT EXISTS idx_shares_candidate ON recruiter_candidate_shares(candidate_id);
CREATE INDEX IF NOT EXISTS idx_audit_entity ON audit_log(entity_type, entity_id);
"""


class MigrationManager:
    """Manages versioned database schema migrations with automated pre-migration backups."""

    CURRENT_VERSION = 4

    @staticmethod
    def get_current_version(conn: sqlite3.Connection) -> int:
        """Returns the current schema version recorded in SQLite."""
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM schema_version")
            row = cursor.fetchone()
            if row and row[0] is not None:
                return int(row[0])
            return 0
        except Exception:
            return 0

    @staticmethod
    def create_pre_migration_backup(conn: sqlite3.Connection, target_version: int) -> str:
        """Creates an automated pre-migration SQLite backup before schema modifications."""
        try:
            from datetime import datetime
            import os
            from app.config import config
            backup_dir = config.get("backup_dir")
            os.makedirs(backup_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(
                backup_dir, f"pst_registry_backup_pre_migration_v{target_version}_{timestamp}.db"
            )
            backup_conn = sqlite3.connect(backup_file)
            conn.backup(backup_conn)
            backup_conn.close()
            logger.info("Created automated pre-migration backup: %s", backup_file)
            return backup_file
        except Exception as e:
            logger.warning("Could not create pre-migration backup via API: %s", e)
            return ""

    @classmethod
    def apply_migrations(cls, conn: sqlite3.Connection):
        """Applies versioned schema migrations safely with rollback on failure."""
        current_v = cls.get_current_version(conn)
        if current_v >= cls.CURRENT_VERSION:
            return

        from datetime import datetime
        cls.create_pre_migration_backup(conn, cls.CURRENT_VERSION)
        cursor = conn.cursor()
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if current_v < 1:
            try:
                cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
                cursor.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (1, now_str, "Initial baseline schema with Phase 1 candidate management")
                )
                conn.commit()
                current_v = 1
            except Exception as e:
                conn.rollback()
                logger.error("Migration to v1 failed: %s", e)
                raise e

        if current_v < 2:
            try:
                cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
                _migrate_existing_data(conn)
                cursor.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (2, now_str, "Phase 2 Employment Facilitation: Location, Documents, Jobs, Recruiters, Applications")
                )
                conn.commit()
                current_v = 2
                logger.info("Successfully applied database migration to version %d", current_v)
            except Exception as e:
                conn.rollback()
                logger.error("Migration to v2 failed: %s", e)
                raise e

        if current_v < 3:
            try:
                cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
                cursor.execute("PRAGMA table_info(candidates)")
                columns = [col[1] for col in cursor.fetchall()]
                if "is_demo" not in columns:
                    cursor.execute("ALTER TABLE candidates ADD COLUMN is_demo INTEGER NOT NULL DEFAULT 0;")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_is_demo ON candidates(is_demo);")
                cursor.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (3, now_str, "Demonstration data segregation flag (is_demo)")
                )
                conn.commit()
                current_v = 3
                logger.info("Successfully applied database migration to version %d", current_v)
            except Exception as e:
                conn.rollback()
                logger.error("Migration to v3 failed: %s", e)
                raise e

        if current_v < 4:
            try:
                cursor.execute("BEGIN IMMEDIATE TRANSACTION;")
                cursor.execute("PRAGMA table_info(candidates)")
                columns = [col[1] for col in cursor.fetchall()]
                if "intake_office" not in columns:
                    cursor.execute("ALTER TABLE candidates ADD COLUMN intake_office TEXT NOT NULL DEFAULT 'Pernem';")
                cursor.execute("UPDATE candidates SET intake_office = 'Korgao' WHERE candidate_id LIKE 'KPST-%';")
                cursor.execute("CREATE INDEX IF NOT EXISTS idx_candidates_office ON candidates(intake_office);")
                cursor.execute(
                    "INSERT OR REPLACE INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (4, now_str, "Add intake_office to candidates with Korgao (KPST) / Pernem (PST) segregation")
                )
                conn.commit()
                current_v = 4
                logger.info("Successfully applied database migration to version %d", current_v)
            except Exception as e:
                conn.rollback()
                logger.error("Migration to v4 failed: %s", e)
                raise e


def init_database(conn: sqlite3.Connection):
    """Initializes tables and indexes in SQLite, and performs versioned migrations."""
    try:
        conn.executescript(SCHEMA_SQL)
        MigrationManager.apply_migrations(conn)
        logger.info("Database schema initialized successfully with facilitation extensions.")
    except Exception as e:
        logger.error("Database schema initialization failed: %s", e)
        raise e


def _migrate_existing_data(conn: sqlite3.Connection):
    """Backfills location and consent defaults for pre-existing candidates if missing."""
    try:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR IGNORE INTO candidate_locations (candidate_id, house_building, vaddo, village, booth, taluka, pincode, full_address_landmark)
            SELECT candidate_id, '', '', village, '', taluka, pincode, address
            FROM candidates
            WHERE candidate_id NOT IN (SELECT candidate_id FROM candidate_locations)
            """
        )
        cursor.execute(
            """
            INSERT OR IGNORE INTO candidate_consent (candidate_id, consent_status, updated_at)
            SELECT candidate_id, 'Not Asked', updated_at
            FROM candidates
            WHERE candidate_id NOT IN (SELECT candidate_id FROM candidate_consent)
            """
        )
    except Exception as e:
        logger.warning("Migration data backfill warning: %s", e)


