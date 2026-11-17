#!/usr/bin/env python3
"""Metadata backfill for VyralX videos uploaded outside the autopilot lane.

The viral autopilot (PR #882) stamps per-clip tags, the correct YouTube
category for the clip's editorial lane, an explicit language and the
generated custom thumbnail at upload time. Videos uploaded before that
wiring existed — the manual-era uploads — never received any of it: they
carry whatever category/tags the one-off upload scripts of the day used,
no explicit language fields, and no custom thumbnail even where a
generated thumbnail file still exists on the server.

This tool backfills exactly those fields for an explicit list of video
ids, reusing the autopilot's own derivation logic so old and new videos
follow one rule:

* category  <- ``viral_remix.YOUTUBE_CATEGORY_BY_EDITORIAL`` for the
  video's lane (COMEDY 23 / SPORTS 17 / VIRAL 24),
* tags      <- ``viral_remix._derive_tags`` with the video's OWN current
  tags as the proven tag set (the manual-era analogue of the source
  video's harvested tags), capped at 15 tags / 450 chars,
* language  <- ``settings.youtube_default_language`` for both
  defaultLanguage and defaultAudioLanguage, exactly as the #882 upload
  body sends them,
* thumbnail <- ``youtube.set_thumbnail`` when a generated thumbnail file
  for the video is supplied AND still exists on disk. The tool never
  fabricates a thumbnail: a missing file is reported, not replaced.

Title and description are NEVER rewritten — they are read live and
round-tripped verbatim into the videos.update body (YouTube replaces
the whole snippet, so omitting them would erase them).

The lane is inferred from the video's own title/tags/description
(``infer_lane``) and can be pinned per video with ``--lane VIDEO=LANE``.

    # dry-run (default; performs ZERO writes, prints the plan as JSON)
    python scripts/backfill_public_metadata.py --video-id VIDEO_ID
    python scripts/backfill_public_metadata.py \
        --video-id A --video-id B --lane B=SPORTS \
        --thumbnail A=/path/to/thumb.jpg

    # live apply (only on an explicit operator order)
    python scripts/backfill_public_metadata.py --video-id VIDEO_ID --apply
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.config import get_settings  # noqa: E402
from app.services.viral_remix import (  # noqa: E402
    YOUTUBE_CATEGORY_BY_EDITORIAL,
    _derive_tags,
)
from app.services.youtube import set_thumbnail, youtube_service  # noqa: E402

# Strong per-lane signals for videos that carry no stored lane (the
# manual-era uploads). Weak/generic words ("relatable", "viral",
# "trending") are deliberately absent: they appear on everything and
# would force a lane the content may not have.
_LANE_SIGNALS: dict[str, tuple[str, ...]] = {
    "SPORTS": (
        "sport", "soccer", "football", "basketball", "tennis", "cricket",
        "boxing", "mma", "ufc", "workout", "fitness", "athlete",
        "goalkeeper", "stunt", "skateboard", "surfing", "marathon",
    ),
    "COMEDY": (
        "comedy", "funny", "humor", "humour", "parody", "meme", "prank",
        "hilarious", "joke", "laugh",
    ),
}
# Tie-break order when two lanes score equally: the more specific
# physical-feat lane wins over comedy; VIRAL is the fallback lane.
_LANE_PRIORITY = ("SPORTS", "COMEDY")


def infer_lane(title: str, tags: list[str], description: str = "") -> tuple[str, list[str]]:
    """Infer the editorial lane from the video's own text.

    Returns (lane, signals) where signals lists the matched keywords, so
    a human reviewing a dry-run can see — and override — the reasoning.
    """
    haystack = " ".join([title or "", " ".join(tags or []), description or ""]).casefold()
    matched: dict[str, list[str]] = {}
    for lane, words in _LANE_SIGNALS.items():
        hits = [w for w in words if w in haystack]
        if hits:
            matched[lane] = hits
    if not matched:
        return "VIRAL", []
    best = max(len(v) for v in matched.values())
    for lane in _LANE_PRIORITY:
        if len(matched.get(lane, [])) == best:
            return lane, matched[lane]
    lane = next(iter(matched))
    return lane, matched[lane]


def fetch_current(service: Any, video_id: str) -> dict[str, Any] | None:
    """Read one video's live snippet/status (read-only)."""
    resp = service.videos().list(part="snippet,status", id=video_id).execute()
    items = resp.get("items", [])
    if not items:
        return None
    v = items[0]
    sn = v.get("snippet", {})
    st = v.get("status", {})
    return {
        "id": v["id"],
        "title": sn.get("title", ""),
        "description": sn.get("description", ""),
        "tags": list(sn.get("tags", [])),
        "categoryId": sn.get("categoryId", ""),
        "defaultLanguage": sn.get("defaultLanguage", ""),
        "defaultAudioLanguage": sn.get("defaultAudioLanguage", ""),
        "privacy": st.get("privacyStatus", ""),
    }


