"""
Repository layer providing transactional CRUD operations, sequential ID generation,
duplicate detection, and sync status tracking for Pedne Sewa Trust.
"""

import sqlite3
import re
import json
from datetime import datetime
from typing import List, Optional, Dict, Any
from app.constants import (
    SYNC_STATUS_PENDING,
    SYNC_STATUS_SYNCED,
    SYNC_STATUS_FAILED
)
from database.connection import db_manager
from database.schema import init_database
from models.candidate import Candidate, Education, Employment, EmploymentPreferences
from models.facilitation import (
    CandidateLocation, CandidateDocument, GovernmentJob, PrivateJob,
    Recruiter, CandidateConsent, RecruiterCandidateShare,
    GovernmentJobApplication, PrivateJobApplication, AuditEntry
)
from models.visitor import VisitorRecord
from utils.logger import logger
from utils.validators import clean_mobile


class CandidateRepository:
    """Handles all SQLite read/write operations for candidates."""

    def __init__(self, db_manager_instance=None):
        self.db = db_manager_instance or db_manager
        # Auto-initialize database schema
        with self.db.get_connection() as conn:
            init_database(conn)

    def generate_candidate_id(self, conn: sqlite3.Connection, office: str = "Pernem") -> str:
        """
        Generates the next unique sequential Candidate ID in format 'PST-000001' or 'KPST-000001'
        based on the intake office (Korgao -> KPST, Pernem -> PST).
        Must be called within an active transaction for concurrency safety.
        """
        from app.constants import OFFICE_KORGAO
        prefix = "KPST" if office == OFFICE_KORGAO or office == "KPST" else "PST"
        cursor = conn.cursor()
        if prefix == "KPST":
            cursor.execute("SELECT candidate_id FROM candidates WHERE candidate_id LIKE 'KPST-%' ORDER BY rowid DESC")
        else:
            cursor.execute("SELECT candidate_id FROM candidates WHERE candidate_id LIKE 'PST-%' AND candidate_id NOT LIKE 'KPST-%' ORDER BY rowid DESC")
        rows = cursor.fetchall()
        max_num = 0
        pattern = re.compile(rf"^{prefix}-(\d+)")
        for r in rows:
            cid = r["candidate_id"]
            match = pattern.search(cid)
            if match:
                val = int(match.group(1))
                if val > max_num:
                    max_num = val
        next_num = max_num + 1
        return f"{prefix}-{next_num:06d}"

    def check_duplicates(
        self,
        mobile: str,
        email: str = "",
        full_name: str = "",
        address: str = "",
        exclude_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Detects potential duplicate candidates using:
        - Mobile number
        - Email address (if provided)
        - Full Name + Mobile
        - Full Name + Address (if provided)
        """
        results = []
        clean_mob = clean_mobile(mobile)
        norm_name = full_name.strip().lower()
        norm_email = email.strip().lower() if email else ""
        norm_addr = address.strip().lower() if address else ""

        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            query = "SELECT candidate_id, full_name, mobile, email, village, address FROM candidates WHERE is_deleted = 0"
            params = []
            if exclude_id:
                query += " AND candidate_id != ?"
                params.append(exclude_id)

            cursor.execute(query, params)
            for row in cursor.fetchall():
                row_id = row["candidate_id"]
                row_mob = clean_mobile(row["mobile"] or "")
                row_name = (row["full_name"] or "").strip().lower()
                row_email = (row["email"] or "").strip().lower()
                row_addr = (row["address"] or "").strip().lower()

                match_reasons = []

                # Check 1: Exact mobile match
                if clean_mob and row_mob == clean_mob:
                    match_reasons.append("Exact Mobile Number match")

                # Check 2: Email match
                if norm_email and row_email and norm_email == row_email:
                    match_reasons.append("Exact Email match")

                # Check 3: Name + Mobile
                if norm_name and norm_name == row_name and clean_mob and clean_mob == row_mob:
                    if "Exact Mobile Number match" not in match_reasons:
                        match_reasons.append("Same Full Name & Mobile Number")

                # Check 4: Name + Address
                if norm_name and norm_addr and norm_name == row_name and norm_addr == row_addr:
                    match_reasons.append("Same Full Name & Address")

                if match_reasons:
                    results.append({
                        "candidate_id": row_id,
                        "full_name": row["full_name"],
                        "mobile": row["mobile"],
                        "email": row["email"],
                        "village": row["village"],
                        "address": row["address"],
                        "reasons": match_reasons
                    })

        return results

    def save_candidate(self, candidate: Candidate) -> Candidate:
        """
        Atomically saves candidate into SQLite across all 4 tables.
        Generates Candidate ID if empty, sets sync_status to PENDING.
        """
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            if not candidate.candidate_id:
                candidate.candidate_id = self.generate_candidate_id(conn, office=getattr(candidate, "intake_office", "Pernem"))

            candidate.created_at = candidate.created_at or now
            candidate.updated_at = now
            candidate.sync_status = SYNC_STATUS_PENDING

            # 1. Insert into candidates
            conn.execute(
                """
                INSERT INTO candidates (
                    candidate_id, full_name, dob, age, gender, address,
                    village, taluka, pincode, mobile, alternate_mobile, email,
                    created_at, updated_at, sync_status, last_synced_at, is_deleted, is_demo,
                    intake_office
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    candidate.full_name.strip(),
                    candidate.dob or "",
                    candidate.age,
                    candidate.gender or "",
                    candidate.address or "",
                    candidate.village.strip(),
                    candidate.taluka.strip() or "Pernem",
                    candidate.pincode or "",
                    candidate.mobile.strip(),
                    candidate.alternate_mobile or "",
                    candidate.email or "",
                    candidate.created_at,
                    candidate.updated_at,
                    candidate.sync_status,
                    candidate.last_synced_at,
                    1 if candidate.is_deleted else 0,
                    1 if candidate.is_demo else 0,
                    getattr(candidate, "intake_office", "Pernem") or "Pernem"
                )
            )

            # 2. Insert into education
            edu = candidate.education
            conn.execute(
                """
                INSERT INTO education (
                    candidate_id, highest_qualification, degree_course, specialisation,
                    institution, passing_year, additional_qualifications, certifications, skills
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    edu.highest_qualification or "",
                    edu.degree_course or "",
                    edu.specialisation or "",
                    edu.institution or "",
                    edu.passing_year,
                    edu.additional_qualifications or "",
                    edu.certifications or "",
                    edu.skills or ""
                )
            )

            # 3. Insert into employment
            emp = candidate.employment
            conn.execute(
                """
                INSERT INTO employment (
                    candidate_id, status, category, department_company, designation,
                    work_location, years_experience, previous_experience, current_salary,
                    govt_applied, govt_post_exam, govt_department, govt_app_year,
                    govt_result_status, govt_remarks, self_emp_business_nature,
                    self_emp_location, self_emp_years_active, self_emp_employees_count,
                    self_emp_monthly_income, student_current_course, student_institution,
                    student_expected_year, student_interested_in_employment
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    emp.status or "UNEMPLOYED",
                    emp.category or "",
                    emp.department_company or "",
                    emp.designation or "",
                    emp.work_location or "",
                    emp.years_experience or 0.0,
                    emp.previous_experience or "",
                    emp.current_salary,
                    1 if emp.govt_applied else 0,
                    emp.govt_post_exam or "",
                    emp.govt_department or "",
                    emp.govt_app_year,
                    emp.govt_result_status or "",
                    emp.govt_remarks or "",
                    emp.self_emp_business_nature or "",
                    emp.self_emp_location or "",
                    emp.self_emp_years_active,
                    emp.self_emp_employees_count,
                    emp.self_emp_monthly_income,
                    emp.student_current_course or "",
                    emp.student_institution or "",
                    emp.student_expected_year,
                    1 if emp.student_interested_in_employment else 0
                )
            )

            # 4. Insert into employment_preferences
            pref = candidate.preferences
            conn.execute(
                """
                INSERT INTO employment_preferences (
                    candidate_id, preferred_sector, preferred_role, preferred_location,
                    willing_to_relocate, preferred_employment_type, languages_known,
                    skills_list, certifications_list, total_experience_years,
                    previous_employers, remarks
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    candidate.candidate_id,
                    pref.preferred_sector or "",
                    pref.preferred_role or "",
                    pref.preferred_location or "",
                    1 if pref.willing_to_relocate else 0,
                    pref.preferred_employment_type or "Full-Time",
                    pref.languages_known or "",
                    pref.skills_list or "",
                    pref.certifications_list or "",
                    pref.total_experience_years or 0.0,
                    pref.previous_employers or "",
                    pref.remarks or ""
                )
            )

            # 5. Insert or update location
            if candidate.location:
                candidate.location.candidate_id = candidate.candidate_id
                self.save_candidate_location(candidate.location, conn=conn)
            else:
                self.save_candidate_location(CandidateLocation(
                    candidate_id=candidate.candidate_id,
                    village=candidate.village,
                    taluka=candidate.taluka,
                    pincode=candidate.pincode or "",
                    full_address_landmark=candidate.address or ""
                ), conn=conn)

            # 6. Insert or update consent
            if candidate.consent:
                candidate.consent.candidate_id = candidate.candidate_id
                self.save_candidate_consent(candidate.consent, actor="System", conn=conn)
            else:
                conn.execute(
                    "INSERT OR IGNORE INTO candidate_consent (candidate_id, consent_status, updated_at) VALUES (?, 'Not Asked', ?)",
                    (candidate.candidate_id, now)
                )

            # 7. Audit log
            self.log_audit(
                "Candidate", candidate.candidate_id, "CREATE",
                "", candidate.full_name, "System", "Candidate registered", conn=conn
            )

        logger.info("Candidate %s saved successfully to SQLite with status PENDING", candidate.candidate_id)
        return candidate

    def update_candidate(self, candidate: Candidate) -> bool:
        """
        Updates an existing candidate across all tables and re-marks status as PENDING.
        """
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            candidate.updated_at = now
            candidate.sync_status = SYNC_STATUS_PENDING

            # 1. Update candidates table
            conn.execute(
                """
                UPDATE candidates SET
                    full_name = ?, dob = ?, age = ?, gender = ?, address = ?,
                    village = ?, taluka = ?, pincode = ?, mobile = ?, alternate_mobile = ?,
                    email = ?, updated_at = ?, sync_status = ?, is_deleted = ?,
                    intake_office = ?
                WHERE candidate_id = ?
                """,
                (
                    candidate.full_name.strip(),
                    candidate.dob or "",
                    candidate.age,
                    candidate.gender or "",
                    candidate.address or "",
                    candidate.village.strip(),
                    candidate.taluka.strip() or "Pernem",
                    candidate.pincode or "",
                    candidate.mobile.strip(),
                    candidate.alternate_mobile or "",
                    candidate.email or "",
                    candidate.updated_at,
                    candidate.sync_status,
                    1 if candidate.is_deleted else 0,
                    getattr(candidate, "intake_office", "Pernem") or "Pernem",
                    candidate.candidate_id
                )
            )

            # 2. Update education
            edu = candidate.education
            conn.execute(
                """
                UPDATE education SET
                    highest_qualification = ?, degree_course = ?, specialisation = ?,
                    institution = ?, passing_year = ?, additional_qualifications = ?,
                    certifications = ?, skills = ?
                WHERE candidate_id = ?
                """,
                (
                    edu.highest_qualification or "",
                    edu.degree_course or "",
                    edu.specialisation or "",
                    edu.institution or "",
                    edu.passing_year,
                    edu.additional_qualifications or "",
                    edu.certifications or "",
                    edu.skills or "",
                    candidate.candidate_id
                )
            )

            # 3. Update employment
            emp = candidate.employment
            conn.execute(
                """
                UPDATE employment SET
                    status = ?, category = ?, department_company = ?, designation = ?,
                    work_location = ?, years_experience = ?, previous_experience = ?,
                    current_salary = ?, govt_applied = ?, govt_post_exam = ?,
                    govt_department = ?, govt_app_year = ?, govt_result_status = ?,
                    govt_remarks = ?, self_emp_business_nature = ?, self_emp_location = ?,
                    self_emp_years_active = ?, self_emp_employees_count = ?,
                    self_emp_monthly_income = ?, student_current_course = ?,
                    student_institution = ?, student_expected_year = ?,
                    student_interested_in_employment = ?
                WHERE candidate_id = ?
                """,
                (
                    emp.status or "UNEMPLOYED",
                    emp.category or "",
                    emp.department_company or "",
                    emp.designation or "",
                    emp.work_location or "",
                    emp.years_experience or 0.0,
                    emp.previous_experience or "",
                    emp.current_salary,
                    1 if emp.govt_applied else 0,
                    emp.govt_post_exam or "",
                    emp.govt_department or "",
                    emp.govt_app_year,
                    emp.govt_result_status or "",
                    emp.govt_remarks or "",
                    emp.self_emp_business_nature or "",
                    emp.self_emp_location or "",
                    emp.self_emp_years_active,
                    emp.self_emp_employees_count,
                    emp.self_emp_monthly_income,
                    emp.student_current_course or "",
                    emp.student_institution or "",
                    emp.student_expected_year,
                    1 if emp.student_interested_in_employment else 0,
                    candidate.candidate_id
                )
            )

            # 4. Update preferences
            pref = candidate.preferences
            conn.execute(
                """
                UPDATE employment_preferences SET
                    preferred_sector = ?, preferred_role = ?, preferred_location = ?,
                    willing_to_relocate = ?, preferred_employment_type = ?,
                    languages_known = ?, skills_list = ?, certifications_list = ?,
                    total_experience_years = ?, previous_employers = ?, remarks = ?
                WHERE candidate_id = ?
                """,
                (
                    pref.preferred_sector or "",
                    pref.preferred_role or "",
                    pref.preferred_location or "",
                    1 if pref.willing_to_relocate else 0,
                    pref.preferred_employment_type or "Full-Time",
                    pref.languages_known or "",
                    pref.skills_list or "",
                    pref.certifications_list or "",
                    pref.total_experience_years or 0.0,
                    pref.previous_employers or "",
                    pref.remarks or "",
                    candidate.candidate_id
                )
            )

            # 5. Update location
            if candidate.location:
                candidate.location.candidate_id = candidate.candidate_id
                self.save_candidate_location(candidate.location, conn=conn)

            # 6. Update consent
            if candidate.consent:
                candidate.consent.candidate_id = candidate.candidate_id
                self.save_candidate_consent(candidate.consent, actor="System", conn=conn)

            # 7. Audit log
            self.log_audit(
                "Candidate", candidate.candidate_id, "UPDATE",
                "", candidate.full_name, "System", "Candidate updated", conn=conn
            )

        logger.info("Candidate %s updated successfully, re-marked as PENDING", candidate.candidate_id)
        return True

    def delete_candidate(self, candidate_id: str) -> bool:
        """Deletes candidate by ID."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM candidates WHERE candidate_id = ?", (candidate_id,))
            self.log_audit("Candidate", candidate_id, "DELETE", "", "", "System", "Candidate deleted", conn=conn)
        logger.info("Candidate %s deleted successfully from SQLite", candidate_id)
        return True

    def get_candidate(self, candidate_id: str) -> Optional[Candidate]:
        """Loads complete candidate entity by ID."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM candidates WHERE candidate_id = ?", (candidate_id,))
            c_row = cursor.fetchone()
            if not c_row:
                return None

            cursor.execute("SELECT * FROM education WHERE candidate_id = ?", (candidate_id,))
            e_row = cursor.fetchone()

            cursor.execute("SELECT * FROM employment WHERE candidate_id = ?", (candidate_id,))
            emp_row = cursor.fetchone()

            cursor.execute("SELECT * FROM employment_preferences WHERE candidate_id = ?", (candidate_id,))
            p_row = cursor.fetchone()

            cursor.execute("SELECT * FROM candidate_locations WHERE candidate_id = ?", (candidate_id,))
            loc_row = cursor.fetchone()

            cursor.execute("SELECT * FROM candidate_consent WHERE candidate_id = ?", (candidate_id,))
            con_row = cursor.fetchone()

            return self._build_candidate(c_row, e_row, emp_row, p_row, loc_row, con_row)

    def _build_candidate(self, c_row, e_row, emp_row, p_row, loc_row=None, con_row=None) -> Candidate:
        if "intake_office" in c_row.keys() and c_row["intake_office"]:
            intake_office = c_row["intake_office"]
        else:
            cid = c_row["candidate_id"] or ""
            intake_office = "Korgao" if cid.startswith("KPST") else "Pernem"

        cand = Candidate(
            candidate_id=c_row["candidate_id"],
            full_name=c_row["full_name"],
            dob=c_row["dob"] or "",
            age=c_row["age"],
            gender=c_row["gender"] or "",
            address=c_row["address"] or "",
            village=c_row["village"],
            taluka=c_row["taluka"],
            pincode=c_row["pincode"] or "",
            mobile=c_row["mobile"],
            alternate_mobile=c_row["alternate_mobile"] or "",
            email=c_row["email"] or "",
            created_at=c_row["created_at"],
            updated_at=c_row["updated_at"],
            sync_status=c_row["sync_status"],
            last_synced_at=c_row["last_synced_at"],
            is_deleted=bool(c_row["is_deleted"]),
            is_demo=bool(c_row["is_demo"]) if "is_demo" in c_row.keys() else False,
            intake_office=intake_office
        )

        if e_row:
            cand.education = Education(
                highest_qualification=e_row["highest_qualification"] or "",
                degree_course=e_row["degree_course"] or "",
                specialisation=e_row["specialisation"] or "",
                institution=e_row["institution"] or "",
                passing_year=e_row["passing_year"],
                additional_qualifications=e_row["additional_qualifications"] or "",
                certifications=e_row["certifications"] or "",
                skills=e_row["skills"] or ""
            )

        if emp_row:
            cand.employment = Employment(
                status=emp_row["status"] or "UNEMPLOYED",
                category=emp_row["category"] or "",
                department_company=emp_row["department_company"] or "",
                designation=emp_row["designation"] or "",
                work_location=emp_row["work_location"] or "",
                years_experience=emp_row["years_experience"] or 0.0,
                previous_experience=emp_row["previous_experience"] or "",
                current_salary=emp_row["current_salary"],
                govt_applied=bool(emp_row["govt_applied"]),
                govt_post_exam=emp_row["govt_post_exam"] or "",
                govt_department=emp_row["govt_department"] or "",
                govt_app_year=emp_row["govt_app_year"],
                govt_result_status=emp_row["govt_result_status"] or "",
                govt_remarks=emp_row["govt_remarks"] or "",
                self_emp_business_nature=emp_row["self_emp_business_nature"] or "",
                self_emp_location=emp_row["self_emp_location"] or "",
                self_emp_years_active=emp_row["self_emp_years_active"],
                self_emp_employees_count=emp_row["self_emp_employees_count"],
                self_emp_monthly_income=emp_row["self_emp_monthly_income"],
                student_current_course=emp_row["student_current_course"] or "",
                student_institution=emp_row["student_institution"] or "",
                student_expected_year=emp_row["student_expected_year"],
                student_interested_in_employment=bool(emp_row["student_interested_in_employment"])
            )

        if p_row:
            cand.preferences = EmploymentPreferences(
                preferred_sector=p_row["preferred_sector"] or "",
                preferred_role=p_row["preferred_role"] or "",
                preferred_location=p_row["preferred_location"] or "",
                willing_to_relocate=bool(p_row["willing_to_relocate"]),
                preferred_employment_type=p_row["preferred_employment_type"] or "Full-Time",
                languages_known=p_row["languages_known"] or "",
                skills_list=p_row["skills_list"] or "",
                certifications_list=p_row["certifications_list"] or "",
                total_experience_years=p_row["total_experience_years"] or 0.0,
                previous_employers=p_row["previous_employers"] or "",
                remarks=p_row["remarks"] or ""
            )

        if loc_row:
            cand.location = CandidateLocation(
                candidate_id=loc_row["candidate_id"],
                house_building=loc_row["house_building"] or "",
                vaddo=loc_row["vaddo"] or "",
                village=loc_row["village"] or cand.village,
                booth=loc_row["booth"] or "",
                taluka=loc_row["taluka"] or cand.taluka,
                pincode=loc_row["pincode"] or cand.pincode,
                full_address_landmark=loc_row["full_address_landmark"] or cand.address
            )
        else:
            cand.location = CandidateLocation(
                candidate_id=cand.candidate_id,
                village=cand.village,
                taluka=cand.taluka,
                pincode=cand.pincode,
                full_address_landmark=cand.address
            )

        if con_row:
            cand.consent = CandidateConsent(
                candidate_id=con_row["candidate_id"],
                consent_status=con_row["consent_status"] or "Not Asked",
                consent_date=con_row["consent_date"] or "",
                consent_method=con_row["consent_method"] or "",
                consent_notes=con_row["consent_notes"] or "",
                updated_at=con_row["updated_at"] or ""
            )
        else:
            cand.consent = CandidateConsent(
                candidate_id=cand.candidate_id,
                consent_status="Not Asked"
            )

        return cand

    def get_all_candidates(self, include_deleted: bool = False) -> List[Candidate]:
        """Loads all candidates with full child entities."""
        candidates = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            del_clause = "" if include_deleted else "WHERE c.is_deleted = 0"
            sql = f"""
            SELECT c.*,
                   e.highest_qualification, e.degree_course, e.specialisation, e.institution,
                   e.passing_year, e.additional_qualifications, e.certifications, e.skills as edu_skills,
                   emp.status as emp_status, emp.category, emp.department_company, emp.designation,
                   emp.work_location, emp.years_experience, emp.previous_experience, emp.current_salary,
                   emp.govt_applied, emp.govt_post_exam, emp.govt_department, emp.govt_app_year,
                   emp.govt_result_status, emp.govt_remarks, emp.self_emp_business_nature,
                   emp.self_emp_location, emp.self_emp_years_active, emp.self_emp_employees_count,
                   emp.self_emp_monthly_income, emp.student_current_course, emp.student_institution,
                   emp.student_expected_year, emp.student_interested_in_employment,
                   p.preferred_sector, p.preferred_role, p.preferred_location,
                   p.willing_to_relocate, p.preferred_employment_type, p.languages_known,
                   p.skills_list, p.certifications_list, p.total_experience_years,
                   p.previous_employers, p.remarks,
                   loc.house_building, loc.vaddo, loc.booth, loc.full_address_landmark,
                   con.consent_status, con.consent_date, con.consent_method, con.consent_notes, con.updated_at as consent_updated_at
            FROM candidates c
            LEFT JOIN education e ON c.candidate_id = e.candidate_id
            LEFT JOIN employment emp ON c.candidate_id = emp.candidate_id
            LEFT JOIN employment_preferences p ON c.candidate_id = p.candidate_id
            LEFT JOIN candidate_locations loc ON c.candidate_id = loc.candidate_id
            LEFT JOIN candidate_consent con ON c.candidate_id = con.candidate_id
            {del_clause}
            ORDER BY c.rowid DESC
            """
            cursor.execute(sql)
            for row in cursor.fetchall():
                if "intake_office" in row.keys() and row["intake_office"]:
                    intake_office = row["intake_office"]
                else:
                    cid = row["candidate_id"] or ""
                    intake_office = "Korgao" if cid.startswith("KPST") else "Pernem"

                cand = Candidate(
                    candidate_id=row["candidate_id"],
                    full_name=row["full_name"],
                    dob=row["dob"] or "",
                    age=row["age"],
                    gender=row["gender"] or "",
                    address=row["address"] or "",
                    village=row["village"],
                    taluka=row["taluka"],
                    pincode=row["pincode"] or "",
                    mobile=row["mobile"],
                    alternate_mobile=row["alternate_mobile"] or "",
                    email=row["email"] or "",
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    sync_status=row["sync_status"],
                    last_synced_at=row["last_synced_at"],
                    is_deleted=bool(row["is_deleted"]),
                    is_demo=bool(row["is_demo"]) if "is_demo" in row.keys() else False,
                    intake_office=intake_office
                )
                cand.education = Education(
                    highest_qualification=row["highest_qualification"] or "",
                    degree_course=row["degree_course"] or "",
                    specialisation=row["specialisation"] or "",
                    institution=row["institution"] or "",
                    passing_year=row["passing_year"],
                    additional_qualifications=row["additional_qualifications"] or "",
                    certifications=row["certifications"] or "",
                    skills=row["edu_skills"] or ""
                )
                cand.employment = Employment(
                    status=row["emp_status"] or "UNEMPLOYED",
                    category=row["category"] or "",
                    department_company=row["department_company"] or "",
                    designation=row["designation"] or "",
                    work_location=row["work_location"] or "",
                    years_experience=row["years_experience"] or 0.0,
                    previous_experience=row["previous_experience"] or "",
                    current_salary=row["current_salary"],
                    govt_applied=bool(row["govt_applied"]),
                    govt_post_exam=row["govt_post_exam"] or "",
                    govt_department=row["govt_department"] or "",
                    govt_app_year=row["govt_app_year"],
                    govt_result_status=row["govt_result_status"] or "",
                    govt_remarks=row["govt_remarks"] or "",
                    self_emp_business_nature=row["self_emp_business_nature"] or "",
                    self_emp_location=row["self_emp_location"] or "",
                    self_emp_years_active=row["self_emp_years_active"],
                    self_emp_employees_count=row["self_emp_employees_count"],
                    self_emp_monthly_income=row["self_emp_monthly_income"],
                    student_current_course=row["student_current_course"] or "",
                    student_institution=row["student_institution"] or "",
                    student_expected_year=row["student_expected_year"],
                    student_interested_in_employment=bool(row["student_interested_in_employment"])
                )
                cand.preferences = EmploymentPreferences(
                    preferred_sector=row["preferred_sector"] or "",
                    preferred_role=row["preferred_role"] or "",
                    preferred_location=row["preferred_location"] or "",
                    willing_to_relocate=bool(row["willing_to_relocate"]),
                    preferred_employment_type=row["preferred_employment_type"] or "Full-Time",
                    languages_known=row["languages_known"] or "",
                    skills_list=row["skills_list"] or "",
                    certifications_list=row["certifications_list"] or "",
                    total_experience_years=row["total_experience_years"] or 0.0,
                    previous_employers=row["previous_employers"] or "",
                    remarks=row["remarks"] or ""
                )
                cand.location = CandidateLocation(
                    candidate_id=row["candidate_id"],
                    house_building=row["house_building"] or "",
                    vaddo=row["vaddo"] or "",
                    village=row["village"],
                    booth=row["booth"] or "",
                    taluka=row["taluka"],
                    pincode=row["pincode"] or "",
                    full_address_landmark=row["full_address_landmark"] or (row["address"] or "")
                )
                cand.consent = CandidateConsent(
                    candidate_id=row["candidate_id"],
                    consent_status=row["consent_status"] or "Not Asked",
                    consent_date=row["consent_date"] or "",
                    consent_method=row["consent_method"] or "",
                    consent_notes=row["consent_notes"] or "",
                    updated_at=row["consent_updated_at"] or ""
                )
                candidates.append(cand)


        return candidates

    def get_pending_sync_candidates(self) -> List[Candidate]:
        """Returns all candidates with sync_status in ('PENDING', 'FAILED')."""
        all_cands = self.get_all_candidates(include_deleted=False)
        return [c for c in all_cands if c.sync_status in (SYNC_STATUS_PENDING, SYNC_STATUS_FAILED)]

    def mark_candidates_synced(self, candidate_ids: List[str], synced_at: str):
        """Marks a list of candidate IDs as SYNCED with timestamp."""
        if not candidate_ids:
            return
        with self.db.transaction() as conn:
            placeholders = ",".join(["?"] * len(candidate_ids))
            sql = f"UPDATE candidates SET sync_status = '{SYNC_STATUS_SYNCED}', last_synced_at = ? WHERE candidate_id IN ({placeholders})"
            params = [synced_at] + candidate_ids
            conn.execute(sql, params)
        logger.info("Marked %d candidates as SYNCED", len(candidate_ids))

    def mark_candidate_sync_failed(self, candidate_id: str, error_msg: str):
        """Marks candidate as FAILED with error details."""
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE candidates SET sync_status = '{SYNC_STATUS_FAILED}' WHERE candidate_id = ?",
                (candidate_id,)
            )
        logger.warning("Candidate %s marked as sync FAILED: %s", candidate_id, error_msg)

    def count_demo_candidates(self) -> int:
        """Returns the total number of demo candidates currently in the database."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM candidates WHERE is_demo = 1 AND is_deleted = 0")
            row = cursor.fetchone()
            return row[0] if row else 0

    def remove_demo_candidates(self) -> int:
        """
        Safely deletes all demonstration candidates (is_demo = 1) and their associated child records.
        Does not disturb any genuine candidate registrations.
        """
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT candidate_id FROM candidates WHERE is_demo = 1")
            demo_ids = [r[0] for r in cursor.fetchall()]
            if not demo_ids:
                return 0

            placeholders = ",".join("?" for _ in demo_ids)
            conn.execute(f"DELETE FROM education WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM employment WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM employment_preferences WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM candidate_locations WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM candidate_documents WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM candidate_consent WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM recruiter_candidate_shares WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM government_job_applications WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute(f"DELETE FROM private_job_applications WHERE candidate_id IN ({placeholders})", demo_ids)
            conn.execute("DELETE FROM candidates WHERE is_demo = 1")

            self.log_audit("System", "ALL_DEMO", "DELETE", "", f"{len(demo_ids)} records", "Admin", "Removed demonstration candidates", conn=conn)

        logger.info("Successfully removed %d demonstration candidates.", len(demo_ids))
        return len(demo_ids)

    def log_sync_event(
        self,
        records_pushed: int,
        records_failed: int,
        status: str,
        error_message: str = "",
        details: str = ""
    ):
        """Records a sync cycle outcome in synchronisation_log table."""
        now = datetime.now().isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO synchronisation_log (
                    timestamp, records_pushed, records_failed, status, error_message, details
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (now, records_pushed, records_failed, status, error_message, details)
            )

    def get_sync_logs(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves recent synchronisation logs."""
        logs = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM synchronisation_log ORDER BY id DESC LIMIT ?", (limit,))
            for row in cursor.fetchall():
                logs.append(dict(row))
        return logs

    def get_sync_statistics(self) -> Dict[str, Any]:
        """Computes aggregate cloud sync stats."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) as total FROM candidates WHERE is_deleted = 0")
            total = cursor.fetchone()["total"]

            cursor.execute("SELECT COUNT(*) as synced FROM candidates WHERE sync_status = 'SYNCED' AND is_deleted = 0")
            synced = cursor.fetchone()["synced"]

            cursor.execute("SELECT COUNT(*) as pending FROM candidates WHERE sync_status = 'PENDING' AND is_deleted = 0")
            pending = cursor.fetchone()["pending"]

            cursor.execute("SELECT COUNT(*) as failed FROM candidates WHERE sync_status = 'FAILED' AND is_deleted = 0")
            failed = cursor.fetchone()["failed"]

            cursor.execute("SELECT timestamp, status, error_message FROM synchronisation_log ORDER BY id DESC LIMIT 1")
            last_log = cursor.fetchone()

            cursor.execute("SELECT timestamp FROM synchronisation_log WHERE status = 'SUCCESS' ORDER BY id DESC LIMIT 1")
            last_success = cursor.fetchone()

        return {
            "total_candidates": total,
            "synced_count": synced,
            "pending_count": pending,
            "failed_count": failed,
            "last_attempted_sync": last_log["timestamp"] if last_log else None,
            "last_successful_sync": last_success["timestamp"] if last_success else None,
            "last_error": last_log["error_message"] if (last_log and last_log["status"] != "SUCCESS") else ""
        }

    # =========================================================================
    # AUDIT LOGGING
    # =========================================================================
    def log_audit(
        self,
        entity_type: str,
        entity_id: str,
        action: str,
        old_val: str = "",
        new_val: str = "",
        user_action: str = "System",
        notes: str = "",
        conn: Optional[sqlite3.Connection] = None
    ) -> int:
        """Records an immutable audit event."""
        now = datetime.now().isoformat()
        sql = """
        INSERT INTO audit_log (timestamp, user_action, entity_type, entity_id, action, old_value, new_value, notes)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (now, user_action, entity_type, entity_id, action, old_val, new_val, notes)

        if conn is not None:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            return cursor.lastrowid
        else:
            with self.db.transaction() as c:
                cursor = c.cursor()
                cursor.execute(sql, params)
                return cursor.lastrowid

    def get_audit_logs(
        self,
        entity_type: Optional[str] = None,
        entity_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Retrieves recent audit log records."""
        query = "SELECT * FROM audit_log WHERE 1=1"
        params = []
        if entity_type:
            query += " AND entity_type = ?"
            params.append(entity_type)
        if entity_id:
            query += " AND entity_id = ?"
            params.append(entity_id)
        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        logs = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                logs.append(AuditEntry(
                    id=row["id"],
                    timestamp=row["timestamp"],
                    user_action=row["user_action"] or "",
                    entity_type=row["entity_type"],
                    entity_id=row["entity_id"],
                    action=row["action"],
                    old_value=row["old_value"] or "",
                    new_value=row["new_value"] or "",
                    notes=row["notes"] or ""
                ))
        return logs

    # =========================================================================
    # CANDIDATE LOCATION (VADDO & BOOTH INDEPENDENT)
    # =========================================================================
    def save_candidate_location(self, loc: CandidateLocation, conn: Optional[sqlite3.Connection] = None):
        """Saves or updates independent location details (house, vaddo, booth)."""
        sql = """
        INSERT INTO candidate_locations (
            candidate_id, house_building, vaddo, village, booth, taluka, pincode, full_address_landmark
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_id) DO UPDATE SET
            house_building = excluded.house_building,
            vaddo = excluded.vaddo,
            village = excluded.village,
            booth = excluded.booth,
            taluka = excluded.taluka,
            pincode = excluded.pincode,
            full_address_landmark = excluded.full_address_landmark
        """
        params = (
            loc.candidate_id,
            loc.house_building or "",
            loc.vaddo or "",
            loc.village or "",
            loc.booth or "",
            loc.taluka or "Pernem",
            loc.pincode or "",
            loc.full_address_landmark or ""
        )
        if conn is not None:
            conn.execute(sql, params)
        else:
            with self.db.transaction() as c:
                c.execute(sql, params)

    def get_candidate_location(self, candidate_id: str) -> Optional[CandidateLocation]:
        """Retrieves location record for a candidate."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM candidate_locations WHERE candidate_id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CandidateLocation(
                candidate_id=row["candidate_id"],
                house_building=row["house_building"] or "",
                vaddo=row["vaddo"] or "",
                village=row["village"] or "",
                booth=row["booth"] or "",
                taluka=row["taluka"] or "Pernem",
                pincode=row["pincode"] or "",
                full_address_landmark=row["full_address_landmark"] or ""
            )

    def search_candidates_by_location(
        self,
        vaddo: str = "",
        booth: str = "",
        village: str = ""
    ) -> List[Candidate]:
        """
        Filters candidates independently by vaddo, booth, or village.
        Vaddo and booth are completely independent.
        """
        all_cands = self.get_all_candidates()
        results = []
        norm_vaddo = vaddo.strip().lower()
        norm_booth = booth.strip().lower()
        norm_village = village.strip().lower()

        for c in all_cands:
            loc = c.location
            c_vaddo = (loc.vaddo if loc else "").lower()
            c_booth = (loc.booth if loc else "").lower()
            c_village = (c.village or (loc.village if loc else "")).lower()

            if norm_vaddo and norm_vaddo not in c_vaddo:
                continue
            if norm_booth and norm_booth not in c_booth:
                continue
            if norm_village and norm_village not in c_village:
                continue
            results.append(c)
        return results

    # =========================================================================
    # CANDIDATE DOCUMENT INVENTORY
    # =========================================================================
    def save_candidate_document(self, doc: CandidateDocument, conn: Optional[sqlite3.Connection] = None) -> CandidateDocument:
        """Saves a document inventory item."""
        now = datetime.now().isoformat()
        doc.updated_at = now
        sql = """
        INSERT INTO candidate_documents (
            candidate_id, document_type, document_category, status, issue_date,
            expiry_date, application_date, reference_number, expected_availability_date,
            verification_status, notes, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            doc.candidate_id, doc.document_type, doc.document_category, doc.status,
            doc.issue_date or "", doc.expiry_date or "", doc.application_date or "",
            doc.reference_number or "", doc.expected_availability_date or "",
            doc.verification_status or "Not Checked", doc.notes or "", doc.updated_at
        )
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            doc.id = cursor.lastrowid
        else:
            with self.db.transaction() as c:
                cursor = c.cursor()
                cursor.execute(sql, params)
                doc.id = cursor.lastrowid
        return doc

    def save_candidate_documents_bulk(self, candidate_id: str, docs: List[CandidateDocument]):
        """Replaces or saves bulk document inventory for a candidate."""
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM candidate_documents WHERE candidate_id = ?", (candidate_id,))
            for d in docs:
                d.candidate_id = candidate_id
                self.save_candidate_document(d, conn=conn)

    def get_candidate_documents(self, candidate_id: str) -> List[CandidateDocument]:
        """Loads all documents for a candidate."""
        docs = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM candidate_documents WHERE candidate_id = ? ORDER BY document_category, document_type",
                (candidate_id,)
            )
            for r in cursor.fetchall():
                docs.append(CandidateDocument(
                    id=r["id"],
                    candidate_id=r["candidate_id"],
                    document_type=r["document_type"],
                    document_category=r["document_category"],
                    status=r["status"],
                    issue_date=r["issue_date"] or "",
                    expiry_date=r["expiry_date"] or "",
                    application_date=r["application_date"] or "",
                    reference_number=r["reference_number"] or "",
                    expected_availability_date=r["expected_availability_date"] or "",
                    verification_status=r["verification_status"] or "Not Checked",
                    notes=r["notes"] or "",
                    updated_at=r["updated_at"] or ""
                ))
        return docs

    def delete_candidate_document(self, doc_id: int) -> bool:
        with self.db.transaction() as conn:
            conn.execute("DELETE FROM candidate_documents WHERE id = ?", (doc_id,))
        return True

    # =========================================================================
    # GOVERNMENT JOBS
    # =========================================================================
    def save_government_job(self, job: GovernmentJob) -> GovernmentJob:
        """Saves or updates a government job opportunity."""
        req_docs_json = json.dumps(job.required_documents) if isinstance(job.required_documents, list) else (job.required_documents or "[]")
        sql = """
        INSERT INTO government_jobs (
            job_id, source, advertisement_number, department, post_name, vacancies_count,
            employment_type, pay_level_salary, minimum_qualification, preferred_qualification,
            experience_requirement_years, age_limit_min, age_limit_max, gender_requirement,
            category_reservation, konkani_marathi_required, required_documents,
            application_start_date, application_closing_date, application_method,
            official_ad_url, official_apply_url, ad_pdf_url, last_checked_at,
            source_last_updated_at, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            source = excluded.source,
            advertisement_number = excluded.advertisement_number,
            department = excluded.department,
            post_name = excluded.post_name,
            vacancies_count = excluded.vacancies_count,
            employment_type = excluded.employment_type,
            pay_level_salary = excluded.pay_level_salary,
            minimum_qualification = excluded.minimum_qualification,
            preferred_qualification = excluded.preferred_qualification,
            experience_requirement_years = excluded.experience_requirement_years,
            age_limit_min = excluded.age_limit_min,
            age_limit_max = excluded.age_limit_max,
            gender_requirement = excluded.gender_requirement,
            category_reservation = excluded.category_reservation,
            konkani_marathi_required = excluded.konkani_marathi_required,
            required_documents = excluded.required_documents,
            application_start_date = excluded.application_start_date,
            application_closing_date = excluded.application_closing_date,
            application_method = excluded.application_method,
            official_ad_url = excluded.official_ad_url,
            official_apply_url = excluded.official_apply_url,
            ad_pdf_url = excluded.ad_pdf_url,
            last_checked_at = excluded.last_checked_at,
            source_last_updated_at = excluded.source_last_updated_at,
            status = excluded.status
        """
        params = (
            job.job_id, job.source, job.advertisement_number or "", job.department,
            job.post_name, job.vacancies_count, job.employment_type or "Regular / Permanent",
            job.pay_level_salary or "", job.minimum_qualification or "", job.preferred_qualification or "",
            job.experience_requirement_years or 0.0, job.age_limit_min, job.age_limit_max,
            job.gender_requirement or "Any", job.category_reservation or "",
            job.konkani_marathi_required or "Konkani Essential, Marathi Desirable",
            req_docs_json, job.application_start_date or "", job.application_closing_date or "",
            job.application_method or "Online", job.official_ad_url or "", job.official_apply_url or "",
            job.ad_pdf_url or "", job.last_checked_at, job.source_last_updated_at or "", job.status or "OPEN"
        )
        with self.db.transaction() as conn:
            conn.execute(sql, params)
        return job

    def save_government_jobs_bulk(self, jobs: List[GovernmentJob]):
        """Bulk upserts government jobs."""
        for j in jobs:
            self.save_government_job(j)

    def get_government_job(self, job_id: str) -> Optional[GovernmentJob]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM government_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._build_government_job(row)

    def get_all_government_jobs(self, status_filter: Optional[str] = None) -> List[GovernmentJob]:
        query = "SELECT * FROM government_jobs"
        params = []
        if status_filter:
            query += " WHERE status = ?"
            params.append(status_filter)
        query += " ORDER BY application_closing_date ASC, job_id DESC"

        jobs = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                jobs.append(self._build_government_job(row))
        return jobs

    def update_government_job_status(self, job_id: str, new_status: str):
        with self.db.transaction() as conn:
            conn.execute("UPDATE government_jobs SET status = ? WHERE job_id = ?", (new_status, job_id))

    def _build_government_job(self, row) -> GovernmentJob:
        req_docs = []
        if row["required_documents"]:
            try:
                req_docs = json.loads(row["required_documents"])
            except Exception:
                req_docs = [d.strip() for d in row["required_documents"].split(",") if d.strip()]

        return GovernmentJob(
            job_id=row["job_id"],
            source=row["source"],
            advertisement_number=row["advertisement_number"] or "",
            department=row["department"],
            post_name=row["post_name"],
            vacancies_count=row["vacancies_count"] or 1,
            employment_type=row["employment_type"] or "Regular / Permanent",
            pay_level_salary=row["pay_level_salary"] or "",
            minimum_qualification=row["minimum_qualification"] or "",
            preferred_qualification=row["preferred_qualification"] or "",
            experience_requirement_years=row["experience_requirement_years"] or 0.0,
            age_limit_min=row["age_limit_min"] or 18,
            age_limit_max=row["age_limit_max"] or 45,
            gender_requirement=row["gender_requirement"] or "Any",
            category_reservation=row["category_reservation"] or "",
            konkani_marathi_required=row["konkani_marathi_required"] or "Konkani Essential, Marathi Desirable",
            required_documents=req_docs,
            application_start_date=row["application_start_date"] or "",
            application_closing_date=row["application_closing_date"] or "",
            application_method=row["application_method"] or "Online",
            official_ad_url=row["official_ad_url"] or "",
            official_apply_url=row["official_apply_url"] or "",
            ad_pdf_url=row["ad_pdf_url"] or "",
            last_checked_at=row["last_checked_at"] or "",
            source_last_updated_at=row["source_last_updated_at"] or "",
            status=row["status"] or "OPEN"
        )

    # =========================================================================
    # PRIVATE JOBS
    # =========================================================================
    def save_private_job(self, job: PrivateJob) -> PrivateJob:
        """Saves or updates a curated private job."""
        now = datetime.now().isoformat()
        job.date_added = job.date_added or now
        req_docs_json = json.dumps(job.required_documents) if isinstance(job.required_documents, list) else (job.required_documents or "[]")
        sql = """
        INSERT INTO private_jobs (
            job_id, employer, job_title, department, job_description,
            required_qualification, required_skills, required_experience_years,
            required_documents, location, salary_range, employment_type,
            work_mode, application_deadline, source, source_url, application_url,
            contact_person, contact_email, contact_phone, date_added,
            last_verified_at, verification_status, status
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            employer = excluded.employer,
            job_title = excluded.job_title,
            department = excluded.department,
            job_description = excluded.job_description,
            required_qualification = excluded.required_qualification,
            required_skills = excluded.required_skills,
            required_experience_years = excluded.required_experience_years,
            required_documents = excluded.required_documents,
            location = excluded.location,
            salary_range = excluded.salary_range,
            employment_type = excluded.employment_type,
            work_mode = excluded.work_mode,
            application_deadline = excluded.application_deadline,
            source = excluded.source,
            source_url = excluded.source_url,
            application_url = excluded.application_url,
            contact_person = excluded.contact_person,
            contact_email = excluded.contact_email,
            contact_phone = excluded.contact_phone,
            last_verified_at = excluded.last_verified_at,
            verification_status = excluded.verification_status,
            status = excluded.status
        """
        params = (
            job.job_id, job.employer, job.job_title, job.department or "",
            job.job_description or "", job.required_qualification or "",
            job.required_skills or "", job.required_experience_years or 0.0,
            req_docs_json, job.location or "Pernem",
            job.salary_range or "", job.employment_type or "Full-Time",
            job.work_mode or "On-Site", job.application_deadline or "",
            job.source or "Curated", job.source_url or "", job.application_url or "",
            job.contact_person or "", job.contact_email or "", job.contact_phone or "",
            job.date_added, job.last_verified_at or "", job.verification_status or "VERIFIED",
            job.status or "ACTIVE"
        )
        with self.db.transaction() as conn:
            conn.execute(sql, params)
        return job

    def get_private_job(self, job_id: str) -> Optional[PrivateJob]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM private_jobs WHERE job_id = ?", (job_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._build_private_job(row)

    def get_all_private_jobs(self, status_filter: Optional[str] = None) -> List[PrivateJob]:
        query = "SELECT * FROM private_jobs"
        params = []
        if status_filter:
            query += " WHERE status = ?"
            params.append(status_filter)
        query += " ORDER BY date_added DESC, job_id DESC"

        jobs = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                jobs.append(self._build_private_job(row))
        return jobs

    def update_private_job_status(self, job_id: str, new_status: str):
        with self.db.transaction() as conn:
            conn.execute("UPDATE private_jobs SET status = ? WHERE job_id = ?", (new_status, job_id))

    def _build_private_job(self, row) -> PrivateJob:
        req_docs = []
        if row["required_documents"]:
            try:
                req_docs = json.loads(row["required_documents"])
            except Exception:
                req_docs = [d.strip() for d in row["required_documents"].split(",") if d.strip()]

        return PrivateJob(
            job_id=row["job_id"],
            employer=row["employer"],
            job_title=row["job_title"],
            department=row["department"] or "",
            job_description=row["job_description"] or "",
            required_qualification=row["required_qualification"] or "",
            required_skills=row["required_skills"] or "",
            required_experience_years=row["required_experience_years"] or 0.0,
            required_documents=req_docs,
            location=row["location"] or "Pernem",
            salary_range=row["salary_range"] or "",
            employment_type=row["employment_type"] or "Full-Time",
            work_mode=row["work_mode"] or "On-Site",
            application_deadline=row["application_deadline"] or "",
            source=row["source"] or "Curated",
            source_url=row["source_url"] or "",
            application_url=row["application_url"] or "",
            contact_person=row["contact_person"] or "",
            contact_email=row["contact_email"] or "",
            contact_phone=row["contact_phone"] or "",
            date_added=row["date_added"] or "",
            last_verified_at=row["last_verified_at"] or "",
            verification_status=row["verification_status"] or "VERIFIED",
            status=row["status"] or "ACTIVE"
        )

    # =========================================================================
    # RECRUITERS & VERIFICATION
    # =========================================================================
    def save_recruiter(self, recruiter: Recruiter) -> Recruiter:
        now = datetime.now().isoformat()
        recruiter.date_added = recruiter.date_added or now
        sql = """
        INSERT INTO recruiters (
            recruiter_id, company, contact_person, designation, email, phone,
            industry, location, website, verification_status, date_added,
            last_contact_at, candidates_shared_count, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(recruiter_id) DO UPDATE SET
            company = excluded.company,
            contact_person = excluded.contact_person,
            designation = excluded.designation,
            email = excluded.email,
            phone = excluded.phone,
            industry = excluded.industry,
            location = excluded.location,
            website = excluded.website,
            verification_status = excluded.verification_status,
            last_contact_at = excluded.last_contact_at,
            candidates_shared_count = excluded.candidates_shared_count,
            notes = excluded.notes
        """
        params = (
            recruiter.recruiter_id, recruiter.company, recruiter.contact_person,
            recruiter.designation or "", recruiter.email, recruiter.phone,
            recruiter.industry or "", recruiter.location or "", recruiter.website or "",
            recruiter.verification_status or "UNVERIFIED", recruiter.date_added,
            recruiter.last_contact_at or "", recruiter.candidates_shared_count or 0,
            recruiter.notes or ""
        )
        with self.db.transaction() as conn:
            conn.execute(sql, params)
            self.log_audit(
                "Recruiter", recruiter.recruiter_id, "CREATE/UPDATE",
                "", recruiter.verification_status, "Operator",
                f"Recruiter {recruiter.company} saved", conn=conn
            )
        return recruiter

    def get_recruiter(self, recruiter_id: str) -> Optional[Recruiter]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM recruiters WHERE recruiter_id = ?", (recruiter_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return Recruiter(
                recruiter_id=row["recruiter_id"],
                company=row["company"],
                contact_person=row["contact_person"],
                designation=row["designation"] or "",
                email=row["email"],
                phone=row["phone"],
                industry=row["industry"] or "",
                location=row["location"] or "",
                website=row["website"] or "",
                verification_status=row["verification_status"] or "UNVERIFIED",
                date_added=row["date_added"] or "",
                last_contact_at=row["last_contact_at"] or "",
                candidates_shared_count=row["candidates_shared_count"] or 0,
                notes=row["notes"] or ""
            )

    def get_all_recruiters(self, status_filter: Optional[str] = None) -> List[Recruiter]:
        query = "SELECT * FROM recruiters"
        params = []
        if status_filter:
            query += " WHERE verification_status = ?"
            params.append(status_filter)
        query += " ORDER BY company ASC"

        recruiters = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                recruiters.append(Recruiter(
                    recruiter_id=row["recruiter_id"],
                    company=row["company"],
                    contact_person=row["contact_person"],
                    designation=row["designation"] or "",
                    email=row["email"],
                    phone=row["phone"],
                    industry=row["industry"] or "",
                    location=row["location"] or "",
                    website=row["website"] or "",
                    verification_status=row["verification_status"] or "UNVERIFIED",
                    date_added=row["date_added"] or "",
                    last_contact_at=row["last_contact_at"] or "",
                    candidates_shared_count=row["candidates_shared_count"] or 0,
                    notes=row["notes"] or ""
                ))
        return recruiters

    def update_recruiter_status(self, recruiter_id: str, status: str, actor: str = "Operator", notes: str = ""):
        """Updates recruiter verification status and creates mandatory audit entry."""
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT verification_status FROM recruiters WHERE recruiter_id = ?", (recruiter_id,))
            row = cursor.fetchone()
            old_status = row["verification_status"] if row else "UNKNOWN"

            conn.execute(
                "UPDATE recruiters SET verification_status = ?, notes = COALESCE(?, notes) WHERE recruiter_id = ?",
                (status, notes if notes else None, recruiter_id)
            )
            self.log_audit(
                "Recruiter", recruiter_id, "RECRUITER_VERIFIED" if status == "VERIFIED" else "STATUS_CHANGE",
                old_status, status, actor, notes, conn=conn
            )

    # =========================================================================
    # CANDIDATE CONSENT
    # =========================================================================
    def save_candidate_consent(
        self,
        consent: CandidateConsent,
        actor: str = "Operator",
        conn: Optional[sqlite3.Connection] = None
    ) -> CandidateConsent:
        """Saves consent and records audit entry."""
        now = datetime.now().isoformat()
        consent.updated_at = now
        sql = """
        INSERT INTO candidate_consent (candidate_id, consent_status, consent_date, consent_method, consent_notes, updated_at)
        VALUES (?, ?, ?, ?, ?, ?)
        ON CONFLICT(candidate_id) DO UPDATE SET
            consent_status = excluded.consent_status,
            consent_date = excluded.consent_date,
            consent_method = excluded.consent_method,
            consent_notes = excluded.consent_notes,
            updated_at = excluded.updated_at
        """
        params = (
            consent.candidate_id, consent.consent_status,
            consent.consent_date or "", consent.consent_method or "",
            consent.consent_notes or "", consent.updated_at
        )
        if conn is not None:
            cursor = conn.cursor()
            cursor.execute("SELECT consent_status FROM candidate_consent WHERE candidate_id = ?", (consent.candidate_id,))
            row = cursor.fetchone()
            old_status = row["consent_status"] if row else "None"

            conn.execute(sql, params)
            if old_status != consent.consent_status:
                self.log_audit(
                    "Consent", consent.candidate_id, "CONSENT_CHANGE",
                    old_status, consent.consent_status, actor,
                    f"Method: {consent.consent_method}; Notes: {consent.consent_notes}", conn=conn
                )
        else:
            with self.db.transaction() as c:
                cursor = c.cursor()
                cursor.execute("SELECT consent_status FROM candidate_consent WHERE candidate_id = ?", (consent.candidate_id,))
                row = cursor.fetchone()
                old_status = row["consent_status"] if row else "None"

                c.execute(sql, params)
                if old_status != consent.consent_status:
                    self.log_audit(
                        "Consent", consent.candidate_id, "CONSENT_CHANGE",
                        old_status, consent.consent_status, actor,
                        f"Method: {consent.consent_method}; Notes: {consent.consent_notes}", conn=c
                    )
        return consent


    def get_candidate_consent(self, candidate_id: str) -> Optional[CandidateConsent]:
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM candidate_consent WHERE candidate_id = ?", (candidate_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return CandidateConsent(
                candidate_id=row["candidate_id"],
                consent_status=row["consent_status"] or "Not Asked",
                consent_date=row["consent_date"] or "",
                consent_method=row["consent_method"] or "",
                consent_notes=row["consent_notes"] or "",
                updated_at=row["updated_at"] or ""
            )

    def get_consented_candidates(self) -> List[Candidate]:
        """Returns all candidates with consent_status == 'Consented'."""
        all_cands = self.get_all_candidates()
        return [c for c in all_cands if c.consent and c.consent.consent_status == "Consented"]

    def update_candidate_consent(
        self,
        candidate_id: str,
        status: str,
        method: str = "",
        notes: str = "",
        actor: str = "Operator"
    ):
        consent = CandidateConsent(
            candidate_id=candidate_id,
            consent_status=status,
            consent_date=datetime.now().strftime("%Y-%m-%d"),
            consent_method=method,
            consent_notes=notes
        )
        self.save_candidate_consent(consent, actor=actor)

    # =========================================================================
    # RECRUITER CANDIDATE SHARES
    # =========================================================================
    def record_candidate_share(self, share: RecruiterCandidateShare) -> RecruiterCandidateShare:
        """Records a candidate sharing event with full audit trail."""
        now = datetime.now().isoformat()
        share.shared_date = share.shared_date or now
        sql = """
        INSERT INTO recruiter_candidate_shares (
            recruiter_id, candidate_id, job_id, shared_date, export_mode,
            consent_status_at_sharing, shared_by, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            share.recruiter_id, share.candidate_id, share.job_id,
            share.shared_date, share.export_mode, share.consent_status_at_sharing,
            share.shared_by or "Operator", share.notes or ""
        )
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            share.id = cursor.lastrowid

            # Increment recruiter shared count
            conn.execute(
                """
                UPDATE recruiters SET
                    candidates_shared_count = candidates_shared_count + 1,
                    last_contact_at = ?
                WHERE recruiter_id = ?
                """,
                (now, share.recruiter_id)
            )

            # Log audit
            self.log_audit(
                "Share", share.candidate_id, "SHARE_EXPORT",
                "", f"Recruiter: {share.recruiter_id}, Mode: {share.export_mode}",
                share.shared_by or "Operator",
                f"Consent at sharing: {share.consent_status_at_sharing}; Job: {share.job_id or 'General'}",
                conn=conn
            )
        return share

    def get_recruiter_shares(
        self,
        recruiter_id: Optional[str] = None,
        candidate_id: Optional[str] = None
    ) -> List[RecruiterCandidateShare]:
        query = "SELECT * FROM recruiter_candidate_shares WHERE 1=1"
        params = []
        if recruiter_id:
            query += " AND recruiter_id = ?"
            params.append(recruiter_id)
        if candidate_id:
            query += " AND candidate_id = ?"
            params.append(candidate_id)
        query += " ORDER BY id DESC"

        shares = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                shares.append(RecruiterCandidateShare(
                    id=row["id"],
                    recruiter_id=row["recruiter_id"],
                    candidate_id=row["candidate_id"],
                    job_id=row["job_id"],
                    shared_date=row["shared_date"],
                    export_mode=row["export_mode"],
                    consent_status_at_sharing=row["consent_status_at_sharing"],
                    shared_by=row["shared_by"] or "",
                    notes=row["notes"] or ""
                ))
        return shares

    # =========================================================================
    # APPLICATION TRACKING (MULTI-APPLICATION HISTORY)
    # =========================================================================
    def save_government_job_application(self, app: GovernmentJobApplication) -> GovernmentJobApplication:
        sql = """
        INSERT INTO government_job_applications (
            candidate_id, job_id, advertisement_number, post_name, department,
            application_date, application_status, exam_date, result_details, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            app.candidate_id, app.job_id, app.advertisement_number or "",
            app.post_name, app.department, app.application_date,
            app.application_status or "APPLIED", app.exam_date or "",
            app.result_details or "", app.notes or ""
        )
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            app.application_id = cursor.lastrowid
            self.log_audit(
                "GovJobApp", app.candidate_id, "CREATE",
                "", f"{app.department} - {app.post_name}", "Operator",
                f"Status: {app.application_status}", conn=conn
            )
        return app

    def get_government_job_applications(self, candidate_id: Optional[str] = None) -> List[GovernmentJobApplication]:
        query = "SELECT * FROM government_job_applications"
        params = []
        if candidate_id:
            query += " WHERE candidate_id = ?"
            params.append(candidate_id)
        query += " ORDER BY application_id DESC"

        apps = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                apps.append(GovernmentJobApplication(
                    application_id=row["application_id"],
                    candidate_id=row["candidate_id"],
                    job_id=row["job_id"],
                    advertisement_number=row["advertisement_number"] or "",
                    post_name=row["post_name"],
                    department=row["department"],
                    application_date=row["application_date"],
                    application_status=row["application_status"],
                    exam_date=row["exam_date"] or "",
                    result_details=row["result_details"] or "",
                    notes=row["notes"] or ""
                ))
        return apps

    def save_private_job_application(self, app: PrivateJobApplication) -> PrivateJobApplication:
        sql = """
        INSERT INTO private_job_applications (
            candidate_id, job_id, company_employer, job_title, application_date,
            application_method, application_status, interview_date, notes
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            app.candidate_id, app.job_id, app.company_employer, app.job_title,
            app.application_date, app.application_method or "Direct",
            app.application_status or "APPLIED", app.interview_date or "",
            app.notes or ""
        )
        with self.db.transaction() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            app.application_id = cursor.lastrowid
            self.log_audit(
                "PrivateJobApp", app.candidate_id, "CREATE",
                "", f"{app.company_employer} - {app.job_title}", "Operator",
                f"Status: {app.application_status}", conn=conn
            )
        return app

    def get_private_job_applications(self, candidate_id: Optional[str] = None) -> List[PrivateJobApplication]:
        query = "SELECT * FROM private_job_applications"
        params = []
        if candidate_id:
            query += " WHERE candidate_id = ?"
            params.append(candidate_id)
        query += " ORDER BY application_id DESC"

        apps = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            for row in cursor.fetchall():
                apps.append(PrivateJobApplication(
                    application_id=row["application_id"],
                    candidate_id=row["candidate_id"],
                    job_id=row["job_id"],
                    company_employer=row["company_employer"],
                    job_title=row["job_title"],
                    application_date=row["application_date"],
                    application_method=row["application_method"] or "Direct",
                    application_status=row["application_status"],
                    interview_date=row["interview_date"] or "",
                    notes=row["notes"] or ""
                ))
        return apps

    # ==============================================================================
    # Visiting Register Operations
    # ==============================================================================

    def get_next_visitor_sr_no(self, conn: Optional[sqlite3.Connection] = None) -> int:
        """Returns the next sequential Sr No for visiting register (1, 2, 3...)."""
        query = "SELECT COALESCE(MAX(sr_no), 0) + 1 FROM visiting_register WHERE is_deleted = 0"
        if conn:
            cursor = conn.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 1

        with self.db.get_connection() as c:
            cursor = c.cursor()
            cursor.execute(query)
            row = cursor.fetchone()
            return int(row[0]) if row and row[0] is not None else 1

    def save_visitor(self, visitor: VisitorRecord) -> int:
        """
        Saves a new visitor record with an auto-assigned sequential Sr No.
        Returns the assigned record ID.
        """
        now_iso = datetime.now().isoformat()
        with self.db.transaction() as conn:
            if not visitor.sr_no or visitor.sr_no <= 0:
                visitor.sr_no = self.get_next_visitor_sr_no(conn)
            if not visitor.created_at:
                visitor.created_at = now_iso
            visitor.updated_at = now_iso

            cursor = conn.cursor()
            cursor.execute(
                """
                INSERT INTO visiting_register (
                    sr_no, visit_date, visit_time, candidate_name, village,
                    mobile, purpose, created_at, updated_at, sync_status,
                    last_synced_at, is_deleted
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    visitor.sr_no, visitor.visit_date, visitor.visit_time,
                    visitor.candidate_name, visitor.village, visitor.mobile,
                    visitor.purpose, visitor.created_at, visitor.updated_at,
                    visitor.sync_status, visitor.last_synced_at, visitor.is_deleted
                )
            )
            visitor.id = cursor.lastrowid
            logger.info("Saved visitor Sr No. %d (ID %d) to Visiting Register", visitor.sr_no, visitor.id)
            return visitor.id

    def update_visitor(self, visitor: VisitorRecord) -> bool:
        """Updates an existing visitor entry in the Visiting Register."""
        if not visitor.id:
            return False
        now_iso = datetime.now().isoformat()
        visitor.updated_at = now_iso
        visitor.sync_status = SYNC_STATUS_PENDING
        with self.db.transaction() as conn:
            conn.execute(
                """
                UPDATE visiting_register SET
                    visit_date = ?, visit_time = ?, candidate_name = ?,
                    village = ?, mobile = ?, purpose = ?, updated_at = ?,
                    sync_status = ?
                WHERE id = ?
                """,
                (
                    visitor.visit_date, visitor.visit_time, visitor.candidate_name,
                    visitor.village, visitor.mobile, visitor.purpose,
                    visitor.updated_at, visitor.sync_status, visitor.id
                )
            )
        logger.info("Updated visitor ID %d in Visiting Register", visitor.id)
        return True

    def delete_visitor(self, visitor_id: int) -> bool:
        """Soft-deletes a visitor entry from the Visiting Register."""
        now_iso = datetime.now().isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                f"UPDATE visiting_register SET is_deleted = 1, updated_at = ?, sync_status = '{SYNC_STATUS_PENDING}' WHERE id = ?",
                (now_iso, visitor_id)
            )
        logger.info("Soft-deleted visitor ID %d from Visiting Register", visitor_id)
        return True

    def get_all_visitors(self, include_deleted: bool = False) -> List[VisitorRecord]:
        """Retrieves all visitor entries ordered by sr_no DESC."""
        sql = "SELECT * FROM visiting_register"
        if not include_deleted:
            sql += " WHERE is_deleted = 0"
        sql += " ORDER BY sr_no DESC, id DESC"

        visitors = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            for row in cursor.fetchall():
                visitors.append(VisitorRecord.from_row(row))
        return visitors

    def get_visitor_by_id(self, visitor_id: int) -> Optional[VisitorRecord]:
        """Retrieves a single visitor entry by SQLite primary key."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM visiting_register WHERE id = ?", (visitor_id,))
            row = cursor.fetchone()
            if row:
                return VisitorRecord.from_row(row)
        return None

    def search_visitors(self, query: str = "", date_filter: str = "", village_filter: str = "") -> List[VisitorRecord]:
        """Filters visitors by search terms, date, or village."""
        sql = "SELECT * FROM visiting_register WHERE is_deleted = 0"
        params = []

        if query:
            q = f"%{query.strip()}%"
            sql += " AND (candidate_name LIKE ? OR mobile LIKE ? OR purpose LIKE ? OR CAST(sr_no AS TEXT) LIKE ?)"
            params.extend([q, q, q, q])

        if date_filter:
            sql += " AND visit_date = ?"
            params.append(date_filter.strip())

        if village_filter:
            sql += " AND village = ?"
            params.append(village_filter.strip())

        sql += " ORDER BY sr_no DESC, id DESC"

        visitors = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            for row in cursor.fetchall():
                visitors.append(VisitorRecord.from_row(row))
        return visitors

    def get_pending_sync_visitors(self) -> List[VisitorRecord]:
        """Returns all visitor entries requiring cloud synchronisation."""
        sql = f"SELECT * FROM visiting_register WHERE sync_status IN ('{SYNC_STATUS_PENDING}', '{SYNC_STATUS_FAILED}') AND is_deleted = 0 ORDER BY sr_no ASC"
        visitors = []
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql)
            for row in cursor.fetchall():
                visitors.append(VisitorRecord.from_row(row))
        return visitors

    def mark_visitors_synced(self, visitor_ids: List[int], synced_at: str):
        """Marks visitor entries as SYNCED with timestamp."""
        if not visitor_ids:
            return
        with self.db.transaction() as conn:
            placeholders = ",".join(["?"] * len(visitor_ids))
            sql = f"UPDATE visiting_register SET sync_status = '{SYNC_STATUS_SYNCED}', last_synced_at = ? WHERE id IN ({placeholders})"
            params = [synced_at] + visitor_ids
            conn.execute(sql, params)
        logger.info("Marked %d visitors as SYNCED", len(visitor_ids))

    def get_visitors_summary_counts(self) -> Dict[str, int]:
        """Returns counts for Today, This Month, and All-Time."""
        today = datetime.now().strftime("%Y-%m-%d")
        month_prefix = datetime.now().strftime("%Y-%m")
        counts = {"today": 0, "this_month": 0, "total": 0, "pending_sync": 0}
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM visiting_register WHERE is_deleted = 0 AND visit_date = ?", (today,))
            counts["today"] = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM visiting_register WHERE is_deleted = 0 AND visit_date LIKE ?", (f"{month_prefix}%",))
            counts["this_month"] = cursor.fetchone()[0] or 0

            cursor.execute("SELECT COUNT(*) FROM visiting_register WHERE is_deleted = 0")
            counts["total"] = cursor.fetchone()[0] or 0

            cursor.execute(f"SELECT COUNT(*) FROM visiting_register WHERE is_deleted = 0 AND sync_status IN ('{SYNC_STATUS_PENDING}', '{SYNC_STATUS_FAILED}')")
            counts["pending_sync"] = cursor.fetchone()[0] or 0
        return counts

    def bulk_import_visitors(self, visitors_data: List[Dict[str, Any]]) -> Dict[str, int]:
        """
        Batch imports visitor records from Excel or CSV.
        Auto-assigns sequential Sr No if missing or conflicting.
        Returns dict with inserted and skipped counts.
        """
        inserted = 0
        skipped = 0
        now_iso = datetime.now().isoformat()
        with self.db.transaction() as conn:
            for item in visitors_data:
                name = str(item.get("candidate_name") or "").strip()
                if not name:
                    skipped += 1
                    continue
                sr_no_val = item.get("sr_no")
                try:
                    sr_no = int(sr_no_val) if sr_no_val is not None and str(sr_no_val).strip() != "" else 0
                except (ValueError, TypeError):
                    sr_no = 0

                if sr_no <= 0:
                    sr_no = self.get_next_visitor_sr_no(conn)
                else:
                    cursor = conn.cursor()
                    cursor.execute("SELECT id FROM visiting_register WHERE sr_no = ?", (sr_no,))
                    if cursor.fetchone():
                        sr_no = self.get_next_visitor_sr_no(conn)

                visit_date = str(item.get("visit_date") or datetime.now().strftime("%Y-%m-%d")).strip()
                visit_time = str(item.get("visit_time") or datetime.now().strftime("%I:%M %p")).strip()
                village = str(item.get("village") or "").strip()
                mobile = clean_mobile(str(item.get("mobile") or "")) if item.get("mobile") else ""
                purpose = str(item.get("purpose") or "General Inquiry").strip()

                conn.execute(
                    """
                    INSERT INTO visiting_register (
                        sr_no, visit_date, visit_time, candidate_name, village,
                        mobile, purpose, created_at, updated_at, sync_status,
                        last_synced_at, is_deleted
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        sr_no, visit_date, visit_time, name, village, mobile,
                        purpose, now_iso, now_iso, SYNC_STATUS_PENDING, None, 0
                    )
                )
                inserted += 1
        logger.info("Bulk imported %d visitors (%d skipped)", inserted, skipped)
        return {"inserted": inserted, "skipped": skipped}


repository = CandidateRepository()

