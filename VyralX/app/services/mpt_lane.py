"""MoneyPrinterTurbo producer lane for the viral autopilot (IG2 · B7-C1).

Why this module exists — the Instagram General-section read (cluster
B7-C1) surfaced MoneyPrinterTurbo (github.com/harry0703/MoneyPrinterTurbo,
MIT): a complete open-source topic->short pipeline (script -> stock
footage -> subtitles -> music -> rendered HD short). This module adds it
to VyralX as an *optional producer lane*: an adapter that takes a topic
brief, invokes the MPT CLI, and hands the resulting MP4 + script +
captions into the same five fail-closed quality gates
(:mod:`app.services.viral_quality`, TASK-VYR-014) that the native
viral-remix lane must pass. Nothing bypasses the gates; a gate rejection
is a valid, expected outcome.

Posture — fail closed and inert by default:

* The lane runs only when BOTH ``viral_producer_lane == "mpt"`` and
  ``viral_mpt_lane_enabled`` are set; either one alone does nothing, and
  the native lane remains the default.
* The lane has **no ungated path**: if the TASK-VYR-014 gates are
  disabled (``viral_quality_gates_enabled`` False) the lane refuses to
  run at all rather than ship ungated output.
* Free-only, enforced in preflight, not by convention: the brief must
  carry its own script (MPT's LLM script generation is never invoked —
  the CLI's ``--video-script`` path skips it), the stock source must be
  Pexels or Pixabay (the free tiers; MPT's paid AI-generation sources
  are rejected), the MPT home's TTS server must be the free Edge TTS
  (``azure-tts-v1`` — the same engine family VyralX's own lane uses),
  paid TTS voice prefixes (``gemini:``, ``elevenlabs:``, ...) are
  rejected, the subtitle provider must be ``edge`` (the Whisper
  provider's ~3 GB model cannot fit the fleet), and MPT's bundled
  YouTube-sourced songs are never used (``--bgm-type none``).
* Nothing uploads: MPT's own cross-posting (Upload-Post) must be
  disabled in the MPT home's config or the lane refuses to run, and a
  passed candidate is reported as ``GATED_PASS`` — deliberately *not*
  ``QUEUED_FOR_PUBLISH``. This lane never creates a publish job; the
  publish hand-off is a separate coordinator enablement step.
* Fleet fit is a gate, not a hope: the MPT subprocess's measured peak
  RSS must fit ``render_max_memory_mb`` or the candidate is rejected
  with ``fleet_memory_exceeded`` before any quality gate runs.

Gate mapping (packet requirement — the gates apply to an MPT package
exactly as to a native candidate, in the native order):

1. event-arc — ``measure_event_arc`` + ``arc_gate`` on the rendered MP4.
2. vision grounding — ``analyze_scene`` on the rendered MP4; no record,
   or a static record, rejects. The record describes MPT's *stock
   footage selection*, which is what a source-footage gate means for
   this lane.
3. consistency — ``check_consistency`` of script/title/description
   against that record.
4. structure (hook/payoff) — ``check_structure`` on the script.
5. length + narration fit — ``check_script_length`` on the script, then
   ``evaluate_narration_fit`` on the *measured* narration extracted
   from the finished MP4, including final-sentence coverage.

The one native behaviour adapted, not dropped: the native lane retries
its editorial LLM with the violations as feedback. MPT cannot
regenerate copy, so there is no retry loop — but the deterministic,
fact-free description-question repair is applied with the same
condition (question-only violations) and re-checked once, exactly as
in :func:`app.services.viral_remix.produce_viral_short`. The captions
MPT burned in come from the same script text the gates judged; if MPT
reports a different script than the brief supplied, the package is
rejected as unverifiable rather than gated on words nobody spoke.
"""
from __future__ import annotations

import json
import logging
import re
import resource
import shlex
import subprocess
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from app.config import get_settings
from app.services import viral_quality, viral_remix
from app.services.scene_analysis import analyze_scene
from app.services.source_analysis import probe_media

