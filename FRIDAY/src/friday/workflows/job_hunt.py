"""TASK-IG-FRD-003 — Job-hunt assistant workflow (IG corpus, 3 reels).

The pattern from the corpus (DeYL3wXs5gd / DehBdAERZWo / DfKvyiNSQXD):
scan company career pages directly, match every posting against the
owner's profile, keep only real fits, surface the overlooked ones, build
a prep plan for the best match, and draft the outreach — with a human
gate before anything is ever sent or submitted.

Hard rules of this module, by design:
- NOTHING is ever sent or submitted. There is no send/apply function
  here at all. Outreach is drafted to a local file for the owner to
  review and send himself; applications remain the owner's clicks.
- Listings come only from pages actually fetched, parsed for JSON-LD
  ``JobPosting`` blocks (the structured data career sites publish for
  Google for Jobs). A page that yields no postings produces an honest
  empty result with the reason recorded — never invented listings.
  Greenhouse job boards are the exception: their pages carry no
  JobPosting blocks, so for those URLs the official public Job Board API
  single-job endpoint is fetched instead (read-only, no auth).
- Fit scoring is a declared formula (see ``score_listing``): title,
  skills, location, recency, with hard exclusions. Every score ships
  with its matched/missing skills and reasons, so a rank is explainable.

State is file-backed under ``FRIDAY/.data/job_hunt/``: ``profile.json``
(the owner's CV profile — he owns and edits it), ``last_scan.json``
(scan results), ``drafts/`` (prep plans + outreach drafts).
"""

from __future__ import annotations

import html
import json
import logging
import os
import re
import time
import urllib.request
import uuid
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# Declared scoring weights (sum = 1.0). Changed only with a reason.
W_TITLE = 0.35
W_SKILLS = 0.40
W_LOCATION = 0.15
W_RECENCY = 0.10

#: A strong fit whose posting is at least this old is flagged
#: "overlooked" — the corpus pattern of surfacing the high-paying role
#: everyone else scrolled past. Heuristic, and labelled as one.
OVERLOOKED_MIN_DAYS = 3
OVERLOOKED_MIN_SCORE = 0.65

FetcherFn = Callable[[str], str]


def _data_dir() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        base = os.path.abspath(os.path.join(cwd, ".data", "job_hunt"))
    else:
        here = os.path.dirname(__file__)  # .../friday/workflows
        base = os.path.abspath(os.path.join(here, "..", "..", ".data", "job_hunt"))
    os.makedirs(base, exist_ok=True)
    return base


# ----------------------------------------------------------------------
# Profile
# ----------------------------------------------------------------------

def load_profile(path: Optional[str] = None) -> Optional[dict[str, Any]]:
    """The owner's job profile, or None (honestly) when not set up yet."""
    p = path or os.path.join(_data_dir(), "profile.json")
    try:
        with open(p, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except FileNotFoundError:
        return None
    except Exception as exc:
        logger.warning("[JOB-HUNT] profile unreadable (%s)", exc)
        return None
    profile.setdefault("skills", [])
    profile.setdefault("target_titles", [])
    profile.setdefault("locations", [])
    profile.setdefault("exclude_keywords", [])
    profile.setdefault("name", "the owner")
    return profile


PROFILE_TEMPLATE: dict[str, Any] = {
    "name": "",
    "skills": ["python", "fastapi"],
    "target_titles": ["software engineer"],
    "locations": ["remote", "hyderabad"],
    "remote_ok": True,
    "exclude_keywords": ["unpaid", "commission only"],
    "summary": "One-paragraph professional summary used in outreach drafts.",
}


# ----------------------------------------------------------------------
# Fetch + extract
# ----------------------------------------------------------------------

def default_fetcher(url: str) -> str:
    """Fetch a career page as text. Raises on failure — callers record it."""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "FRIDAY-JobHunt/1.0 (+personal assistant; owner-directed)",
            "Accept": "text/html,application/xhtml+xml",
        },
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        raw = resp.read(2_000_000)
    return raw.decode("utf-8", errors="replace")


_LD_JSON_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)