def build_plan(
    current: dict[str, Any],
    lane: str | None = None,
    thumbnail_path: str | None = None,
    language: str = "en",
) -> dict[str, Any]:
    """Pure plan: what WOULD change for this video. No IO beyond the
    thumbnail existence check, no writes."""
    # Inference uses title + tags ONLY: the manual-era descriptions carry
    # channel boilerplate ("SUBSCRIBE ... daily unhinged comedy & viral
    # moments") that claims comedy on every upload regardless of content.
    inferred, signals = infer_lane(current["title"], current["tags"])
    lane_was_override = lane is not None
    lane = (lane or inferred).upper()
    # The video's own current tags are its proven tag set (they were
    # chosen for this exact clip); _derive_tags re-anchors them with the
    # channel anchors + lane base set + title keywords, deduped/capped.
    candidate = SimpleNamespace(tags=list(current["tags"]))
    new_tags = _derive_tags(candidate, current["title"], lane)
    new_category = YOUTUBE_CATEGORY_BY_EDITORIAL.get(lane, "24")

    if thumbnail_path is None:
        thumbnail = {"path": None, "status": "none_provided"}
    elif Path(thumbnail_path).is_file():
        thumbnail = {"path": thumbnail_path, "status": "ready"}
    else:
        thumbnail = {"path": thumbnail_path, "status": "missing_file"}

    return {
        "video_id": current["id"],
        "privacy": current.get("privacy", ""),
        "lane": lane,
        "lane_source": "override" if lane_was_override else "inferred",
        "lane_signals": signals,
        "title": current["title"],
        "description": current["description"],
        "category": {"before": current["categoryId"], "after": new_category},
        "tags": {"before": list(current["tags"]), "after": new_tags},
        "defaultLanguage": {"before": current["defaultLanguage"], "after": language},
        "defaultAudioLanguage": {"before": current["defaultAudioLanguage"], "after": language},
        "thumbnail": thumbnail,
        "metadata_changed": (
            new_category != current["categoryId"]
            or new_tags != list(current["tags"])
            or language != current["defaultLanguage"]
            or language != current["defaultAudioLanguage"]
        ),
    }


def apply_plan(service: Any, plan: dict[str, Any]) -> dict[str, Any]:
    """Execute one plan against the live API. Only called with --apply."""
    result: dict[str, Any] = {"video_id": plan["video_id"], "updated": False, "thumbnail_set": False}
    if plan["metadata_changed"]:
        body = {
            "id": plan["video_id"],
            "snippet": {
                # Title/description round-trip verbatim: videos.update
                # replaces the whole snippet.
                "title": plan["title"],
                "description": plan["description"],
                "tags": plan["tags"]["after"],
                "categoryId": plan["category"]["after"],
                "defaultLanguage": plan["defaultLanguage"]["after"],
                "defaultAudioLanguage": plan["defaultAudioLanguage"]["after"],
            },
        }
        service.videos().update(part="snippet", body=body).execute()
        result["updated"] = True
    if plan["thumbnail"]["status"] == "ready":
        result["thumbnail_set"] = bool(
            set_thumbnail(plan["video_id"], plan["thumbnail"]["path"])
        )
    return result


def _parse_kv(pairs: list[str] | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for pair in pairs or []:
        if "=" not in pair:
            raise SystemExit(f"expected VIDEO=VALUE, got: {pair!r}")
        key, value = pair.split("=", 1)
        out[key.strip()] = value.strip()
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--video-id", action="append", required=True,
                        help="video id to backfill (repeatable)")
    parser.add_argument("--lane", action="append", default=[],
                        help="pin a lane: VIDEO=COMEDY|SPORTS|VIRAL (repeatable)")
    parser.add_argument("--thumbnail", action="append", default=[],
                        help="generated thumbnail file: VIDEO=/path/to.jpg (repeatable)")
    parser.add_argument("--apply", action="store_true",
                        help="perform the writes (default is a read-only dry-run)")
    args = parser.parse_args(argv)

    lanes = _parse_kv(args.lane)
    thumbnails = _parse_kv(args.thumbnail)
    language = get_settings().youtube_default_language or "en"

    service = youtube_service()
    exit_code = 0
    for video_id in args.video_id:
        current = fetch_current(service, video_id)
        if current is None:
            print(json.dumps({"video_id": video_id, "error": "not_found"}))
            exit_code = 1
            continue
        plan = build_plan(
            current,
            lane=lanes.get(video_id),
            thumbnail_path=thumbnails.get(video_id),
            language=language,
        )
        plan["mode"] = "apply" if args.apply else "dry-run"
        if args.apply:
            plan["result"] = apply_plan(service, plan)
        print(json.dumps(plan, ensure_ascii=False))
    if not args.apply:
        print("DRY-RUN: no writes performed", file=sys.stderr)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
