"""IntelX public-footprint OSINT lookups (TASK-IG-INT-04)."""

from intelx.osint.audit import FootprintAudit
from intelx.osint.breach_check import (
    EmailBreachResult,
    PasswordBreachResult,
    check_email_breaches,
    check_password_breach,
)
from intelx.osint.email import EmailFootprint, check_email
from intelx.osint.helix_lookup import HelixHit, HelixReport, helix_lookup
from intelx.osint.helix_watch import HelixWatchStore, diff_helix_reports, get_watch_store
from intelx.osint.image_ela import (
    ImageElaResult,
    check_image_ela,
    check_image_file_ela,
    ela_reading_guide,
)
from intelx.osint.phone import PhoneInfo, parse_phone
from intelx.osint.username import UsernameHit, check_username

__all__ = [
    "EmailBreachResult",
    "EmailFootprint",
    "FootprintAudit",
    "HelixHit",
    "HelixReport",
    "HelixWatchStore",
    "ImageElaResult",
    "diff_helix_reports",
    "get_watch_store",
    "PasswordBreachResult",
    "PhoneInfo",
    "UsernameHit",
    "check_email",
    "check_email_breaches",
    "check_password_breach",
    "check_image_ela",
    "check_image_file_ela",
    "check_username",
    "ela_reading_guide",
    "helix_lookup",
    "parse_phone",
]
