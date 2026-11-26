"""TASK-VYR-081: GTA 6 content series — moment-finding, vertical cut, series render gate.

Series model (board TASK-VYR-081, unchanged): short excerpts, her English
narration over the clip, source voice ducked under hers, subtitles ALWAYS
on, BGM mandatory and ducked, unlisted + review-first, renders held for the
owner. Loop stays OFF, uploader stays paused — nothing uploads without the
owner's word.

Pipeline: moment-finding on permitted footage (audio-spike + scene
detection), vertical cut, pre-post self-check, then the standing
machine-QA gates (caption-track count, BGM presence, watermark, loudness)
before any human review. Builds on the clipping-toolchain evaluation
already filed from Df0B9Z4n4BU (docs/collaboration/
TASK-VYR-077-REPO-IMPLEMENT.md) — that evaluation is not duplicated here.

Moment-finding method: the board cites "the PySceneDetect /
faster-whisper pattern from Df5V_2anUAj missions 3-5". There is no
PySceneDetect in VyralX and this module adds no new dependency: scene
cuts come from ffmpeg's own ``select='gt(scene,...)'`` filter (the same
detector, no library), audio spikes from ffmpeg ebur128 momentary
loudness (``framelog=verbose``), and transcript windows from the
faster-whisper timed words via ``shorts_generator`` when the caller
supplies them. A source with no measurable moment signal yields an
honest empty result, never invented clips.

Footage rule: ONLY her own gameplay capture, or campaign-supplied
footage under a live TASK-EARN-024 campaign brief. No third-party
streamer footage outside a campaign brief. :func:`validate_footage_source`
rejects anything else before any work starts.

Honest limits, carried in the series record so nobody overclaims
later: YouTube pays NOTHING on raw compiled clips (reused-content
policy), and Rockstar/Take-Two fan-content rules are non-commercial
with takedown at will. This series is a growth/audience play for the
channel; any money attached to GTA 6 clips comes only through
TASK-EARN-024 campaign platforms under their own terms, never from
YouTube revenue on the clips themselves.

Registration note: the series is registered here, as the
``gta6-clips`` record in this module — NOT as a second entry in
``app/data/channel_strategy.json``. That file is pinned by
test_ig_vyr10_channel_strategy.py to exactly one series seed (the
Silk Road seed, history lane) and the owner has exactly three lanes
(space_science / history / tech_ai); GTA 6 is not a new lane, it runs
on the existing model. Adding a gaming seed there would break the
pinned shape and misrepresent the lane model. The seed shape this
module exposes (:func:`series_seed`) matches the series_automation
contract (lane + title + topics) for future use.

Fail-closed throughout: an unmeasured gate is a failed gate, never a
pass. The one exception is the VYR-060 bad-take verdict, which is
advisory until PR #1730 merges: when it is absent the gate records
``bad_take_detection_not_available`` and does not fail on that alone;
when it is present and reports bad takes, the gate fails.

Pure stdlib + the existing VyralX services (media_quality,
viral_quality, take_verification, shorts_generator). No network.
Python 3.10.
"""
from __future__ import annotations

import math
import re
import subprocess
from pathlib import Path
from statistics import median
from typing import Any

from app.services import shorts_generator as sg
from app.services import viral_quality
from app.services.media_quality import analyze_media_signals
from app.services.take_verification import verify_render_signals

SERIES_VERSION = "vyr081-1"
SERIES_ID = "gta6-clips"
SERIES_TITLE = "GTA 6 clips: short excerpts with her English narration"

#: The only permitted footage provenances for this series.
FOOTAGE_SOURCES = ("own_capture", "earn024_campaign")

#: Series model, from the board acceptance — unchanged.
SERIES_MODEL = (
    "short excerpts, her English narration over the clip, source voice "
    "ducked under hers, subtitles ALWAYS on, BGM mandatory and ducked, "
    "unlisted + review-first, renders held for the owner"
)

FOOTAGE_RULE = (
    "ONLY footage VyralX is permitted to use: her own gameplay capture, "
    "or campaign-supplied footage under a live TASK-EARN-024 campaign "
    "brief. No third-party streamer footage outside a campaign brief."
)

