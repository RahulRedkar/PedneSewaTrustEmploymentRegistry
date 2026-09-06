"""
Demonstration Data Generator for Pedne Sewa Trust - Employment Facilitation Platform.
Generates 100 synthetic, realistic Pernem / Goa candidate profiles with:
- Strict is_demo = 1 segregation
- Realistic Goan names, Pernem villages, independent vaddos, and booths
- Varied education levels, employment statuses, and document inventories
- Exact data-integrity reconciliation:
  * Employed = Govt Employed + Private Employed
  * Unemployed = Govt Applicants + Never Applied
  * Total = Employed + Unemployed + Self-Employed + Students
"""

import random
from datetime import datetime, timedelta
from typing import List
from models.candidate import Candidate, Education, Employment, EmploymentPreferences
from models.facilitation import CandidateLocation, CandidateDocument, CandidateConsent
from database.repository import CandidateRepository
from utils.logger import logger


VILLAGES_PERNEM = [
    "Agarwada", "Alorna", "Amberem", "Arambol (Harmal)", "Casarvarnem (Kasarvarnem)",
    "Chandel", "Chopdem", "Corgao", "Dargalim", "Ibrampur", "Mandrem", "Morjim",
    "Mopa", "Ozorim", "Paliem", "Parsem", "Pernem (Town)", "Poroscodem", "Querim (Keri)",
    "Tamboxem", "Tiracol (Terekhol)", "Torxem", "Tuem", "Uguem", "Varcond", "Virnora"
]

VADDOS = [
    "Khalchawada", "Madhlawada", "Varchawada", "Deulwada", "Bamonwada",
    "Gaunchewada", "Bhandarwada", "Tembwada", "Bhatwadi", "Khajanwada",
    "Morjim Beach Road", "Harmal Cliff", "Tuem Industrial Area", "Mopa Plateau", "Market Road"
]

FIRST_NAMES_MALE = [
    "Rohan", "Prathamesh", "Sanket", "Nilesh", "Swapnil", "Saish", "Gauresh",
    "Tanmay", "Omkar", "Siddhesh", "Darshan", "Sahil", "Suraj", "Abhishek",
    "Mayur", "Pritesh", "Gaurav", "Kalpesh", "Aniket", "Vaibhav", "Yash",
    "Tejas", "Chinmay", "Shrikant", "Rahul", "Dattaprasad", "Manish", "Girish"
]

FIRST_NAMES_FEMALE = [
    "Sneha", "Shruti", "Pooja", "Ankita", "Tanvi", "Diksha", "Sanjana",
    "Priyanka", "Rutuja", "Divya", "Sakshi", "Neha", "Siddhi", "Manasi",
    "Harshada", "Prajakta", "Purva", "Gauri", "Chetana", "Akshata", "Rasika",
    "Vaishali", "Prachi", "Deepa", "Shreya", "Kavita", "Archana", "Pallavi"
]

SURNAMES = [
    "Parab", "Sawant", "Naik", "Parsekar", "Deshprabhu", "Shetgaonkar",
    "Mandrekar", "Harmalkar", "Toraskar", "Chodankar", "Gawas", "Halarnkar",
    "Kambli", "Mahale", "Aroskar", "Kerkar", "Vengurlekar", "Salgaonkar",
    "Pednekar", "Dhargalkar", "Fernandes", "D'Souza", "Rodrigues", "Pereira"
]

DEPARTMENTS_GOVT = [
    "Directorate of Education", "Public Works Department (PWD)",
    "Directorate of Health Services", "Goa Police Department",
    "Directorate of Agriculture", "Forest Department",
    "Directorate of Transport", "Electricity Department", "Water Resources Department"
]

