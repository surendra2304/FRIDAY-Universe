"""TASK-VYR-044: machine-QA gates over the held-render pool.

Runs the four gates named on the board record — caption-track count,
BGM presence, watermark, loudness — over one finished render and
returns a per-gate pass/fail verdict with the measured evidence. The
module is the repo-side half of VYR-044; the live leg runs it against
the held renders on VyralX-Server (``renders/framed-*.mp4``) and files
the per-render table in ``docs/collaboration/TASK-VYR-044-HELD-RENDER-QA.md``.

Behaviour pinned here:

* loudness reuses :func:`app.services.media_quality.analyze_media_signals`
  (ffmpeg ebur128): pass iff integrated loudness is in [-24, -10] LUFS
  and true peak is <= -1.0 dBFS — the same constants as the VYR-081
  series gate and the media-quality thresholds. ``clipped_samples``
  is None on the deployed scanner (VYR-060 evidence); it is carried
  as None, never invented, and never a pass/fail input;
* BGM presence is measured on the finished render, not read off the
  manifest (861 records a real ``bgm_source`` yet the watch heard no
  audible BGM): ffmpeg volumedetect RMS per segment, split into
  voiced stretches (ASS dialogue timings, hook/title layers
  excluded — see ``HOOK_STYLE_MARKERS``) and voiceless gaps
  (>= 0.5 s). Pass iff every voiceless gap measures above the
  -45 dBFS floor AND no silence interval from the loudness scan
  falls in a voiceless stretch — a continuous music bed keeps
  every gap above the floor, so a silent gap is a bed dropout.
  When the speech union tiles the whole render there is no gap
  to measure; then any silence interval is itself the absence
  evidence, and with neither a gap nor a silence interval the
  gate is unmeasured (the bed cannot be separated from the voice
  by this method);
* watermark is measured honestly: the ffprobe format-comment marker
  ``vyralx-provenance:<record_id>`` (the visible layer
  ``watermark_video_frame`` writes) plus an LSB extraction attempt on
  sampled frames (``provenance_watermark.extract_payload``). The LSB
  payload does not survive re-encoding, so it is reported, never
  required; pass iff the comment marker is present. No produce-path
  caller sets that marker today, so the column is expected absent —
  an absent column is a table result plus follow-on work, not a
  skipped column;
* caption-track count reuses the VYR-045 gate
  (:func:`app.services.viral_quality.caption_track_gate`) over the
  deployed vision sampler
  (:func:`app.services.scene_analysis.sample_render_caption_detections`,
  lazy import so unit tests never need the vision stack). A sampler
  that returns None reports ``caption_gate_unmeasured`` — fail-closed,
  never a pass. The sampler paces vision calls >= 65 s apart and the
  loop's daily vision budget is 180k tokens, so a dense 11-render
  sample does not fit one run; the caller chooses which renders get
  the vision measurement and the rest stay unmeasured with the reason
  named;
* the ASS file next to a render is corroboration, not the gate: the
  .ass is what ffmpeg burned in, so overlapping dialogue events in
  it are the authored caption tracks. ``ass_caption_track_count``
  counts distinct (style, text) tracks active at once; the vision
  verdict stays the gate where measured;
* an unavailable measurement is reported unavailable, never as
  passing — every gate returns ``passed`` False with a reason when
  its measurement failed, and the overall verdict is False.
"""

from __future__ import annotations

import json
import logging
import re
import subprocess
from pathlib import Path
from typing import Any

from app.services import media_quality
from app.services import viral_quality

log = logging.getLogger(__name__)

LOUDNESS_MIN_LUFS = -24.0
LOUDNESS_MAX_LUFS = -10.0
TRUE_PEAK_MAX_DBFS = -1.0
BGM_FLOOR_DBFS = -45.0
BGM_VOICELESS_MIN_SECONDS = 0.5
WATERMARK_MARKER_PREFIX = "vyralx-provenance:"

_ASS_TIMESTAMP_RE = re.compile(
    r"^(\d+):(\d{2}):(\d{2})\.(\d{2})$"
)
_ASS_OVERRIDE_RE = re.compile(r"\{[^}]*\}")
# Hook/title layers are not speech: in the held pool the hook layer
# is the AntonFraming style — exactly 2 events per render, durations
# up to 13.46 s against a speech median of ~1–2 s (measured live on
# VyralX-Server 2026-11-25). The VYR-032 record calls it "a top hook
# layer". Speech-track counting and voiced segmentation use speech
# events only, so the hook never inflates either.
HOOK_STYLE_MARKERS = ("framing", "hook", "title")
_MEAN_VOLUME_RE = re.compile(
    r"mean_volume:\s*(-?[\d.]+)\s*dB", re.IGNORECASE
)
_MAX_VOLUME_RE = re.compile(
    r"max_volume:\s*(-?[\d.]+)\s*dB", re.IGNORECASE
)


