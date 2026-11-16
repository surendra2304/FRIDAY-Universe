"""IntelX public-footprint OSINT lookups (TASK-IG-INT-04)."""

from intelx.osint.audit import FootprintAudit
from intelx.osint.breach_check import (
    EmailBreachResult,
    PasswordBreachResult,
    check_email_breaches,
    check_password_breach,
)
from intelx.osint.email import EmailFootprint, check_email
from intelx.osint.phone import PhoneInfo, parse_phone
from intelx.osint.username import UsernameHit, check_username

__all__ = [
    "EmailBreachResult",
    "EmailFootprint",
    "FootprintAudit",
    "PasswordBreachResult",
    "PhoneInfo",
    "UsernameHit",
    "check_email",
    "check_email_breaches",
    "check_password_breach",
    "check_username",
    "parse_phone",
]
