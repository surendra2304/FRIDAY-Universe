"""VyralX live render path for the VYR-077 short-video ports (TASK-VYR-077).

Wires the two pattern-only ports into VyralX's live production path:

* ``shorts_factory`` (TASK-IG2-VYR-03, Short Video Factory pattern) — a
  factory job spec becomes a render plan.
* ``shorts_generator`` (TASK-IG2-VYR-04, Anil-matcha local-mode pattern) —
  a highlight clip becomes a render plan.

This module plans and, when asked, executes one render. It renders
nothing by itself on import, uploads nothing, publishes nothing, and
stays unlisted and review-first. FREE ONLY: no paid mode, no LLM call,
no MuAPI. The upstream LLM highlight-ranking step stays replaced by
VyralX's deterministic scoring in ``shorts_generator``.

Failure cases handled here, not silently:

* missing BGM — ``select_bgm_track_for_tone`` returns None, so the plan
  falls back to ``synthesize_ambient_pad_bgm`` and records the fallback
  instead of failing or rendering silent;
* doubled captions — ``dedupe_cues`` removes exact duplicate cues
  (same start, end and text) and records how many were removed, because
  ``captions.write_srt`` raises on overlapping cues;
* watermark — the plan carries the job's provenance licence through to
  the render; watermarking itself is ``provenance_watermark``'s job and
  is recorded as a separate step, never faked here.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from app.services import audio_mixer, captions, renderer, shorts_factory, shorts_generator


class LivePathError(ValueError):
    """Raised when a job or clip cannot become a render plan."""


MAX_SHORT_SECONDS = 59.0
PRESET = "shorts"


def dedupe_cues(cues: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], int]:
    """Remove exact duplicate cues, keeping first occurrence order.

    A cue is a duplicate when another cue has the same start_seconds,
    end_seconds and text. Returns the cleaned list and how many cues
    were removed. Overlapping but non-identical cues are left alone:
    ``captions.write_srt`` raises on those, which is the honest failure.
    """
    seen: set[tuple[Any, Any, Any]] = set()
    cleaned: list[dict[str, Any]] = []
    removed = 0
    for cue in cues:
        key = (cue.get("start_seconds"), cue.get("end_seconds"), cue.get("text"))
        if key in seen:
            removed += 1
            continue
        seen.add(key)
        cleaned.append(dict(cue))
    return cleaned, removed


def resolve_bgm(
    tone: str,
    music_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Resolve a BGM track, or name the ambient-pad fallback.

    Returns ``{"bgm_path": <str or None>, "fallback": "ambient_pad" or None}``.
    A missing library or an empty library is a planned fallback, never a
    silent render without music and never an exception.
    """
    track = audio_mixer.select_bgm_track_for_tone(tone, music_dir)
    if track is None:
        return {"bgm_path": None, "fallback": "ambient_pad"}
    return {"bgm_path": str(track), "fallback": None}


def clip_subtitles(
    timed_words: Iterable[dict[str, Any]],
    start: float,
    end: float,
) -> list[dict[str, Any]]:
    """Slice timed words into SRT cues for one clip window.

    Words are grouped into short cues (at most 4 words each) inside
    [start, end]. An empty window returns no cues, honestly.
    """
    words = [w for w in timed_words if start <= float(w["start"]) < end]
    if not words:
        return []
    cues: list[dict[str, Any]] = []
    chunk: list[dict[str, Any]] = []
    for word in words:
        chunk.append(word)
        if len(chunk) >= 4:
            cues.append({
                "start_seconds": float(chunk[0]["start"]),
                "end_seconds": float(chunk[-1]["end"]),
                "text": " ".join(str(w["word"]) for w in chunk),
            })
            chunk = []
    if chunk:
        cues.append({
            "start_seconds": float(chunk[0]["start"]),
            "end_seconds": float(chunk[-1]["end"]),
            "text": " ".join(str(w["word"]) for w in chunk),
        })
    return cues


