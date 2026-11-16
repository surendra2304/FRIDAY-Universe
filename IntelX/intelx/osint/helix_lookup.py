"""On-demand Helix-style username lookup for IntelX (TASK-IG2-INT-03).

Source pattern: thalha-a9/helix (MIT) — a username OSINT checker that
checks one username across a very large site database, then *re-checks
every hit against made-up "control probe" usernames* before reporting it,
and scores identity confidence with the discipline that a username match
alone is never above LOW.

Fleet adaptation (binding constraints from the spec card):
  * **On-demand only** — a library call, never a resident service or a
    standing poller.
  * **Bounded scans** — Helix's ~12k-site database does not fit a ~180 MB
    service envelope on a 956 MB VM. A run checks at most ``max_sites``
    platforms (default 25, hard cap 50) from IntelX's curated platform
    list, with low concurrency (default 4, hard cap 8 — Helix's own README
    warns high concurrency makes healthy sites time out).
  * **Approved-subject gate** — lookups run only for subjects the owner
    has named: the caller must pass the subject in ``approved_subjects``
    or the call raises :class:`PermissionError`. No gate, no scan.
  * **Control-probe verification** — every ``found`` verdict is re-checked
    with a deterministic impossible control username on the same platform;
    if the control also reads ``found``, the hit is discarded as a
    false positive and reported in ``discarded`` — never silently, never
    counted.
  * **Confidence honesty** — existence alone caps at LOW. Cross-links
    declared on a found profile that point at another found profile raise
    that hit to MEDIUM; a mutual cross-link cluster raises to HIGH.
    Avatar perceptual hashing (Helix's other signal) is not implemented
    here and is never implied.

Fetching is injectable for hermetic tests, mirroring ``osint.username``.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Collection

from intelx.osint.username import PLATFORMS, PlatformSpec

logger = logging.getLogger("intelx.osint.helix_lookup")

FetchBytes = Callable[[str], Awaitable[tuple[int, str, bytes]]]

DEFAULT_MAX_SITES = 25
HARD_MAX_SITES = 50
DEFAULT_CONCURRENCY = 4
HARD_MAX_CONCURRENCY = 8

_USERNAME_RE = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")

CONFIDENCE_RANK = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}


@dataclass(frozen=True)
class HelixHit:
    platform: str
    profile_url: str
    confidence: str  # LOW | MEDIUM | HIGH
    signals: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "profile_url": self.profile_url,
            "confidence": self.confidence,
            "signals": list(self.signals),
        }


@dataclass
class HelixReport:
    username: str
    control_username: str
    sites_checked: int
    hits: list[HelixHit] = field(default_factory=list)
    discarded: list[dict] = field(default_factory=list)  # control-probe false positives
    unknown: list[dict] = field(default_factory=list)  # blocked / inconclusive platforms

    @property
    def overall_confidence(self) -> str:
        if not self.hits:
            return "NONE"
        return max((h.confidence for h in self.hits), key=lambda c: CONFIDENCE_RANK[c])

    def to_dict(self) -> dict:
        return {
            "username": self.username,
            "control_username": self.control_username,
            "sites_checked": self.sites_checked,
            "overall_confidence": self.overall_confidence,
            "hits": [h.to_dict() for h in self.hits],
            "discarded_false_positives": self.discarded,
            "unknown": self.unknown,
        }


def control_username_for(username: str) -> str:
    """Deterministic impossible control name for a subject (Helix pattern)."""
    digest = hashlib.sha256(f"helix-control:{username}".encode()).hexdigest()[:12]
    return f"hxctl{digest}zz"


async def _default_fetch(url: str) -> tuple[int, str, bytes]:
    from intelx.connectors.web import HttpFetchConnector

    result = await HttpFetchConnector().fetch(url)
    return result.status_code, result.final_url, result.content


def _verdict(spec: PlatformSpec, status: int, body: bytes) -> str:
    if status == 404:
        return "not_found"
    if status == 200:
        text = body.decode("utf-8", errors="ignore").lower()
        if any(marker in text for marker in spec.not_found_markers):
            return "not_found"
        return "found"
    return "unknown"


async def helix_lookup(
    username: str,
    *,
    approved_subjects: Collection[str],
    fetch: FetchBytes | None = None,
    platforms: tuple[PlatformSpec, ...] = PLATFORMS,
    max_sites: int = DEFAULT_MAX_SITES,
    concurrency: int = DEFAULT_CONCURRENCY,
) -> HelixReport:
    """Run one bounded, control-probe-verified username lookup.

    Raises :class:`PermissionError` if ``username`` is not an approved
    subject, :class:`ValueError` for a malformed username.
    """
    if username not in approved_subjects:
        raise PermissionError(
            f"subject {username!r} is not owner-approved for OSINT lookup; "
            "pass it in approved_subjects only when the owner has named it"
        )
    if not _USERNAME_RE.match(username or ""):
        raise ValueError(f"invalid username {username!r}")
    max_sites = max(1, min(int(max_sites), HARD_MAX_SITES))
    concurrency = max(1, min(int(concurrency), HARD_MAX_CONCURRENCY))
    specs = tuple(platforms[:max_sites])
    fetch = fetch or _default_fetch
    control = control_username_for(username)
    semaphore = asyncio.Semaphore(concurrency)

    async def probe(spec: PlatformSpec, name: str) -> tuple[str, bytes]:
        url = spec.url_template.format(u=name)
        async with semaphore:
            try:
                status, _final, body = await fetch(url)
            except Exception as exc:  # network failure is unknown, never absence
                logger.debug("helix probe failed %s: %s", url, exc)
                return "unknown", b""
        return _verdict(spec, status, body), body if status == 200 else b""

    subject_results = await asyncio.gather(*(probe(spec, username) for spec in specs))
    found: dict[str, tuple[PlatformSpec, bytes]] = {}
    unknown: list[dict] = []
    for spec, (verdict, body) in zip(specs, subject_results):
        if verdict == "found":
            found[spec.name] = (spec, body)
        elif verdict == "unknown":
            unknown.append({"platform": spec.name, "profile_url": spec.url_template.format(u=username),
                            "detail": "platform blocked or inconclusive; not reported as absence"})

    # Control-probe verification: re-check every found platform with the
    # impossible control name. A platform that "finds" the control too is
    # reporting existence unreliably — discard the hit, on the record.
    discarded: list[dict] = []
    if found:
        control_results = await asyncio.gather(
            *(probe(spec, control) for spec, _ in found.values())
        )
        for (name, (spec, _body)), (cverdict, _cbody) in zip(found.items(), control_results):
            if cverdict == "found":
                discarded.append({
                    "platform": name,
                    "profile_url": spec.url_template.format(u=username),
                    "reason": "control probe also reported found — platform verdict unreliable, hit discarded",
                })
        for entry in discarded:
            found.pop(entry["platform"], None)

    # Cross-link signals: a found profile whose page links to another found
    # profile is identity evidence beyond a bare name match.
    found_urls = {name: spec.url_template.format(u=username) for name, (spec, _b) in found.items()}
    hits: list[HelixHit] = []
    linked_from: dict[str, set[str]] = {name: set() for name in found}
    for name, (spec, body) in found.items():
        page_urls = set(_URL_RE.findall(body.decode("utf-8", errors="ignore")))
        signals: list[str] = []
        for other_name, other_url in found_urls.items():
            if other_name != name and other_url in page_urls:
                signals.append(f"declares cross-link to {other_name}")
                linked_from[other_name].add(name)
        confidence = "MEDIUM" if signals else "LOW"
        hits.append(HelixHit(platform=name, profile_url=found_urls[name], confidence=confidence,
                             signals=tuple(signals)))
    # Mutual cross-links (A links B and B links A) are the strongest
    # existence-level signal Helix's model admits -> HIGH.
    promoted: list[HelixHit] = []
    by_name = {h.platform: h for h in hits}
    for hit in hits:
        mutual = any(
            hit.platform in linked_from.get(other, set()) and other in linked_from.get(hit.platform, set())
            for other in by_name
            if other != hit.platform
        )
        if mutual and hit.confidence != "HIGH":
            hit = HelixHit(platform=hit.platform, profile_url=hit.profile_url, confidence="HIGH",
                           signals=hit.signals + ("mutual cross-link cluster",))
        promoted.append(hit)

    return HelixReport(
        username=username,
        control_username=control,
        sites_checked=len(specs),
        hits=promoted,
        discarded=discarded,
        unknown=unknown,
    )