log = logging.getLogger("vyralx.mpt_lane")

LANE_NAME = "mpt"

# The only stock sources this lane may use: free tiers, per the packet's
# free-only check. MPT also offers paid AI-generation sources
# (wavespeed, volcengine_seedance, ofox, ...) — never selectable here.
FREE_VIDEO_SOURCES = {"pexels", "pixabay"}
# MPT's [ui] tts_server value for its built-in Edge TTS: free, no API
# key, the same engine family as VyralX's own commentary synthesis.
FREE_TTS_SERVER = "azure-tts-v1"
# MPT's subtitle provider that timestamps from TTS output; the other
# provider ("whisper") downloads a ~3 GB model the fleet cannot hold.
FREE_SUBTITLE_PROVIDER = "edge"
# Voice-name prefixes that select paid TTS providers in MPT's CLI
# (from `cli.py --help`); an unprefixed name is an Edge TTS voice.
PAID_VOICE_PREFIXES = (
    "gemini:", "mimo:", "elevenlabs:", "chatterbox:", "kokoro:", "voxcpm:",
)
# Violation kinds the native lane may repair deterministically.
_QUESTION_KINDS = {"question_ungrounded", "cta_without_question"}


class LaneRefusal(Exception):
    """Preflight refusal: the lane will not run. ``reason`` is stable."""

    def __init__(self, reason: str, detail: str = ""):
        super().__init__(detail or reason)
        self.reason = reason
        self.detail = detail or reason


@dataclass
class MPTBrief:
    """One topic brief for the lane. ``script`` is mandatory: it is the
    exact text MPT will speak and caption, and the exact text the gates
    judge. The lane never lets MPT (or an LLM behind it) write copy."""

    topic: str
    script: str
    title: str = ""
    description: str = ""
    category: str = "VIRAL"
    terms: list[str] = field(default_factory=list)
    voice_name: str = ""
    video_source: str = ""


@dataclass
class RunnerResult:
    returncode: int
    stdout: str
    stderr: str
    peak_rss_mb: float | None = None


# A runner executes the MPT CLI and reports its output + peak child RSS.
# Tests inject a fake; production uses :func:`_subprocess_runner`.
Runner = Callable[..., RunnerResult]


def _subprocess_runner(cmd: list[str], *, cwd: Path, timeout: int) -> RunnerResult:
    proc = subprocess.run(
        cmd, cwd=str(cwd), capture_output=True, text=True,
        errors="replace", timeout=timeout,
    )
    peak_mb: float | None = None
    try:
        # ru_maxrss is KiB on Linux: the peak RSS of the largest waited-for
        # child — the fleet-fit measurement for the render just made.
        peak_mb = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss / 1024.0
    except (ValueError, OSError):  # pragma: no cover - non-Linux fallback
        peak_mb = None
    return RunnerResult(proc.returncode, proc.stdout, proc.stderr, peak_mb)


# --------------------------------------------------------------------------- #
# MPT home preflight — the lane reads (never writes) the operator-provisioned
# MoneyPrinterTurbo checkout's config.toml and refuses anything unsafe.
# --------------------------------------------------------------------------- #
def _toml_scalar(text: str, key: str) -> str | None:
    """First non-comment ``key = value`` RHS in a TOML text, or None.

    Deliberately small: the preflight only reads simple scalars and
    string lists, and anything it cannot determine is treated as absent
    (which, for the keys that matter, means refuse)."""
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        match = re.match(rf"{re.escape(key)}\s*=\s*(.+)$", stripped)
        if match:
            return match.group(1).strip()
    return None


def _toml_bool(text: str, key: str) -> bool:
    raw = _toml_scalar(text, key)
    return bool(raw and raw.split("#")[0].strip().lower() == "true")


def _toml_string(text: str, key: str) -> str | None:
    raw = _toml_scalar(text, key)
    if raw is None:
        return None
    match = re.search(r'"([^"]*)"', raw)
    return match.group(1) if match else None


