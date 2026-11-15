"""Lane-3 (tech & AI explainers) source catalogue for VyralX.

TASK-VYR-012 stocked the lane-3 shelf for the remix pipeline
(TASK-VYR-004), mirroring TASK-VYR-006's lane-1 catalogue:
``app/data/source_catalog_lane3.json`` holds one record per clip from
keyless public feeds (Wikimedia Commons, the Internet Archive's
Prelinger collection, the NASA Image and Video Library). Unlike lane 1
(public domain only), lane 3 admits the full TASK-VYR-004 licence
gate — CC0 / public domain / CC BY / CC BY-SA — and every record
carries the licence and provenance fields VyralX's rights gate
(``app.services.rights.source_is_publishable``) requires, plus the
measured duration / resolution (and its measurement source) the
remix editor needs to plan cuts.

This module is deliberately stdlib-only and returns plain dicts, so
the pipeline can register catalogue clips as ``app.models.Source``
rows (via :func:`as_source_rows`) or consume the raw records directly.
The interface is identical to the lane-1 loader
(``app.services.source_catalog``) so lanes are interchangeable.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LANE = "lane3_tech_ai"
CATALOG_PATH = Path(__file__).resolve().parent.parent / "data" / "source_catalog_lane3.json"

_cache: dict[str, Any] | None = None


def load_catalogue(path: Path | None = None) -> dict[str, Any]:
    """Load (and cache) the lane-3 catalogue document."""
    global _cache
    if path is None and _cache is not None:
        return _cache
    doc = json.loads(Path(path or CATALOG_PATH).read_text(encoding="utf-8"))
    if path is None:
        _cache = doc
    return doc


def load_clips(
    *,
    tag: str | None = None,
    platform: str | None = None,
    min_duration: float = 0.0,
    min_width: int = 0,
) -> list[dict[str, Any]]:
    """Return catalogue clips, optionally filtered for an edit's needs."""
    clips = load_catalogue().get("clips", [])
    out = []
    for clip in clips:
        if tag and tag not in clip.get("topic_tags", []):
            continue
        if platform and clip.get("platform") != platform:
            continue
        if float(clip.get("duration_seconds") or 0) < min_duration:
            continue
        if int(clip.get("width") or 0) < min_width:
            continue
        out.append(clip)
    return out


def as_source_rows(clips: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    """Map catalogue records onto ``app.models.Source`` fields.

    The remix pipeline can insert these rows unchanged; the rights gate
    then sees a meaningful ``license_name`` and ``permission_reference``
    on every row, and ``rights_verified`` is only ever True because each
    record's ``rights_basis`` documents the licence provenance the
    harvest gate (CC0 / PD / CC BY / CC BY-SA) verified.
    """
    rows = []
    for clip in clips if clips is not None else load_clips():
        notes = " | ".join(
            part
            for part in [
                f"catalogue: {clip.get('catalog_id', '')}",
                f"external_id: {clip.get('external_id', '')}",
                f"page: {clip.get('page_url', '')}",
                f"{clip.get('resolution', '')} / {clip.get('duration_seconds', '')}s",
                str(clip.get("rights_basis", "")),
            ]
            if part
        )
        rows.append(
            {
                "title": clip.get("title", ""),
                "source_url": clip.get("source_url", ""),
                "platform": clip.get("platform", ""),
                "creator": clip.get("creator", ""),
                "license_name": clip.get("license_name", ""),
                "permission_reference": clip.get("permission_reference", ""),
                "repeat_use_allowed": bool(clip.get("repeat_use_allowed")),
                "rights_verified": bool(clip.get("rights_verified")),
                "status": "discovered",
                "notes": notes,
            }
        )
    return rows


def catalogue_stats() -> dict[str, Any]:
    """Small summary the pipeline/ops can log: size, coverage, HD share."""
    clips = load_clips()
    by_platform: dict[str, int] = {}
    by_tag: dict[str, int] = {}
    total_seconds = 0.0
    hd = 0
    for clip in clips:
        by_platform[clip.get("platform", "?")] = by_platform.get(clip.get("platform", "?"), 0) + 1
        for tag in clip.get("topic_tags", []):
            by_tag[tag] = by_tag.get(tag, 0) + 1
        total_seconds += float(clip.get("duration_seconds") or 0)
        if int(clip.get("width") or 0) >= 1280:
            hd += 1
    return {
        "lane": LANE,
        "clip_count": len(clips),
        "by_platform": by_platform,
        "by_tag": by_tag,
        "total_seconds": round(total_seconds, 1),
        "hd_or_better": hd,
    }
