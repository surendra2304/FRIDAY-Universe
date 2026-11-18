"""Long-form lane for the autonomous loop (TASK-VYR-019).

Owner decision 2026-11-18, option B: shorts are the staple, plus
occasional longer videos. The loop's long-form v1 is a **compilation**:
once a series has enough held shorts, they are assembled into one
1920x1080 video (each clip on a blurred-pad canvas, keeping its own
audio — every clip already carries its mandatory BGM bed, ducked the
same way as in its short, so no second bed is laid over the
compilation) and held as an unlisted ``pending_approval`` publish job
exactly like the shorts. The owner reviews and publishes; the lane
never uploads anything itself.

Clips are chosen from the loop manifest (``viral_loop_manifest.jsonl``):
held renders of one series that no earlier compilation has consumed.
A compilation consumes its clips — the manifest records the
compilation entry with the clip render paths, so a clip is never
compiled twice.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, PublishJob, RenderJob, Source, VideoProject, utcnow
from app.services import viral_remix as vr
from app.services.viral_series import SERIES_BY_LABEL, normalise_label

log = logging.getLogger("vyralx.viral_longform")


def read_manifest(path: Path) -> list[dict[str, Any]]:
    """All entries of the loop manifest (missing file = empty)."""
    entries: list[dict[str, Any]] = []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return entries
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if isinstance(payload, dict):
            entries.append(payload)
    return entries


def append_manifest(path: Path, entry: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry, ensure_ascii=False) + "\n")


def available_clips(entries: list[dict[str, Any]], series: str) -> list[dict[str, Any]]:
    """Held short renders of ``series`` not yet consumed by a compilation."""
    consumed: set[str] = set()
    for entry in entries:
        if entry.get("kind") == "longform":
            for clip in entry.get("clips") or []:
                consumed.add(str(clip))
    clips: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("kind") != "short":
            continue
        if normalise_label(str(entry.get("series") or "")) != series:
            continue
        render = str(entry.get("render") or "")
        if not render or render in consumed:
            continue
        if not Path(render).is_file():
            continue
        clips.append(entry)
    return clips


def best_series_for_compilation(
    entries: list[dict[str, Any]], min_clips: int
) -> tuple[str, list[dict[str, Any]]] | None:
    """The series with the most unconsumed held clips, if it clears the bar."""
    best: tuple[str, list[dict[str, Any]]] | None = None
    for label in SERIES_BY_LABEL:
        clips = available_clips(entries, label)
        if len(clips) >= max(1, int(min_clips)):
            if best is None or len(clips) > len(best[1]):
                best = (label, clips)
    return best


def render_compilation(clip_paths: list[Path], output_path: Path) -> Path:
    """Concatenate clips onto a 1920x1080 blurred-pad canvas.

    Each clip keeps its own audio untouched (its bed and ducking are
    already mixed in); the only processing is the canvas fit and a
    loudness normalisation across the joins.
    """
    settings = get_settings()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    filters: list[str] = []
    for index in range(len(clip_paths)):
        filters.append(
            f"[{index}:v]split=2[bg{index}][fg{index}];"
            f"[bg{index}]scale=1920:1080,gblur=sigma=40[bgb{index}];"
            f"[fg{index}]scale=1920:1080:force_original_aspect_ratio=decrease[fgb{index}];"
            f"[bgb{index}][fgb{index}]overlay=(W-w)/2:(H-h)/2[v{index}];"
            f"[{index}:a]aresample=48000[a{index}]"
        )
    joins = "".join(f"[v{i}][a{i}]" for i in range(len(clip_paths)))
    filters.append(
        f"{joins}concat=n={len(clip_paths)}:v=1:a=1[vc][ac];"
        "[ac]loudnorm=I=-14:LRA=9:TP=-1.5[a]"
    )
    cmd = [settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y"]
    for clip in clip_paths:
        cmd += ["-i", str(clip)]
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[vc]", "-map", "[a]",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        str(output_path),
    ]
    vr._run(cmd, timeout=3600)
    return output_path


def produce_compilation(
    db: Session,
    *,
    manifest_path: Path,
    min_clips: int = 3,
    series: str = "",
) -> dict[str, Any]:
    """Build one held long-form compilation from the loop manifest.

    Picks the richest series (or the requested one), renders the
    compilation, persists it with a held publish job, and records the
    compilation in the manifest so its clips are consumed.
    """
    settings = get_settings()
    settings.prepare_directories()
    settings.render_dir.mkdir(parents=True, exist_ok=True)
    entries = read_manifest(manifest_path)
    if series:
        label = normalise_label(series)
        clips = available_clips(entries, label)
        picked = (label, clips) if len(clips) >= max(1, int(min_clips)) else None
    else:
        picked = best_series_for_compilation(entries, min_clips)
    if picked is None:
        return {"status": "SKIPPED", "reason": "not_enough_clips", "edit_mode": "compilation"}
    label, clips = picked
    clips = clips[:12]  # a compilation stays watchable; the rest wait for the next one
    clip_paths = [Path(str(clip["render"])) for clip in clips]
    info = SERIES_BY_LABEL[label]
    project_key = f"longform-{label.casefold()}-{uuid.uuid4().hex[:6]}"
    render_path = settings.render_dir / f"{project_key}.mp4"
    render_compilation(clip_paths, render_path)
    probe = vr.probe_media(render_path)
    total_seconds = float(probe.duration or 0.0)

    titles = [str(clip.get("title") or "") for clip in clips if clip.get("title")]
    description_lines = [
        f"{info['series']} — the best of the series so far, in one video.",
        "",
        "Featuring:",
        *[f"• {title}" for title in titles[:12]],
        "",
        "Every clip is an original transformative edit with commentary or "
        "framing narration, subtitles and attribution to the original creators.",
    ]
    title = f"{info['series']} — Best Moments Compilation"
    tags = list(dict.fromkeys([
        info["slug"].replace("-", " "), "compilation", "best moments",
        "viral", label.casefold(), "vyralx",
    ]))

    source = Source(
        title=f"Compilation source: {info['series']} held renders",
        source_url="",
        platform="vyralx_compilation",
        creator="VyralX",
        license_name="Original VyralX compilation of its own held renders",
        permission_reference=(
            "All clips are VyralX renders held in the loop manifest; each "
            "clip's own source rights record stands."
        )[:2000],
        repeat_use_allowed=True,
        repeat_use_reviewed_at=utcnow(),
        repeat_use_review_notes="Internal compilation; no external rights involved.",
        rights_verified=True,
        status="approved",
        notes="Long-form lane compilation (TASK-VYR-019).",
    )
    db.add(source)
    db.flush()
    asset = Asset(
        source_id=source.id,
        title=title[:280],
        file_path=str(render_path),
        duration_seconds=total_seconds,
        width=probe.width,
        height=probe.height,
        rights_verified=True,
    )
    db.add(asset)
    db.flush()
    project = VideoProject(
        project_key=project_key,
        topic=f"Compilation: {info['series']}",
        video_format="long_form",
        target_seconds=int(round(total_seconds)),
        audience="series followers",
        tone="compilation",
        scene_count=len(clips),
        confirm_pexels_license=False,
        confirm_pexels_repeat_use=False,
        use_voiceover=True,
        status="completed",
        primary_asset_id=asset.id,
        asset_ids_json=json.dumps([asset.id]),
        thumbnail_path="",
        completed_at=utcnow(),
        attempts=1,
    )
    db.add(project)
    db.flush()
    render_job = RenderJob(
        asset_id=asset.id,
        preset="longform",
        status="completed",
        output_path=str(render_path),
        attempts=1,
        project_id=None,
        options_json=json.dumps({
            "edit_mode": "compilation",
            "series": label,
            "clips": [str(path) for path in clip_paths],
            "hold_for_review": True,
        }),
        completed_at=utcnow(),
    )
    db.add(render_job)
    db.flush()
    project.render_job_id = render_job.id
    publish_job = PublishJob(
        asset_id=asset.id,
        render_job_id=render_job.id,
        title=title,
        description="\n".join(description_lines)[:4800],
        tags_json=json.dumps(tags),
        privacy_status=str(getattr(settings, "autonomous_publish_privacy", "unlisted")),
        status="pending_approval",
        approved_at=None,
        thumbnail_path="",
        category_id=str(info["youtube_category_id"]),
    )
    db.add(publish_job)
    db.commit()

    append_manifest(manifest_path, {
        "kind": "longform",
        "series": label,
        "render": str(render_path),
        "render_job_id": render_job.id,
        "publish_job_id": publish_job.id,
        "title": title,
        "clips": [str(path) for path in clip_paths],
        "status": "HELD",
    })
    result = {
        "status": "QUEUED_FOR_PUBLISH",
        "project_key": project_key,
        "project_id": project.id,
        "render_job_id": render_job.id,
        "publish_job_id": publish_job.id,
        "edit_mode": "compilation",
        "series": label,
        "title": title,
        "duration": round(total_seconds, 1),
        "clips": len(clips),
        "render": str(render_path),
        "hold_for_review": True,
    }
    log.info("Long-form compilation ready: %s", result)
    return result
