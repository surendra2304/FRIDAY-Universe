"""Framed production for voiced sources (TASK-VYR-019).

The owner's audio rule (locked 2026-11-18): a source WITH voice keeps
its own voice — VyralX never talks over it. Her narration only frames
the clip:

* a **hook** line before the moment (source audio ducked under it),
* the source's own speech at full level in between, carried by
  timing-true Whisper subtitles (the :class:`SpeechReport` cues —
  measured timings, never invented ones),
* a **payoff** line after it (source ducked again),
* a real BGM bed under everything, ducked under her lines.

A source WITHOUT voice never reaches this module — the loop routes it
to the commentary path in :mod:`app.services.viral_remix`, whose whole
design is a full voice-over. The two modes share the quality gates'
grounding discipline: the framing lines are claim-checked against the
same structured vision record the commentary path uses, the hook obeys
the same 18-word cap (and the same deterministic repair), and a line
that cannot be grounded or cannot fit its window skips the candidate
instead of shipping.

Short excerpts only (owner decision 2A): a source up to
``viral_max_source_seconds`` is used whole; a longer source contributes
one window around its event-arc peak, never the whole thing.
"""
from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Asset, PublishJob, RenderJob, Source, VideoProject, utcnow
from app.services import viral_quality as vq
from app.services import viral_remix as vr
from app.services.scene_analysis import analyze_scene, scene_text
from app.services.viral_series import normalise_label

log = logging.getLogger("vyralx.viral_framing")

# Spoken rate the production gates calibrate against (words per second).
_WORDS_PER_SECOND = 2.45
_HOOK_WORD_CAP = 18

# Render-fit profile (TASK-VYR-021). The first supervised loop cycle
# (2026-11-18) lost both framed renders to the 2,400s production
# timeout: at the old profile (1080x1920, libx264 veryfast/crf20) a
# 40s framed render costs 70.5 CPU-seconds on one core (1.76 per
# output second) with a 378MB peak RSS — on the shared ~956MB S2 host
# that working set invites swap pressure and the encode starves.
# Profiled stage split: the x264 encode is ~66% of the CPU, decode +
# filters ~23%, the audio chain ~7%; the caption burn-in is only
# ~3 CPU-s, so the captions stay exactly as they are.
#
# This profile measures 30.4 CPU-s for the same 40s render (0.76 per
# output second, 2.3x cheaper), 39.2 CPU-s for the longest possible
# 58s excerpt, and a 243MB peak RSS; a 60fps source gets 3.9x cheaper
# because the fps cap halves its frames before scaling. Quality:
# SSIM 0.965 against the old profile on a grain-heavy fixture, and a
# dark-gradient banding probe is indistinguishable (0.9993) from a
# superfast/crf21 encode. The output is still a 9:16 Short with the
# same burned captions (the ASS PlayRes is unchanged — libass scales
# proportionally), the same ducking and the same loudnorm target.
# Pinned by tests/test_viral_framing.py — do not retune casually.
_RENDER_WIDTH = 720
_RENDER_HEIGHT = 1280
_RENDER_MAX_FPS = 30
_X264_PRESET = "ultrafast"
_X264_CRF = "23"
_X264_THREADS = "2"


def excerpt_window(
    duration: float,
    peak_position: float | None,
    *,
    full_seconds: float = 58.0,
    window_seconds: float = 40.0,
) -> tuple[float, float]:
    """The (start, end) excerpt for a source of ``duration`` seconds.

    Short sources are used whole. Longer ones contribute one
    ``window_seconds`` window centred on the event-arc peak (or on the
    middle when no arc could be measured), clamped to the source.
    """
    total = max(0.0, float(duration or 0.0))
    if total <= full_seconds:
        return 0.0, total
    window = min(window_seconds, total)
    peak = total / 2.0 if peak_position is None else float(peak_position) * total
    start = min(max(0.0, peak - window / 2.0), total - window)
    return round(start, 3), round(start + window, 3)


def hook_window_seconds(excerpt_seconds: float) -> float:
    """How long her hook may run before the source takes over."""
    return min(7.0, max(1.5, excerpt_seconds * 0.30))


