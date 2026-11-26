"""VyralX Reddit sourcing adapter for the discovery pipeline (TASK-VYR-058).

A subreddit is a new source pool for the same discovery pipeline that
serves YouTube candidates. The adapter reads a subreddit listing, picks
the link posts that point at YouTube videos, resolves each video's
metadata, and runs every video through the SAME machine-QA gates the
YouTube paths use — :func:`app.services.viral_discovery._accept`
(duration window, minimum views, comedy lane, licence policy,
deduplication) and :func:`app.services.viral_discovery.score_candidate`
— following the :func:`app.services.youtube_api_discovery.discover_via_api`
precedent exactly (same ``_lane_for`` with a COMEDY fallback, same
``reuse_licensed`` refusal: the listing carries no licence proof, so
that policy yields no candidates instead of guessed ones).

What a Reddit post can and cannot become:

* A link post to a YouTube video becomes a
  :class:`app.services.viral_discovery.Candidate` with its Reddit
  provenance attached (``source_platform="reddit"``, subreddit, post
  id, permalink, Reddit score/comments). It then flows through the
  loop, the audition, and the five TASK-VYR-014 quality gates exactly
  like a YouTube-sourced candidate.
* A self post, a stickied post, an NSFW post (unless explicitly
  allowed), or a link to anywhere but YouTube is NOT a video
  candidate: it is counted in the report with its reason and never
  fabricated into one. The story-post lane already exists separately
  (:mod:`app.services.reddit_trends`, TASK-IG3-VYR-03).

Honesty contract:

* The listing fetch fails loudly — :func:`app.services.reddit_trends.fetch_listing`
  raises ``RuntimeError`` on an HTTP/transport failure, and that
  propagates out of here unchanged. A dead subreddit never
  masquerades as an empty one.
* Video metadata is resolved per video (YouTube Data API first, then
  yt-dlp metadata). A video whose metadata cannot be resolved is
  skipped with reason ``metadata_unavailable`` — views, duration and
  score are never invented, so a candidate that cannot prove it
  passes the views/duration gates never enters the pool.
* No live call is made when the pool is off (no subreddits
  configured) or when the policy refuses (``reuse_licensed``).

Transport and metadata resolution are injectable (``fetcher``,
``metadata_resolver``) so the whole adapter is testable offline.
Pure stdlib + the existing discovery modules; Python 3.10.
"""
from __future__ import annotations

import logging
import re
from typing import Any, Callable, Iterable
from urllib.parse import parse_qs, urlsplit

from app.config import get_settings
from app.services import reddit_trends
from app.services.viral_discovery import (
    Candidate,
    _accept,
    _is_comedy,
    _lane_by_category,
    _lane_for,
)

log = logging.getLogger("vyralx.reddit_discovery")

ADAPTER_VERSION = "vyr058-1"

_YOUTUBE_HOSTS = ("youtube.com", "www.youtube.com", "m.youtube.com", "youtu.be")
_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_MAX_SKIPPED_SAMPLE = 25


# --------------------------------------------------------------------------- #
# YouTube video-id extraction from a post's link URL (pure)
# --------------------------------------------------------------------------- #
def youtube_video_id_from_url(url: str) -> str:
    """Extract a YouTube video id from a link URL, or ``""``.

    Accepts the three shapes Reddit link posts use: ``watch?v=``,
    ``youtu.be/`` and ``/shorts/`` (plus ``/embed/``). Anything else
    — another host, a malformed id, an empty value — returns ``""``;
    the caller treats that as "not a YouTube video link".
    """
    try:
        parts = urlsplit(str(url or "").strip())
    except ValueError:
        return ""
    host = (parts.netloc or "").lower().split(":")[0]
    if host.endswith("youtu.be"):
        candidate = parts.path.strip("/").split("/")[0]
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    if host not in _YOUTUBE_HOSTS:
        return ""
    path = parts.path or ""
    if path.startswith("/shorts/") or path.startswith("/embed/"):
        candidate = path.split("/")[2] if len(path.split("/")) > 2 else ""
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    if path == "/watch":
        values = parse_qs(parts.query or {}).get("v") or []
        candidate = values[0] if values else ""
        return candidate if _VIDEO_ID_RE.match(candidate) else ""
    return ""