def _toml_string_list(text: str, key: str) -> list[str]:
    raw = _toml_scalar(text, key)
    if raw is None:
        return []
    return [item for item in re.findall(r'"([^"]*)"', raw) if item.strip()]


@dataclass
class MPTPlan:
    mpt_home: Path
    task_id: str
    video_source: str
    voice_name: str
    script: str  # sanitized — the exact words gated and spoken


def preflight(brief: MPTBrief, settings: Any) -> MPTPlan:
    """Validate lane, brief and MPT home. Raises :class:`LaneRefusal`."""
    if str(getattr(settings, "viral_producer_lane", "viral_remix")).lower() != LANE_NAME:
        raise LaneRefusal("lane_not_selected", "viral_producer_lane is not 'mpt'")
    if not bool(getattr(settings, "viral_mpt_lane_enabled", False)):
        raise LaneRefusal("lane_disabled", "viral_mpt_lane_enabled is False")
    if not bool(getattr(settings, "viral_quality_gates_enabled", True)):
        # The lane has no ungated path — the emergency kill switch that
        # lets the native lane run ungated must never ungate this one.
        raise LaneRefusal(
            "quality_gates_disabled",
            "the MPT lane refuses to run while the quality gates are off",
        )
    script = viral_quality.sanitize_spoken_text(str(brief.script or ""))
    if not script:
        raise LaneRefusal(
            "brief_script_missing",
            "a brief must carry its own script; MPT's LLM generation is never used",
        )
    if not str(brief.topic or "").strip():
        raise LaneRefusal("brief_topic_missing", "a brief needs a topic")
    source = (
        str(brief.video_source or getattr(settings, "viral_mpt_video_source", "pexels"))
        .strip().lower()
    )
    if source not in FREE_VIDEO_SOURCES:
        raise LaneRefusal(
            "video_source_not_free",
            f"video_source {source!r} is not a free stock source "
            f"(allowed: {sorted(FREE_VIDEO_SOURCES)})",
        )
    voice = str(brief.voice_name or getattr(settings, "viral_mpt_voice_name", "") or "")
    if voice.lower().startswith(PAID_VOICE_PREFIXES):
        raise LaneRefusal(
            "voice_provider_not_free",
            f"voice_name {voice!r} selects a paid TTS provider",
        )
    home_raw = str(getattr(settings, "viral_mpt_home", "") or "").strip()
    if not home_raw:
        raise LaneRefusal("mpt_not_provisioned", "viral_mpt_home is not configured")
    home = Path(home_raw)
    if not (home / "cli.py").is_file():
        raise LaneRefusal(
            "mpt_not_provisioned", f"no MoneyPrinterTurbo cli.py under {home}"
        )
    config_path = home / "config.toml"
    if not config_path.is_file():
        raise LaneRefusal(
            "mpt_not_provisioned",
            f"no config.toml in the MPT home {home}; provision it first",
        )
    config_text = config_path.read_text(encoding="utf-8", errors="replace")
    if _toml_bool(config_text, "upload_post_enabled") or _toml_bool(
        config_text, "upload_post_auto_upload"
    ):
        raise LaneRefusal(
            "mpt_cross_posting_enabled",
            "MPT cross-posting (Upload-Post) is enabled in config.toml; "
            "this lane never uploads, so it refuses to run MPT at all",
        )
    tts_server = _toml_string(config_text, "tts_server")
    if tts_server is not None and tts_server != FREE_TTS_SERVER:
        raise LaneRefusal(
            "mpt_tts_not_free",
            f"MPT tts_server is {tts_server!r}; only {FREE_TTS_SERVER!r} (Edge TTS) is free",
        )
    subtitle_provider = _toml_string(config_text, "subtitle_provider")
    if subtitle_provider is not None and subtitle_provider != FREE_SUBTITLE_PROVIDER:
        raise LaneRefusal(
            "mpt_subtitle_provider_not_edge",
            f"MPT subtitle_provider is {subtitle_provider!r}; the whisper "
            "provider's model cannot fit the fleet — use 'edge'",
        )
    keys = _toml_string_list(config_text, f"{source}_api_keys")
    if not keys:
        raise LaneRefusal(
            "mpt_stock_keys_missing",
            f"no free-tier {source} API key configured in the MPT home's config.toml",
        )
    return MPTPlan(
        mpt_home=home,
        task_id=str(uuid.uuid4()),
        video_source=source,
        voice_name=voice,
        script=script,
    )