def payoff_window_seconds(excerpt_seconds: float) -> float:
    """How long her payoff may run at the end of the excerpt."""
    return min(9.0, max(1.5, excerpt_seconds * 0.35))


def generate_framing(
    category: str,
    source_title: str,
    channel: str,
    transcript: str,
    scene: str = "",
    taken_titles: set[str] | None = None,
    feedback: list[str] | None = None,
) -> dict[str, str]:
    """Write title, hook, payoff and description for a framed edit.

    Same transport and reply discipline as
    :func:`app.services.viral_remix.generate_editorial` — one JSON
    object, no reasoning in the reply. Returns ``{}`` when the model
    gives nothing usable; the caller treats that as a transient
    editorial failure and skips the candidate (no template framing is
    invented in its place).
    """
    settings = get_settings()
    taken = {title.casefold().strip() for title in (taken_titles or set())}
    prompt = (
        "You write for a viral Shorts channel that re-cuts other creators' clips "
        "WITHOUT talking over them: the source keeps its own voice, and your two "
        "short lines frame it — a hook before the moment and a payoff after it.\n\n"
        f"Source clip title: \"{source_title[:160]}\"\n"
        f"Source channel: {channel[:80]}\n"
        f"Category: {category}\n"
        f"What the clip actually shows (frame analysis - the only source of truth "
        f"for the action): \"{(scene or 'not available')[:700]}\"\n"
        f"What the source's own voice says (transcript): \"{(transcript or '')[:600]}\"\n\n"
        "Reply with the JSON object only - no reasoning, no markdown. "
        "Keys: title, hook, payoff, description.\n"
        "title: 5-11 words in the channel's style, 1-2 emojis, then ' #Shorts'. It must "
        "name the specific thing that happens in this clip and be totally new.\n"
        "hook: ONE sentence, at most 18 words, spoken over the opening seconds while "
        "the source audio is ducked. It teases the moment that is coming, using only "
        "what the frame analysis and transcript prove. Never invent characters, "
        "objects, dialogue or events. No 'you won't believe', no rhetorical filler.\n"
        "payoff: ONE sentence, at most 22 words, spoken over the closing seconds. It "
        "lands the moment — the reaction, the twist, the result — again only from the "
        "frame analysis and transcript. Never close with 'like and subscribe' or any "
        "engagement filler.\n"
        "description: two short sentences about the moment, then a blank line, then a "
        "one-line question starting with an emoji and ending with 'Drop your answer "
        "below!', then a blank line, then ten hashtags starting with #Shorts."
    )
    if taken:
        prompt += (
            "\n\nThese titles are already on the channel and must NOT be reused, echoed "
            "or paraphrased closely:\n"
            + "\n".join(f"- {title}" for title in sorted(taken)[:60])
        )
    if feedback:
        prompt += (
            "\n\nYour previous draft was REJECTED by the footage checker. Fix each of "
            "these problems:\n"
            + "\n".join(f"- {item}" for item in feedback[:10])
            + "\nNever state a colour, item of clothing, time of day, posture, emotion "
            "or eye state that the frame analysis does not record."
        )
    try:
        url = settings.inference_url.rstrip("/") + settings.inference_generation_path
        model = (settings.inference_model or "").strip()
        if not model or model.lower() == "auto":
            model = "llama-3.3-70b-versatile"
        body = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are a short-form video editor. Output one compact JSON "
                        "object with the keys title, hook, payoff and description. "
                        "Output ONLY the JSON object."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.9,
            "max_tokens": 1200,
            "response_format": {"type": "json_object"},
            "stream": False,
            "reasoning_effort": "none",
            "chat_template_kwargs": {"enable_thinking": False},
        }
        response = httpx.post(
            url,
            headers={
                "Authorization": f"Bearer {settings.inference_api_key}",
                "X-API-Key": settings.inference_api_key,
                "Content-Type": "application/json",
            },
            json=body,
            timeout=120,
        )
        response.raise_for_status()
        raw = vr._editorial_text(response.json())
        for payload in reversed(vr._json_objects(str(raw))):
            title = " ".join(str(payload.get("title") or "").split())
            hook = vr._trim_to_sentence(str(payload.get("hook") or ""))
            payoff = vr._trim_to_sentence(str(payload.get("payoff") or ""))
            if not title or title.casefold() in taken or len(title.split()) < 4:
                continue
            if not hook or not payoff:
                continue
            return {
                "title": title,
                "hook": hook,
                "payoff": payoff,
                "description": str(payload.get("description") or "").strip(),
            }
        log.warning("Framing reply had no usable package: %s", str(raw)[:500])
    except Exception as exc:
        log.info("Framing generation unavailable (%s: %s)", type(exc).__name__, str(exc)[:200])
    return {}