HONEST_LIMITS = (
    "YouTube pays NOTHING on raw compiled clips (reused-content policy); "
    "Rockstar/Take-Two fan-content rules are non-commercial with takedown "
    "at will. Growth/audience play only; any money attached to GTA 6 "
    "clips comes only through TASK-EARN-024 campaign platforms under "
    "their own terms, never from YouTube revenue on the clips."
)

#: Standing machine-QA thresholds (shared with media_quality).
LOUDNESS_MIN_LUFS = -24.0
LOUDNESS_MAX_LUFS = -10.0
TRUE_PEAK_MAX_DBFS = -1.0

#: Moment-finding defaults.
SPIKE_LUFS = -30.0
SPIKE_MIN_LIFT_LU = 6.0
SPIKE_MIN_DURATION_S = 0.5
SCENE_THRESHOLD = 0.4
MIN_MOMENT_S = 8.0
MAX_MOMENT_S = 59.0
MAX_MOMENTS = 5

_EBUR_FRAME_RE = re.compile(r"t:\s*(?P<t>-?\d+(?:\.\d+)?).*?\bM:\s*(?P<m>-?\d+(?:\.\d+)?)")
_SHOWINFO_RE = re.compile(r"pts_time:\s*(?P<t>-?\d+(?:\.\d+)?)")
_EBUR_FILTER = "ebur128=peak=true:framelog=verbose"


def _finite_float(value: Any, default: float = 0.0) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _run(cmd: list[str], *, timeout_seconds: int) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True,
                              errors="replace", timeout=max(1, int(timeout_seconds)))
    except (subprocess.TimeoutExpired, OSError, ValueError):
        return None


def _probe_duration(path: Path, *, ffprobe_bin: str = "ffprobe",
                    timeout_seconds: int = 30) -> float | None:
    proc = _run([str(ffprobe_bin), "-v", "error", "-show_entries",
                 "format=duration", "-of", "csv=p=0", str(path)],
                timeout_seconds=timeout_seconds)
    if proc is None or proc.returncode != 0:
        return None
    duration = _finite_float((proc.stdout or "").strip(), -1.0)
    return duration if duration > 0 else None


def _has_audio_stream(path: Path, *, ffprobe_bin: str = "ffprobe",
                      timeout_seconds: int = 30) -> bool | None:
    proc = _run([str(ffprobe_bin), "-v", "error", "-show_entries",
                 "stream=codec_type", "-of", "csv=p=0", str(path)],
                timeout_seconds=timeout_seconds)
    if proc is None or proc.returncode != 0:
        return None
    return any(line.strip() == "audio" for line in (proc.stdout or "").splitlines())


def validate_footage_source(source: str) -> str:
    """Accept only a permitted footage provenance, or raise.

    ``own_capture`` = her own gameplay capture; ``earn024_campaign``
    = campaign-supplied footage under a live TASK-EARN-024 brief.
    Anything else is rejected here, before any work starts.
    """
    value = str(source or "").strip()
    if value not in FOOTAGE_SOURCES:
        raise ValueError(
            f"footage source {source!r} is not permitted for the GTA 6 "
            f"series ({FOOTAGE_RULE} Permitted: {', '.join(FOOTAGE_SOURCES)}.)")
    return value


def build_series_record() -> dict[str, Any]:
    """The registered ``gta6-clips`` series record.

    Episodes are appended by :func:`build_series_episode`; the record
    itself carries the model, the footage rule and the honest limits
    so they travel with every episode.
    """
    return {
        "version": SERIES_VERSION,
        "series_id": SERIES_ID,
        "title": SERIES_TITLE,
        "task": "TASK-VYR-081",
        "model": SERIES_MODEL,
        "footage_rule": FOOTAGE_RULE,
        "honest_limits": HONEST_LIMITS,
        "registration": (
            "registered in app/services/gta6_series.py as the gta6-clips "
            "record (see module docstring: not a channel_strategy.json "
            "series_seeds entry — that file pins exactly one Silk Road "
            "seed and the owner has exactly three lanes)"),
        "loop": "OFF",
        "uploader": "paused",
        "privacy": "unlisted",
        "review_first": True,
        "renders_held_for_owner": True,
        "publishes_anything": False,
        "episodes": [],
    }