PRIVATE_EMPLOYERS = [
    ("Taj Tiracol Resort & Spa", "Hospitality Executive", "Hospitality & Tourism"),
    ("Manohar International Airport (GMR Mopa)", "Aviation Operations Assistant", "Logistics, Aviation & Transport (Mopa Airport)"),
    ("Tuem Industrial Corporation", "Production Line Technician", "Manufacturing & Industrial (Tuem IDC / Verna)"),
    ("Arambol Beach Resorts", "Guest Relations Officer", "Hospitality & Tourism"),
    ("HDFC Bank Pernem Branch", "Customer Relationship Officer", "Banking, Finance & Insurance"),
    ("Morjim Eco-Tourism Ltd", "Front Desk Supervisor", "Hospitality & Tourism"),
    ("Goa State Co-op Bank Tuem", "Assistant Accountant", "Banking, Finance & Insurance"),
    ("Pernem Health Clinic", "Medical Lab Assistant", "Healthcare & Pharmaceuticals"),
    ("Tuem Tech Solutions", "Junior Web Developer", "Information Technology & Software"),
    ("Mopa Cargo Logistics Hub", "Warehouse Coordinator", "Logistics, Aviation & Transport (Mopa Airport)")
]

SELF_EMP_TYPES = [
    ("Bike & Car Rental Services", "Morjim / Arambol", 3, 35000),
    ("Traditional Bakery & Confectionery", "Pernem Market", 6, 45000),
    ("Homestay & Guesthouse Operator", "Mandrem Beach", 4, 60000),
    ("Electrical & Plumbing Contracting", "Corgao / Tuem", 2, 30000),
    ("Local Grocery & Retail Store", "Dargalim", 8, 40000),
    ("Agricultural Nursery & Coconut Trade", "Ibrampur", 5, 28000),
    ("Tour Guiding & Coastal Water Sports", "Arambol", 3, 50000),
    ("Automobile Repair Garage", "Pernem Town", 4, 38000)
]

STUDENT_COURSES = [
    ("Sant Sohirobanath Ambiye Govt College of Arts & Commerce, Virnora", "B.Com Final Year"),
    ("Govt ITI Tuem", "Electrician Trade (NCVT)"),
    ("Govt Polytechnic Mayem / Bicholim", "Diploma in Civil Engineering"),
    ("Goa College of Engineering (Farmagudi)", "B.E. Mechanical Engineering"),
    ("Goa University, Taleigao", "M.A. Konkani"),
    ("Dhempe College of Arts & Science", "B.Sc Biotechnology")
]


