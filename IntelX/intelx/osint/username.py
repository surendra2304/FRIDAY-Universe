"""Username existence checks across public platforms (TASK-IG-INT-04).

The Sherlock pattern (corpus items DaLZEXNjZQ5, DaIzCa0Dbgq): for a given
username, check whether a public profile exists at the canonical profile
URL of each curated platform. Read-only GETs only.

Verdict discipline — three states, never two:
  * ``found``     — HTTP 200 and no not-found marker in the page;
  * ``not_found`` — HTTP 404, or HTTP 200 with the platform's known
                    "no such user" marker in the body;
  * ``unknown``   — anything else (403 bot wall, 429, 5xx, network error).
                    Platforms that block automated reads report ``unknown``
                    with the reason — a block is never reported as absence.
"""

from __future__ import annotations

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Awaitable, Callable

logger = logging.getLogger("intelx.osint.username")

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]  # (status, final_url, body)


@dataclass(frozen=True)
class PlatformSpec:
    name: str
    url_template: str  # contains {u}
    not_found_markers: tuple[str, ...] = ()


# Curated for reliable status semantics. Platforms whose profile URLs need
# numeric ids (Stack Overflow) or that wall every automated read are absent
# by design — an all-unknown platform adds noise, not signal.
PLATFORMS: tuple[PlatformSpec, ...] = (
    PlatformSpec("GitHub", "https://github.com/{u}"),
    PlatformSpec("GitLab", "https://gitlab.com/{u}"),
    PlatformSpec("Keybase", "https://keybase.io/{u}"),
    PlatformSpec("Reddit", "https://www.reddit.com/user/{u}", ("page not found", "nobody on reddit goes by that name")),
    PlatformSpec("Mastodon (mastodon.social)", "https://mastodon.social/@{u}"),
    PlatformSpec("Bluesky", "https://bsky.app/profile/{u}", ("could not find", "profile not found")),
    PlatformSpec("Medium", "https://medium.com/@{u}", ("page not found",)),
    PlatformSpec("Dev.to", "https://dev.to/{u}", ("page not found",)),
    PlatformSpec("Hacker News", "https://news.ycombinator.com/user?id={u}", ("no such user",)),
    PlatformSpec("PyPI", "https://pypi.org/user/{u}/"),
    PlatformSpec("npm", "https://www.npmjs.com/~{u}", ("404 - not found",)),
    PlatformSpec("Wikipedia", "https://en.wikipedia.org/wiki/User:{u}", ("does not have an article", "this user does not exist")),
)

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


@dataclass(frozen=True)
class UsernameHit:
    platform: str
    profile_url: str
    status: str  # found | not_found | unknown
    detail: str

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "profile_url": self.profile_url,
            "status": self.status,
            "detail": self.detail,
        }


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


async def check_username(
    username: str,
    fetch: FetchBytes | None = None,
    platforms: tuple[PlatformSpec, ...] = PLATFORMS,
) -> list[UsernameHit]:
    """Check one username across the curated platforms (concurrent GETs)."""
    if not _USERNAME_RE.match(username or ""):
        raise ValueError(f"invalid username {username!r}: letters, digits, '.', '_' and '-' only, 1-64 chars")
    fetch = fetch or _default_fetch

    async def check_one(spec: PlatformSpec) -> UsernameHit:
        url = spec.url_template.format(u=username)
        try:
            status, _final, body = await fetch(url)
        except Exception as exc:  # network errors are unknowns, not absences
            return UsernameHit(spec.name, url, "unknown", f"fetch failed: {exc}")
        if status == 404:
            return UsernameHit(spec.name, url, "not_found", "HTTP 404")
        if status == 200:
            text = body.decode("utf-8", errors="replace").lower()
            for marker in spec.not_found_markers:
                if marker in text:
                    return UsernameHit(spec.name, url, "not_found", f"HTTP 200 with not-found marker '{marker}'")
            return UsernameHit(spec.name, url, "found", "HTTP 200, profile page served")
        return UsernameHit(spec.name, url, "unknown", f"HTTP {status} (platform may block automated reads)")

    return list(await asyncio.gather(*(check_one(spec) for spec in platforms)))


__all__ = ["PLATFORMS", "PlatformSpec", "UsernameHit", "check_username"]
