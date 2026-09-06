"""
Unit tests for candidate validators and relaxed field rules.
"""

import pytest
from datetime import date
from utils.validators import (
    validate_mobile,
    validate_email,
    validate_pincode,
    calculate_age_from_dob,
    validate_candidate_form,
    clean_mobile
)


def test_clean_mobile():
    assert clean_mobile("+91 9876543210") == "9876543210"
    assert clean_mobile("09876543210") == "9876543210"
    assert clean_mobile("9876543210") == "9876543210"
    assert clean_mobile("919876543210") == "9876543210"


def test_validate_mobile():
    assert validate_mobile("9876543210")[0] is True
    assert validate_mobile("8888888888")[0] is True
    assert validate_mobile("7123456789")[0] is True
    assert validate_mobile("6123456789")[0] is True
    assert validate_mobile("1234567890")[0] is False  # Must start with 6-9
    assert validate_mobile("")[0] is False           # Required


def test_validate_email():
    assert validate_email("")[0] is True             # Optional
    assert validate_email("test@example.com")[0] is True
    assert validate_email("invalid-email")[0] is False


def test_validate_pincode():
    assert validate_pincode("")[0] is True           # Optional
    assert validate_pincode("403512")[0] is True
    assert validate_pincode("40351")[0] is False     # Must be 6 digits
    assert validate_pincode("abc123")[0] is False


def test_calculate_age_from_dob():
    assert calculate_age_from_dob("2000-01-01") is not None
    assert calculate_age_from_dob("01-01-2000") is not None
    assert calculate_age_from_dob(None) is None
    assert calculate_age_from_dob("invalid") is None


def test_validate_candidate_form_mandatory_only():
    # Only Name, Mobile, Village, Employment Status are strictly required
    data = {
        "full_name": "Rohan Parab",
        "mobile": "9822112233",
        "village": "Corgao",
        "employment_status": "EMPLOYED"
    }
    is_valid, errors = validate_candidate_form(data)
    assert is_valid is True
    assert len(errors) == 0


def test_validate_candidate_form_missing_required():
    data = {
        "full_name": "",
        "mobile": "1234",
        "village": "",
        "employment_status": ""
    }
    is_valid, errors = validate_candidate_form(data)
    assert is_valid is False
    assert "full_name" in errors
    assert "mobile" in errors
    assert "village" in errors
    assert "employment_status" in errors