def build_cli_args(plan: MPTPlan, brief: MPTBrief) -> list[str]:
    """The exact MPT CLI invocation for one brief.

    ``--video-script`` is always present (it is what keeps MPT's LLM out
    of the loop), ``--bgm-type none`` keeps MPT's bundled songs out, and
    ``--stop-at video`` ends the run at the render — the stage boundary
    the lane hands over to VyralX's gates."""
    args = ["cli.py"] + [
        "--task-id", plan.task_id,
        "--video-subject", str(brief.topic),
        "--video-script", plan.script,
        "--video-source", plan.video_source,
        "--bgm-type", "none",
        "--stop-at", "video",
    ]
    if brief.terms:
        args += ["--video-terms", ", ".join(str(term) for term in brief.terms)]
    if plan.voice_name:
        args += ["--voice-name", plan.voice_name]
    return args


def _launcher(settings: Any) -> list[str]:
    """How to run MPT's cli.py. MPT must execute in *its own*
    environment (its dependencies are not VyralX's), so the operator
    points ``viral_mpt_python_cmd`` at the MPT venv's python or at
    ``uv run python`` (the run's cwd is the MPT home, so uv resolves
    MPT's own project). The bare default is PATH python3."""
    raw = str(getattr(settings, "viral_mpt_python_cmd", "") or "").strip()
    return shlex.split(raw) if raw else ["python3"]


# --------------------------------------------------------------------------- #
# artefact collection
# --------------------------------------------------------------------------- #
def _result_json(stdout: str) -> dict[str, Any]:
    text = (stdout or "").strip()
    if not text:
        return {}
    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else {}
    except ValueError:
        pass
    # Logs are documented to go to stderr, but tolerate a noisy stdout:
    # take the last complete JSON object in the stream.
    start = text.rfind("\n{")
    if start >= 0:
        try:
            parsed = json.loads(text[start + 1:])
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _mp4s_in_result(payload: Any) -> list[str]:
    found: list[str] = []
    if isinstance(payload, dict):
        for value in payload.values():
            found += _mp4s_in_result(value)
    elif isinstance(payload, list):
        for value in payload:
            found += _mp4s_in_result(value)
    elif isinstance(payload, str) and payload.lower().endswith(".mp4"):
        found.append(payload)
    return found


@dataclass
class MPTArtefacts:
    video_path: Path
    captions_path: Path | None
    reported_script: str | None


def collect_artefacts(plan: MPTPlan, result: RunnerResult) -> MPTArtefacts:
    """Locate the rendered MP4 (+ captions) for the task, fail closed."""
    payload = _result_json(result.stdout)
    task_dir = plan.mpt_home / "storage" / "tasks" / plan.task_id
    candidates: list[Path] = []
    for raw in _mp4s_in_result(payload):
        path = Path(raw)
        if not path.is_absolute():
            path = plan.mpt_home / path
        if path.is_file():
            candidates.append(path)
    if task_dir.is_dir():
        on_disk = sorted(task_dir.glob("*.mp4"))
        for preferred in ("final", "combined"):
            candidates += [p for p in on_disk if p.name.startswith(preferred)]
        candidates += on_disk
    seen: set[Path] = set()
    unique = [p for p in candidates if not (p in seen or seen.add(p))]
    if not unique:
        raise LaneRefusal(
            "mpt_failed",
            f"MPT produced no MP4 for task {plan.task_id} "
            f"(stderr tail: {result.stderr[-300:]!r})",
        )
    captions: Path | None = None
    if task_dir.is_dir():
        srt_files = sorted(task_dir.glob("*.srt"))
        if srt_files:
            captions = next(
                (p for p in srt_files if p.name == "subtitle.srt"), srt_files[0]
            )
    reported = payload.get("script") if isinstance(payload, dict) else None
    return MPTArtefacts(
        video_path=unique[0],
        captions_path=captions,
        reported_script=str(reported) if reported else None,
    )


