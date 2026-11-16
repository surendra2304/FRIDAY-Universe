"""VyralX take verification: best-take selection + blank-frame
self-verification (TASK-IG3-VYR-05).

Two wave-2 clusters meet here. Cluster 119 (IG source
DXlFWL5EkaN, the AutoEdit pattern) asked for automatic bad-take
detection in talking-head footage; cluster 121 (IG source
DdlIP2YAqsq, the Laya pattern) asked for a local editing skill
that keeps the best take and self-verifies its output. Both
were graded PARTIAL: ``style_recipe.clean_transcript`` cleans
retakes/false starts out of a timed transcript and
``nl_editor`` executes instruction-driven edits, but nothing
*selected* a best take among takes, and nothing *verified* a
recording — supervisor AUDIT-2 re-confirmed ``best_take`` /
``blank`` / ``verif`` at zero hits. This module is the missing
measurement layer:

* :func:`parse_blackdetect` parses ffmpeg ``blackdetect``
  output into blank segments — the raw signal for dropped /
  frozen / blank frames;
* :func:`blank_gate` is the self-verification gate: a recording
  fails if any single blank runs longer than the threshold or
  blanks exceed the allowed share of the runtime, and the
  verdict carries the measured numbers either way;
* :func:`score_take` scores one take from its timed transcript
  via ``style_recipe.clean_transcript`` — kept words are the
  payload, retakes and false starts are penalised, pauses are
  reported as evidence (dead air is cut by the editor, not a
  quality flaw in the take itself);
* :func:`select_best_take` ranks takes deterministically and
  names the winner with the full per-take evidence table;
* :func:`verify_recording` combines both halves for a single
  recorded take: transcript score + blank gate -> one verdict.

Honesty boundaries: scores are a stated heuristic over
transcript evidence, not a judgement of performance; the gate
measures blank frames, not picture quality; nothing here
renders, records, or publishes — it measures recordings the
pipeline already made and reports what it measured.

The module carries its own FastAPI router, mounted by
``app.main`` at ``/api/v1`` (``POST
/api/v1/take-verification/blank-gate``, ``.../best-take``,
``.../verify``, ``GET /api/v1/take-verification/policy``) —
the AUDIT-2 production-caller standard.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import re
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import style_recipe

VERIFY_VERSION = "ig3-vyr05-1"
IG_SOURCES = ("DXlFWL5EkaN", "DdlIP2YAqsq")

_BLACKDETECT_RE = re.compile(
    r"black_start:(?P<start>[\d.]+)\s+black_end:(?P<end>[\d.]+)"
    r"\s+black_duration:(?P<duration>[\d.]+)")

#: Take-score penalties (stated heuristic): a retake costs more
#: than a false start — the retake means the line was delivered
#: twice and one delivery must be cut.
_RETAKE_PENALTY = 3
_FALSE_START_PENALTY = 2


# --------------------------------------------------------------------------- #
# Blank-frame measurement
# --------------------------------------------------------------------------- #
def parse_blackdetect(output: str) -> list[dict[str, float]]:
    """Parse ffmpeg blackdetect output into blank segments.

    Each ``black_start:X black_end:Y black_duration:Z`` triple
    (the filter's stderr line format) becomes one segment,
    ordered by start. No triples -> no blank segments; the
    parser never invents a segment the filter did not report.
    """
    segments = [
        {"start": float(m.group("start")),
         "end": float(m.group("end")),
         "duration": float(m.group("duration"))}
        for m in _BLACKDETECT_RE.finditer(output or "")
    ]
    segments.sort(key=lambda s: s["start"])
    return segments


def blank_gate(segments: list[dict[str, float]], *,
               duration_s: float,
               max_single_blank_s: float = 1.5,
               max_blank_ratio: float = 0.05) -> dict[str, Any]:
    """The blank-frame self-verification gate.

    Fails when any single blank exceeds ``max_single_blank_s``
    (a frozen/dropped stretch) or when total blank time exceeds
    ``max_blank_ratio`` of the runtime. The verdict always
    carries the measured totals — a pass and a fail are equally
    specific about what was measured.
    """
    if duration_s <= 0:
        raise ValueError("duration_s must be positive")
    blank_seconds = round(sum(s["duration"] for s in segments), 3)
    ratio = round(blank_seconds / duration_s, 4) if duration_s else 0.0
    longest = max((s["duration"] for s in segments), default=0.0)
    failures = []
    for seg in segments:
        if seg["duration"] > max_single_blank_s:
            failures.append({
                "kind": "single_blank_too_long",
                "start": seg["start"], "end": seg["end"],
                "duration": seg["duration"],
                "threshold_s": max_single_blank_s,
            })
    if ratio > max_blank_ratio:
        failures.append({
            "kind": "blank_ratio_too_high",
            "blank_ratio": ratio, "threshold": max_blank_ratio,
        })
    return {
        "passed": not failures,
        "blank_seconds": blank_seconds,
        "blank_ratio": ratio,
        "segment_count": len(segments),
        "longest_blank_s": longest,
        "failures": failures,
        "thresholds": {"max_single_blank_s": max_single_blank_s,
                       "max_blank_ratio": max_blank_ratio},
        "basis": "ffmpeg blackdetect segments vs stated "
                 "thresholds — blank frames measured, picture "
                 "quality not judged",
    }


# --------------------------------------------------------------------------- #
# Take scoring (transcript evidence)
# --------------------------------------------------------------------------- #
def score_take(take: dict[str, Any]) -> dict[str, Any]:
    """Score one take from its timed transcript.

    score = kept_words - 3*retakes - 2*false_starts, computed
    over ``style_recipe.clean_transcript``'s cut list. Pauses
    are counted as evidence only. A take with no words scores
    its (negative) penalties alone — an empty take cannot win
    on a technicality.
    """
    if not isinstance(take, dict) or "take_id" not in take:
        raise ValueError("each take must be an object with a take_id")
    if "timed_words" not in take:
        raise ValueError(
            f"take {take['take_id']!r} carries no timed_words — "
            "an unmeasured take cannot be scored")
    cleaned = style_recipe.clean_transcript(list(take["timed_words"]))
    kinds = [c["kind"] for c in cleaned["cuts"]]
    retakes = kinds.count("retake")
    false_starts = kinds.count("false_start")
    pauses = kinds.count("pause")
    score = (cleaned["kept_count"]
             - _RETAKE_PENALTY * retakes
             - _FALSE_START_PENALTY * false_starts)
    return {
        "take_id": str(take["take_id"]),
        "kept_words": cleaned["kept_count"],
        "cuts": {"retake": retakes, "false_start": false_starts,
                 "pause": pauses, "total": cleaned["cut_count"]},
        "score": score,
        "basis": "kept_words - 3*retakes - 2*false_starts over "
                 "style_recipe.clean_transcript (stated heuristic)",
    }


def select_best_take(takes: list[dict[str, Any]]) -> dict[str, Any]:
    """Rank takes and name the best, with the full table.

    Deterministic: higher score wins; ties break on take_id,
    so the same takes always select the same winner.
    """
    if not takes:
        raise ValueError("at least one take is required")
    ranking = [score_take(t) for t in takes]
    ranking.sort(key=lambda r: (-r["score"], r["take_id"]))
    for position, entry in enumerate(ranking, start=1):
        entry["rank"] = position
    return {
        "kind": "best_take_selection",
        "version": VERIFY_VERSION,
        "ig_sources": list(IG_SOURCES),
        "best_take_id": ranking[0]["take_id"],
        "ranking": ranking,
        "status": "pending_review",
        "publish": False,
        "note": "Selection is a transcript-evidence heuristic; "
                "the winning take still goes through the normal "
                "review queue before any production use.",
    }


def verify_recording(take: dict[str, Any], blackdetect_output: str,
                     *, duration_s: float,
                     max_single_blank_s: float = 1.5,
                     max_blank_ratio: float = 0.05) -> dict[str, Any]:
    """One recorded take, verified both ways.

    Passes only if the blank gate passes AND the take carries
    at least one kept word — a silent or blank recording is a
    failed take however clean its transcript looks.
    """
    transcript = score_take(take)
    gate = blank_gate(parse_blackdetect(blackdetect_output),
                      duration_s=duration_s,
                      max_single_blank_s=max_single_blank_s,
                      max_blank_ratio=max_blank_ratio)
    return {
        "kind": "take_verification",
        "version": VERIFY_VERSION,
        "ig_sources": list(IG_SOURCES),
        "take_id": transcript["take_id"],
        "transcript": transcript,
        "blank_gate": gate,
        "passed": bool(gate["passed"] and transcript["kept_words"] > 0),
        "status": "pending_review",
        "publish": False,
    }


# --------------------------------------------------------------------------- #
# Router (mounted by app.main — the production path)
# --------------------------------------------------------------------------- #
router = APIRouter()


class BlankGateRequest(BaseModel):
    blackdetect_output: str
    duration_s: float
    max_single_blank_s: float = 1.5
    max_blank_ratio: float = 0.05


class BestTakeRequest(BaseModel):
    takes: list[dict[str, Any]]


class VerifyRequest(BaseModel):
    take: dict[str, Any]
    blackdetect_output: str
    duration_s: float
    max_single_blank_s: float = 1.5
    max_blank_ratio: float = 0.05


@router.get("/take-verification/policy")
def take_verification_policy() -> dict[str, Any]:
    return {
        "version": VERIFY_VERSION,
        "ig_sources": list(IG_SOURCES),
        "measures": "blank frames (ffmpeg blackdetect) + "
                    "transcript evidence (style_recipe."
                    "clean_transcript)",
        "does_not_measure": "picture quality or performance "
                            "quality — scores are a stated "
                            "heuristic over transcript evidence",
        "status": "pending_review",
        "publish": False,
    }


@router.post("/take-verification/blank-gate")
def take_verification_blank_gate(req: BlankGateRequest) -> dict[str, Any]:
    try:
        return blank_gate(parse_blackdetect(req.blackdetect_output),
                          duration_s=req.duration_s,
                          max_single_blank_s=req.max_single_blank_s,
                          max_blank_ratio=req.max_blank_ratio)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/take-verification/best-take")
def take_verification_best_take(req: BestTakeRequest) -> dict[str, Any]:
    try:
        return select_best_take(req.takes)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/take-verification/verify")
def take_verification_verify(req: VerifyRequest) -> dict[str, Any]:
    try:
        return verify_recording(
            req.take, req.blackdetect_output,
            duration_s=req.duration_s,
            max_single_blank_s=req.max_single_blank_s,
            max_blank_ratio=req.max_blank_ratio)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
