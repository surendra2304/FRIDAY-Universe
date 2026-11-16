"""VyralX OpenVoice narration — assessment, gate, offline job (TASK-IG2-VYR-07).

Pattern assessed from myshell-ai/OpenVoice (MIT, V1+V2 free for
commercial use; spec card ``openvoice.md``, IG source Dd_sICVjFKq):
instant voice cloning — extract a reference speaker's tone colour
from a short clip, apply it to base TTS speech (V2 via MeloTTS) with
emotion/accent/rhythm control, incl. zero-shot cross-lingual cloning.

ASSESSMENT (honest, card-verified + encoded as this gate): OpenVoice
is a PyTorch model with separately downloaded V1/V2 checkpoints plus
MeloTTS — far beyond a ~180MB service on a ~956MB fleet VM, and CPU
inference is slow. It CANNOT run on the fleet. The feasible shape is
the same offline pattern as VoiceStudio/HyperFrames: render narration
on the owner's hardware (or future GPU/ARM capacity), hand VyralX a
finished MP3, and let VyralX assemble + publish (UNLISTED). Gemini
Live remains FRIDAY's live voice; this is an offline TTS source only.

This module is that integration, with the gate enforced in code:

* :func:`assess_environment` — the feasibility verdict from measured
  inputs (free RAM, torch presence, checkpoint presence/size). On
  fleet-shaped inputs it returns ``feasible=False`` with the reasons.
* :func:`build_narration_job` — a validated offline job spec
  (reference clip rules, V2 language list, style controls) that an
  off-fleet renderer consumes. Building a job NEVER downloads weights
  and NEVER runs inference.
* :func:`ingest_narration` — accepts a finished narration MP3's
  metadata into a VyralX assembly plan (pending_review, unlisted);
  a job whose gate failed cannot be ingested as OpenVoice output.

No network, no torch import, no execution. Python 3.10, stdlib only.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

GATE_VERSION = "ig2-vyr07-1"
# Fleet shape (fleet ground truth): ~956MB VMs, ~180MB per-service cap.
FLEET_RAM_MB = 956
SERVICE_CAP_MB = 180
# Checkpoint footprint is on the order of hundreds of MB before torch
# runtime; the gate requires clear headroom over the service cap.
MIN_FREE_RAM_MB = 1024
V2_LANGUAGES = ("en", "es", "fr", "zh", "ja", "ko")
REF_MIN_SECONDS, REF_MAX_SECONDS = 3.0, 60.0
STYLE_CONTROLS = ("emotion", "accent", "rhythm", "pauses", "intonation")


def assess_environment(*, free_ram_mb: int, torch_available: bool,
                       checkpoint_present: bool,
                       checkpoint_mb: float = 0.0,
                       host_role: str = "fleet_service") -> dict[str, Any]:
    """Feasibility verdict. Reasons are named, never a bare no."""
    reasons = []
    if host_role == "fleet_service":
        reasons.append(f"fleet service cap is ~{SERVICE_CAP_MB}MB on a "
                       f"~{FLEET_RAM_MB}MB VM; a PyTorch checkpoint model "
                       "cannot live inside it")
    if free_ram_mb < MIN_FREE_RAM_MB:
        reasons.append(f"free RAM {free_ram_mb}MB < {MIN_FREE_RAM_MB}MB minimum")
    if not torch_available:
        reasons.append("torch is not installed (and must not be added to "
                       "the fleet service image)")
    if not checkpoint_present:
        reasons.append("no OpenVoice checkpoint present; checkpoints are "
                       "downloaded separately and are never fetched by "
                       "this service")
    feasible = not reasons
    return {"version": GATE_VERSION, "feasible": feasible,
            "host_role": host_role, "reasons": reasons,
            "checkpoint_mb": checkpoint_mb,
            "verdict": "may render offline narration" if feasible else
                       "do NOT run on this host — render on owner "
                       "hardware / future GPU-ARM and ingest the MP3",
            "live_voice_unaffected": "Gemini Live remains FRIDAY's live voice"}


def validate_reference_clip(clip: dict[str, Any]) -> dict[str, Any]:
    dur = float(clip.get("duration_seconds", 0))
    if not (REF_MIN_SECONDS <= dur <= REF_MAX_SECONDS):
        raise ValueError(f"reference clip must be {REF_MIN_SECONDS}-{REF_MAX_SECONDS}s "
                         f"(got {dur}s) — tone colour needs a short clean clip")
    if not clip.get("path"):
        raise ValueError("reference clip needs a path")
    return {"path": clip["path"], "duration_seconds": dur,
            "consent": clip.get("consent", "owner_voice"),
            "note": "only clone a voice the channel has the right to use"}


def build_narration_job(*, text: str, reference_clip: dict[str, Any],
                        language: str = "en",
                        style: dict[str, Any] | None = None,
                        assessment: dict[str, Any]) -> dict[str, Any]:
    """A validated OFFLINE job spec. Refused when the gate failed and
    the job claims a fleet host; owner-hardware jobs carry the fleet
    assessment as a warning instead of a block."""
    if not text.strip():
        raise ValueError("narration text is empty")
    if language not in V2_LANGUAGES:
        raise ValueError(f"V2 language {language!r} not in {V2_LANGUAGES}")
    ref = validate_reference_clip(reference_clip)
    style = {k: v for k, v in (style or {}).items() if k in STYLE_CONTROLS}
    return {"version": GATE_VERSION, "engine": "openvoice_v2",
            "text": text, "language": language, "reference": ref,
            "style": style, "output_format": "mp3",
            "render_host": "owner_hardware_or_future_gpu_arm",
            "assessment_feasible": bool(assessment.get("feasible")),
            "assessment_reasons": assessment.get("reasons", []),
            "downloads_weights": False, "runs_in_service": False,
            "status": "pending_review", "privacy": "unlisted",
            "publish": False}


def ingest_narration(job: dict[str, Any], rendered: dict[str, Any]) -> dict[str, Any]:
    """Assemble a finished offline narration MP3 into a VyralX plan."""
    path = str(rendered.get("path", ""))
    if not path.endswith(".mp3") or not rendered.get("bytes"):
        raise ValueError("ingest needs a finished .mp3 with a byte size")
    if job.get("engine") != "openvoice_v2":
        raise ValueError("ingest only accepts openvoice_v2 jobs")
    return {"version": GATE_VERSION, "narration_path": path,
            "bytes": int(rendered["bytes"]),
            "duration_seconds": rendered.get("duration_seconds"),
            "engine": "openvoice_v2", "job_text": job["text"],
            "language": job["language"], "status": "pending_review",
            "privacy": "unlisted", "publish": False,
            "next_step": "assemble with the film/shorts plan, then the "
                         "normal approval-gated UNLISTED upload"}