# --------------------------------------------------------------------------- #
# the gates, applied to an MPT package in the native order
# --------------------------------------------------------------------------- #
@dataclass
class GateVerdict:
    passed: bool
    reason: str = ""
    violations: list[viral_quality.Violation] = field(default_factory=list)
    event_arc: dict[str, Any] | None = None
    description: str = ""
    description_repaired: bool = False


def _script_violations(
    *, script: str, title: str, description: str,
    record: dict[str, Any], duration: float,
) -> list[viral_quality.Violation]:
    return (
        viral_quality.check_consistency(
            commentary=script, title=title, description=description, record=record
        )
        + viral_quality.check_structure(commentary=script, record=record)
        + viral_quality.check_script_length(commentary=script, duration=duration)
    )


def gate_mpt_package(
    *,
    video_path: Path,
    script: str,
    title: str,
    description: str,
    duration: float,
    settings: Any,
    work_dir: Path,
) -> GateVerdict:
    """Run the five TASK-VYR-014 gates over an MPT-rendered package.

    Mirrors :func:`app.services.viral_remix.produce_viral_short`'s gate
    sequence and reason strings; a rejection here means exactly what the
    same rejection means in the native lane."""
    # 1. event-arc gate (an unmeasured arc defers to the vision gate,
    #    exactly as arc_gate's contract specifies).
    arc = viral_quality.measure_event_arc(
        video_path, duration, ffmpeg_bin=settings.ffmpeg_bin
    )
    arc_ok, arc_reason = viral_quality.arc_gate(arc)
    arc_info: dict[str, Any] | None = None
    if arc is not None:
        arc_info = {
            "mean_change": arc.mean_change,
            "max_change": arc.max_change,
            "static_ratio": arc.static_ratio,
            "peak_position": arc.peak_position,
            "verdict": arc_reason,
        }
    if not arc_ok:
        return GateVerdict(False, "static_scene", event_arc=arc_info,
                           description=description)
    # 2. vision grounding: look at the render before believing its copy.
    record = analyze_scene(video_path, duration)
    if record is None:
        return GateVerdict(False, "vision_unavailable", event_arc=arc_info,
                           description=description)
    if record.get("static"):
        return GateVerdict(False, "static_scene", event_arc=arc_info,
                           description=description)
    # 3+4+5a. consistency, structure (hook/payoff) and script length.
    violations = _script_violations(
        script=script, title=title, description=description,
        record=record, duration=duration,
    )
    repaired = False
    if violations and all(v.kind in _QUESTION_KINDS for v in violations):
        # The native lane's one deterministic repair, same condition:
        # the copy is grounded; only the description's question is not.
        fixed = viral_quality.repair_description_question(description, record)
        if fixed != description:
            recheck = _script_violations(
                script=script, title=title, description=fixed,
                record=record, duration=duration,
            )
            if not recheck:
                violations = []
                description = fixed
                repaired = True
    if violations:
        return GateVerdict(False, "script_unverifiable", violations,
                           event_arc=arc_info, description=description)
    # 5b. narration fit on the MEASURED narration inside the render.
    audio_path = work_dir / "narration.wav"
    proc = subprocess.run(
        [settings.ffmpeg_bin, "-hide_banner", "-loglevel", "error", "-nostdin",
         "-y", "-i", str(video_path), "-vn", "-ac", "1", "-ar", "16000",
         str(audio_path)],
        capture_output=True, text=True, errors="replace", timeout=300,
    )
    narration_seconds = 0.0
    coverage: float | None = None
    if proc.returncode == 0 and audio_path.is_file():
        narration_seconds = float(probe_media(audio_path).duration or 0.0)
        coverage = viral_remix._last_sentence_coverage(script, audio_path)
    fit_violations = viral_quality.evaluate_narration_fit(
        commentary=script,
        narration_seconds=narration_seconds,
        duration=duration,
        last_sentence_coverage=coverage,
    )
    if fit_violations:
        return GateVerdict(False, "script_length_misfit", fit_violations,
                           event_arc=arc_info, description=description)
    return GateVerdict(True, "", [], event_arc=arc_info,
                       description=description, description_repaired=repaired)


