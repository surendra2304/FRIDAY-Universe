"""TASK-FRD-061 — lead verification pass for FRIDAY's lead-gen errand.

The errand (``friday.autonomous.lead_generation``) extracts contacts
from a directory listing and delivers a table. It never checked whether
those contacts are still alive. This module adds the missing step from
the Yello-directory pattern (friday package F-28, reel DPGp5CbDJ-v):
verify each lead's phone/email against its current public listing
BEFORE outreach, so no effort is spent on dead contacts.

Statuses (every lead carries one, with the check date):
- ``verified`` — at least one contact route is on file and every route
  present checks out (website reachable, email domain resolves, phone
  format plausible).
- ``stale`` — a route on file provably fails (website 4xx/5xx or
  refused, email domain does not resolve, email/phone format invalid).
- ``unverifiable`` — no contact routes on file at all, or a check could
  not run (network/DNS error while checking — that is "could not tell",
  never "dead").

Hard boundaries (same as the errand): public data only, no scraping
behind logins, no outreach — this module never sends mail, never dials,
never messages anyone. A mailbox is never probed; email is checked by
format + domain resolution only. Website checks reuse the errand's
SSRF guard (``check_url_allowed``) and the injected fetcher, so tests
stay hermetic and production never fetches a private address.
"""

from __future__ import annotations

import csv
import io
import re
import socket
from datetime import datetime
from typing import Any, Callable

from friday.autonomous.lead_generation import (
    Lead,
    _EMAIL_RE,
    _PHONE_RE,
    check_url_allowed,
)
from friday.core.owner_time import now_owner_tz

STATUS_VERIFIED = "verified"
STATUS_STALE = "stale"
STATUS_UNVERIFIABLE = "unverifiable"
STATUS_UNCHECKED = "unchecked"

ALL_STATUSES = (STATUS_VERIFIED, STATUS_STALE, STATUS_UNVERIFIABLE, STATUS_UNCHECKED)


def _digits(phone: str) -> str:
    return re.sub(r"\D", "", phone or "")


def _default_dns_resolver(host: str) -> bool:
    """True when the host resolves (any address family). Never raises."""
    try:
        socket.getaddrinfo(host, None)
    except (socket.gaierror, OSError, UnicodeError):
        return False
    return True


def _default_website_checker(url: str) -> tuple[bool, str]:
    """Fetch a website head (SSRF-guarded). Returns (ok, detail)."""
    reason = check_url_allowed(url)
    if reason:
        return False, f"not checked: {reason}"
    import httpx  # fleet dependency, imported lazily

    try:
        with httpx.Client(timeout=5.0, follow_redirects=True) as client:
            resp = client.get(url, headers={"User-Agent": "FRIDAY-LeadVerify/1.0"})
    except Exception as exc:  # network failure is "could not tell", not "dead"
        return False, f"could not reach to check ({type(exc).__name__})"
    if 200 <= resp.status_code < 400:
        return True, f"HTTP {resp.status_code}"
    return False, f"HTTP {resp.status_code}"


