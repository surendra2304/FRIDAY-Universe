"""BGM policy and track selection (TASK-VYR-019).

Owner decision 2026-11-18, option C — the background-music policy is a
switch (``settings.viral_bgm_policy``):

``growth`` (default)
    While the channel is growing and everything is unlisted, videos
    carry the actual popular/chart tracks: the best, most relevant
    track the local library holds for the video's category, at proper
    volume (the renderers duck it under any voice and let it sit at
    full level in voiceless stretches). **Phonk is a first-class
    source category in this mode** (owner sharpening 2026-11-18):
    phonk tracks and phonk edits sit alongside the other popular
    tracks in the same library, and for the high-energy edit
    categories (sports, gaming, autos, viral) a phonk track is the
    preferred pick whenever the library holds one — same volume
    discipline as every other track.
``monetisation``
    Once monetisation starts, only YouTube Audio Library tracks are
    used, from the library folder reserved for them.

The library is operator-provisioned: audio files plus a ``catalog.json``
(``{"tracks": [{"file": ..., "title": ..., "artist": ...,
"categories": [...], "styles": [...], "moods": [...]}]}``) in the policy's
folder — ``<data_dir>/bgm`` for growth, ``<data_dir>/bgm_library`` for
monetisation, unless ``viral_bgm_library_dir`` / ``viral_bgm_catalog_path``
override them. This module never downloads music by itself.

A track's ``styles`` list names its source category — ``"phonk"`` is
the named first-class style (a file whose name contains "phonk" also
counts as phonk even without a catalog entry, so dropping phonk edits
into the folder is enough to stock the shelf).

One rule outranks the policy: **a real bed is mandatory**. If no track
fits (or the library is empty), :func:`prepare_music_bed` falls back
to the generated synth bed from :mod:`app.services.viral_remix` and
says so in the source label it returns — the label is recorded on the
render job, so a fallback is visible in the record, never silent, and
no render ever ships with the phantom "[music]" of the old pipeline.
"""
from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import Any

from app.config import get_settings

log = logging.getLogger("vyralx.viral_bgm")

_AUDIO_SUFFIXES = {".mp3", ".m4a", ".wav", ".aac", ".ogg", ".opus", ".flac"}

_POLICY_FOLDERS = {
    "growth": "bgm",
    "monetisation": "bgm_library",
}

#: The named first-class style of the growth library (owner, 2026-11-18).
PHONK_STYLE = "phonk"

#: Editorial labels whose edits are phonk-shaped by default — the
#: high-energy montage categories where phonk edits are the sound of
#: the format. For these, a phonk track wins selection whenever the
#: library holds one (still inside the category-matched pool first).
PHONK_PREFERRED_CATEGORIES = frozenset({"SPORTS", "GAMING", "AUTOS", "VIRAL"})


def preferred_style(category: str = "") -> str:
    """The style a category's bed should prefer ("" = no preference)."""
    wanted = str(category or "").strip().upper()
    return PHONK_STYLE if wanted in PHONK_PREFERRED_CATEGORIES else ""


def policy(settings: Any = None) -> str:
    """The active BGM policy, normalised (defaults to growth)."""
    settings = settings or get_settings()
    value = str(getattr(settings, "viral_bgm_policy", "growth") or "growth").strip().lower()
    return value if value in _POLICY_FOLDERS else "growth"


def library_dir(settings: Any = None) -> Path:
    """Folder holding the active policy's track files."""
    settings = settings or get_settings()
    override = str(getattr(settings, "viral_bgm_library_dir", "") or "").strip()
    if override:
        return Path(override)
    return Path(settings.data_dir) / _POLICY_FOLDERS[policy(settings)]


def catalog_path(settings: Any = None) -> Path:
    settings = settings or get_settings()
    override = str(getattr(settings, "viral_bgm_catalog_path", "") or "").strip()
    if override:
        return Path(override)
    return library_dir(settings) / "catalog.json"


def load_catalog(settings: Any = None) -> list[dict[str, Any]]:
    """Usable tracks in the active library: catalog entries + bare files.

    A catalog entry counts only while its file exists. Audio files with
    no catalog entry are still usable (title = file stem, no category
    affinity). A missing or unreadable catalog simply means "no
    metadata", never an error.
    """
    folder = library_dir(settings)
    if not folder.is_dir():
        return []
    by_file: dict[str, dict[str, Any]] = {}
    path = catalog_path(settings)
    if path.is_file():
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.warning("BGM catalog unreadable (%s); using bare files", exc)
            raw = {}
        for entry in (raw.get("tracks") or []) if isinstance(raw, dict) else []:
            if not isinstance(entry, dict):
                continue
            name = str(entry.get("file") or "").strip()
            if name:
                by_file[name] = entry
    tracks: list[dict[str, Any]] = []
    for file_path in sorted(folder.iterdir()):
        if file_path.suffix.lower() not in _AUDIO_SUFFIXES or not file_path.is_file():
            continue
        entry = by_file.get(file_path.name, {})
        styles = [
            str(value).strip().lower() for value in (entry.get("styles") or [])
        ]
        if PHONK_STYLE in file_path.stem.lower() and PHONK_STYLE not in styles:
            styles.append(PHONK_STYLE)
        tracks.append({
            "file": file_path.name,
            "path": file_path,
            "title": str(entry.get("title") or file_path.stem),
            "artist": str(entry.get("artist") or ""),
            "categories": [
                str(value).strip().upper() for value in (entry.get("categories") or [])
            ],
            "styles": styles,
            "moods": [str(value).strip() for value in (entry.get("moods") or [])],
        })
    return tracks