def parse_ass_timestamp(text: str) -> float | None:
    """Parse an ASS ``H:MM:SS.cc`` timestamp to seconds, or None."""
    match = _ASS_TIMESTAMP_RE.match((text or "").strip())
    if not match:
        return None
    hours, minutes, seconds, centis = (int(g) for g in match.groups())
    return hours * 3600 + minutes * 60 + seconds + centis / 100.0


def parse_ass_dialogue(ass_path: Path | str) -> tuple[list[dict[str, Any]], int]:
    """Parse ``Dialogue:`` events from an ASS file.

    Returns ``(events, malformed)`` where each event is
    ``{"start": float, "end": float, "style": str, "text": str}``.
    Malformed lines are skipped and counted, never invented.
    """
    events: list[dict[str, Any]] = []
    malformed = 0
    try:
        lines = Path(ass_path).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return [], 0
    for line in lines:
        if not line.startswith("Dialogue:"):
            continue
        fields = line[len("Dialogue:"):].strip().split(",", 9)
        if len(fields) < 10:
            malformed += 1
            continue
        start = parse_ass_timestamp(fields[1])
        end = parse_ass_timestamp(fields[2])
        if start is None or end is None or end <= start:
            malformed += 1
            continue
        events.append({
            "start": start,
            "end": end,
            "style": fields[3].strip(),
            # Override tags ({\\c&H...&}, {\\fscx115...}) are formatting,
            # not visible text — strip them so track identity keys on
            # the words the viewer sees.
            "text": _ASS_OVERRIDE_RE.sub("", fields[9]).strip(),
        })
    events.sort(key=lambda e: (e["start"], e["end"], e["style"], e["text"]))
    return events, malformed


