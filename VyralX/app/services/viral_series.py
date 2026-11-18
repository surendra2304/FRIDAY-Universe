"""Series registry for the autonomous loop (TASK-VYR-019).

The owner's locked shape (2026-11-18): VyralX finds popular videos
across ALL categories — not only the channel's original comedy lanes —
and organises them as separate series/playlists per category, so a
viewer who follows one strand is never flooded with another.

This module is the single source of truth for that organisation:

* ``YOUTUBE_TRENDING_CATEGORIES`` — the assignable YouTube category
  ids the trending discovery sweeps, each mapped to the editorial
  label the rest of the pipeline already speaks (the label keys
  ``VOICE_BY_CATEGORY`` / ``HASHTAGS_BY_CATEGORY`` /
  ``YOUTUBE_CATEGORY_BY_EDITORIAL`` in :mod:`app.services.viral_remix`).
* ``SERIES_BY_LABEL`` — editorial label -> series identity: the series
  name used in manifests and reports, the YouTube playlist title the
  owner's publish step files the video under, and a slug used in tags.

Nothing here performs I/O; it is pure mapping data plus normalisers.
"""
from __future__ import annotations

from typing import Any

# (youtube_category_id, editorial_label, youtube_category_name)
YOUTUBE_TRENDING_CATEGORIES: list[tuple[str, str, str]] = [
    ("1", "FILM", "Film & Animation"),
    ("2", "AUTOS", "Autos & Vehicles"),
    ("10", "MUSIC", "Music"),
    ("15", "PETS", "Pets & Animals"),
    ("17", "SPORTS", "Sports"),
    ("19", "TRAVEL", "Travel & Events"),
    ("20", "GAMING", "Gaming"),
    ("22", "PEOPLE", "People & Blogs"),
    ("23", "COMEDY", "Comedy"),
    ("24", "ENTERTAINMENT", "Entertainment"),
    ("25", "NEWS", "News & Politics"),
    ("26", "HOWTO", "Howto & Style"),
    ("27", "EDUCATION", "Education"),
    ("28", "TECH", "Science & Technology"),
]

LABEL_BY_YOUTUBE_ID: dict[str, str] = {
    category_id: label for category_id, label, _name in YOUTUBE_TRENDING_CATEGORIES
}

YOUTUBE_ID_BY_LABEL: dict[str, str] = {
    label: category_id for category_id, label, _name in YOUTUBE_TRENDING_CATEGORIES
}


def _series(label: str, name: str, youtube_id: str) -> dict[str, Any]:
    return {
        "label": label,
        "series": f"VyralX {name}",
        "playlist_title": f"{name} | VyralX",
        "slug": name.casefold().replace(" ", "-").replace("&", "and"),
        "youtube_category_id": youtube_id,
    }


SERIES_BY_LABEL: dict[str, dict[str, Any]] = {
    "VIRAL": _series("VIRAL", "Viral", "24"),
    "COMEDY": _series("COMEDY", "Comedy", "23"),
    "SPORTS": _series("SPORTS", "Sports", "17"),
    "FILM": _series("FILM", "Film", "1"),
    "AUTOS": _series("AUTOS", "Autos", "2"),
    "MUSIC": _series("MUSIC", "Music", "10"),
    "PETS": _series("PETS", "Pets and Animals", "15"),
    "TRAVEL": _series("TRAVEL", "Travel", "19"),
    "GAMING": _series("GAMING", "Gaming", "20"),
    "PEOPLE": _series("PEOPLE", "People", "22"),
    "ENTERTAINMENT": _series("ENTERTAINMENT", "Entertainment", "24"),
    "NEWS": _series("NEWS", "News", "25"),
    "HOWTO": _series("HOWTO", "How To", "26"),
    "EDUCATION": _series("EDUCATION", "Education", "27"),
    "TECH": _series("TECH", "Tech and Science", "28"),
}

# Aliases the discovery layers have historically emitted or may emit.
_LABEL_ALIASES = {
    "SCIENCE": "TECH",
    "TECHNOLOGY": "TECH",
    "SCIENCE & TECHNOLOGY": "TECH",
    "NEWS & POLITICS": "NEWS",
    "POLITICS": "NEWS",
    "HOWTO & STYLE": "HOWTO",
    "STYLE": "HOWTO",
    "PETS & ANIMALS": "PETS",
    "ANIMALS": "PETS",
    "TRAVEL & EVENTS": "TRAVEL",
    "EVENTS": "TRAVEL",
    "PEOPLE & BLOGS": "PEOPLE",
    "BLOGS": "PEOPLE",
    "FILM & ANIMATION": "FILM",
    "ANIMATION": "FILM",
    "AUTOS & VEHICLES": "AUTOS",
    "VEHICLES": "AUTOS",
    "ENTERTAINMENT": "ENTERTAINMENT",
}


def normalise_label(category: str | None) -> str:
    """Map any category spelling onto a registry editorial label."""
    label = str(category or "").strip().upper()
    if label in SERIES_BY_LABEL:
        return label
    return _LABEL_ALIASES.get(label, "VIRAL")


def series_for_category(category: str | None) -> dict[str, Any]:
    """Series identity for a candidate category (never raises)."""
    return SERIES_BY_LABEL[normalise_label(category)]


def label_for_youtube_category_id(category_id: str | int | None) -> str:
    """Editorial label for a YouTube category id (VIRAL when unknown)."""
    return LABEL_BY_YOUTUBE_ID.get(str(category_id or "").strip(), "VIRAL")
