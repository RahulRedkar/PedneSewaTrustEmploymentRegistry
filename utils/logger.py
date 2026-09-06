"""
Logging utility for Pedne Sewa Trust - Employment Registry.
Ensures sensitive personal data (mobile, email, address) is redacted from application logs.
"""

import logging
import re
import os
import sys
from pathlib import Path

# Common patterns for sensitive personal info
_MOBILE_PATTERN = re.compile(r'\b(?:\+?91[\-\s]?)?[6789]\d{9}\b')
_EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')


class RedactingFormatter(logging.Formatter):
    """Custom formatter to redact PII like mobile numbers and emails from logs."""

    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        # Redact mobile numbers, preserving last 4 digits for debugging
        def redact_mobile(match):
            m = match.group(0)
            return "X" * (len(m) - 4) + m[-4:] if len(m) >= 4 else "XXXX"

        # Redact email addresses
        def redact_email(match):
            e = match.group(0)
            parts = e.split("@")
            user = parts[0]
            domain = parts[1] if len(parts) > 1 else ""
            redacted_user = user[0] + "***" if len(user) > 1 else "***"
            return f"{redacted_user}@{domain}"

        msg = _MOBILE_PATTERN.sub(redact_mobile, msg)
        msg = _EMAIL_PATTERN.sub(redact_email, msg)
        return msg


def setup_logger(log_dir: str = None) -> logging.Logger:
    """Configures application logger with both console and rotating file handlers."""
    logger = logging.getLogger("PedneSewaTrust")
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    # Format
    formatter = RedactingFormatter(
        fmt="%(asctime)s [%(levelname)s] (%(name)s:%(funcName)s:%(lineno)d) - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # File Handler
    try:
        if not log_dir:
            log_dir = os.path.join(os.path.expanduser("~"), ".pedne_sewa_trust", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, "app.log")
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(log_file, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)
    except Exception as e:
        print(f"Warning: Could not set up file logger: {e}", file=sys.stderr)

    return logger


logger = setup_logger()