def _job_postings_from_ldjson(block: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(block, dict):
        if block.get("@type") == "JobPosting":
            found.append(block)
        for value in block.values():
            found.extend(_job_postings_from_ldjson(value))
    elif isinstance(block, list):
        for item in block:
            found.extend(_job_postings_from_ldjson(item))
    return found


def _days_ago(date_text: str, now_epoch: float) -> Optional[int]:
    try:
        from datetime import datetime, timezone

        dt = datetime.fromisoformat(date_text.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return max(0, int((now_epoch - dt.timestamp()) // 86400))
    except Exception:
        return None


def extract_listings(page_text: str, source_url: str, *, now_epoch: Optional[float] = None) -> list[dict[str, Any]]:
    """Extract JobPosting listings from a page's JSON-LD blocks.

    Returns [] when the page carries no JobPosting structured data —
    an honest empty, with the caller recording the source as unparsed.
    """
    now = now_epoch if now_epoch is not None else time.time()
    listings: list[dict[str, Any]] = []
    for match in _LD_JSON_RE.finditer(page_text or ""):
        try:
            data = json.loads(match.group(1).strip())
        except Exception:
            continue
        for posting in _job_postings_from_ldjson(data):
            org = posting.get("hiringOrganization") or {}
            loc = posting.get("jobLocation") or {}
            address = (loc.get("address") or {}) if isinstance(loc, dict) else {}
            location = ", ".join(
                str(x) for x in [address.get("addressLocality"), address.get("addressCountry")] if x
            )
            if posting.get("jobLocationType") == "TELECOMMUTE":
                location = (location + " remote").strip()
            listings.append(
                {
                    "id": f"job-{uuid.uuid4().hex[:10]}",
                    "title": str(posting.get("title") or "").strip(),
                    "company": str(org.get("name") or "").strip(),
                    "url": str(posting.get("url") or source_url),
                    "location": location,
                    "description": re.sub(r"<[^>]+>", " ", str(posting.get("description") or ""))[:6000],
                    "posted_days_ago": _days_ago(str(posting.get("datePosted") or ""), now),
                    "source_url": source_url,
                }
            )
    return [l for l in listings if l["title"]]


#: Greenhouse job-board hosts whose pages are JS-rendered shells with no
#: JobPosting structured data (IG-FRD-003 follow-up: live GitLab/Canonical
#: postings carry 0 LD-JSON blocks). For these URLs the official public
#: Job Board API single-job endpoint is the source instead.
_GREENHOUSE_RE = re.compile(
    r"https?://(?:job-boards|boards)\.greenhouse\.io/([^/?#]+)/jobs/(\d+)",
    re.IGNORECASE,
)


def greenhouse_api_url(board: str, job_id: str) -> str:
    """Public Job Board API single-job endpoint (no auth for reads)."""
    return f"https://boards-api.greenhouse.io/v1/boards/{board}/jobs/{job_id}"


def _strip_tags(text: str) -> str:
    return re.sub(r"<[^>]+>", " ", text or "")


def extract_listings_from_greenhouse_json(
    job: Any, source_url: str, *, now_epoch: Optional[float] = None
) -> list[dict[str, Any]]:
    """Map one Greenhouse Job Board API job object onto the listing schema.

    Returns [] when the payload is not a usable job object — an honest
    empty, same as a page with no JobPosting blocks. ``content`` arrives
    double-entity-encoded; unescape twice, then strip tags.
    """
    if not isinstance(job, dict) or not str(job.get("title") or "").strip():
        return []
    now = now_epoch if now_epoch is not None else time.time()
    location = job.get("location") or {}
    content = str(job.get("content") or "")
    description = _strip_tags(html.unescape(html.unescape(content))).strip()[:6000]
    job_id = job.get("id")
    return [
        {
            "id": f"gh-{job_id}" if job_id is not None else f"job-{uuid.uuid4().hex[:10]}",
            "title": str(job.get("title") or "").strip(),
            "company": str(job.get("company_name") or "").strip(),
            "url": str(job.get("absolute_url") or source_url),
            "location": str(location.get("name") or "").strip() if isinstance(location, dict) else "",
            "description": description,
            "posted_days_ago": _days_ago(str(job.get("first_published") or ""), now),
            "source_url": source_url,
        }
    ]


# ----------------------------------------------------------------------
# Scoring — declared formula, explainable output
# ----------------------------------------------------------------------

def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9+#.]+", (text or "").lower()))


def score_listing(profile: dict[str, Any], listing: dict[str, Any]) -> dict[str, Any]:
    """Score one listing against the profile. Returns the full audit
    trail: score, matched/missing skills, and every reason that moved it."""
    title = (listing.get("title") or "").lower()
    desc = (listing.get("description") or "").lower()
    loc = (listing.get("location") or "").lower()
    reasons: list[str] = []

    for bad in profile.get("exclude_keywords") or []:
        if bad.lower() in title or bad.lower() in desc:
            return {
                "score": 0.0,
                "rejected": True,
                "matched_skills": [],
                "missing_skills": list(profile.get("skills") or []),
                "reasons": [f"hard exclusion: {bad!r} appears in the posting"],
            }

    def _title_hit(target: str) -> bool:
        if target.lower() in title:
            return True
        want = _tokens(target)
        if not want:
            return False
        # Near-match: all but at most one of the target's tokens present.
        return len(want & _tokens(title)) >= max(1, len(want) - 1)

    title_hits = [t for t in profile.get("target_titles") or [] if _title_hit(t)]
    title_score = 1.0 if title_hits else 0.0
    if title_hits:
        reasons.append(f"title matches target: {title_hits[0]!r}")

    skills = [s.lower() for s in profile.get("skills") or []]
    haystack = f"{title} {desc}"
    matched = [s for s in skills if s in haystack]
    missing = [s for s in skills if s not in haystack]
    skills_score = (len(matched) / len(skills)) if skills else 0.0
    reasons.append(f"skills matched {len(matched)}/{len(skills)}")

    wanted = [l.lower() for l in profile.get("locations") or []]
    if not wanted:
        location_score = 0.5
    elif any(w in loc for w in wanted) or ("remote" in loc and profile.get("remote_ok")):
        location_score = 1.0
        reasons.append("location fits")
    else:
        location_score = 0.0
        reasons.append(f"location {listing.get('location')!r} not in profile locations")

    days = listing.get("posted_days_ago")
    if days is None:
        recency_score = 0.5
    else:
        recency_score = max(0.0, 1.0 - (float(days) / 30.0))
        reasons.append(f"posted {days}d ago")

    score = (
        W_TITLE * title_score
        + W_SKILLS * skills_score
        + W_LOCATION * location_score
        + W_RECENCY * recency_score
    )
    overlooked = bool(
        score >= OVERLOOKED_MIN_SCORE
        and days is not None
        and days >= OVERLOOKED_MIN_DAYS
    )
    if overlooked:
        reasons.append("flagged overlooked: strong fit, posting is not fresh (heuristic)")
    return {
        "score": round(score, 4),
        "rejected": False,
        "matched_skills": matched,
        "missing_skills": missing,
        "overlooked": overlooked,
        "reasons": reasons,
    }


def rank_listings(profile: dict[str, Any], listings: list[dict[str, Any]]) -> list[dict[str, Any]]:
    ranked = []
    for listing in listings:
        verdict = score_listing(profile, listing)
        if verdict["rejected"]:
            continue
        ranked.append({**listing, "match": verdict})
    ranked.sort(key=lambda l: l["match"]["score"], reverse=True)
    return ranked


# ----------------------------------------------------------------------
# Scan orchestration (file-backed state)
# ----------------------------------------------------------------------

def run_scan(
    profile: dict[str, Any],
    urls: list[str],
    *,
    fetcher: FetcherFn = default_fetcher,
    state_path: Optional[str] = None,
) -> dict[str, Any]:
    """Fetch each career page, extract, score, rank, persist the scan.

    Per-source failures are recorded with their error — a failed source
    is reported, never silently dropped or papered over with old data.
    Greenhouse job-board URLs are fetched from the Job Board API instead
    of the HTML page (see ``extract_listings_from_greenhouse_json``).
    """
    all_listings: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for url in urls:
        try:
            gh = _GREENHOUSE_RE.search(url)
            if gh:
                text = fetcher(greenhouse_api_url(gh.group(1), gh.group(2)))
                try:
                    payload = json.loads(text)
                except Exception as exc:
                    raise ValueError(f"Greenhouse API returned non-JSON: {exc}") from exc
                found = extract_listings_from_greenhouse_json(payload, url)
            else:
                text = fetcher(url)
                found = extract_listings(text, url)
            sources.append(
                {"url": url, "status": "ok" if found else "no_postings_found", "count": len(found)}
            )
            all_listings.extend(found)
        except Exception as exc:
            sources.append({"url": url, "status": "fetch_failed", "error": f"{type(exc).__name__}: {exc}"})
    shortlist = rank_listings(profile, all_listings)
    scan = {
        "scanned_at": time.time(),
        "sources": sources,
        "total_listings": len(all_listings),
        "shortlist": shortlist,
    }
    path = state_path or os.path.join(_data_dir(), "last_scan.json")
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(scan, f, indent=2)
    os.replace(tmp, path)
    return scan


def load_last_scan(state_path: Optional[str] = None) -> Optional[dict[str, Any]]:
    path = state_path or os.path.join(_data_dir(), "last_scan.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


# ----------------------------------------------------------------------
# Prep plan + outreach draft (files only — never sent)
# ----------------------------------------------------------------------

def build_prep_plan(profile: dict[str, Any], listing: dict[str, Any]) -> str:
    """A deterministic 30-day prep plan shaped by the match audit:
    missing skills get the study weeks, matched strengths get the
    portfolio/interview weeks."""
    match = listing.get("match") or score_listing(profile, listing)
    missing = match.get("missing_skills") or []
    matched = match.get("matched_skills") or []
    role = f"{listing.get('title')} at {listing.get('company')}"
    lines = [
        f"# 30-day prep plan — {role}",
        "",
        f"Fit score: {match.get('score')} · matched: {', '.join(matched) or '—'} · "
        f"gaps: {', '.join(missing) or 'none'}",
        "",
        "## Week 1 — Close the biggest gaps",
    ]
    if missing:
        for skill in missing[:4]:
            lines.append(f"- Study block: {skill} — fundamentals + one small build using it.")
    else:
        lines.append("- No profile-skill gaps: go straight to role-specific depth.")
    lines += [
        "",
        "## Week 2 — Build proof",
        f"- Ship one portfolio piece that demonstrates: {', '.join(matched[:3]) or 'your core stack'}.",
        f"- Rewrite your CV bullets against the {listing.get('company')} posting's own words.",
        "",
        "## Week 3 — Interview mechanics",
        "- Two mock interviews (one technical, one behavioural) using the posting's stack.",
        "- Prepare three stories: hardest bug, hardest deadline, a disagreement handled well.",
        "",
        "## Week 4 — Apply and rehearse",
        "- Final CV + outreach review (the draft beside this plan).",
        "- Apply through the company's own careers page — personally, after review.",
        "- Daily 30-minute revision of Week 1 gaps until the interview.",
        "",
        "_Generated by FRIDAY's job-hunt workflow (TASK-IG-FRD-003). A plan, not a promise._",
    ]
    return "\n".join(lines)


def draft_outreach(profile: dict[str, Any], listing: dict[str, Any]) -> str:
    """Draft (never send) a short outreach note for one listing."""
    match = listing.get("match") or score_listing(profile, listing)
    matched = match.get("matched_skills") or []
    return (
        f"Subject: Application interest — {listing.get('title')} ({listing.get('company')})\n\n"
        f"Hello {listing.get('company')} team,\n\n"
        f"I'm {profile.get('name') or 'a candidate'} and I found your "
        f"{listing.get('title')} opening on your careers page. "
        f"{profile.get('summary') or ''}\n\n"
        f"The parts of the role that line up with my background: "
        f"{', '.join(matched) if matched else 'my overall experience'}.\n\n"
        "I'd welcome a conversation about the role.\n\n"
        "— DRAFT prepared by FRIDAY (TASK-IG-FRD-003). Review, edit and send "
        "personally; FRIDAY does not send outreach.\n"
    )


def save_draft(kind: str, listing: dict[str, Any], text: str, *, drafts_dir: Optional[str] = None) -> str:
    """Persist a prep plan or outreach draft; returns the file path."""
    base = drafts_dir or os.path.join(_data_dir(), "drafts")
    os.makedirs(base, exist_ok=True)
    safe_company = re.sub(r"[^a-z0-9]+", "-", (listing.get("company") or "company").lower()).strip("-")
    path = os.path.join(base, f"{kind}-{safe_company}-{listing.get('id', 'x')}.md")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path
