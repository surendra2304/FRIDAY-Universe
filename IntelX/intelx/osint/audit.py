"""Personal digital-footprint audit (TASK-IG-INT-04).

Implements the corpus idea from item Dc-9-4kyO-o ("What can someone find
about you online? A personal footprint audit") by composing this package's
keyless checks — username presence, email public profile, phone format —
into one report, and by listing, IN the report itself, what could NOT be
checked and why. An audit that silently omits the unchecked surfaces
overstates its own coverage; this one never does.

Explicitly out of scope, named in every report:
  * Dark-web / leak-forum search (item DaiasjkJSVn) — there is no keyless,
    safe, legal public source; commercial indexes and Tor scraping are not
    something this fleet performs. Stated, not simulated.
  * Breach-database checks — HIBP requires a paid API key.
  * Carrier / line-type lookup — commercial APIs only.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Awaitable, Callable

from intelx.osint.email import BREACH_CHECK_NOTE, check_email
from intelx.osint.phone import CARRIER_LOOKUP_NOTE, parse_phone
from intelx.osint.username import check_username

UTC = timezone.utc

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]

UNAVAILABLE_SECTIONS: list[dict] = [
    {
        "section": "dark_web_search",
        "status": "not_implemented",
        "reason": (
            "No keyless, safe public source exists for dark-web/leak-forum search; "
            "commercial indexes require paid access and Tor scraping is out of fleet policy. "
            "This surface was NOT checked."
        ),
    },
    {
        "section": "breach_database_check",
        "status": "not_implemented",
        "reason": BREACH_CHECK_NOTE,
    },
    {
        "section": "carrier_line_type_lookup",
        "status": "not_implemented",
        "reason": CARRIER_LOOKUP_NOTE,
    },
]


class FootprintAudit:
    """Composes the keyless footprint checks into a single honest report."""

    def __init__(self, fetch: FetchBytes | None = None) -> None:
        self._fetch = fetch

    async def run(
        self,
        username: str | None = None,
        email: str | None = None,
        phone: str | None = None,
    ) -> dict:
        if not (username or email or phone):
            raise ValueError("at least one of username, email or phone is required")
        report: dict = {
            "generated_at": datetime.now(UTC).isoformat(),
            "subject": {"username": username, "email": email, "phone": phone},
            "sections": {},
            "unavailable": list(UNAVAILABLE_SECTIONS),
            "coverage_note": (
                "This audit covers only the public, keyless checks listed under 'sections'. "
                "Surfaces under 'unavailable' were NOT checked; absence of a finding there "
                "means nothing."
            ),
        }
        if username:
            hits = await check_username(username, fetch=self._fetch)
            report["sections"]["username"] = {
                "found": [h.to_dict() for h in hits if h.status == "found"],
                "not_found": [h.to_dict() for h in hits if h.status == "not_found"],
                "unknown": [h.to_dict() for h in hits if h.status == "unknown"],
            }
        if email:
            report["sections"]["email"] = (await check_email(email, fetch=self._fetch)).to_dict()
        if phone:
            report["sections"]["phone"] = parse_phone(phone).to_dict()
        return report


__all__ = ["UNAVAILABLE_SECTIONS", "FootprintAudit"]
