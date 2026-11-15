"""Email public-footprint checks (TASK-IG-INT-04).

Keyless subset (corpus items DaIzCa0Dbgq, Dc-9-4kyO-o):

  * Gravatar — a public profile/avatar keyed by the MD5 of the normalised
    email. Existence is checked with the documented ``?d=404`` behaviour
    (verified live 2026-11-15: unknown emails return 404, known return the
    image). The public profile JSON, when present, is returned verbatim —
    display name, about text and linked URLs are the owner's own published
    fields, quoted, never paraphrased into claims.
  * Breach exposure (Have I Been Pwned) — the API REQUIRES an API key.
    ``EmailFootprint.breach_check`` states that plainly as a structured
    unavailable result. It is never simulated: a footprint report that
    claims "no breaches found" without having checked would be a
    fabrication, so this module refuses to produce one.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Awaitable, Callable

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]

BREACH_CHECK_NOTE = (
    "unavailable: Have I Been Pwned requires a paid API key (HIBP_API_KEY not configured); "
    "breach exposure was NOT checked and must not be read as 'no breaches'"
)


@dataclass(frozen=True)
class GravatarProfile:
    exists: bool
    profile_url: str
    avatar_url: str
    display_name: str = ""
    about: str = ""  # verbatim 'aboutMe' from the public profile, if any
    linked_urls: list[dict] = field(default_factory=list)  # verbatim 'urls' entries

    def to_dict(self) -> dict:
        return {
            "exists": self.exists,
            "profile_url": self.profile_url,
            "avatar_url": self.avatar_url,
            "display_name": self.display_name,
            "about": self.about,
            "linked_urls": self.linked_urls,
        }


@dataclass(frozen=True)
class EmailFootprint:
    email: str
    email_md5: str
    gravatar: GravatarProfile
    breach_check: str = BREACH_CHECK_NOTE

    def to_dict(self) -> dict:
        return {
            "email": self.email,
            "email_md5": self.email_md5,
            "gravatar": self.gravatar.to_dict(),
            "breach_check": self.breach_check,
        }


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


async def check_email(email: str, fetch: FetchBytes | None = None) -> EmailFootprint:
    """Run the keyless email footprint checks (Gravatar today)."""
    normalised = (email or "").strip().lower()
    if "@" not in normalised or normalised.startswith("@") or normalised.endswith("@"):
        raise ValueError(f"invalid email address {email!r}")
    fetch = fetch or _default_fetch
    digest = hashlib.md5(normalised.encode("utf-8")).hexdigest()
    avatar_url = f"https://www.gravatar.com/avatar/{digest}?d=404"
    profile_url = f"https://www.gravatar.com/{digest}.json"

    status, _, _ = await fetch(avatar_url)
    exists = status == 200

    display_name = ""
    about = ""
    linked: list[dict] = []
    if exists:
        pstatus, _, pbody = await fetch(profile_url)
        if pstatus == 200:
            try:
                entry = (json.loads(pbody.decode("utf-8", errors="replace")).get("entry") or [{}])[0]
                display_name = str(entry.get("displayName", ""))
                about = str(entry.get("aboutMe", ""))
                linked = [
                    {"title": str(u.get("title", "")), "value": str(u.get("value", ""))}
                    for u in entry.get("urls", []) or []
                ]
            except (json.JSONDecodeError, AttributeError, IndexError):
                pass  # avatar exists but no parseable public profile: exists stays True

    return EmailFootprint(
        email=normalised,
        email_md5=digest,
        gravatar=GravatarProfile(
            exists=exists,
            profile_url=f"https://www.gravatar.com/{digest}",
            avatar_url=f"https://www.gravatar.com/avatar/{digest}",
            display_name=display_name,
            about=about,
            linked_urls=linked,
        ),
    )


__all__ = ["BREACH_CHECK_NOTE", "EmailFootprint", "GravatarProfile", "check_email"]