def generate_100_demo_candidates() -> List[Candidate]:
    """
    Generates 100 realistic, fully-populated demo candidate profiles.
    Distribution strictly satisfies:
    - 45 Employed (15 Govt, 30 Private)
    - 35 Unemployed (20 Govt Applicants, 15 Never Applied)
    - 12 Self-Employed
    - 8 Students
    Total = 100
    """
    # Deterministic seed for consistent reproducible demo data
    rnd = random.Random(42)
    candidates: List[Candidate] = []

    # Category buckets to guarantee strict totals
    statuses = (
        [("EMPLOYED", "Government")] * 15 +
        [("EMPLOYED", "Private")] * 30 +
        [("UNEMPLOYED", "Govt_Applicant")] * 20 +
        [("UNEMPLOYED", "Never_Applied")] * 15 +
        [("SELF_EMPLOYED", "")] * 12 +
        [("STUDENT", "")] * 8
    )
    rnd.shuffle(statuses)

    now = datetime.now()

    for idx, (status_type, subtype) in enumerate(statuses, start=1):
        cid = f"PST-DEMO-{idx:04d}"
        is_male = rnd.random() > 0.45
        first_name = rnd.choice(FIRST_NAMES_MALE) if is_male else rnd.choice(FIRST_NAMES_FEMALE)
        surname = rnd.choice(SURNAMES)
        full_name = f"{first_name} {surname}"
        gender = "Male" if is_male else "Female"

        age = rnd.randint(20, 48) if status_type != "STUDENT" else rnd.randint(18, 23)
        birth_year = now.year - age
        birth_month = rnd.randint(1, 12)
        birth_day = rnd.randint(1, 28)
        dob_str = f"{birth_year:04d}-{birth_month:02d}-{birth_day:02d}"

        village = rnd.choice(VILLAGES_PERNEM)
        vaddo = rnd.choice(VADDOS)
        booth = f"Booth {rnd.randint(1, 18)}"
        house_no = f"H.No. {rnd.randint(10, 450)}"
        address = f"{house_no}, {vaddo}, {village}, Pernem, Goa"
        pincode = "403512" if "Pernem" in village else "403519" if "Mandrem" in village or "Arambol" in village else "403527"
        mobile = f"98{rnd.randint(20000000, 99999999)}"
        email = f"{first_name.lower()}.{surname.lower()}{rnd.randint(10, 99)}@example.com"

        reg_days_ago = rnd.randint(1, 90)
        reg_time = (now - timedelta(days=reg_days_ago, hours=rnd.randint(1, 10))).isoformat()

        # Education
        edu = Education()
        if status_type == "STUDENT":
            college, course = rnd.choice(STUDENT_COURSES)
            edu.highest_qualification = "12th / HSSC (Commerce)" if "B.Com" in course else "12th / HSSC (Science)"
            edu.institution = college
            edu.degree_course = course
            edu.passing_year = now.year + rnd.randint(0, 2)
            edu.skills = "Computer Applications, English, Tally"
        elif age > 30:
            edu.highest_qualification = rnd.choice([
                "Graduate - B.Com", "Graduate - B.A.", "12th / HSSC (Commerce)",
                "Polytechnic Diploma", "Graduate - B.E. / B.Tech"
            ])
            edu.degree_course = edu.highest_qualification
            edu.institution = "Pernem / Mapusa College"
            edu.passing_year = birth_year + 21
            edu.skills = "Administration, Operations, Accounts, Team Coordination"
        else:
            edu.highest_qualification = rnd.choice([
                "Graduate - B.Com", "Graduate - B.Sc", "Graduate - BBA / BCA",
                "ITI / Technical Certificate", "12th / HSSC (Science)"
            ])
            edu.degree_course = edu.highest_qualification
            edu.institution = "Govt College Pernem"
            edu.passing_year = birth_year + 21
            edu.skills = "MS Office, Basic Coding, Customer Support, Logistics"

        # Employment details
        emp = Employment()
        if status_type == "EMPLOYED":
            emp.status = "EMPLOYED"
            if subtype == "Government":
                emp.category = "Government"
                emp.department_company = rnd.choice(DEPARTMENTS_GOVT)
                emp.designation = rnd.choice(["Lower Division Clerk", "Junior Engineer", "Multi-Tasking Staff", "Police Constable", "Field Assistant"])
                emp.work_location = rnd.choice(["Pernem", "Panaji", "Mapusa"])
                emp.years_experience = round(rnd.uniform(1.5, 9.0), 1)
                emp.current_salary = rnd.choice([24000, 28000, 32000, 38000, 45000])
            else:
                emp.category = "Private"
                company, desig, sector = rnd.choice(PRIVATE_EMPLOYERS)
                emp.department_company = company
                emp.designation = desig
                emp.work_location = rnd.choice(["Pernem", "Mopa Airport", "Tuem IDC", "Morjim"])
                emp.years_experience = round(rnd.uniform(0.5, 6.0), 1)
                emp.current_salary = rnd.choice([16000, 20000, 25000, 30000, 35000])
        elif status_type == "UNEMPLOYED":
            emp.status = "UNEMPLOYED"
            if subtype == "Govt_Applicant":
                emp.govt_applied = True
                emp.govt_department = rnd.choice(DEPARTMENTS_GOVT)
                emp.govt_post_exam = rnd.choice(["LDC Examination", "Junior Stenographer", "Police Sub-Inspector", "Staff Nurse"])
                emp.govt_app_year = rnd.choice([2024, 2025, 2026])
                emp.govt_result_status = rnd.choice(["Examination Pending", "Awaiting Result", "Interview Pending"])
                emp.years_experience = round(rnd.uniform(0.0, 2.0), 1)
            else:
                emp.govt_applied = False
                emp.years_experience = 0.0
                emp.govt_remarks = "Seeking employment in local Pernem / Mopa area"
        elif status_type == "SELF_EMPLOYED":
            emp.status = "SELF_EMPLOYED"
            biz_name, biz_loc, biz_years, biz_inc = rnd.choice(SELF_EMP_TYPES)
            emp.self_emp_business_nature = biz_name
            emp.self_emp_location = f"{biz_loc}, Pernem"
            emp.self_emp_years_active = float(biz_years)
            emp.self_emp_employees_count = rnd.randint(1, 5)
            emp.self_emp_monthly_income = float(biz_inc)
            emp.years_experience = float(biz_years)
        elif status_type == "STUDENT":
            emp.status = "STUDENT"
            college, course = rnd.choice(STUDENT_COURSES)
            emp.student_current_course = course
            emp.student_institution = college
            emp.student_expected_year = now.year + rnd.randint(0, 2)
            emp.student_interested_in_employment = True

        # Preferences
        pref = EmploymentPreferences(
            preferred_sector=rnd.choice([
                "Hospitality & Tourism", "Government Administration",
                "Logistics, Aviation & Transport (Mopa Airport)",
                "Information Technology & Software", "Banking, Finance & Insurance"
            ]),
            preferred_role="Administrative / Field / Technical Role",
            preferred_location="Pernem Taluka / North Goa",
            willing_to_relocate=(rnd.random() > 0.6),
            preferred_employment_type="Full-Time",
            languages_known="Konkani, Marathi, English, Hindi",
            skills_list=edu.skills,
            total_experience_years=emp.years_experience
        )

        # Location
        loc = CandidateLocation(
            candidate_id=cid,
            house_building=house_no,
            vaddo=vaddo,
            village=village,
            booth=booth,
            taluka="Pernem",
            pincode=pincode,
            full_address_landmark=address
        )

        # Consent (approx 65% consented for recruiter facilitation)
        has_consent = (rnd.random() > 0.35)
        con = CandidateConsent(
            candidate_id=cid,
            consent_status="Consented" if has_consent else "Not Asked",
            consent_date=(now - timedelta(days=rnd.randint(2, 60))).strftime("%Y-%m-%d") if has_consent else None,
            consent_method="Signed Form / In-Person Intake" if has_consent else None,
            consent_notes="Authorized profile sharing with verified Pernem/Goa employers." if has_consent else ""
        )

        cand = Candidate(
            candidate_id=cid,
            full_name=full_name,
            dob=dob_str,
            age=age,
            gender=gender,
            address=address,
            village=village,
            taluka="Pernem",
            pincode=pincode,
            mobile=mobile,
            alternate_mobile="",
            email=email,
            created_at=reg_time,
            updated_at=reg_time,
            sync_status="PENDING",
            is_deleted=False,
            is_demo=True,
            education=edu,
            employment=emp,
            preferences=pref,
            location=loc,
            consent=con
        )
        candidates.append(cand)

    return candidates


