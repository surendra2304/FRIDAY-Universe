"""Cross-post release bundles for every produced Short (TASK-VYR-014).

The channel's videos are rendered once (1080x1920) and uploaded to YouTube.
The same vertical file is directly postable to Instagram Reels, TikTok and
Facebook Reels — but until now nothing prepared those posts: the older
``multiplatform_publisher`` packager is only invoked by dead manual scripts,
and it rewrites titles through the SEO optimiser instead of using the words
that actually shipped.

This module writes, next to every produced Short, a bundle under
``<data_dir>/exports/crosspost_<video_key>/``:

* ``video.mp4`` — a copy of the exact render that went to YouTube;
* ``POST_COPY.txt`` — copy-paste captions per platform, built from the ACTUAL
  title, description and tags of the YouTube upload;
* ``manifest.json`` — machine-readable record of the bundle.

Platform notes (rules checked 2026-11-17): TikTok has been banned in India
since 2020, so its caption is prepared for completeness only — the reachable
audiences are Instagram Reels and Facebook Reels, where income is brand
deals and Shopping rather than per-view pay. Bundles never post anything by
themselves; they remove the manual work between "uploaded to YouTube" and
"posted everywhere else".
"""
from __future__ import annotations

import json
import logging
import re
import shutil
from pathlib import Path
from typing import Any

from app.config import get_settings
from app.models import utcnow

log = logging.getLogger("vyralx.crosspost_export")

_HASHTAG_RE = re.compile(r"#\w+")


def _hashtags_from(tags: list[str], description: str, *, limit: int) -> list[str]:
    """Prefer the hashtags that actually shipped in the description; fall
    back to the upload's tag list."""
    found = _HASHTAG_RE.findall(description or "")
    seen: list[str] = []
    for tag in found:
        if tag not in seen:
            seen.append(tag)
    if len(seen) < 3:
        for raw in tags or []:
            tag = "#" + "".join(str(raw).split())
            if tag not in seen:
                seen.append(tag)
    return seen[:limit]


def _title_core(title: str) -> str:
    return _HASHTAG_RE.sub("", str(title or "")).strip(" -|:")


def _question_line(description: str) -> str:
    for line in (description or "").splitlines():
        if "👉" in line or line.strip().endswith("?"):
            return line.strip()
    return ""


def build_platform_captions(
    *,
    title: str,
    description: str,
    tags: list[str],
    category: str = "",
) -> dict[str, str]:
    """Per-platform captions derived from the shipped YouTube metadata."""
    core = _title_core(title)
    question = _question_line(description)

    ig_tags = _hashtags_from(tags, description, limit=15)
    ig_caption = core
    if question:
        ig_caption += f"\n\n{question}"
    ig_caption += "\n\nFollow for daily viral moments! 🔥"
    if ig_tags:
        ig_caption += f"\n\n{' '.join(ig_tags)}"

    tt_tags = _hashtags_from(tags, description, limit=5)
    tt_caption = f"{core} 😱"
    if tt_tags:
        tt_caption += " " + " ".join(tt_tags)
    tt_caption = tt_caption[:150]

    fb_tags = _hashtags_from(tags, description, limit=8)
    fb_caption = core
    if question:
        fb_caption += f"\n\n{question}"
    if fb_tags:
        fb_caption += f"\n\n{' '.join(fb_tags)}"

    return {
        "youtube_shorts": f"TITLE:\n{title}\n\nDESCRIPTION:\n{description}",
        "instagram_reels": ig_caption[:2200],
        "tiktok": tt_caption,
        "facebook_reels": fb_caption,
    }


def write_crosspost_bundle(
    render_path: Path,
    *,
    title: str,
    description: str,
    tags: list[str],
    category: str = "",
    video_key: str,
    export_root: Path | None = None,
) -> dict[str, Any]:
    """Write the bundle for one produced Short. Returns a summary dict.

    Never raises for a missing render file — the bundle still carries the
    captions, with the manifest recording that the video copy was skipped.
    """
    settings = get_settings()
    root = export_root or (settings.data_dir / "exports")
    bundle_dir = root / f"crosspost_{video_key}"
    bundle_dir.mkdir(parents=True, exist_ok=True)

    captions = build_platform_captions(
        title=title, description=description, tags=tags, category=category
    )

    video_file = bundle_dir / "video.mp4"
    video_copied = False
    if render_path and Path(render_path).is_file():
        if not video_file.is_file():
            shutil.copy2(render_path, video_file)
        video_copied = True

    sections = [
        ("YOUTUBE SHORTS (as uploaded)", captions["youtube_shorts"]),
        ("INSTAGRAM REELS", captions["instagram_reels"]),
        ("TIKTOK (prepared; TikTok is banned in India — post only where legal)", captions["tiktok"]),
        ("FACEBOOK REELS", captions["facebook_reels"]),
    ]
    post_copy = "\n\n".join(f"=== {name} ===\n{text}" for name, text in sections)
    (bundle_dir / "POST_COPY.txt").write_text(post_copy, encoding="utf-8")

    manifest = {
        "video_key": video_key,
        "title": title,
        "category": str(category or "").upper(),
        "source_render": str(render_path),
        "video_copied": video_copied,
        "created_at": utcnow().isoformat(),
        "platforms": list(captions.keys()),
        "captions": captions,
    }
    (bundle_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    log.info("Cross-post bundle written: %s (video_copied=%s)", bundle_dir, video_copied)
    return {"bundle": str(bundle_dir), "platforms": list(captions.keys()), "video_copied": video_copied}
