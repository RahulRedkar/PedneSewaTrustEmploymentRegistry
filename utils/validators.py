"""
Validation utilities for candidate intake forms.
Enforces relaxed validation rules suitable for field enumerators:
Only Full Name, Mobile, Village, and Employment Status are mandatory.
"""

import re
from datetime import datetime, date
from typing import Tuple, Dict, Any, Optional

# Indian mobile: 10 digits optionally prefixed by +91 or 0, starting with 6-9
INDIAN_MOBILE_REGEX = re.compile(r"^(?:\+91|91|0)?[6-9]\d{9}$")
EMAIL_REGEX = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
PINCODE_REGEX = re.compile(r"^\d{6}$")


def clean_mobile(mobile: str) -> str:
    """Extracts raw 10-digit mobile number, removing prefixes/spaces."""
    if not mobile:
        return ""
    digits = re.sub(r"\D", "", mobile)
    if len(digits) == 10:
        return digits
    elif len(digits) > 10 and digits.startswith("91"):
        return digits[-10:]
    elif len(digits) == 11 and digits.startswith("0"):
        return digits[1:]
    return digits


def validate_mobile(mobile: str) -> Tuple[bool, str]:
    """Validates 10-digit Indian mobile number."""
    if not mobile or not mobile.strip():
        return False, "Mobile number is required."
    clean = clean_mobile(mobile)
    if len(clean) == 10 and clean[0] in "6789":
        return True, ""
    return False, "Please enter a valid 10-digit Indian mobile number."


def validate_email(email: str) -> Tuple[bool, str]:
    """Validates email format if provided; empty is allowed."""
    if not email or not email.strip():
        return True, ""
    if EMAIL_REGEX.match(email.strip()):
        return True, ""
    return False, "Please enter a valid email address."


def validate_pincode(pincode: str) -> Tuple[bool, str]:
    """Validates 6-digit postal pincode if provided; empty is allowed."""
    if not pincode or not pincode.strip():
        return True, ""
    if PINCODE_REGEX.match(pincode.strip()):
        return True, ""
    return False, "Pincode must be 6 digits."


def calculate_age_from_dob(dob_input: Any) -> Optional[int]:
    """Calculates integer age from Date of Birth (string YYYY-MM-DD or date/QDate)."""
    if not dob_input:
        return None
    try:
        if isinstance(dob_input, (datetime, date)):
            birth_date = dob_input if isinstance(dob_input, date) else dob_input.date()
        else:
            s = str(dob_input).strip()
            # Try multiple common formats
            for fmt in ("%Y-%m-%d", "%d-%m-%Y", "%d/%m/%Y", "%Y/%m/%d"):
                try:
                    birth_date = datetime.strptime(s, fmt).date()
                    break
                except ValueError:
                    continue
            else:
                return None

        today = date.today()
        age = today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
        return max(0, age) if age >= 0 else None
    except Exception:
        return None


def validate_candidate_form(data: Dict[str, Any]) -> Tuple[bool, Dict[str, str]]:
    """
    Validates complete candidate intake payload.
    Returns: (is_valid, errors_dict)
    """
    errors: Dict[str, str] = {}

    # 1. Full Name (Mandatory)
    name = str(data.get("full_name", "")).strip()
    if not name:
        errors["full_name"] = "Full name is required."
    elif len(name) < 2:
        errors["full_name"] = "Full name must be at least 2 characters."

    # 2. Mobile Number (Mandatory)
    mobile = str(data.get("mobile", "")).strip()
    valid_mobile, mob_err = validate_mobile(mobile)
    if not valid_mobile:
        errors["mobile"] = mob_err

    # 3. Alternate Mobile (Optional)
    alt_mobile = str(data.get("alternate_mobile", "")).strip()
    if alt_mobile:
        valid_alt, alt_err = validate_mobile(alt_mobile)
        if not valid_alt:
            errors["alternate_mobile"] = f"Alternate: {alt_err}"

    # 4. Email (Optional)
    email = str(data.get("email", "")).strip()
    if email:
        valid_email, email_err = validate_email(email)
        if not valid_email:
            errors["email"] = email_err

    # 5. Village (Mandatory)
    village = str(data.get("village", "")).strip()
    if not village:
        errors["village"] = "Village selection is required."

    # 6. Pincode (Optional)
    pincode = str(data.get("pincode", "")).strip()
    if pincode:
        valid_pin, pin_err = validate_pincode(pincode)
        if not valid_pin:
            errors["pincode"] = pin_err

    # 7. Employment Status (Mandatory)
    status = str(data.get("employment_status", "")).strip().upper()
    valid_statuses = {"EMPLOYED", "UNEMPLOYED", "SELF_EMPLOYED", "STUDENT"}
    if not status:
        errors["employment_status"] = "Employment status selection is required."
    elif status not in valid_statuses:
        errors["employment_status"] = f"Invalid status: {status}"

    # 8. Numeric range checks if provided
    age_val = data.get("age")
    if age_val is not None and str(age_val).strip() != "":
        try:
            a = int(age_val)
            if a < 0 or a > 120:
                errors["age"] = "Age must be between 0 and 120."
        except ValueError:
            errors["age"] = "Age must be a valid number."

    years_exp = data.get("years_experience")
    if years_exp is not None and str(years_exp).strip() != "":
        try:
            exp = float(years_exp)
            if exp < 0 or exp > 70:
                errors["years_experience"] = "Years of experience must be between 0 and 70."
        except ValueError:
            errors["years_experience"] = "Experience must be a valid number."

    return len(errors) == 0, errors