def seed_demo_data(repo: CandidateRepository) -> int:
    """
    Inserts 100 demo candidates and their documents into SQLite.
    Returns count of demo candidates created.
    """
    existing_demo_count = repo.count_demo_candidates()
    if existing_demo_count >= 100:
        logger.info("Demo data already loaded (%d records). Skipping duplicate seeding.", existing_demo_count)
        return existing_demo_count

    candidates = generate_100_demo_candidates()
    loaded_count = 0

    for cand in candidates:
        try:
            repo.insert_candidate(cand)
            loaded_count += 1

            # Seed standard documents for candidate
            cid = cand.candidate_id
            repo.save_candidate_document(CandidateDocument(
                candidate_id=cid,
                document_type="15-Year Residence Certificate",
                document_category="Identity / Residence",
                status=random.choice(["Available", "Available", "Applied / Awaiting", "Missing"]),
                verification_status="Verified" if cand.is_demo else "Not Checked"
            ))
            repo.save_candidate_document(CandidateDocument(
                candidate_id=cid,
                document_type="Valid Employment Exchange Card",
                document_category="Employment Eligibility",
                status=random.choice(["Available", "Available", "Needs Renewal", "Missing"]),
                verification_status="Verified" if cand.is_demo else "Not Checked"
            ))
            repo.save_candidate_document(CandidateDocument(
                candidate_id=cid,
                document_type="Birth Certificate",
                document_category="Identity / Residence",
                status="Available",
                verification_status="Verified"
            ))
        except Exception as e:
            logger.error("Error inserting demo candidate %s: %s", cand.candidate_id, e)

    logger.info("Successfully seeded %d demonstration candidates into SQLite.", loaded_count)
    return loaded_count