def framing_violations(
    *,
    hook: str,
    payoff: str,
    title: str,
    description: str,
    record: dict[str, Any] | None,
    excerpt_seconds: float,
) -> list[vq.Violation]:
    """Gate suite for a framing package.

    Consistency is the production claim-check, unchanged. The
    structural half is framing-shaped (a hook and a payoff are two
    lines, not a 3-7 sentence commentary), but it enforces the same
    disciplines: the 18-word hook cap, no missing half, and an
    estimated-length fit against each line's duck window at the
    production spoken rate.
    """
    violations: list[vq.Violation] = []
    if record is not None:
        violations += vq.check_consistency(
            commentary=f"{hook} {payoff}".strip(),
            title=title,
            description=description,
            record=record,
        )
    if not hook:
        violations.append(vq.Violation(
            "hook_missing", "commentary", "the framing hook is empty",
        ))
    elif len(hook.split()) > _HOOK_WORD_CAP:
        violations.append(vq.Violation(
            "hook_too_long", "commentary",
            f"hook has {len(hook.split())} words; the cap is {_HOOK_WORD_CAP}",
        ))
    if not payoff:
        violations.append(vq.Violation(
            "payoff_missing", "commentary", "the framing payoff is empty",
        ))
    sentences = vq.split_sentences(f"{hook} {payoff}".strip())
    if len(sentences) > 3:
        violations.append(vq.Violation(
            "too_many_sentences", "commentary",
            f"framing has {len(sentences)} sentences; a hook and a payoff only",
        ))
    hook_estimate = len(hook.split()) / _WORDS_PER_SECOND if hook else 0.0
    if hook_estimate > hook_window_seconds(excerpt_seconds) + 0.35:
        violations.append(vq.Violation(
            "hook_overruns_window", "commentary",
            f"hook needs ~{hook_estimate:.1f}s at {_WORDS_PER_SECOND} wps; "
            f"its duck window is {hook_window_seconds(excerpt_seconds):.1f}s",
        ))
    payoff_estimate = len(payoff.split()) / _WORDS_PER_SECOND if payoff else 0.0
    if payoff_estimate > payoff_window_seconds(excerpt_seconds) + 0.35:
        violations.append(vq.Violation(
            "payoff_overruns_window", "commentary",
            f"payoff needs ~{payoff_estimate:.1f}s at {_WORDS_PER_SECOND} wps; "
            f"its duck window is {payoff_window_seconds(excerpt_seconds):.1f}s",
        ))
    return violations


def framed_cues(
    speech_cues: Any,
    *,
    excerpt_start: float,
    excerpt_seconds: float,
    hook: str,
    hook_seconds: float,
    payoff: str,
    payoff_seconds: float,
) -> list[dict[str, Any]]:
    """Caption cues for a framed edit, on the excerpt's timeline.

    The source's own speech keeps its measured Whisper timings
    (shifted into the excerpt and clipped to it — a cue that falls
    outside the excerpt is dropped, never stretched). Her hook and
    payoff cues sit at the two ends, where she actually speaks.
    Subtitles are on the whole video, always.
    """
    cues: list[dict[str, Any]] = []
    for cue in speech_cues or ():
        start = float(cue.get("start") or 0.0) - excerpt_start
        end = float(cue.get("end") or 0.0) - excerpt_start
        if end <= 0.0 or start >= excerpt_seconds:
            continue
        text = str(cue.get("text") or "").strip()
        if not text:
            continue
        cues.append({
            "start": round(max(0.0, start), 2),
            "end": round(min(excerpt_seconds, end), 2),
            "text": text,
            "speech": True,
        })
    if hook and hook_seconds > 0:
        cues.append({
            "start": 0.0,
            "end": round(min(hook_seconds, excerpt_seconds), 2),
            "text": hook,
        })
    if payoff and payoff_seconds > 0:
        cues.append({
            "start": round(max(0.0, excerpt_seconds - payoff_seconds), 2),
            "end": round(excerpt_seconds, 2),
            "text": payoff,
        })
    cues.sort(key=lambda item: (item["start"], item["end"]))
    return vr._sanitize_cues(cues)