def series_seed() -> dict[str, Any]:
    """Series-automation seed shape (lane + title + topics) for gta6-clips.

    The topics are planned episode topics, not claims that footage
    exists — every episode still waits on permitted footage (see
    ``status``). The lane value is descriptive: there is no gaming
    lane playbook; the series runs on the existing model.
    """
    return {
        "series_id": SERIES_ID,
        "lane": "gaming",
        "title": SERIES_TITLE,
        "cadence_days": 2,
        "format": SERIES_MODEL,
        "footage_rule": FOOTAGE_RULE,
        "status": ("planned — no permitted footage on file; episodes wait "
                   "on own capture or a live TASK-EARN-024 brief"),
        "honest_limits": HONEST_LIMITS,
        "topics": [
            "trailer 2: Vice City, first look",
            "Lucia — the new protagonist",
            "Jason and Lucia — the duo at the centre",
            "the map: Leonida State and what the trailer shows",
            "what the trailer does not show (and why)",
        ],
    }


def detect_audio_spikes(
    path: str | Path, *,
    spike_lufs: float = SPIKE_LUFS,
    min_lift_lu: float = SPIKE_MIN_LIFT_LU,
    min_duration_s: float = SPIKE_MIN_DURATION_S,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Audio-spike intervals from ebur128 momentary loudness.

    A spike is a run of 100 ms frames whose momentary loudness (M)
    stays above ``threshold = max(spike_lufs, median_M + min_lift_lu)``
    for at least ``min_duration_s``. The relative lift keeps a
    uniformly loud clip from reporting one giant spike; the absolute
    floor keeps a whisper-quiet clip from reporting noise as spikes.
    """
    media = Path(path)
    if not media.is_file() or media.stat().st_size <= 0:
        return {"status": "unavailable", "error_type": "missing_output",
                "spikes": [], "has_audio": None}
    has_audio = _has_audio_stream(media, ffprobe_bin=ffprobe_bin)
    if has_audio is False:
        return {"status": "analyzed", "error_type": None, "spikes": [],
                "has_audio": False, "median_momentary_lufs": None,
                "threshold_lufs": None}
    proc = _run([str(ffmpeg_bin), "-hide_banner", "-nostats", "-v", "verbose",
                 "-i", str(media), "-map", "0:a:0", "-af", _EBUR_FILTER,
                 "-f", "null", "-"], timeout_seconds=timeout_seconds)
    if proc is None:
        return {"status": "unavailable", "error_type": "ffmpeg_unavailable",
                "spikes": [], "has_audio": has_audio}
    if proc.returncode != 0:
        return {"status": "unavailable", "error_type": "ffmpeg_exit",
                "spikes": [], "has_audio": has_audio}
    frames: list[tuple[float, float]] = []
    for line in (proc.stderr or "").splitlines():
        match = _EBUR_FRAME_RE.search(line)
        if match:
            frames.append((_finite_float(match.group("t"), -1.0),
                           _finite_float(match.group("m"), -120.7)))
    frames = [(t, m) for t, m in frames if t >= 0]
    if not frames:
        return {"status": "unavailable", "error_type": "no_loudness_frames",
                "spikes": [], "has_audio": True}
    momentary = [m for _, m in frames]
    med = float(median(momentary))
    threshold = max(float(spike_lufs), med + float(min_lift_lu))
    spikes: list[dict[str, Any]] = []
    run_start: float | None = None
    run_peak = -120.7
    run_last = 0.0
    for t, m in frames + [(frames[-1][0] + 0.1, threshold - 1.0)]:
        if m > threshold:
            if run_start is None:
                run_start, run_peak = t, m
            run_peak = max(run_peak, m)
            run_last = t
        elif run_start is not None:
            end = run_last + 0.1
            if end - run_start >= float(min_duration_s):
                spikes.append({
                    "start_seconds": round(run_start, 3),
                    "end_seconds": round(end, 3),
                    "duration_seconds": round(end - run_start, 3),
                    "peak_lufs": round(run_peak, 2),
                })
            run_start, run_peak = None, -120.7
    return {"status": "analyzed", "error_type": None, "spikes": spikes,
            "has_audio": True, "median_momentary_lufs": round(med, 2),
            "threshold_lufs": round(threshold, 2)}


def detect_scene_cuts(
    path: str | Path, *,
    threshold: float = SCENE_THRESHOLD,
    ffmpeg_bin: str = "ffmpeg",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Scene-cut times from ffmpeg's ``select='gt(scene,...)'`` filter.

    The first frame is not a cut; every selected frame after it is.
    """
    media = Path(path)
    if not media.is_file() or media.stat().st_size <= 0:
        return {"status": "unavailable", "error_type": "missing_output",
                "cuts": []}
    proc = _run([str(ffmpeg_bin), "-hide_banner", "-nostats", "-v", "info",
                 "-i", str(media), "-vf",
                 f"select='gt(scene,{float(threshold)})',showinfo",
                 "-f", "null", "-"], timeout_seconds=timeout_seconds)
    if proc is None:
        return {"status": "unavailable", "error_type": "ffmpeg_unavailable",
                "cuts": []}
    if proc.returncode != 0:
        return {"status": "unavailable", "error_type": "ffmpeg_exit",
                "cuts": []}
    cuts: list[float] = []
    for line in (proc.stderr or "").splitlines():
        match = _SHOWINFO_RE.search(line)
        if match:
            t = _finite_float(match.group("t"), -1.0)
            if t > 0:
                cuts.append(round(t, 3))
    return {"status": "analyzed", "error_type": None, "cuts": cuts,
            "threshold": float(threshold)}


def _moment_window(spike: dict[str, Any], duration: float, *,
                   pre_roll_s: float = 1.0, post_roll_s: float = 3.0) -> tuple[float, float]:
    start = max(0.0, spike["start_seconds"] - pre_roll_s)
    end = min(duration, spike["end_seconds"] + post_roll_s)
    if duration >= MIN_MOMENT_S and end - start < MIN_MOMENT_S:
        end = min(duration, start + MIN_MOMENT_S)
        if end - start < MIN_MOMENT_S:
            start = max(0.0, end - MIN_MOMENT_S)
    if end - start > MAX_MOMENT_S:
        end = start + MAX_MOMENT_S
    return round(start, 3), round(end, 3)


def find_moments(
    path: str | Path, *,
    timed_words: list[dict[str, Any]] | None = None,
    footage_source: str | None = None,
    max_moments: int = MAX_MOMENTS,
    spike_lufs: float = SPIKE_LUFS,
    scene_threshold: float = SCENE_THRESHOLD,
    ffmpeg_bin: str = "ffmpeg",
    ffprobe_bin: str = "ffprobe",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """Moment-finding on permitted footage: audio spikes + scene cuts (+ transcript).

    ``footage_source`` must be a permitted provenance when given —
    unpermitted footage is rejected before ffmpeg runs. Each moment
    is a Shorts-legal window (8–59 s) with its evidence: the spike
    that fired it, the scene cut inside it if any, and the transcript
    virality score when timed words were supplied. Every moment
    carries ``status="pending_review"`` and ``privacy="unlisted"``.
    """
    if footage_source is not None:
        validate_footage_source(footage_source)
    media = Path(path)
    if not media.is_file() or media.stat().st_size <= 0:
        return {"status": "unavailable", "error_type": "missing_output",
                "moments": [], "audio_spikes": [], "scene_cuts": [],
                "source_duration_s": None}
    duration = _probe_duration(media, ffprobe_bin=ffprobe_bin)
    if duration is None:
        return {"status": "unavailable", "error_type": "unprobed_duration",
                "moments": [], "audio_spikes": [], "scene_cuts": [],
                "source_duration_s": None}
    spikes = detect_audio_spikes(
        media, spike_lufs=spike_lufs, ffmpeg_bin=ffmpeg_bin,
        ffprobe_bin=ffprobe_bin, timeout_seconds=timeout_seconds)
    cuts = detect_scene_cuts(
        media, threshold=scene_threshold, ffmpeg_bin=ffmpeg_bin,
        timeout_seconds=timeout_seconds)
    if spikes["status"] != "analyzed" or cuts["status"] != "analyzed":
        error = spikes.get("error_type") or cuts.get("error_type")
        return {"status": "unavailable", "error_type": error,
                "moments": [], "audio_spikes": spikes.get("spikes", []),
                "scene_cuts": cuts.get("cuts", []),
                "source_duration_s": duration}
    spike_list = spikes["spikes"]
    cut_list = cuts["cuts"]
    # No audio stream means no threshold was computed (and no spikes
    # exist to score); fall back to the default so scoring never
    # crashes on a silent source.
    threshold = float(spikes.get("threshold_lufs") or SPIKE_LUFS)
    candidates: list[dict[str, Any]] = []
    for spike in spike_list:
        start, end = _moment_window(spike, duration)
        inside = [c for c in cut_list if start <= c <= end]
        lift = max(0.0, spike["peak_lufs"] - threshold)
        score = round(min(1.0, 0.5 + (0.2 if inside else 0.0)
                          + 0.3 * min(1.0, lift / 12.0)), 4)
        candidates.append({
            "start": start, "end": end, "duration": round(end - start, 3),
            "viral_score": score, "audio_spike_peak_lufs": spike["peak_lufs"],
            "scene_cut_at": inside[0] if inside else None,
            "basis": "audio_spike" + ("+scene_cut" if inside else ""),
        })
    if not spike_list and cut_list:
        for cut in cut_list:
            fake = {"start_seconds": cut, "end_seconds": cut + 0.1}
            start, end = _moment_window(fake, duration)
            candidates.append({
                "start": start, "end": end, "duration": round(end - start, 3),
                "viral_score": 0.5, "audio_spike_peak_lufs": None,
                "scene_cut_at": cut,
                "basis": "scene_cut",
            })
    if timed_words:
        for window in sg.candidate_windows(timed_words):
            words = [w for w in timed_words
                     if window["start"] <= float(w["start"]) < window["end"]]
            spike_hit = any(s["start_seconds"] < window["end"]
                            and s["end_seconds"] > window["start"]
                            for s in spike_list)
            candidates.append({
                "start": window["start"], "end": window["end"],
                "duration": window["duration"],
                "viral_score": window["viral_score"],
                "audio_spike_peak_lufs": None,
                "scene_cut_at": None,
                "basis": "transcript_window" + ("+audio_spike" if spike_hit else ""),
                "text": window.get("text", ""),
            })
    if not candidates:
        return {"status": "analyzed", "error_type": None, "moments": [],
                "audio_spikes": spike_list, "scene_cuts": cut_list,
                "source_duration_s": duration,
                "reason": "no moment signal found (no audio spike, scene "
                          "cut or transcript window)"}
    kept = sg.dedupe_windows(candidates)
    ranked = sorted(kept, key=lambda m: -m["viral_score"])[:max(1, int(max_moments))]
    moments = []
    for m in sorted(ranked, key=lambda x: x["start"]):
        moments.append({
            "start_seconds": m["start"], "end_seconds": m["end"],
            "duration_seconds": m["duration"],
            "viral_score": m["viral_score"],
            "audio_spike_peak_lufs": m.get("audio_spike_peak_lufs"),
            "scene_cut_at": m.get("scene_cut_at"),
            "basis": m["basis"],
            "text": m.get("text", ""),
            "status": "pending_review", "privacy": "unlisted",
            "publish": False,
        })
    return {"status": "analyzed", "error_type": None, "moments": moments,
            "audio_spikes": spike_list, "scene_cuts": cut_list,
            "source_duration_s": duration}


def plan_episode_cut(
    moment: dict[str, Any], *,
    source_width: int = 1920, source_height: int = 1080,
    face_center_x: float | None = None,
) -> dict[str, Any]:
    """9:16 vertical-cut plan for one moment (shorts_generator standard).

    The ffmpeg argv is built, never executed here — the render waits
    for review like every other VyralX plan.
    """
    clip = {"start": float(moment["start_seconds"]),
            "end": float(moment["end_seconds"])}
    plan = sg.vertical_crop_plan(clip, source_width=source_width,
                                 source_height=source_height,
                                 face_center_x=face_center_x)
    return {"moment": {"start_seconds": moment["start_seconds"],
                       "end_seconds": moment["end_seconds"],
                       "basis": moment.get("basis", "")},
            "crop": plan, "status": "pending_review",
            "privacy": "unlisted", "publish": False}


def _bad_take_count(verdict: dict[str, Any]) -> int | None:
    """Bad-take count from a VYR-060 verdict dict, or None if unrecognised."""
    if not isinstance(verdict, dict):
        return None
    count = verdict.get("bad_take_count")
    if isinstance(count, (int, float)):
        return int(count)
    segments = verdict.get("segments")
    if isinstance(segments, list):
        return sum(1 for s in segments
                   if isinstance(s, dict) and s.get("verdict") == "bad")
    return None


def gate_series_episode(
    *, caption_detections: list[dict[str, Any]] | None = None,
    bgm_present: bool | None = None,
    watermark_verified: bool | None = None,
    signal_analysis: dict[str, Any] | None = None,
    bad_take_verdict: dict[str, Any] | None = None,
    duration_s: float | None = None,
) -> dict[str, Any]:
    """Series render gate: the standing machine-QA gates for one episode.

    Fail-closed: any unmeasured input fails the gate. Caption track
    (exactly one, via viral_quality), BGM present (mandatory, VYR-032),
    watermark verified, loudness in -24..-10 LUFS with true peak at
    most -1.0 dBFS, and the VYR-061 blank self-verification over the
    signal scan's black intervals. The VYR-060 bad-take verdict is
    advisory until PR #1730 merges: absent it is recorded, not failed
    on; present with bad takes it fails the gate.
    """
    checks: dict[str, Any] = {}
    if caption_detections is None:
        checks["captions"] = {"passed": False, "reason": "caption_gate_unmeasured"}
    else:
        ok, reason = viral_quality.caption_track_gate(caption_detections)
        checks["captions"] = {"passed": bool(ok), "reason": reason,
                              "tracks": viral_quality.count_caption_tracks(caption_detections)}
    if bgm_present is None:
        checks["bgm"] = {"passed": False, "reason": "bgm_unmeasured"}
    elif not bgm_present:
        checks["bgm"] = {"passed": False, "reason": "bgm_missing"}
    else:
        checks["bgm"] = {"passed": True, "reason": "bgm_present"}
    if watermark_verified is None:
        checks["watermark"] = {"passed": False, "reason": "watermark_unmeasured"}
    elif not watermark_verified:
        checks["watermark"] = {"passed": False, "reason": "watermark_unverified"}
    else:
        checks["watermark"] = {"passed": True, "reason": "watermark_verified"}
    metrics: dict[str, Any] = {}
    if isinstance(signal_analysis, dict) and signal_analysis.get("status") == "analyzed":
        raw = signal_analysis.get("audio_metrics")
        metrics = raw if isinstance(raw, dict) else {}
    integrated = _finite_float(metrics.get("integrated_loudness_lufs"), math.nan)
    true_peak = _finite_float(metrics.get("true_peak_dbfs"), math.nan)
    clipped = metrics.get("clipped_samples")
    if not math.isfinite(integrated) or not math.isfinite(true_peak):
        checks["loudness"] = {"passed": False, "reason": "loudness_unmeasured",
                              "integrated_loudness_lufs": None,
                              "true_peak_dbfs": None}
    elif not (LOUDNESS_MIN_LUFS <= integrated <= LOUDNESS_MAX_LUFS
              and true_peak <= TRUE_PEAK_MAX_DBFS):
        checks["loudness"] = {"passed": False, "reason": "loudness_out_of_range",
                              "integrated_loudness_lufs": integrated,
                              "true_peak_dbfs": true_peak}
    elif isinstance(clipped, int) and clipped > 0:
        checks["loudness"] = {"passed": False, "reason": "audio_clipped",
                              "integrated_loudness_lufs": integrated,
                              "true_peak_dbfs": true_peak,
                              "clipped_samples": clipped}
    else:
        checks["loudness"] = {"passed": True, "reason": "loudness_in_range",
                              "integrated_loudness_lufs": integrated,
                              "true_peak_dbfs": true_peak,
                              "clipped_samples": clipped}
    black = None
    if isinstance(signal_analysis, dict) and signal_analysis.get("status") == "analyzed":
        black = signal_analysis.get("black_intervals")
    if duration_s is None or float(duration_s) <= 0:
        checks["blank"] = {"passed": False, "reason": "blank_unmeasured"}
    else:
        verdict = verify_render_signals(black, duration_s=float(duration_s))
        passed = verdict.get("passed")
        checks["blank"] = {"passed": passed,
                           "reason": ("blank_gate_passed" if passed is True
                                      else "blank_gate_failed" if passed is False
                                      else "blank_unmeasured"),
                           "status": verdict.get("status")}
    if bad_take_verdict is None:
        checks["bad_takes"] = {"passed": None, "advisory": True,
                               "reason": "bad_take_detection_not_available",
                               "note": "VYR-060 PR #1730 unmerged; verdict "
                                       "absent, gate does not fail on it"}
    else:
        count = _bad_take_count(bad_take_verdict)
        if count is None:
            checks["bad_takes"] = {"passed": None, "advisory": True,
                                   "reason": "bad_take_verdict_unrecognized"}
        elif count > 0:
            checks["bad_takes"] = {"passed": False, "advisory": False,
                                   "reason": f"bad_takes_detected:{count}",
                                   "bad_take_count": count}
        else:
            checks["bad_takes"] = {"passed": True, "advisory": False,
                                   "reason": "no_bad_takes",
                                   "bad_take_count": 0}
    failed = [name for name, c in checks.items()
              if c.get("passed") is False and not c.get("advisory")]
    unmeasured = [name for name, c in checks.items() if c.get("passed") is None
                  and not c.get("advisory")]
    passed = not failed and not unmeasured
    reason = ("series_gate_passed" if passed
              else checks[failed[0]]["reason"] if failed
              else checks[unmeasured[0]]["reason"])
    return {"version": SERIES_VERSION, "task": "TASK-VYR-081",
            "passed": passed, "reason": reason, "checks": checks}


def build_series_episode(
    *, episode_no: int, moment: dict[str, Any],
    cut_plan: dict[str, Any], gate: dict[str, Any],
    footage_source: str,
) -> dict[str, Any]:
    """One episode record: moment + cut plan + gate verdict, held for review.

    An episode is ``held_for_review`` only when its gate passed; a
    failed gate is ``rejected`` with the reason carried. Either way
    nothing publishes from here.
    """
    validate_footage_source(footage_source)
    passed = bool(gate.get("passed"))
    return {
        "episode_no": int(episode_no), "series_id": SERIES_ID,
        "task": "TASK-VYR-081", "footage_source": footage_source,
        "moment": moment, "cut_plan": cut_plan, "gate": gate,
        "status": "held_for_review" if passed else "rejected",
        "privacy": "unlisted", "publish": False,
        "review_first": True,
    }


def episode_qa_evidence(episode: dict[str, Any]) -> dict[str, Any]:
    """Compact QA evidence for one episode, for filing with the review."""
    gate = episode.get("gate") or {}
    checks = gate.get("checks") or {}
    return {
        "series_id": SERIES_ID, "episode_no": episode.get("episode_no"),
        "task": "TASK-VYR-081", "status": episode.get("status"),
        "privacy": episode.get("privacy"), "publish": False,
        "gate_passed": gate.get("passed"), "gate_reason": gate.get("reason"),
        "checks": {name: {"passed": c.get("passed"), "reason": c.get("reason")}
                   for name, c in checks.items()},
        "moment": episode.get("moment"),
    }


def analyze_render_for_gate(
    render_path: str | Path, *, actual_duration: float,
    audio_stream_count: int, ffmpeg_bin: str = "ffmpeg",
    timeout_seconds: int = 120,
) -> dict[str, Any]:
    """The signal scan the series gate consumes (media_quality, one decode)."""
    return analyze_media_signals(
        render_path, ffmpeg_bin=ffmpeg_bin, actual_duration=actual_duration,
        audio_stream_count=audio_stream_count, timeout_seconds=timeout_seconds)