def verify_lead(
    lead: Lead,
    *,
    website_checker: Callable[[str], tuple[bool, str]] | None = None,
    dns_resolver: Callable[[str], bool] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Verify one lead's contact routes. Fills lead.status/checked_at/note.

    Returns ``{"lead": lead, "status": ..., "checked_at": ..., "checks": {...},
    "reason": ...}``. ``checks`` maps each route to
    ``{"result": "ok" | "failed" | "skipped" | "unknown", "detail": ...}``.
    """
    moment = now or now_owner_tz()
    checked_at = moment.strftime("%Y-%m-%d %H:%M IST")
    check_website = website_checker or _default_website_checker
    resolve = dns_resolver or _default_dns_resolver

    checks: dict[str, dict[str, str]] = {}
    failed: list[str] = []
    unknown: list[str] = []
    present = 0

    # Website: reachable means the public listing still serves.
    if (lead.website or "").strip():
        present += 1
        ok, detail = check_website(lead.website.strip())
        if ok:
            checks["website"] = {"result": "ok", "detail": detail}
        elif detail.startswith("could not reach") or detail.startswith("not checked"):
            checks["website"] = {"result": "unknown", "detail": detail}
            unknown.append(f"website {detail}")
        else:
            checks["website"] = {"result": "failed", "detail": detail}
            failed.append(f"website {detail}")
    else:
        checks["website"] = {"result": "skipped", "detail": "no website on file"}

    # Email: format + domain resolution only. A mailbox is never probed.
    if (lead.email or "").strip():
        present += 1
        email = lead.email.strip()
        if not _EMAIL_RE.fullmatch(email):
            checks["email"] = {"result": "failed", "detail": "invalid email format"}
            failed.append("email format invalid")
        else:
            domain = email.rsplit("@", 1)[1]
            if resolve(domain):
                checks["email"] = {"result": "ok", "detail": f"domain {domain} resolves"}
            else:
                checks["email"] = {"result": "failed", "detail": f"domain {domain} does not resolve"}
                failed.append(f"email domain {domain} does not resolve")
    else:
        checks["email"] = {"result": "skipped", "detail": "no email on file"}

    # Phone: format plausibility only. Nobody is dialled.
    if (lead.phone or "").strip():
        present += 1
        phone = lead.phone.strip()
        if _PHONE_RE.search(phone) and len(_digits(phone)) >= 7:
            checks["phone"] = {"result": "ok", "detail": "plausible format"}
        else:
            checks["phone"] = {"result": "failed", "detail": "implausible phone format"}
            failed.append("phone format implausible")
    else:
        checks["phone"] = {"result": "skipped", "detail": "no phone on file"}

    if present == 0:
        status, reason = STATUS_UNVERIFIABLE, "no contact routes on file"
    elif failed:
        status, reason = STATUS_STALE, "; ".join(failed)
    elif unknown:
        status, reason = STATUS_UNVERIFIABLE, "; ".join(unknown)
    else:
        status, reason = STATUS_VERIFIED, "all routes on file check out"

    lead.status = status
    lead.checked_at = checked_at
    lead.verification_note = reason
    return {
        "lead": lead,
        "status": status,
        "checked_at": checked_at,
        "checks": checks,
        "reason": reason,
    }


def verify_leads(
    leads: list[Lead],
    *,
    website_checker: Callable[[str], tuple[bool, str]] | None = None,
    dns_resolver: Callable[[str], bool] | None = None,
    now: datetime | None = None,
) -> list[dict[str, Any]]:
    """Verify every lead in a list, in order. Returns one result per lead."""
    return [
        verify_lead(
            lead,
            website_checker=website_checker,
            dns_resolver=dns_resolver,
            now=now,
        )
        for lead in leads
    ]


def finalize_outreach_list(
    leads: list[Lead], *, drop_stale: bool = True
) -> dict[str, Any]:
    """Split a verified list into the final outreach list and the dropped.

    Stale leads are dropped by default (they are dead contacts — the
    whole point of the pass); unverifiable leads stay, flagged, for the
    owner to decide. With ``drop_stale=False`` stale leads stay too, as
    flagged entries. Counts are reported either way.
    """
    counts = {status: 0 for status in ALL_STATUSES}
    for lead in leads:
        counts[lead.status] = counts.get(lead.status, 0) + 1
    if drop_stale:
        final = [lead for lead in leads if lead.status != STATUS_STALE]
        dropped = [lead for lead in leads if lead.status == STATUS_STALE]
    else:
        final, dropped = list(leads), []
    return {
        "final": final,
        "dropped": dropped,
        "counts": counts,
        "total": len(leads),
    }


def render_verification_table(leads: list[Lead], fmt: str = "markdown") -> str:
    """Render a verified list (status + checked date per lead).

    The errand's own ``render_table`` is left untouched (its tests assert
    its exact shape); this is the verified-list rendering.
    """
    if fmt == "csv":
        out = io.StringIO()
        writer = csv.writer(out)
        writer.writerow(["name", "phone", "email", "website", "category", "status", "checked_at", "note", "source_url"])
        for lead in leads:
            writer.writerow([lead.name, lead.phone, lead.email, lead.website,
                             lead.category, lead.status, lead.checked_at,
                             lead.verification_note, lead.source_url])
        return out.getvalue()
    lines = ["| Name | Phone | Email | Website | Status | Checked | Note |",
             "|---|---|---|---|---|---|---|"]
    for lead in leads:
        def cell(v: str) -> str:
            return (v or "").replace("|", "/").strip()
        lines.append(f"| {cell(lead.name)} | {cell(lead.phone)} | {cell(lead.email)} "
                     f"| {cell(lead.website)} | {cell(lead.status)} | {cell(lead.checked_at)} "
                     f"| {cell(lead.verification_note)} |")
    return "\n".join(lines)


__all__ = [
    "STATUS_VERIFIED",
    "STATUS_STALE",
    "STATUS_UNVERIFIABLE",
    "STATUS_UNCHECKED",
    "verify_lead",
    "verify_leads",
    "finalize_outreach_list",
    "render_verification_table",
]
