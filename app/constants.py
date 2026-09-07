"""
Application Constants for Pedne Sewa Trust - Employment Registry.
Contains Pernem Taluka geographic lists, qualification presets,
employment categories, and schema constants.
"""

from app.version import APP_VERSION, APP_NAME, APP_ORGANISATION

APP_TALUKA_DEFAULT = "Pernem"

# Intake Offices & Candidate ID Prefix Mapping
OFFICE_PERNEM = "Pernem"
OFFICE_KORGAO = "Korgao"
INTAKE_OFFICES = [OFFICE_PERNEM, OFFICE_KORGAO]

OFFICE_PREFIX_MAP = {
    OFFICE_PERNEM: "PST",
    OFFICE_KORGAO: "KPST"
}
PREFIX_OFFICE_MAP = {
    "PST": OFFICE_PERNEM,
    "KPST": OFFICE_KORGAO
}

# Google Sheets & Cloud Backup Configuration Defaults
DEFAULT_SPREADSHEET_ID = "1DC9TY2D2_mJgyJJ_hM3a91UsSOuqssWiBuMKhaxoW_0"
DEFAULT_WORKSHEET_NAME = "Candidates"
DEFAULT_SYNC_INTERVAL_MINUTES = 10
DEFAULT_APPS_SCRIPT_URL = "https://script.google.com/macros/s/AKfycbx_YOUR_DEPLOYMENT_ID/exec"


# Villages in Pernem (Pedne) Taluka, Goa
PERNEM_VILLAGES = [
    "Agarwada",
    "Alorna",
    "Amberem",
    "Arambol (Harmal)",
    "Casarvarnem (Kasarvarnem)",
    "Chandel",
    "Chopdem",
    "Corgao",
    "Dargalim",
    "Ibrampur",
    "Mandrem",
    "Morjim",
    "Mopa",
    "Ozorim",
    "Paliem",
    "Parsem",
    "Pernem (Town)",
    "Poroscodem",
    "Querim (Keri)",
    "Tamboxem",
    "Tiracol (Terekhol)",
    "Torxem",
    "Tuem",
    "Uguem",
    "Varcond",
    "Virnora",
    "Other"
]

# Educational Qualification Options
QUALIFICATION_LEVELS = [
    "Below 10th",
    "10th / SSC",
    "12th / HSSC (Arts)",
    "12th / HSSC (Commerce)",
    "12th / HSSC (Science)",
    "12th / HSSC (Vocational)",
    "ITI / Technical Certificate",
    "Polytechnic Diploma",
    "Graduate - B.A.",
    "Graduate - B.Com",
    "Graduate - B.Sc",
    "Graduate - B.E. / B.Tech",
    "Graduate - BBA / BCA",
    "Graduate - Other",
    "Post Graduate - M.A.",
    "Post Graduate - M.Com",
    "Post Graduate - M.Sc",
    "Post Graduate - M.E. / M.Tech",
    "Post Graduate - MBA / MCA",
    "Post Graduate - Other",
    "Doctorate / Ph.D.",
    "Other"
]

# Employment Status Types
STATUS_EMPLOYED = "EMPLOYED"
STATUS_UNEMPLOYED = "UNEMPLOYED"
STATUS_SELF_EMPLOYED = "SELF_EMPLOYED"
STATUS_STUDENT = "STUDENT"

EMPLOYMENT_STATUSES = [
    STATUS_EMPLOYED,
    STATUS_UNEMPLOYED,
    STATUS_SELF_EMPLOYED,
    STATUS_STUDENT
]

# Employment Categories
CATEGORY_GOVERNMENT = "Government"
CATEGORY_PRIVATE = "Private"

EMPLOYMENT_CATEGORIES = [
    CATEGORY_GOVERNMENT,
    CATEGORY_PRIVATE
]

# Government Job Result Statuses
RESULT_STATUS_AWAITING = "Awaiting Result"
RESULT_STATUS_EXAM_PENDING = "Examination Pending"
RESULT_STATUS_INTERVIEW_PENDING = "Interview Pending"
RESULT_STATUS_SELECTED = "Selected"
RESULT_STATUS_NOT_SELECTED = "Not Selected"
RESULT_STATUS_OTHER = "Other"

GOVT_RESULT_STATUSES = [
    RESULT_STATUS_AWAITING,
    RESULT_STATUS_EXAM_PENDING,
    RESULT_STATUS_INTERVIEW_PENDING,
    RESULT_STATUS_SELECTED,
    RESULT_STATUS_NOT_SELECTED,
    RESULT_STATUS_OTHER
]

# Experience Ranges for Reporting
EXPERIENCE_RANGES = [
    "0 years (Fresher)",
    "Less than 1 year",
    "1–3 years",
    "3–5 years",
    "5–10 years",
    "10+ years"
]

# Job Sectors Common in Pernem / Goa
JOB_SECTORS = [
    "Information Technology & Software",
    "Hospitality & Tourism",
    "Government Administration",
    "Manufacturing & Industrial (Tuem IDC / Verna)",
    "Retail & Sales",
    "Healthcare & Pharmaceuticals",
    "Banking, Finance & Insurance",
    "Education & Teaching",
    "Logistics, Aviation & Transport (Mopa Airport)",
    "Construction & Real Estate",
    "Agriculture & Fisheries",
    "Security & Facility Management",
    "Customer Support / BPO",
    "Automobile & Mechanical",
    "Electrical & Maintenance",
    "Other"
]

# Employment Types
EMPLOYMENT_TYPES = [
    "Full-Time",
    "Part-Time",
    "Contract / Temporary",
    "Apprenticeship / Trainee",
    "Freelance / Remote",
    "Any"
]

# Synchronisation Status Values
SYNC_STATUS_PENDING = "PENDING"
SYNC_STATUS_SYNCED = "SYNCED"
SYNC_STATUS_FAILED = "FAILED"

# Google Sheets 42-Column Canonical Flat Schema
GOOGLE_SHEETS_COLUMNS = [
    "Candidate ID",
    "Registration Date",
    "Full Name",
    "DOB",
    "Age",
    "Gender",
    "Address",
    "Village",
    "Taluka",
    "Pincode",
    "Mobile",
    "Alternate Mobile",
    "Email",
    "Highest Qualification",
    "Course",
    "Specialisation",
    "Institution",
    "Passing Year",
    "Skills",
    "Certifications",
    "Employment Status",
    "Employment Category",
    "Organisation",
    "Designation",
    "Work Location",
    "Years Experience",
    "Previous Experience",
    "Applied Government Job",
    "Government Application/Post",
    "Government Application Year",
    "Government Result Status",
    "Self Employment Details",
    "Preferred Sector",
    "Preferred Role",
    "Preferred Location",
    "Willing To Relocate",
    "Preferred Employment Type",
    "Languages",
    "Remarks",
    "Created At",
    "Updated At",
    "Sync Status"
]
