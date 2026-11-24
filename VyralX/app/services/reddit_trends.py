"""VyralX Reddit story sourcing (TASK-IG3-VYR-03).

Wave-2 cluster 113 (IG source Dd4D7qrgb9V) is the
Reddit-story-to-Short lane: find a story post on Reddit, turn it
into a narrated cartoon/story Short. The script-to-video half of
that lane shipped in wave 2 (``shorts_factory``,
``short_video_assembly``), but the lane's defining input — a
Reddit sourcing step — existed nowhere in the IG modules
(supervisor AUDIT-2 re-confirmed: ``reddit`` in VyralX/app hit
only a pre-IG ad-platform taxonomy). This module is that
sourcing step:

* :func:`parse_listing` normalises a Reddit listing payload
  (the public ``/r/<sub>/<listing>.json`` shape) into plain post
  records — pure, no network;
* :func:`fetch_listing` retrieves a listing through an
  *injectable* fetcher, so tests and operators can supply any
  transport; the default fetcher is a stdlib urllib GET against
  the public JSON endpoint and fails loudly on HTTP errors;
* :func:`select_stories` deterministically picks story posts
  (self-posts with real body text; stickied and, by default,
  NSFW posts excluded), ranked by score, then comments;
* :func:`story_brief` turns a post into a production brief that
  carries its provenance (subreddit, author, permalink) and is
  marked ``rewrite_required`` — a brief is a sourcing record,
  never a script: the post's text is excerpted for identification
  only and must be rewritten before any production use;
* :func:`enqueue_briefs` appends briefs to the VYR-004 review
  queue via ``remix_flow.enqueue_review`` (lazy import, the
  established pattern).

The module carries its own FastAPI router, mounted by
``app.main`` at ``/api/v1`` (``POST /api/v1/reddit-trends/briefs``,
``GET /api/v1/reddit-trends/policy``) — the AUDIT-2
production-caller standard: a library no production code calls
is not delivered. Everything the lane emits is
``pending_review``; nothing here publishes, posts, or votes.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.request
from typing import Any, Callable

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

TRENDS_VERSION = "ig3-vyr03-1"
IG_SOURCE = "Dd4D7qrgb9V"

_SUBREDDIT_RE = re.compile(r"^[A-Za-z0-9_]{2,21}$")
_LISTINGS = ("top", "hot", "new", "rising")
_EXCERPT_CHARS = 300

#: The rewrite policy every brief carries. A sourced story is
#: raw material for an original script, never copy to read aloud
#: verbatim — the brief exists so a human/agent rewrites it.
REWRITE_NOTE = (
    "rewrite_required: this brief excerpts the source post for "
    "identification only. Any production script must be an "
    "original rewrite; the source text is never a shooting script."
)


# --------------------------------------------------------------------------- #
# Listing parsing (pure)
# --------------------------------------------------------------------------- #
def _normalise_post(raw: dict[str, Any]) -> dict[str, Any]:
    permalink = str(raw.get("permalink") or "")
    return {
        "post_id": str(raw.get("id") or ""),
        "subreddit": str(raw.get("subreddit") or ""),
        "author": str(raw.get("author") or ""),
        "title": str(raw.get("title") or ""),
        "selftext": str(raw.get("selftext") or ""),
        # TASK-VYR-058: the post's external link (a link post's target;
        # empty for self posts). The discovery adapter reads this to
        # find YouTube videos sourced from a subreddit.
        "link_url": str(raw.get("url") or ""),
        "score": int(raw.get("score") or 0),
        "num_comments": int(raw.get("num_comments") or 0),
        "permalink": permalink,
        "url": ("https://www.reddit.com" + permalink) if permalink else "",
        "created_utc": float(raw.get("created_utc") or 0.0),
        "stickied": bool(raw.get("stickied")),
        "over_18": bool(raw.get("over_18")),
        "is_self": bool(raw.get("is_self")),
    }


def parse_listing(payload: Any) -> list[dict[str, Any]]:
    """Normalise a Reddit listing payload into post records.

    Accepts the public listing shape
    ``{"data": {"children": [{"data": {...}}, ...]}}`` or a bare
    list of post dicts. Anything else raises ``ValueError`` —
    an unrecognised payload is reported, never guessed at.
    """
    if isinstance(payload, list):
        children = payload
    elif isinstance(payload, dict):
        data = payload.get("data")
        if not isinstance(data, dict) or not isinstance(
                data.get("children"), list):
            raise ValueError(
                "unrecognised listing payload: expected "
                "{'data': {'children': [...]}} or a list of posts")
        children = data["children"]
    else:
        raise ValueError(
            f"unrecognised listing payload type: {type(payload).__name__}")
    posts = []
    for child in children:
        raw = child.get("data") if isinstance(child, dict) else None
        if not isinstance(raw, dict):
            raw = child if isinstance(child, dict) else None
        if raw is None:
            continue
        posts.append(_normalise_post(raw))
    return posts


# --------------------------------------------------------------------------- #
# Fetching (injectable transport)
# --------------------------------------------------------------------------- #
def _urllib_fetcher(url: str) -> Any:
    """Default fetcher: stdlib GET of the public JSON endpoint.

    Fails loudly — an HTTP error or a non-JSON body raises, so a
    blocked/changed endpoint can never masquerade as an empty
    listing.
    """
    req = urllib.request.Request(
        url, headers={"User-Agent": "vyralx-ig3-vyr03/1.0 "
                                   "(friday-universe story sourcing)"})
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise RuntimeError(
            f"reddit listing fetch failed: HTTP {exc.code} for {url}"
        ) from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(
            f"reddit listing fetch failed: {exc.reason} for {url}"
        ) from exc


def listing_url(subreddit: str, *, listing: str = "top",
                time_filter: str = "week", limit: int = 25) -> str:
    """The public JSON URL for a subreddit listing."""
    if not _SUBREDDIT_RE.match(subreddit or ""):
        raise ValueError(f"invalid subreddit name: {subreddit!r}")
    if listing not in _LISTINGS:
        raise ValueError(
            f"unknown listing {listing!r}; expected one of {_LISTINGS}")
    return (f"https://www.reddit.com/r/{subreddit}/{listing}.json"
            f"?t={time_filter}&limit={int(limit)}&raw_json=1")


def fetch_listing(subreddit: str, *,
                  fetcher: Callable[[str], Any] | None = None,
                  listing: str = "top", time_filter: str = "week",
                  limit: int = 25) -> list[dict[str, Any]]:
    """Fetch + parse a subreddit listing via ``fetcher``.

    ``fetcher`` maps a URL to a parsed JSON payload; tests and
    operators inject their own transport. The default is the
    stdlib public-JSON fetcher above.
    """
    url = listing_url(subreddit, listing=listing,
                      time_filter=time_filter, limit=limit)
    payload = (fetcher or _urllib_fetcher)(url)
    return parse_listing(payload)


# --------------------------------------------------------------------------- #
# Story selection + briefs
# --------------------------------------------------------------------------- #
def select_stories(posts: list[dict[str, Any]], *,
                   min_score: int = 0,
                   min_selftext_chars: int = 280,
                   include_nsfw: bool = False,
                   limit: int = 10) -> list[dict[str, Any]]:
    """Pick story posts from parsed records, deterministically.

    A story post is a self-post with real body text. Stickied
    posts are never stories; NSFW posts are excluded unless
    ``include_nsfw``. Ranking: score, then comment count, then
    newest, then post id — the same input always selects the
    same stories in the same order.
    """
    eligible = [
        p for p in posts
        if p["is_self"] and not p["stickied"]
        and len(p["selftext"]) >= min_selftext_chars
        and p["score"] >= min_score
        and (include_nsfw or not p["over_18"])
    ]
    eligible.sort(key=lambda p: (-p["score"], -p["num_comments"],
                                 -p["created_utc"], p["post_id"]))
    return eligible[:limit]


def story_brief(post: dict[str, Any]) -> dict[str, Any]:
    """A provenance-carrying, rewrite-required production brief."""
    text = " ".join(post["selftext"].split())
    excerpt = text[:_EXCERPT_CHARS]
    return {
        "kind": "reddit_story_brief",
        "version": TRENDS_VERSION,
        "ig_source": IG_SOURCE,
        "title": post["title"],
        "excerpt": excerpt,
        "excerpt_truncated": len(text) > _EXCERPT_CHARS,
        "word_count": len(text.split()),
        "rewrite_required": True,
        "rewrite_note": REWRITE_NOTE,
        "source": {
            "platform": "reddit",
            "subreddit": post["subreddit"],
            "post_id": post["post_id"],
            "author": post["author"],
            "permalink": post["permalink"],
            "url": post["url"],
            "score": post["score"],
            "num_comments": post["num_comments"],
            "created_utc": post["created_utc"],
        },
        "status": "pending_review",
        "publish": False,
    }


def build_briefs(payload: Any, **select_kwargs: Any) -> dict[str, Any]:
    """Parse a listing payload and brief its selected stories."""
    posts = parse_listing(payload)
    selected = select_stories(posts, **select_kwargs)
    return {
        "kind": "reddit_story_selection",
        "version": TRENDS_VERSION,
        "ig_source": IG_SOURCE,
        "received": len(posts),
        "eligible": len(selected),
        "briefs": [story_brief(p) for p in selected],
        "status": "pending_review",
        "publish": False,
    }


def enqueue_briefs(briefs: list[dict[str, Any]],
                   queue_path: Any = None) -> int:
    """Append briefs to the VYR-004 review queue. Returns count.

    The remix_flow import is lazy: the sourcing builder stays
    importable (and testable) without the queue's dependency
    chain.
    """
    from app.services import remix_flow

    for brief in briefs:
        remix_flow.enqueue_review(brief, queue_path)
    return len(briefs)


# --------------------------------------------------------------------------- #
# Router (mounted by app.main — the production path)
# --------------------------------------------------------------------------- #
router = APIRouter()


class BriefsRequest(BaseModel):
    listing: Any
    min_score: int = 0
    min_selftext_chars: int = 280
    include_nsfw: bool = False
    limit: int = 10
    enqueue: bool = False


@router.get("/reddit-trends/policy")
def reddit_trends_policy() -> dict[str, Any]:
    return {
        "version": TRENDS_VERSION,
        "ig_source": IG_SOURCE,
        "lane": "Reddit-story-to-Short sourcing (cluster 113)",
        "rewrite_required": True,
        "rewrite_note": REWRITE_NOTE,
        "status": "pending_review",
        "publish": False,
        "note": "Sourcing only: briefs carry provenance and an "
                "excerpt for identification. Nothing here posts, "
                "votes, publishes, or copies a story verbatim "
                "into production.",
    }


@router.post("/reddit-trends/briefs")
def reddit_trends_briefs(req: BriefsRequest) -> dict[str, Any]:
    try:
        result = build_briefs(
            req.listing, min_score=req.min_score,
            min_selftext_chars=req.min_selftext_chars,
            include_nsfw=req.include_nsfw, limit=req.limit)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    if req.enqueue:
        result["enqueued"] = enqueue_briefs(result["briefs"])
    return result