# --------------------------------------------------------------------------- #
# the lane entry points
# --------------------------------------------------------------------------- #
def produce_mpt_short(
    brief: MPTBrief,
    settings: Any | None = None,
    *,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Run one brief through MPT and the gates. Never uploads, never
    creates a publish job; a pass is reported as ``GATED_PASS``."""
    settings = settings or get_settings()
    try:
        plan = preflight(brief, settings)
    except LaneRefusal as refusal:
        return {"status": "SKIPPED", "reason": refusal.reason,
                "lane": LANE_NAME, "detail": refusal.detail}
    run = runner or _subprocess_runner
    timeout = int(getattr(settings, "viral_mpt_timeout_seconds", 1800) or 1800)
    try:
        result = run(
            _launcher(settings) + build_cli_args(plan, brief),
            cwd=plan.mpt_home, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"status": "SKIPPED", "reason": "timeout", "lane": LANE_NAME,
                "task_id": plan.task_id}
    except OSError as exc:
        return {"status": "SKIPPED", "reason": "mpt_failed", "lane": LANE_NAME,
                "task_id": plan.task_id, "detail": str(exc)}
    if result.returncode != 0:
        payload = _result_json(result.stdout)
        return {"status": "SKIPPED", "reason": "mpt_failed", "lane": LANE_NAME,
                "task_id": plan.task_id,
                "failed_stage": payload.get("failed_stage"),
                "detail": str(payload.get("error") or result.stderr[-300:])}
    # Fleet fit before quality: a render that blew the memory budget is
    # not a candidate on this fleet, whatever the gates would say.
    budget_mb = float(getattr(settings, "render_max_memory_mb", 512) or 512)
    if result.peak_rss_mb is not None and result.peak_rss_mb > budget_mb:
        return {"status": "SKIPPED", "reason": "fleet_memory_exceeded",
                "lane": LANE_NAME, "task_id": plan.task_id,
                "peak_rss_mb": round(result.peak_rss_mb, 1),
                "render_max_memory_mb": budget_mb}
    try:
        artefacts = collect_artefacts(plan, result)
    except LaneRefusal as refusal:
        return {"status": "SKIPPED", "reason": refusal.reason,
                "lane": LANE_NAME, "task_id": plan.task_id,
                "detail": refusal.detail}
    if artefacts.reported_script is not None:
        spoken = viral_quality.sanitize_spoken_text(artefacts.reported_script)
        if spoken != plan.script:
            # The gates judge the words actually spoken, not the words
            # we hoped were spoken.
            violation = viral_quality.Violation(
                "script_rewritten_by_lane", "commentary",
                "MPT reported a different script than the brief supplied; "
                "the package cannot be gated on the brief's words",
            )
            return {"status": "SKIPPED", "reason": "script_unverifiable",
                    "lane": LANE_NAME, "task_id": plan.task_id,
                    "violations": [violation.kind]}
    try:
        probe = probe_media(artefacts.video_path)
        duration = max(0.0, float(probe.duration or 0.0))
    except Exception as exc:
        return {"status": "SKIPPED", "reason": "mpt_failed", "lane": LANE_NAME,
                "task_id": plan.task_id, "detail": f"probe failed: {exc}"}
    work_dir = artefacts.video_path.parent
    verdict = gate_mpt_package(
        video_path=artefacts.video_path,
        script=plan.script,
        title=str(brief.title or brief.topic),
        description=str(brief.description or ""),
        duration=duration,
        settings=settings,
        work_dir=work_dir,
    )
    if not verdict.passed:
        return {"status": "SKIPPED", "reason": verdict.reason,
                "lane": LANE_NAME, "task_id": plan.task_id,
                "violations": [v.kind for v in verdict.violations],
                "event_arc": verdict.event_arc,
                "peak_rss_mb": (round(result.peak_rss_mb, 1)
                                if result.peak_rss_mb is not None else None)}
    # Hand the gated package to VyralX's own tree. Deliberately NOT a
    # publish job: enablement decides what happens to a gated MPT render.
    settings.render_dir.mkdir(parents=True, exist_ok=True)
    video_dest = settings.render_dir / f"mpt-{plan.task_id}.mp4"
    video_dest.write_bytes(artefacts.video_path.read_bytes())
    captions_dest: Path | None = None
    if artefacts.captions_path is not None:
        captions_dest = settings.render_dir / f"mpt-{plan.task_id}.srt"
        captions_dest.write_bytes(artefacts.captions_path.read_bytes())
    log.info(
        "MPT lane: task %s passed all quality gates (%.1fs, peak RSS %s MB)",
        plan.task_id, duration,
        f"{result.peak_rss_mb:.0f}" if result.peak_rss_mb is not None else "?",
    )
    return {
        "status": "GATED_PASS",
        "lane": LANE_NAME,
        "task_id": plan.task_id,
        "video_path": str(video_dest),
        "captions_path": str(captions_dest) if captions_dest else None,
        "script": plan.script,
        "title": str(brief.title or brief.topic),
        "description": verdict.description,
        "description_repaired": verdict.description_repaired,
        "duration": duration,
        "event_arc": verdict.event_arc,
        "quality_gate_attempts": 1,
        "peak_rss_mb": (round(result.peak_rss_mb, 1)
                        if result.peak_rss_mb is not None else None),
        "publish_job_id": None,
    }


def _load_briefs(settings: Any) -> list[MPTBrief] | None:
    raw = str(getattr(settings, "viral_mpt_briefs_path", "") or "").strip()
    path = Path(raw) if raw else Path(settings.data_dir) / "mpt_briefs.json"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(payload, list):
        return None
    briefs: list[MPTBrief] = []
    for item in payload:
        if not isinstance(item, dict):
            continue
        briefs.append(MPTBrief(
            topic=str(item.get("topic") or ""),
            script=str(item.get("script") or ""),
            title=str(item.get("title") or ""),
            description=str(item.get("description") or ""),
            category=str(item.get("category") or "VIRAL"),
            terms=[str(term) for term in (item.get("terms") or [])],
            voice_name=str(item.get("voice_name") or ""),
            video_source=str(item.get("video_source") or ""),
        ))
    return briefs


def produce_from_briefs(
    settings: Any,
    *,
    max_candidates: int = 10,
    runner: Runner | None = None,
) -> dict[str, Any]:
    """Autopilot driver entry for the MPT lane: work the briefs file in
    order, stop at the first gated pass. Mirrors the native driver's
    result shape, except a pass is ``GATED_PASS`` — never ``PRODUCED``,
    so the driver's publish drain is never triggered by this lane."""
    if str(getattr(settings, "viral_producer_lane", "viral_remix")).lower() != LANE_NAME \
            or not bool(getattr(settings, "viral_mpt_lane_enabled", False)):
        return {"status": "LANE_INACTIVE", "attempts": []}
    briefs = _load_briefs(settings)
    if not briefs:
        return {"status": "NO_BRIEFS", "attempts": []}
    attempts: list[dict[str, Any]] = []
    for brief in briefs[: max(1, max_candidates)]:
        result = produce_mpt_short(brief, settings, runner=runner)
        attempts.append(result)
        if result.get("status") == "GATED_PASS":
            return {"status": "GATED_PASS", "result": result, "attempts": attempts}
        log.info("MPT lane skipped a brief: %s", result.get("reason"))
    return {"status": "ALL_BRIEFS_REJECTED", "attempts": attempts}