# --------------------------------------------------------------------------- #
# Video-post selection (pure)
# --------------------------------------------------------------------------- #
def select_video_posts(
    posts: list[dict[str, Any]],
    *,
    min_score: int = 0,
    include_nsfw: bool = False,
    limit: int = 25,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Pick the link posts that can become video candidates.

    Returns ``(selected, skipped)``. A post is selected only when it
    is a non-stickied link post to a YouTube video, is not NSFW (unless
    ``include_nsfw``), and meets ``min_score``. Selected posts carry a
    ``video_id`` key. Duplicates (same video linked twice) keep the
    higher-scored post. Selection is deterministic: score, then
    comments, then newest, then post id. Every rejected post appears
    in ``skipped`` as ``{"post_id", "subreddit", "reason"}`` so the
    caller can report exactly why the pool is thin.
    """
    selected: dict[str, dict[str, Any]] = {}
    skipped: list[dict[str, Any]] = []
    for post in posts or []:
        post_id = str(post.get("post_id") or "")
        subreddit = str(post.get("subreddit") or "")
        entry = {"post_id": post_id, "subreddit": subreddit, "reason": ""}
        if post.get("stickied"):
            skipped.append({**entry, "reason": "stickied"})
            continue
        if post.get("over_18") and not include_nsfw:
            skipped.append({**entry, "reason": "nsfw"})
            continue
        if int(post.get("score") or 0) < min_score:
            skipped.append({**entry, "reason": "below_min_score"})
            continue
        if post.get("is_self"):
            skipped.append({**entry, "reason": "self_post_no_video"})
            continue
        link = str(post.get("link_url") or post.get("url") or "")
        video_id = youtube_video_id_from_url(link)
        if not video_id:
            skipped.append({**entry, "reason": "non_youtube_link"})
            continue
        record = dict(post)
        record["video_id"] = video_id
        existing = selected.get(video_id)
        if existing is None:
            selected[video_id] = record
            continue
        if (int(record.get("score") or 0), int(record.get("num_comments") or 0),
                float(record.get("created_utc") or 0.0)) > (
                int(existing.get("score") or 0),
                int(existing.get("num_comments") or 0),
                float(existing.get("created_utc") or 0.0)):
            selected[video_id] = record
            skipped.append({**entry, "reason": "duplicate_video"})
        else:
            skipped.append({**entry, "reason": "duplicate_video"})
    ranked = sorted(
        selected.values(),
        key=lambda p: (-int(p.get("score") or 0), -int(p.get("num_comments") or 0),
                       -float(p.get("created_utc") or 0.0), str(p.get("post_id") or "")),
    )
    return ranked[: max(1, int(limit))], skipped


# --------------------------------------------------------------------------- #
# Video metadata resolution (injectable; default is best-effort, honest)
# --------------------------------------------------------------------------- #
def _api_metadata(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """YouTube Data API metadata for ids; ``{}`` when unavailable.

    Uses the same ``video_details`` helper as the API discovery path,
    so the ``info`` shape matches what the gates expect. A failed
    batch is skipped, never guessed at.
    """
    try:
        from app.services.youtube import youtube_service
        from app.services.youtube_api_discovery import (
            _compact_upload_date,
            video_details,
        )

        service = youtube_service()
    except Exception as exc:
        log.info("YouTube API service unavailable (%s)", type(exc).__name__)
        return {}
    try:
        details = video_details(service, video_ids)
    except Exception as exc:
        log.info("YouTube video_details failed (%s)", type(exc).__name__)
        return {}
    infos: dict[str, dict[str, Any]] = {}
    for video_id, detail in (details or {}).items():
        infos[video_id] = {
            "id": video_id,
            "title": str(detail.get("title") or ""),
            "channel": str(detail.get("channel") or ""),
            "view_count": int(detail.get("view_count") or 0),
            "like_count": 0,
            "comment_count": 0,
            "duration": float(detail.get("duration_seconds") or 0),
            "upload_date": _compact_upload_date(detail.get("published_at")),
            "description": str(detail.get("description") or ""),
            "license": "",
            "tags": [],
            "webpage_url": f"https://www.youtube.com/watch?v={video_id}",
        }
    return infos


def _ytdlp_metadata(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """yt-dlp metadata per id; ids that fail extraction are absent.

    NOTE (TASK-VYR-056): yt-dlp extraction is currently broken on
    this host (deno/EJS solver crash), so this leg usually returns
    nothing — that surfaces as ``metadata_unavailable`` skips, never
    as fabricated candidates.
    """
    try:
        from app.services.viral_discovery import _video_metadata
    except Exception as exc:
        log.info("viral_discovery metadata helper unavailable (%s)", type(exc).__name__)
        return {}
    infos: dict[str, dict[str, Any]] = {}
    for video_id in video_ids:
        try:
            info = _video_metadata(video_id)
        except Exception:
            info = None
        if isinstance(info, dict) and info.get("id"):
            infos[video_id] = info
    return infos


def default_metadata_resolver(video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Data API first, yt-dlp metadata for whatever the API missed."""
    infos = _api_metadata(list(video_ids))
    missing = [video_id for video_id in video_ids if video_id not in infos]
    if missing:
        infos.update(_ytdlp_metadata(missing))
    return infos


# --------------------------------------------------------------------------- #
# The adapter
# --------------------------------------------------------------------------- #
def _parse_subreddits(subreddits: str | Iterable[str] | None) -> list[str]:
    if subreddits is None:
        return []
    if isinstance(subreddits, str):
        values = [item.strip() for item in subreddits.split(",")]
    else:
        values = [str(item).strip() for item in subreddits]
    seen: set[str] = set()
    parsed: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.add(value)
            parsed.append(value)
    return parsed


def discover_reddit_candidates_detailed(
    subreddits: str | Iterable[str] | None,
    *,
    limit: int = 12,
    exclude_ids: set[str] | None = None,
    min_views: int | None = None,
    min_seconds: float | None = None,
    max_seconds: float = 58.0,
    min_score: int = 0,
    include_nsfw: bool = False,
    listing: str = "top",
    time_filter: str = "week",
    fetcher: Callable[[str], Any] | None = None,
    metadata_resolver: Callable[[list[str]], dict[str, dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """Discover Reddit-sourced candidates through the discovery gates.

    Args:
        subreddits: One subreddit, a comma-separated string, or an
            iterable of names. Empty = the pool is off: returns no
            candidates and makes no network call.
        limit: Maximum candidates returned.
        exclude_ids: Video ids already used/rejected (deduplication
            gate, same as the YouTube paths).
        min_views/min_seconds/max_seconds: The discovery gates; when
            ``None`` they come from settings (``viral_min_source_views``,
            ``viral_min_source_seconds``) with the discovery defaults.
        min_score: Minimum Reddit score for a linked post to enter.
        include_nsfw: Include NSFW posts (default: excluded).
        listing/time_filter: The subreddit listing to read (as in
            :mod:`app.services.reddit_trends`).
        fetcher/metadata_resolver: Injectable transports for offline
            tests and operator overrides. The default metadata
            resolver is :func:`default_metadata_resolver`.

    Returns:
        ``{"candidates": [Candidate, ...], "report": {...}}``. The
        report counts every post received, selected, accepted and
        skipped by reason, so a thin or empty pool is always
        explainable. A listing fetch failure raises ``RuntimeError``
        (loud) instead of returning an empty pool.

    The candidates are :class:`app.services.viral_discovery.Candidate`
    objects with Reddit provenance attached, ranked by score.
    """
    names = _parse_subreddits(subreddits)
    report: dict[str, Any] = {
        "version": ADAPTER_VERSION,
        "subreddits": names,
        "received": 0,
        "video_posts": 0,
        "accepted": 0,
        "skipped": {},
        "skipped_sample": [],
        "reason": "",
    }
    if not names:
        report["reason"] = "no_subreddits_configured"
        return {"candidates": [], "report": report}

    try:
        settings = get_settings()
    except Exception:
        settings = None
    if min_views is None:
        try:
            min_views = max(0, int(getattr(settings, "viral_min_source_views", 250_000)))
        except (TypeError, ValueError):
            min_views = 250_000
    if min_seconds is None:
        try:
            min_seconds = float(getattr(settings, "viral_min_source_seconds", 8.0))
        except (TypeError, ValueError):
            min_seconds = 8.0
    reuse_only = str(getattr(settings, "viral_source_policy", "transformative")) == "reuse_licensed"
    if reuse_only:
        # The public Data API / listing carries no reusable-licence
        # field, so this source cannot prove Creative Commons reuse.
        # Refuse instead of guessing — same as discover_via_api.
        log.warning(
            "viral_source_policy=reuse_licensed: Reddit discovery cannot "
            "verify a source licence, so it returns no candidates"
        )
        report["reason"] = "reuse_licensed_unverifiable"
        return {"candidates": [], "report": report}

    exclude = {str(value) for value in (exclude_ids or set()) if value}
    skipped: list[dict[str, Any]] = []

    all_posts: list[dict[str, Any]] = []
    for name in names:
        # Raises RuntimeError on HTTP/transport failure — loud, by design.
        posts = reddit_trends.fetch_listing(
            name, fetcher=fetcher, listing=listing,
            time_filter=time_filter, limit=25,
        )
        report["received"] += len(posts)
        all_posts.extend(posts)

    inspect_cap = max(int(limit) * 3, 24)
    selected, select_skipped = select_video_posts(
        all_posts, min_score=min_score, include_nsfw=include_nsfw,
        limit=inspect_cap,
    )
    report["video_posts"] = len(selected)
    skipped.extend(select_skipped)

    resolver = metadata_resolver or default_metadata_resolver
    video_ids = [str(post["video_id"]) for post in selected]
    infos = resolver(video_ids) or {}

    found: dict[str, Candidate] = {}
    for post in selected:
        video_id = str(post["video_id"])
        info = infos.get(video_id)
        if not isinstance(info, dict):
            skipped.append({
                "post_id": str(post.get("post_id") or ""),
                "subreddit": str(post.get("subreddit") or ""),
                "reason": "metadata_unavailable",
            })
            continue
        duration = float(info.get("duration") or 0.0)
        if video_id in exclude:
            skipped.append({
                "post_id": str(post.get("post_id") or ""),
                "subreddit": str(post.get("subreddit") or ""),
                "reason": "excluded",
            })
            continue
        if not (float(min_seconds) <= duration <= float(max_seconds)):
            skipped.append({
                "post_id": str(post.get("post_id") or ""),
                "subreddit": str(post.get("subreddit") or ""),
                "reason": "duration_gate",
            })
            continue
        if int(info.get("view_count") or 0) < int(min_views):
            skipped.append({
                "post_id": str(post.get("post_id") or ""),
                "subreddit": str(post.get("subreddit") or ""),
                "reason": "views_gate",
            })
            continue
        lane = _lane_for(info)
        if not _is_comedy(lane):
            # Same fallback as the API discovery path: this pool is
            # intentionally comedy, and _accept enforces the lane.
            lane = _lane_by_category("COMEDY")
        accepted = _accept(
            info, lane, reuse_only, found, exclude,
            float(min_seconds), float(max_seconds), int(min_views),
        )
        if not accepted:
            skipped.append({
                "post_id": str(post.get("post_id") or ""),
                "subreddit": str(post.get("subreddit") or ""),
                "reason": "gate_rejected",
            })
            continue
        candidate = found[video_id]
        candidate.source_platform = "reddit"
        candidate.source_subreddit = str(post.get("subreddit") or "")
        candidate.source_post_id = str(post.get("post_id") or "")
        candidate.source_url = str(post.get("url") or "")
        candidate.reddit_score = int(post.get("score") or 0)
        candidate.reddit_comments = int(post.get("num_comments") or 0)

    ranked = sorted(found.values(), key=lambda item: item.score, reverse=True)
    candidates = ranked[: max(1, int(limit))]
    report["accepted"] = len(candidates)
    for entry in skipped:
        reason = str(entry.get("reason") or "unknown")
        report["skipped"][reason] = report["skipped"].get(reason, 0) + 1
    report["skipped_sample"] = skipped[:_MAX_SKIPPED_SAMPLE]
    log.info(
        "Reddit discovery: subreddits=%s received=%d video_posts=%d accepted=%d",
        ",".join(names), report["received"], report["video_posts"], len(candidates),
    )
    return {"candidates": candidates, "report": report}


def discover_reddit_candidates(
    subreddits: str | Iterable[str] | None,
    **kwargs: Any,
) -> list[Candidate]:
    """Discover Reddit-sourced candidates (the ``candidates`` half of
    :func:`discover_reddit_candidates_detailed`). See that function
    for the arguments and the honesty contract.
    """
    return discover_reddit_candidates_detailed(subreddits, **kwargs)["candidates"]
