"""HaveIBeenPwned breach checks for IntelX OSINT lookups (TASK-IG2-INT-06).

Cluster #48: add HIBP breach checks inside IntelX identity/OSINT lookups.
Owner rule: FREE only, no paid API key. What HIBP actually offers for
free, stated plainly:

  * **Pwned Passwords range API — free, no key.** ``GET
    https://api.pwnedpasswords.com/range/{prefix}`` where ``prefix`` is
    the first 5 hex chars of the password's SHA-1. This is k-anonymity:
    only the 5-char prefix leaves the machine; the password and its full
    hash never do. :func:`check_password_breach` implements this fully —
    it is a real, working check.
  * **Breached-account API (v3) — NOT free.** Looking up an email's
    breaches requires a paid HIBP subscription key; there is no free
    email-breach endpoint. :func:`check_email_breaches` therefore ships
    *behind the key that does not exist yet*: with no ``HIBP_API_KEY``
    configured it returns ``status="unavailable"`` with the reason
    stated and ``checked=False`` — it never fabricates a "no breaches"
    answer. If the owner ever supplies a key, the same function performs
    the real v3 call unchanged.

Both functions take an injectable fetcher for hermetic tests, mirroring
the rest of ``intelx.osint``.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Awaitable, Callable

logger = logging.getLogger("intelx.osint.breach_check")

# (url, headers) -> (status, body_text)
FetchText = Callable[[str, dict], Awaitable[tuple[int, str]]]

PWNED_PASSWORDS_RANGE_URL = "https://api.pwnedpasswords.com/range/{prefix}"
HIBP_BREACHED_ACCOUNT_URL = "https://haveibeenpwned.com/api/v3/breachedaccount/{account}?truncateResponse=false"

EMAIL_UNAVAILABLE_REASON = (
    "HIBP breached-account lookups require a paid subscription API key; "
    "no free email-breach endpoint exists and no HIBP_API_KEY is "
    "configured (owner rule: free only). This check was NOT performed — "
    "an unavailable check is never reported as 'no breaches found'."
)


@dataclass(frozen=True)
class PasswordBreachResult:
    found: bool
    occurrences: int  # times the password appears in breach corpora (0 if not found)
    sha1_prefix: str  # the only data that left the machine
    checked: bool = True

    def to_dict(self) -> dict:
        return {
            "checked": self.checked,
            "found": self.found,
            "occurrences": self.occurrences,
            "sha1_prefix": self.sha1_prefix,
            "method": "pwned-passwords-range (k-anonymity, free, no key)",
        }


@dataclass(frozen=True)
class EmailBreachResult:
    email: str
    status: str  # "breaches_found" | "no_breaches" | "unavailable" | "error"
    checked: bool
    breaches: tuple[dict, ...] = ()
    reason: str = ""

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "status": self.status,
            "checked": self.checked,
            "breaches": list(self.breaches),
            "reason": self.reason,
        }


async def _default_fetch(url: str, headers: dict) -> tuple[int, str]:
    import urllib.request

    def _get() -> tuple[int, str]:
        request = urllib.request.Request(url, headers={"User-Agent": "FRIDAY-IntelX", **headers})
        try:
            with urllib.request.urlopen(request, timeout=15) as response:
                return response.status, response.read().decode("utf-8", errors="ignore")
        except urllib.error.HTTPError as exc:
            return exc.code, exc.read().decode("utf-8", errors="ignore") if exc.fp else ""

    import asyncio

    return await asyncio.to_thread(_get)


def parse_range_response(body: str, suffix: str) -> int:
    """Occurrence count for ``suffix`` in a Pwned Passwords range body."""
    wanted = suffix.upper()
    for line in body.splitlines():
        candidate, _, count = line.partition(":")
        if candidate.strip().upper() == wanted:
            try:
                return int(count.strip())
            except ValueError:
                return 0
    return 0


async def check_password_breach(
    password: str,
    fetch: FetchText | None = None,
) -> PasswordBreachResult:
    """Check a password against Pwned Passwords via k-anonymity (free).

    Only the first 5 hex chars of the SHA-1 digest are sent; the rest of
    the comparison happens locally against the returned suffix list.
    """
    if not password:
        raise ValueError("password must be non-empty")
    digest = hashlib.sha1(password.encode("utf-8")).hexdigest().upper()
    prefix, suffix = digest[:5], digest[5:]
    fetch = fetch or _default_fetch
    status, body = await fetch(PWNED_PASSWORDS_RANGE_URL.format(prefix=prefix), {})
    if status != 200:
        raise RuntimeError(f"pwned passwords range API returned HTTP {status}")
    occurrences = parse_range_response(body, suffix)
    return PasswordBreachResult(found=occurrences > 0, occurrences=occurrences, sha1_prefix=prefix)


async def check_email_breaches(
    email: str,
    fetch: FetchText | None = None,
    api_key: str | None = None,
) -> EmailBreachResult:
    """Check an email against HIBP breached-account v3 — key-gated, honestly.

    Without a key this returns ``unavailable`` (see module docstring):
    the free surface for email breaches does not exist, and this function
    will not pretend otherwise.
    """
    if not email or "@" not in email:
        raise ValueError(f"invalid email {email!r}")
    key = api_key if api_key is not None else os.environ.get("HIBP_API_KEY", "")
    if not key:
        return EmailBreachResult(email=email, status="unavailable", checked=False,
                                 reason=EMAIL_UNAVAILABLE_REASON)
    fetch = fetch or _default_fetch
    from urllib.parse import quote

    url = HIBP_BREACHED_ACCOUNT_URL.format(account=quote(email, safe=""))
    status, body = await fetch(url, {"hibp-api-key": key, "user-agent": "FRIDAY-IntelX"})
    if status == 404:
        return EmailBreachResult(email=email, status="no_breaches", checked=True)
    if status != 200:
        return EmailBreachResult(email=email, status="error", checked=False,
                                 reason=f"HIBP API returned HTTP {status}; check not completed")
    try:
        entries = json.loads(body)
    except json.JSONDecodeError:
        return EmailBreachResult(email=email, status="error", checked=False,
                                 reason="HIBP API returned unparseable JSON; check not completed")
    breaches = tuple(
        {
            "name": entry.get("Name", ""),
            "domain": entry.get("Domain", ""),
            "breach_date": entry.get("BreachDate", ""),
            "pwn_count": entry.get("PwnCount", 0),
            "data_classes": entry.get("DataClasses", []),
        }
        for entry in entries
        if isinstance(entry, dict)
    )
    return EmailBreachResult(email=email, status="breaches_found" if breaches else "no_breaches",
                             checked=True, breaches=breaches)