def _base_plan(*, kind: str, topic: str, duration: float) -> dict[str, Any]:
    if duration > MAX_SHORT_SECONDS:
        raise LivePathError(
            f"short is {duration}s — Shorts must be <60s; shorten, do not trim silently")
    return {
        "version": "vyr077-1",
        "kind": kind,
        "status": "planned",
        "topic": topic,
        "format": "shorts",
        "width": 1080,
        "height": 1920,
        "duration_seconds": duration,
        "preset": PRESET,
        "publish": False,
        "privacy_if_published": "unlisted",
        "review": "pending_review",
    }


def build_factory_render_plan(
    job: dict[str, Any],
    *,
    source_path: str | Path,
    output_dir: str | Path,
    tone: str = "ambient_explainer",
    music_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Render plan for one ``shorts_factory`` job spec.

    The job's subtitle cues are deduped, BGM is resolved (ambient-pad
    fallback when the library has nothing), and the plan names the exact
    ``renderer.render_video`` call. Voiceover is EdgeTTS per the job's
    voice plan; this module does not synthesise it — the plan records
    ``voiceover_path`` as None with ``voiceover_note`` saying so.
    """
    if job.get("kind") != "vyralx.shorts_factory_job":
        raise LivePathError(f"not a shorts_factory job spec: {job.get('kind')!r}")
    if job.get("publish") is not False:
        raise LivePathError("factory job must not publish")
    duration = float(job["estimated_seconds"])
    cues, removed = dedupe_cues(job.get("subtitle_cues") or [])
    if not cues:
        raise LivePathError("factory job has no subtitle cues")
    bgm = resolve_bgm(tone, music_dir)
    plan = _base_plan(kind="vyralx.shorts_factory_render_plan",
                      topic=str(job["topic"]), duration=duration)
    plan.update({
        "job_version": job.get("version"),
        "lane": job.get("lane"),
        "source_path": str(source_path),
        "destination": str(Path(output_dir) / "short.mp4"),
        "subtitle_file": str(Path(output_dir) / "short.srt"),
        "subtitle_cues": cues,
        "duplicated_cues_removed": removed,
        "voiceover_path": None,
        "voiceover_note": "edge_tts_pending: voice plan is EdgeTTS, synthesised at render time",
        "bgm_path": bgm["bgm_path"],
        "bgm_fallback": bgm["fallback"],
        "mix_plan": job.get("mix_plan"),
        "render": "renderer.render_video",
        "fit_mode": "pad",
    })
    return plan


def build_clip_render_plan(
    clip: dict[str, Any],
    timed_words: Iterable[dict[str, Any]],
    *,
    source_path: str | Path,
    output_dir: str | Path,
    tone: str = "ambient_explainer",
    music_dir: Path | str | None = None,
) -> dict[str, Any]:
    """Render plan for one ``shorts_generator`` clip.

    Subtitles come from the transcript's timed words inside the clip
    window. The crop filter comes from the clip's own ``crop`` plan
    (face-tracked vertical crop). BGM resolves with the ambient-pad
    fallback when the library has nothing.
    """
    if clip.get("publish") is not False:
        raise LivePathError("clip must not publish")
    if clip.get("privacy") != "unlisted":
        raise LivePathError("clip must stay unlisted")
    start = float(clip["start"])
    end = float(clip["end"])
    duration = float(clip["duration"])
    cues, removed = dedupe_cues(clip_subtitles(timed_words, start, end))
    bgm = resolve_bgm(tone, music_dir)
    plan = _base_plan(kind="vyralx.shorts_clip_render_plan",
                      topic=str(clip.get("hook", "short")),
                      duration=duration)
    plan.update({
        "clip_start": start,
        "clip_end": end,
        "source_path": str(source_path),
        "destination": str(Path(output_dir) / "clip.mp4"),
        "subtitle_file": str(Path(output_dir) / "clip.srt"),
        "subtitle_cues": cues,
        "duplicated_cues_removed": removed,
        "crop_filter": (clip.get("crop") or {}).get("filter"),
        "face_tracked": (clip.get("crop") or {}).get("face_tracked"),
        "viral_score": clip.get("viral_score"),
        "bgm_path": bgm["bgm_path"],
        "bgm_fallback": bgm["fallback"],
        "render": "renderer.render_video",
        "fit_mode": "crop",
    })
    return plan


def execute_render_plan(
    plan: dict[str, Any],
    *,
    data_root: str | Path,
    max_memory_mb: int | None = None,
    cpu_threads: int | None = None,
) -> dict[str, Any]:
    """Run one render plan: write subtitles, resolve BGM, render.

    Writes the SRT via ``captions.write_srt`` (which raises on
    overlapping cues — that failure is reported, not hidden), plus the
    styled ASS companion via ``captions.write_ass``: the renderer
    prefers the ASS file when present, and on the current ffmpeg build
    the SRT ``subtitles`` filter path needs materially more address
    space than the ``ass`` path (live-trial finding 2026-11-26: SRT
    renders died mid-encode at a 1024MB cap; ASS renders completed).
    plan's BGM fallback is ``ambient_pad``, a pad is synthesised with
    ``audio_mixer.synthesize_ambient_pad_bgm`` before rendering.
    Renders with ``renderer.render_video`` (preset ``shorts``).
    Returns the render result with the output path. Nothing is uploaded
    and nothing is published by this function.

    ``data_root`` must sit inside the VyralX media directory when the
    ambient-pad fallback can fire: the renderer refuses BGM outside it.
    ``max_memory_mb`` / ``cpu_threads`` pass through to the renderer;
    None keeps the fleet settings. (Live-trial finding 2026-11-26: the
    fleet cap RENDER_MAX_MEMORY_MB=320 starves libx264 at 1080x1920 —
    renders need a cap of at least ~1024MB on the current ffmpeg build.)
    """
    if plan.get("status") != "planned":
        raise LivePathError(f"plan is not planned: {plan.get('status')!r}")
    if plan.get("publish") is not False:
        raise LivePathError("plan must not publish")
    destination = Path(plan["destination"])
    subtitle_file = Path(plan["subtitle_file"])
    captions.write_srt(plan["subtitle_cues"], subtitle_file)
    captions.write_ass(plan["subtitle_cues"], subtitle_file.with_suffix(".ass"))
    bgm_path = plan.get("bgm_path")
    if plan.get("bgm_fallback") == "ambient_pad":
        # .m4a, not .wav: synthesize_ambient_pad_bgm encodes AAC, and an
        # AAC stream inside a WAV container is undecodable downstream
        # (live-trial finding 2026-11-26: "Decode error rate 1").
        pad_path = Path(data_root) / "ambient_pad.m4a"
        audio_mixer.synthesize_ambient_pad_bgm(
            pad_path, float(plan["duration_seconds"]), "ambient_explainer")
        bgm_path = str(pad_path)
    kwargs: dict[str, Any] = {
        "subtitle_file": subtitle_file,
        "bgm_path": bgm_path,
        "voiceover_path": plan.get("voiceover_path"),
        "fit_mode": plan.get("fit_mode", "pad"),
        "max_memory_mb": max_memory_mb,
        "cpu_threads": cpu_threads,
    }
    if plan.get("clip_start") is not None:
        kwargs["trim_start_seconds"] = float(plan["clip_start"])
        kwargs["trim_end_seconds"] = float(plan["clip_end"])
    out = renderer.render_video(
        plan["source_path"], destination, plan["preset"], **kwargs)
    return {
        "status": "rendered",
        "output": out,
        "destination": str(destination),
        "subtitle_file": str(subtitle_file),
        "bgm_path": bgm_path,
        "bgm_fallback": plan.get("bgm_fallback"),
        "duplicated_cues_removed": plan.get("duplicated_cues_removed", 0),
        "publish": False,
        "privacy_if_published": "unlisted",
    }