def select_track(
    settings: Any = None,
    *,
    category: str = "",
    rotation_key: str = "",
    style: str = "",
) -> dict[str, Any] | None:
    """Pick the most relevant track for a category (None when empty).

    Category-tagged tracks win; inside that pool, tracks carrying the
    requested ``style`` win (this is how phonk — the first-class style
    — takes the high-energy categories without evicting category
    relevance). Among equals the pick rotates by a hash of
    ``rotation_key`` (the render's project key) so consecutive videos
    do not all land on the same track, while any single render stays
    reproducible.
    """
    tracks = load_catalog(settings)
    if not tracks:
        return None
    wanted = str(category or "").strip().upper()
    matched = [track for track in tracks if wanted and wanted in track["categories"]]
    pool = matched or tracks
    wanted_style = str(style or "").strip().lower()
    if wanted_style:
        styled = [track for track in pool if wanted_style in track["styles"]]
        if styled:
            pool = styled
    if len(pool) == 1:
        return pool[0]
    digest = hashlib.sha256(rotation_key.encode("utf-8")).digest()
    return pool[int.from_bytes(digest[:4], "big") % len(pool)]


def library_status(settings: Any = None) -> dict[str, Any]:
    """What the active policy can actually draw on right now."""
    settings = settings or get_settings()
    tracks = load_catalog(settings)
    phonk = [track for track in tracks if PHONK_STYLE in track["styles"]]
    return {
        "policy": policy(settings),
        "library_dir": str(library_dir(settings)),
        "tracks_available": len(tracks),
        "phonk_tracks": len(phonk),
        "phonk_titles": [track["title"] for track in phonk[:20]],
        "tracks": [track["title"] for track in tracks[:20]],
    }


def prepare_music_bed(
    destination: Path,
    seconds: float,
    *,
    category: str = "",
    style: str = "",
    settings: Any = None,
) -> tuple[Path, str]:
    """Produce a bed of exactly ``seconds`` at ``destination``.

    Returns ``(path, source_label)`` where the label names what the bed
    actually is — ``growth:<title>`` / ``monetisation:<title>`` for a
    library track (with ``:phonk`` appended when the chosen track is a
    phonk track, so the record shows the first-class style was used),
    ``synth_fallback`` when the generated bed had to stand in. The
    label is part of the render record.

    ``style`` defaults to the category's preference
    (:func:`preferred_style`) — phonk for the high-energy categories.
    """
    settings = settings or get_settings()
    from app.services.viral_remix import _run, build_music_bed

    total = max(1.0, float(seconds or 0.0))
    track = select_track(
        settings,
        category=category,
        rotation_key=str(destination),
        style=style or preferred_style(category),
    )
    if track is not None:
        destination.parent.mkdir(parents=True, exist_ok=True)
        fade_start = max(0.0, total - 0.6)
        try:
            _run([
                settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
                "-stream_loop", "-1", "-i", str(track["path"]),
                "-t", f"{total:.3f}",
                "-af", f"afade=t=in:st=0:d=0.2,afade=t=out:st={fade_start:.3f}:d=0.6",
                "-c:a", "pcm_s16le", str(destination),
            ])
            label = f"{policy(settings)}:{track['title']}"
            if PHONK_STYLE in track["styles"]:
                label = f"{label}:phonk"
            log.info("BGM bed from library track %s (%s)", track["file"], label)
            return destination, label
        except Exception as exc:
            log.warning(
                "BGM track %s could not be prepared (%s); falling back to the synth bed",
                track["file"], exc,
            )
    bed = build_music_bed(destination, total)
    return bed, "synth_fallback"


def is_real_track_label(label: str) -> bool:
    """Whether a BGM source label names a real library track (TASK-VYR-038).

    The per-job gate field: :func:`prepare_music_bed` labels a library
    bed ``growth:<title>`` / ``monetisation:<title>`` (``:phonk``
    appended for phonk tracks) and the generated bed ``synth_fallback``;
    an empty label means no bed was prepared. Only the first two name a
    real track, so only they pass the gate. One function owns the check
    so the produce paths never string-match the label themselves.
    """
    return str(label or "").split(":")[0] in ("growth", "monetisation")