def render_framed(
    source_path: Path,
    output_path: Path,
    *,
    excerpt_start: float,
    excerpt_seconds: float,
    hook_audio: Path,
    hook_seconds: float,
    payoff_audio: Path,
    payoff_seconds: float,
    cues: list[dict[str, Any]],
    category: str,
    music_bed_path: Path | None = None,
) -> Path:
    """Assemble the framed edit.

    Video: the excerpt window, channel format + burned captions via
    the production filter, encoded at the render-fit profile above
    (720x1280, TASK-VYR-021 — the framed path runs on the fleet's
    smallest host; the commentary path keeps the 1080x1920 default).
    Audio: the source at full level except
    under her two lines (ducked to 0.22, the production duck level),
    her lines placed at the two ends, and the BGM bed at full level
    in the stretches where nobody speaks and ducked under her lines.
    The mix is loudnormed to the production target.
    """
    settings = get_settings()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    ass_path = vr._write_ass(cues, output_path.with_suffix(".ass"))
    video_chain = vr._base_video_filter(
        cues,
        category,
        ass_path,
        width=_RENDER_WIDTH,
        height=_RENDER_HEIGHT,
        max_fps=_RENDER_MAX_FPS,
    )
    end = excerpt_start + excerpt_seconds
    duck_hook_end = min(excerpt_seconds, hook_seconds + 0.15)
    duck_payoff_start = max(0.0, excerpt_seconds - payoff_seconds - 0.15)
    payoff_delay_ms = int(max(0.0, excerpt_seconds - payoff_seconds) * 1000)

    filters = [
        f"[0:v]trim=start={excerpt_start:.3f}:end={end:.3f},"
        f"setpts=PTS-STARTPTS,{video_chain}[v]",
        f"[0:a]atrim=start={excerpt_start:.3f}:end={end:.3f},"
        "asetpts=PTS-STARTPTS,"
        f"volume=0.22:enable='between(t,0,{duck_hook_end:.3f})',"
        f"volume=0.22:enable='between(t,{duck_payoff_start:.3f},{excerpt_seconds:.3f})'"
        "[src]",
        f"[1:a]apad=whole_dur={excerpt_seconds:.3f}[hk]",
        f"[2:a]adelay={payoff_delay_ms}|{payoff_delay_ms}[po]",
        "[hk][po]amix=inputs=2:duration=first:dropout_transition=0[nar]",
    ]
    if music_bed_path is not None:
        filters.append(
            "[3:a]volume=0.12,"
            f"volume=0.05:enable='between(t,0,{duck_hook_end:.3f})',"
            f"volume=0.05:enable='between(t,{duck_payoff_start:.3f},{excerpt_seconds:.3f})'"
            "[bed]"
        )
        filters.append(
            "[src][nar][bed]amix=inputs=3:duration=first:dropout_transition=2,"
            "loudnorm=I=-14:LRA=9:TP=-1.5[a]"
        )
    else:
        filters.append(
            "[src][nar]amix=inputs=2:duration=first:dropout_transition=2,"
            "loudnorm=I=-14:LRA=9:TP=-1.5[a]"
        )
    cmd = [
        settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-i", str(source_path),
        "-i", str(hook_audio),
        "-i", str(payoff_audio),
    ]
    if music_bed_path is not None:
        cmd += ["-i", str(music_bed_path)]
    cmd += [
        "-filter_complex", ";".join(filters),
        "-map", "[v]", "-map", "[a]",
        "-c:v", "libx264", "-preset", _X264_PRESET, "-crf", _X264_CRF,
        "-pix_fmt", "yuv420p",
        "-threads", _X264_THREADS,
        "-c:a", "aac", "-b:a", "192k",
        "-movflags", "+faststart",
        "-t", f"{excerpt_seconds:.2f}",
        str(output_path),
    ]
    vr._run(cmd, timeout=2400)
    return output_path