def speech_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Dialogue events minus hook/title layers (see HOOK_STYLE_MARKERS)."""
    return [e for e in events
            if not any(m in e["style"].lower() for m in HOOK_STYLE_MARKERS)]


def ass_caption_track_count(events: list[dict[str, Any]]) -> int:
    """Max speech events active at once.

    A single authored track tiles end-to-start, so overlapping
    events mean a second track was authored on top (the 823/841/861
    class). Events are counted, not distinct texts: two tracks
    carrying the same words ~1 s out of sync are two tracks even
    though the words match.
    """
    if not events:
        return 0
    points = sorted({e["start"] for e in events} | {e["end"] for e in events})
    worst = 0
    for a, b in zip(points, points[1:]):
        if b <= a:
            continue
        mid = (a + b) / 2.0
        active = [e for e in events if e["start"] <= mid < e["end"]]
        worst = max(worst, len(active))
    return worst


def voiced_segments(
    events: list[dict[str, Any]], duration: float
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    """Split a render into voiced stretches and voiceless gaps.

    Voiced stretches are the union of the ASS dialogue intervals;
    voiceless gaps are the stretches between them (and the head/tail)
    lasting at least ``BGM_VOICELESS_MIN_SECONDS``. Both are clipped
    to ``[0, duration]``.
    """
    voiced: list[tuple[float, float]] = []
    for event in events:
        start = max(0.0, float(event["start"]))
        end = min(float(duration), float(event["end"]))
        if end <= start:
            continue
        if voiced and start <= voiced[-1][1]:
            voiced[-1] = (voiced[-1][0], max(voiced[-1][1], end))
        else:
            voiced.append((start, end))
    voiceless: list[tuple[float, float]] = []
    cursor = 0.0
    for start, end in voiced:
        if start - cursor >= BGM_VOICELESS_MIN_SECONDS:
            voiceless.append((cursor, start))
        cursor = max(cursor, end)
    if float(duration) - cursor >= BGM_VOICELESS_MIN_SECONDS:
        voiceless.append((cursor, float(duration)))
    return voiced, voiceless


def measure_segment_rms_dbfs(
    render_path: Path | str,
    start: float,
    end: float,
    *,
    ffmpeg_bin: str = "ffmpeg",
    timeout_seconds: int = 120,
) -> float | None:
    """Mean volume (dBFS) of one window via ffmpeg volumedetect.

    Returns None when the measurement itself failed (no ffmpeg, bad
    window, ffmpeg exit) — the caller reports unmeasured, never 0.
    """
    if end <= start:
        return None
    command = [
        str(ffmpeg_bin), "-hide_banner", "-nostats", "-v", "info",
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(render_path),
        "-map", "0:a:0", "-af", "volumedetect", "-f", "null", "-",
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=max(1, int(timeout_seconds)), check=False,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    match = _MEAN_VOLUME_RE.search(result.stderr or "")
    if not match:
        return None
    try:
        value = float(match.group(1))
    except ValueError:
        return None
    return value if value == value else None  # NaN guard


def _mean(values: list[float]) -> float | None:
    if not values:
        return None
    return sum(values) / len(values)


def loudness_gate(signals: dict[str, Any]) -> tuple[bool, str, dict[str, Any]]:
    """Judge an :func:`analyze_media_signals` result on loudness.

    Returns ``(passed, reason, detail)``. ``clipped_samples`` rides
    along as context only — None on the deployed scanner, never a
    pass/fail input.
    """
    detail: dict[str, Any] = {
        "integrated_loudness_lufs": None,
        "true_peak_dbfs": None,
        "clipped_samples": None,
    }
    if not isinstance(signals, dict) or signals.get("status") != "analyzed":
        reason = "loudness_unmeasured"
        if isinstance(signals, dict) and signals.get("error_type"):
            reason = f"loudness_unmeasured:{signals['error_type']}"
        return False, reason, detail
    metrics = signals.get("audio_metrics") or {}
    loudness = metrics.get("integrated_loudness_lufs")
    peak = metrics.get("true_peak_dbfs")
    detail["integrated_loudness_lufs"] = loudness
    detail["true_peak_dbfs"] = peak
    detail["clipped_samples"] = metrics.get("clipped_samples")
    if loudness is None or peak is None:
        return False, "loudness_unmeasured", detail
    if not (LOUDNESS_MIN_LUFS <= loudness <= LOUDNESS_MAX_LUFS):
        return False, "loudness_out_of_range", detail
    if peak > TRUE_PEAK_MAX_DBFS:
        return False, "true_peak_too_high", detail
    return True, "loudness_ok", detail


def bgm_gate(
    render_path: Path | str,
    events: list[dict[str, Any]],
    duration: float,
    *,
    audio_stream_count: int = 1,
    silence_intervals: list[dict[str, Any]] | None = None,
    measure=None,
    ffmpeg_bin: str = "ffmpeg",
) -> tuple[bool, str, dict[str, Any]]:
    """Judge BGM presence from voiced/voiceless RMS (VYR-047 method).

    ``measure`` is a seam for tests; it defaults to
    :func:`measure_segment_rms_dbfs`. Pass iff every voiceless gap
    measures above the -45 dBFS floor AND no silence interval
    (audio below -45 dB for >= 1.0 s, from the loudness scan) falls
    in a voiceless stretch: a continuous music bed keeps every gap
    above the floor, so a silent gap is a bed dropout. When the
    speech union tiles the whole render there is no voiceless gap
    to measure; then any silence interval is itself the evidence
    (bed absent in that stretch), and with neither a gap nor a
    silence interval the gate is unmeasured — the bed cannot be
    separated from the voice by this method.
    """
    detail: dict[str, Any] = {
        "voiced_mean_dbfs": None,
        "voiceless_mean_dbfs": None,
        "voiced_segments": 0,
        "voiceless_segments": 0,
        "silence_intervals": silence_intervals or [],
        "silent_voiceless_gaps": [],
        "bgm_source": None,
    }
    try:
        has_audio = int(audio_stream_count) > 0
    except (TypeError, ValueError):
        has_audio = False
    if not has_audio:
        return False, "no_audio_stream", detail
    voiced, voiceless = voiced_segments(events, duration)
    silence = [
        (float(s.get("start_seconds", -1)), float(s.get("end_seconds", -1)))
        for s in (silence_intervals or [])
        if isinstance(s, dict)
    ]

    def _overlaps_silence(start: float, end: float) -> bool:
        return any(s_start < end and start < s_end
                   for s_start, s_end in silence)

    if not voiceless:
        # No gap to measure: a silence interval is a voiceless
        # stretch with no audible bed; without one, unmeasured.
        if silence:
            detail["silent_voiceless_gaps"] = [
                {"start_seconds": s, "end_seconds": e} for s, e in silence
            ]
            return False, "bgm_absent_voiceless", detail
        return False, "bgm_unmeasured", detail
    measure_fn = measure or measure_segment_rms_dbfs
    voiced_rms = [
        value for (start, end) in voiced
        if (value := measure_fn(render_path, start, end,
                                ffmpeg_bin=ffmpeg_bin)) is not None
    ]
    gap_results = []
    for (start, end) in voiceless:
        rms = measure_fn(render_path, start, end, ffmpeg_bin=ffmpeg_bin)
        gap_results.append({
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "rms_dbfs": rms,
            "silent": _overlaps_silence(start, end),
        })
    detail["voiced_segments"] = len(voiced)
    detail["voiceless_segments"] = len(voiceless)
    detail["voiced_mean_dbfs"] = _mean(voiced_rms)
    detail["voiceless_mean_dbfs"] = _mean(
        [g["rms_dbfs"] for g in gap_results if g["rms_dbfs"] is not None])
    detail["voiceless_gaps"] = gap_results
    detail["silent_voiceless_gaps"] = [
        g for g in gap_results if g["silent"] or g["rms_dbfs"] is None
        or g["rms_dbfs"] <= BGM_FLOOR_DBFS
    ]
    if detail["voiced_mean_dbfs"] is None or detail["voiceless_mean_dbfs"] is None:
        return False, "bgm_unmeasured", detail
    if detail["silent_voiceless_gaps"]:
        return False, "bgm_absent_voiceless", detail
    if detail["voiced_mean_dbfs"] <= BGM_FLOOR_DBFS:
        return False, "bgm_absent_voiced", detail
    return True, "bgm_present", detail


def ffprobe_format_tags(
    render_path: Path | str,
    *,
    ffprobe_bin: str = "ffprobe",
    timeout_seconds: int = 60,
) -> dict[str, str] | None:
    """Format tags of a render via ffprobe JSON, or None on failure."""
    command = [
        str(ffprobe_bin), "-v", "error", "-show_format",
        "-of", "json", str(render_path),
    ]
    try:
        result = subprocess.run(
            command, capture_output=True, text=True,
            timeout=max(1, int(timeout_seconds)), check=False,
        )
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None
    if result.returncode != 0:
        return None
    try:
        data = json.loads(result.stdout or "{}")
    except ValueError:
        return None
    tags = (data.get("format") or {}).get("tags") or {}
    return {str(k): str(v) for k, v in tags.items()}


def watermark_gate(
    render_path: Path | str,
    *,
    sample_times: list[float] | None = None,
    ffprobe=None,
    ffprobe_bin: str = "ffprobe",
    extract_frame=None,
    extract_payload=None,
    ffmpeg_bin: str = "ffmpeg",
) -> tuple[bool, str, dict[str, Any]]:
    """Judge watermark presence: ffprobe comment marker + LSB attempt.

    ``ffprobe`` / ``extract_frame`` / ``extract_payload`` are seams
    for tests; they default to ffprobe JSON tags, an ffmpeg frame
    grab, and :func:`provenance_watermark.extract_payload` (lazy
    import, so unit tests never need PIL). Pass iff the
    ``vyralx-provenance:`` comment marker is present. The LSB
    payload is reported, never required — it does not survive
    re-encoding.
    """
    detail: dict[str, Any] = {
        "marker_present": False,
        "marker": None,
        "lsb_payload_present": None,
        "lsb_frames_checked": 0,
    }
    probe = ffprobe or (
        lambda p: ffprobe_format_tags(p, ffprobe_bin=ffprobe_bin)
    )
    tags = probe(render_path)
    if tags is None:
        return False, "watermark_unmeasured", detail
    comment = tags.get("comment") or ""
    if comment.startswith(WATERMARK_MARKER_PREFIX):
        detail["marker_present"] = True
        detail["marker"] = comment
    if extract_frame is None:
        extract_frame = _extract_frame
    if extract_payload is None:
        from app.services import provenance_watermark

        extract_payload = provenance_watermark.extract_payload
    from PIL import Image

    checked = 0
    found = False
    for at in sample_times or [1.0]:
        frame_path = extract_frame(render_path, at)
        if frame_path is None:
            continue
        try:
            with Image.open(frame_path) as image:
                payload = extract_payload(image)
        except (OSError, ValueError):
            continue
        checked += 1
        if payload:
            found = True
    detail["lsb_frames_checked"] = checked
    detail["lsb_payload_present"] = found if checked else None
    if detail["marker_present"]:
        return True, "watermark_present", detail
    return False, "watermark_absent", detail


def _extract_frame(
    render_path: Path | str, at_seconds: float
) -> Path | None:
    """Grab one frame as a temp PNG, or None on failure."""
    import tempfile

    dest = Path(tempfile.gettempdir()) / (
        f"vyralx_wm_{abs(hash((str(render_path), round(at_seconds, 3)))) % 10**8}.png"
    )
    grab = subprocess.run(
        ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y",
         "-ss", f"{float(at_seconds):.3f}", "-i", str(render_path),
         "-frames:v", "1", str(dest)],
        capture_output=True, text=True, timeout=60,
    )
    if grab.returncode != 0 or not dest.is_file():
        return None
    return dest


def caption_gate(
    render_path: Path | str,
    duration: float,
    *,
    sampler=None,
    sampler_kwargs: dict[str, Any] | None = None,
) -> tuple[bool, str, dict[str, Any]]:
    """Judge caption-track count via the VYR-045 gate + vision sampler.

    ``sampler`` is a seam for tests; it defaults to the deployed
    :func:`scene_analysis.sample_render_caption_detections` (lazy
    import). A sampler returning None reports
    ``caption_gate_unmeasured`` — fail-closed, never a pass.
    """
    detail: dict[str, Any] = {"detections": None, "tracks": None}
    if sampler is None:
        from app.services import scene_analysis

        sampler = scene_analysis.sample_render_caption_detections
    detections = sampler(render_path, duration, **(sampler_kwargs or {}))
    if detections is None:
        return False, "caption_gate_unmeasured", detail
    ok, reason = viral_quality.caption_track_gate(detections)
    detail["detections"] = detections
    detail["tracks"] = viral_quality.count_caption_tracks(detections)
    return ok, reason, detail


def ass_path_for_render(render_path: Path | str) -> Path | None:
    """Sibling ``<stem>.ass`` for a render, or None when absent."""
    candidate = Path(render_path).with_suffix(".ass")
    return candidate if candidate.is_file() else None


def run_held_render_qa(
    render_path: Path | str,
    *,
    duration: float,
    audio_stream_count: int,
    ass_path: Path | str | None = None,
    caption_sampler=None,
    caption_sampler_kwargs: dict[str, Any] | None = None,
    measure=None,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    watermark_sample_times: list[float] | None = None,
) -> dict[str, Any]:
    """Run all four VYR-044 gates over one finished render.

    ``caption_sampler=None`` means the deployed vision sampler; pass
    an explicit sampler (or a stub returning None) to measure or to
    force the unmeasured column. The ASS corroboration is reported
    for every render that has a sibling .ass file.
    """
    render = Path(render_path)
    signals = media_quality.analyze_media_signals(
        render,
        ffmpeg_bin=ffmpeg_bin,
        actual_duration=float(duration),
        audio_stream_count=int(audio_stream_count),
    )
    loud_ok, loud_reason, loud_detail = loudness_gate(signals)
    ass_file = Path(ass_path) if ass_path else ass_path_for_render(render)
    events: list[dict[str, Any]] = []
    malformed = 0
    if ass_file is not None:
        events, malformed = parse_ass_dialogue(ass_file)
    # The hook layer is not speech: BGM segmentation and the ASS
    # track count use speech events only, so the top hook never
    # inflates either (see HOOK_STYLE_MARKERS).
    speech = speech_events(events)
    bgm_ok, bgm_reason, bgm_detail = bgm_gate(
        render, speech, duration,
        audio_stream_count=audio_stream_count,
        silence_intervals=signals.get("silence_intervals") or [],
        measure=measure, ffmpeg_bin=ffmpeg_bin,
    )
    wm_ok, wm_reason, wm_detail = watermark_gate(
        render, ffprobe_bin=ffprobe_bin,
        sample_times=watermark_sample_times,
    )
    cap_ok, cap_reason, cap_detail = caption_gate(
        render, duration,
        sampler=caption_sampler,
        sampler_kwargs=caption_sampler_kwargs,
    )
    gates = {
        "caption_track": {"passed": cap_ok, "reason": cap_reason,
                          "detail": cap_detail},
        "bgm": {"passed": bgm_ok, "reason": bgm_reason,
                "detail": bgm_detail},
        "watermark": {"passed": wm_ok, "reason": wm_reason,
                      "detail": wm_detail},
        "loudness": {"passed": loud_ok, "reason": loud_reason,
                     "detail": loud_detail},
    }
    return {
        "render": str(render),
        "duration_seconds": float(duration),
        "audio_stream_count": int(audio_stream_count),
        "ass_file": str(ass_file) if ass_file is not None else None,
        "ass_events": len(events),
        "ass_speech_events": len(speech),
        "ass_hook_events": len(events) - len(speech),
        "ass_malformed_lines": malformed,
        "ass_caption_tracks": ass_caption_track_count(speech),
        "gates": gates,
        "passed": all(g["passed"] for g in gates.values()),
        "failed_gates": [name for name, g in gates.items()
                         if not g["passed"]],
    }