def _cut_excerpt(source_path: Path, destination: Path, start: float, seconds: float) -> Path:
    """Cut the excerpt window to its own file for vision analysis."""
    settings = get_settings()
    destination.parent.mkdir(parents=True, exist_ok=True)
    vr._run([
        settings.ffmpeg_bin, "-hide_banner", "-nostdin", "-y",
        "-ss", f"{start:.3f}", "-i", str(source_path),
        "-t", f"{seconds:.3f}",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "18",
        "-an", str(destination),
    ])
    return destination


def produce_framed_short(
    candidate: Any,
    db: Session,
    *,
    publish: bool = True,
    hold_for_review: bool = False,
) -> dict[str, Any]:
    """Audition -> excerpt -> frame -> register -> publish-job for one
    voiced candidate. Mirrors :func:`app.services.viral_remix.produce_viral_short`'s
    persistence and result shape, with ``edit_mode="framed"``.

    ``hold_for_review`` has the same meaning as in the commentary
    path: the publish job is created ``pending_approval`` with no
    approval timestamp, so nothing can upload it before the owner
    reviews it.
    """
    settings = get_settings()
    category = normalise_label(str(getattr(candidate, "category", "") or "VIRAL"))
    settings.prepare_directories()
    settings.render_dir.mkdir(parents=True, exist_ok=True)
    settings.media_dir.mkdir(parents=True, exist_ok=True)

    # 1. Audition: this mode exists ONLY for voiced sources, and only
    # when the speech comes with timings we can subtitle. Anything
    # else is a mis-route or an unsubtitlable clip — fail closed.
    audio_dir = settings.media_dir / "viral_audio_probe"
    audio_path = vr.download_audio_only(candidate.video_id, audio_dir)
    if audio_path is None:
        return {"status": "SKIPPED", "reason": "audio_unavailable", "video_id": candidate.video_id}
    speech = vr.detect_speech(audio_path)
    if not speech.has_speech:
        return {"status": "SKIPPED", "reason": "source_has_no_narration", "video_id": candidate.video_id}
    if not speech.cues:
        return {"status": "SKIPPED", "reason": "no_transcript", "video_id": candidate.video_id}

    # 2. Full download, probe, excerpt window around the event peak.
    source_path = vr.download_source_video(candidate.video_id, settings.media_dir / "viral_sources")
    probe = vr.probe_media(source_path)
    duration = max(6.0, probe.duration or float(candidate.duration or 20.0))
    project_key = f"framed-{candidate.video_id}-{uuid.uuid4().hex[:6]}"

    gates_on = bool(getattr(settings, "viral_quality_gates_enabled", True))
    full_arc = None
    if gates_on:
        full_arc = vq.measure_event_arc(source_path, duration, ffmpeg_bin=settings.ffmpeg_bin)
    excerpt_start, excerpt_end = excerpt_window(
        duration,
        full_arc.peak_position if full_arc is not None else None,
        full_seconds=float(getattr(settings, "viral_max_source_seconds", 58.0)),
    )
    excerpt_seconds = round(excerpt_end - excerpt_start, 3)
    excerpt_path = _cut_excerpt(
        source_path,
        settings.media_dir / "viral_sources" / f"{project_key}-excerpt.mp4",
        excerpt_start,
        excerpt_seconds,
    )

    record: dict[str, Any] | None = None
    arc_info: dict[str, Any] | None = None
    if gates_on:
        arc = vq.measure_event_arc(excerpt_path, excerpt_seconds, ffmpeg_bin=settings.ffmpeg_bin)
        arc_ok, arc_reason = vq.arc_gate(arc)
        if arc is not None:
            arc_info = {
                "mean_change": arc.mean_change,
                "max_change": arc.max_change,
                "static_ratio": arc.static_ratio,
                "peak_position": arc.peak_position,
                "verdict": arc_reason,
            }
        if not arc_ok:
            log.info("Skipping %s: static scene (arc %s)", candidate.video_id, arc_info)
            return {
                "status": "SKIPPED", "reason": "static_scene",
                "video_id": candidate.video_id, "event_arc": arc_info,
            }
        record = analyze_scene(excerpt_path, excerpt_seconds)
        if record is None:
            return {"status": "SKIPPED", "reason": "vision_unavailable", "video_id": candidate.video_id}
        if record.get("static"):
            return {
                "status": "SKIPPED", "reason": "static_scene",
                "video_id": candidate.video_id, "event_arc": arc_info,
            }
        scene = scene_text(record)
    else:
        from app.services.scene_analysis import describe_scene

        scene = describe_scene(excerpt_path, excerpt_seconds)

    # 3. Framing editorial under the gate suite (same fail-closed
    # discipline as the commentary path: feedback retries, the
    # deterministic hook repair, then the candidate is skipped).
    taken_titles = vr.existing_upload_titles(db)
    hook = ""
    payoff = ""
    framing: dict[str, str] = {}
    violations: list[vq.Violation] = []
    gate_attempts = 0
    hook_repaired = False
    feedback: list[str] | None = None
    attempts_allowed = 3 if (gates_on and record is not None) else 1
    for attempt in range(attempts_allowed):
        gate_attempts = attempt + 1
        framing = generate_framing(
            category,
            str(getattr(candidate, "title", "")),
            str(getattr(candidate, "channel", "")),
            speech.text,
            scene=scene,
            taken_titles=taken_titles,
            feedback=feedback,
        )
        if not framing:
            return {"status": "SKIPPED", "reason": "editorial_unavailable", "video_id": candidate.video_id}
        hook = vq.sanitize_spoken_text(framing.get("hook") or "")
        payoff = vq.sanitize_spoken_text(framing.get("payoff") or "")
        if not (gates_on and record is not None):
            break
        violations = framing_violations(
            hook=hook,
            payoff=payoff,
            title=str(framing.get("title") or ""),
            description=str(framing.get("description") or ""),
            record=record,
            excerpt_seconds=excerpt_seconds,
        )
        if not violations:
            break
        if any(violation.kind == "hook_too_long" for violation in violations):
            repaired_hook = vq.repair_hook_length(hook)
            if repaired_hook != hook and not framing_violations(
                hook=repaired_hook,
                payoff=payoff,
                title=str(framing.get("title") or ""),
                description=str(framing.get("description") or ""),
                record=record,
                excerpt_seconds=excerpt_seconds,
            ):
                hook = repaired_hook
                hook_repaired = True
                violations = []
                break
        feedback = [violation.detail for violation in violations]
    if gates_on and record is not None and violations:
        return {
            "status": "SKIPPED", "reason": "script_unverifiable",
            "video_id": candidate.video_id,
            "violations": [violation.kind for violation in violations],
        }
    if not hook or not payoff:
        return {"status": "SKIPPED", "reason": "editorial_unavailable", "video_id": candidate.video_id}

    # 4. Her two lines, synthesised and MEASURED against their windows.
    voice = vr.VOICE_BY_CATEGORY.get(category, vr.DEFAULT_VOICE)
    voice_dir = settings.media_dir / "voiceovers"
    hook_audio, _hook_cues = vr.synthesize_commentary(
        hook, voice, voice_dir / f"{project_key}-hook.mp3"
    )
    payoff_audio, _payoff_cues = vr.synthesize_commentary(
        payoff, voice, voice_dir / f"{project_key}-payoff.mp3"
    )
    hook_seconds = float(vr.probe_media(hook_audio).duration or 0.0)
    payoff_seconds = float(vr.probe_media(payoff_audio).duration or 0.0)
    if (
        hook_seconds <= 0
        or payoff_seconds <= 0
        or hook_seconds > hook_window_seconds(excerpt_seconds) + 0.35
        or payoff_seconds > payoff_window_seconds(excerpt_seconds) + 0.35
    ):
        log.info(
            "Skipping %s: framing lines do not fit (hook %.2fs of %.2fs, payoff %.2fs of %.2fs)",
            candidate.video_id, hook_seconds, hook_window_seconds(excerpt_seconds),
            payoff_seconds, payoff_window_seconds(excerpt_seconds),
        )
        return {
            "status": "SKIPPED", "reason": "script_length_misfit",
            "video_id": candidate.video_id,
        }

    # 5. Captions (always), BGM bed (mandatory), render.
    cues = framed_cues(
        speech.cues,
        excerpt_start=excerpt_start,
        excerpt_seconds=excerpt_seconds,
        hook=hook,
        hook_seconds=hook_seconds,
        payoff=payoff,
        payoff_seconds=payoff_seconds,
    )
    if not cues:
        raise RuntimeError("caption generation produced no cues")
    bed_path: Path | None = None
    bgm_source = ""
    if bool(getattr(settings, "viral_music_bed_enabled", True)):
        from app.services.viral_bgm import prepare_music_bed

        bed_path, bgm_source = prepare_music_bed(
            voice_dir / f"{project_key}-bed.wav",
            excerpt_seconds,
            category=category,
        )
    render_path = settings.render_dir / f"{project_key}.mp4"
    render_framed(
        source_path,
        render_path,
        excerpt_start=excerpt_start,
        excerpt_seconds=excerpt_seconds,
        hook_audio=hook_audio,
        hook_seconds=hook_seconds,
        payoff_audio=payoff_audio,
        payoff_seconds=payoff_seconds,
        cues=cues,
        category=category,
        music_bed_path=bed_path,
    )

    thumbnail_path = settings.render_dir / f"{project_key}-thumb.jpg"
    try:
        from app.services.thumbnail_designer import generate_genre_thumbnail

        generate_genre_thumbnail(
            video_path=source_path,
            output_path=thumbnail_path,
            headline=str(candidate.hook or "WAIT FOR IT"),
            category=category,
        )
    except Exception as exc:  # thumbnail is a nice-to-have, never fatal
        log.warning("Thumbnail generation failed: %s", exc)
        thumbnail_path = Path("")

    editorial = {
        "title": str(framing.get("title") or ""),
        "description": str(framing.get("description") or ""),
        "commentary": f"{hook} {payoff}".strip(),
    }
    meta = vr.build_metadata(
        candidate, speech, hook, category, editorial, taken_titles, record=record
    )
    try:
        from app.services.monetization import monetization_footer

        _footer = monetization_footer()
        if _footer:
            meta["description"] = f"{meta['description']}\n\n{_footer}"[:4800]
    except Exception as exc:  # monetization must never break production
        log.warning("Monetization footer skipped: %s", exc)

    # 6. Persist rights record + render + publish job (mirrors the
    # commentary path's block, including its rights bookkeeping).
    reuse_licensed = bool(str(getattr(candidate, "license", "")).strip()) and (
        "creative commons" in str(candidate.license).casefold()
    )
    if reuse_licensed:
        platform = "youtube_creative_commons"
        license_name = str(candidate.license)[:190]
        permission_reference = (
            f"https://www.youtube.com/watch?v={candidate.video_id} - licence: {candidate.license}"
        )[:2000]
        notes = "Reuse licence verified from the source metadata."
    else:
        platform = "youtube_transformative"
        license_name = "Transformative commentary - original creator credited (operator policy)"
        permission_reference = (
            f"https://www.youtube.com/watch?v={candidate.video_id} - operator-attested "
            "transformative commentary: original audio retained or new commentary added, "
            "subtitles and attribution on every upload"
        )[:2000]
        notes = "Operator-selected transformative commentary policy; original creator credited in the description."
    source = Source(
        title=f"Source: {candidate.title[:240]}",
        source_url=f"https://www.youtube.com/watch?v={candidate.video_id}",
        platform=platform,
        creator=str(candidate.channel or "")[:280],
        license_name=license_name,
        permission_reference=permission_reference,
        repeat_use_allowed=True,
        repeat_use_reviewed_at=utcnow(),
        repeat_use_review_notes=(
            "Operator-attested transformative-commentary policy; no repeat-use "
            "review required."
        ),
        rights_verified=True,
        status="approved",
        notes=notes,
    )
    db.add(source)
    db.flush()
    asset = Asset(
        source_id=source.id,
        title=str(candidate.title)[:280],
        file_path=str(source_path),
        duration_seconds=float(duration),
        width=probe.width,
        height=probe.height,
        rights_verified=True,
    )
    db.add(asset)
    db.flush()

    project = VideoProject(
        project_key=project_key,
        topic=f"Framed: {str(candidate.title)[:120]}",
        video_format="shorts",
        target_seconds=int(round(excerpt_seconds)),
        audience="viral shorts audience",
        tone="framing commentary - source voice kept",
        scene_count=1,
        confirm_pexels_license=False,
        confirm_pexels_repeat_use=False,
        use_voiceover=True,
        status="completed",
        primary_asset_id=asset.id,
        asset_ids_json=json.dumps([asset.id]),
        thumbnail_path=str(thumbnail_path) if thumbnail_path else "",
        completed_at=utcnow(),
        attempts=1,
    )
    db.add(project)
    db.flush()

    render_job = RenderJob(
        asset_id=asset.id,
        preset="shorts",
        status="completed",
        output_path=str(render_path),
        attempts=1,
        project_id=None,
        options_json=json.dumps({
            "montage_asset_ids": [asset.id],
            "source_video_id": candidate.video_id,
            "source_views": int(getattr(candidate, "view_count", 0) or 0),
            "edit_mode": "framed",
            "event_arc": arc_info,
            "quality_gate_attempts": gate_attempts,
            "hook_repaired": hook_repaired,
            "hold_for_review": hold_for_review,
            "bgm_source": bgm_source,
            "excerpt": {"start": excerpt_start, "seconds": excerpt_seconds},
            "series": category,
        }),
        completed_at=utcnow(),
    )
    db.add(render_job)
    db.flush()
    project.render_job_id = render_job.id

    publish_job = None
    if publish:
        publish_job = PublishJob(
            asset_id=asset.id,
            render_job_id=render_job.id,
            title=meta["title"],
            description=meta["description"],
            tags_json=json.dumps(meta["tags"]),
            privacy_status=str(getattr(settings, "autonomous_publish_privacy", "unlisted")),
            status="pending_approval" if hold_for_review else "queued",
            approved_at=None if hold_for_review else utcnow(),
            thumbnail_path=str(thumbnail_path) if thumbnail_path else "",
            category_id=str(meta.get("category_id") or ""),
        )
        db.add(publish_job)
    db.commit()

    result = {
        "status": "QUEUED_FOR_PUBLISH" if publish else "RENDERED",
        "project_key": project_key,
        "project_id": project.id,
        "render_job_id": render_job.id,
        "publish_job_id": publish_job.id if publish_job else None,
        "edit_mode": "framed",
        "source_video_id": candidate.video_id,
        "source_views": int(getattr(candidate, "view_count", 0) or 0),
        "source_license": candidate.license,
        "title": meta["title"],
        "duration": round(excerpt_seconds, 1),
        "narration": f"{hook} {payoff}".strip()[:280],
        "render": str(render_path),
        "event_arc": arc_info,
        "quality_gate_attempts": gate_attempts,
        "hook_repaired": hook_repaired,
        "hold_for_review": hold_for_review,
        "bgm_source": bgm_source,
        "excerpt": {"start": excerpt_start, "seconds": excerpt_seconds},
        "series": category,
    }
    if publish and getattr(settings, "crosspost_export_enabled", True):
        try:
            from app.services.crosspost_export import write_crosspost_bundle

            bundle = write_crosspost_bundle(
                render_path,
                title=meta["title"],
                description=meta["description"],
                tags=meta["tags"],
                category=category,
                video_key=project_key,
            )
            result["crosspost_bundle"] = bundle["bundle"]
        except Exception as exc:  # packaging must never break production
            log.warning("Cross-post bundle skipped: %s", exc)
    log.info("Framed short ready: %s", result)
    return result
