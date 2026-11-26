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

TASK-VYR-061 adds the pipeline layer on top of the measurement
layer above:

* :func:`blank_segments_from_intervals` adapts the black
  intervals ``media_quality.analyze_media_signals`` already
  measures for every completed render into this module's
  segment shape, so the pipeline and this gate share ONE blank
  standard instead of two disagreeing ones;
* :func:`verify_render_signals` is that shared verdict for a
  single render: the measured black intervals of a held render,
  judged by :func:`blank_gate`;
* :func:`select_verified_best_take` is best-take selection
  with the gate applied first: a candidate that fails the
  blank gate — or carries no timed words to score — is
  excluded with its evidence, the winner is
  :func:`select_best_take` over the survivors, and when no
  candidate survives there is NO winner (fail-closed: a blank
  or unmeasured take cannot be selected by default).

TASK-VYR-060 adds the per-segment layer on top of the same
measured signals:

* :func:`detect_bad_takes` judges every caption segment of a
  held render on its own window: black and silence intervals
  clipped to the segment, plus :func:`score_take` over the
  segment's timed words when the caller carries them. A
  segment is bad when a sustained black overlaps it, when
  silence dominates it or runs long inside it, or when its
  delivery stumbles repeatedly — so failed/awkward takes are
  flagged per segment before human review, instead of hiding
  inside a whole-render pass;
* the wire is one line in ``project_pipeline`` next to the
  VYR-061 verdict: ``qa_report["bad_take_detection"]``.

Honesty boundaries: loudness and clipping are whole-render
measurements — they ride along as whole-render context, never
as per-segment judgements, because the scan cannot attribute
them to a segment. A segment with no measured evidence is
reported unavailable, never as passing.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import math
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
# Pipeline layer (TASK-VYR-061): best-take selection + blank-frame
# self-verification where the pipeline actually holds a render
# --------------------------------------------------------------------------- #
def blank_segments_from_intervals(
        intervals: list[dict[str, Any]] | None) -> list[dict[str, float]]:
    """Adapt media_quality black intervals to gate segments.

    ``media_quality.analyze_media_signals`` reports black
    intervals as ``start_seconds`` / ``end_seconds`` /
    ``duration_seconds``; :func:`blank_gate` consumes
    ``start`` / ``end`` / ``duration``. Intervals that are not
    dicts or lack a usable duration are skipped — the adapter
    never invents a segment the scan did not measure.
    """
    segments = []
    for interval in intervals or []:
        if not isinstance(interval, dict):
            continue
        try:
            duration = float(interval.get("duration_seconds"))
            start = float(interval.get("start_seconds"))
            end = float(interval.get("end_seconds"))
        except (TypeError, ValueError):
            continue
        segments.append({"start": start, "end": end,
                         "duration": duration})
    segments.sort(key=lambda s: s["start"])
    return segments


def verify_render_signals(
        black_intervals: list[dict[str, Any]] | None, *,
        duration_s: float,
        max_single_blank_s: float = 1.5,
        max_blank_ratio: float = 0.05) -> dict[str, Any]:
    """Blank-frame self-verification verdict for one render.

    ``black_intervals`` is the ``black_intervals`` list from
    ``media_quality.analyze_media_signals`` for the render.
    ``None`` means the signal scan never ran (or was
    unavailable): the verdict is then ``passed: None`` with
    ``status: "unavailable"`` — an unmeasured render is never
    reported as passing. A measured render gets the full
    :func:`blank_gate` verdict either way.
    """
    if black_intervals is None:
        return {
            "kind": "render_blank_self_verification",
            "task": "TASK-VYR-061",
            "version": VERIFY_VERSION,
            "status": "unavailable",
            "passed": None,
            "basis": "media_quality signal scan supplied no "
                     "black intervals — blank frames unmeasured, "
                     "not passed",
        }
    gate = blank_gate(blank_segments_from_intervals(black_intervals),
                      duration_s=duration_s,
                      max_single_blank_s=max_single_blank_s,
                      max_blank_ratio=max_blank_ratio)
    return {
        "kind": "render_blank_self_verification",
        "task": "TASK-VYR-061",
        "version": VERIFY_VERSION,
        "status": "measured",
        **gate,
    }


# --------------------------------------------------------------------------- #
# Pipeline layer (TASK-VYR-060): per-segment bad-take detection
# --------------------------------------------------------------------------- #
def _finite(value: Any) -> float | None:
    """Finite float or None — malformed measurements never crash
    a verdict; they are skipped with the evidence saying so."""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _overlap_seconds(start: float, end: float,
                     intervals: list[dict[str, Any]] | None
                     ) -> tuple[float, float]:
    """(total, longest-single) overlap of media_quality-shaped
    intervals (``start_seconds`` / ``end_seconds``) with the
    window ``[start, end)``. Malformed intervals are skipped —
    the overlap never claims time the scan did not measure."""
    total = 0.0
    longest = 0.0
    for interval in intervals or []:
        if not isinstance(interval, dict):
            continue
        lo = _finite(interval.get("start_seconds"))
        hi = _finite(interval.get("end_seconds"))
        if lo is None or hi is None or hi <= lo:
            continue
        overlap = min(end, hi) - max(start, lo)
        if overlap > 0:
            total += overlap
            longest = max(longest, overlap)
    return round(total, 3), round(longest, 3)


def detect_bad_takes(
        segments: list[dict[str, Any]] | None,
        signal_analysis: dict[str, Any] | None, *,
        blank_overlap_fail_s: float = 0.5,
        max_single_silence_s: float = 2.0,
        max_silence_ratio: float = 0.5,
        max_stumbles: int = 2) -> dict[str, Any]:
    """Bad-take verdict per render segment.

    ``segments`` are the render's caption segments
    (``start_seconds`` / ``end_seconds`` / ``text``, with
    optional ``timed_words``); ``signal_analysis`` is the
    ``media_quality.analyze_media_signals`` dict for the same
    render. Each segment is judged on its own window:

    * black intervals clipped to the window — a sustained
      black (``blank_overlap_fail_s``, the blackdetect minimum
      of 0.5 s, the same bar as the whole-render black check)
      inside a spoken segment is a bad take;
    * silence intervals clipped to the window — a segment is
      bad when one silence runs longer than
      ``max_single_silence_s`` (2.0 s, the whole-render
      silence floor) or silence covers more than
      ``max_silence_ratio`` of the segment (dead air where
      speech was expected);
    * timed words when the caller carries them — the segment
      is bad when :func:`score_take` finds no kept words or at
      least ``max_stumbles`` retakes + false starts (an
      awkward delivery, not one ordinary stumble).

    Loudness and clipping are whole-render measurements: they
    ride along as ``audio_context`` and are never presented as
    per-segment judgements. ``signal_analysis`` missing or not
    ``"analyzed"`` leaves every segment's signals half
    unmeasured; a segment with no measured half at all reports
    ``passed: None`` — an unmeasured segment is never reported
    as passing. Malformed segments are skipped and counted,
    never invented.
    """
    signals_measured = (
        isinstance(signal_analysis, dict)
        and signal_analysis.get("status") == "analyzed")
    black_intervals = (
        signal_analysis.get("black_intervals")
        if signals_measured else None)
    silence_intervals = (
        signal_analysis.get("silence_intervals")
        if signals_measured else None)

    verdicts: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    for index, segment in enumerate(segments or []):
        segment_id = f"segment-{index + 1}"
        if not isinstance(segment, dict):
            skipped.append({"index": index,
                            "reason": "segment is not an object"})
            continue
        if (isinstance(segment.get("segment_id"), str)
                and segment["segment_id"].strip()):
            segment_id = str(segment["segment_id"])
        start = _finite(segment.get("start_seconds"))
        end = _finite(segment.get("end_seconds"))
        if start is None or end is None or end <= start:
            skipped.append({"index": index, "segment_id": segment_id,
                            "reason": "start_seconds/end_seconds "
                                      "missing, non-finite, or "
                                      "end <= start"})
            continue
        window_s = round(end - start, 3)
        text = str(segment.get("text") or "")
        transcript: dict[str, Any] | None = None
        transcript_measured = False
        timed_words = segment.get("timed_words")
        if isinstance(timed_words, list) and timed_words:
            try:
                transcript = score_take({"take_id": segment_id,
                                         "timed_words": timed_words})
                transcript_measured = True
            except (ValueError, KeyError, TypeError, AttributeError):
                transcript = None
        blank_seconds, longest_blank = _overlap_seconds(
            start, end, black_intervals)
        silence_seconds, longest_silence = _overlap_seconds(
            start, end, silence_intervals)
        blank_ratio = round(blank_seconds / window_s, 4)
        silence_ratio = round(silence_seconds / window_s, 4)
        failures: list[dict[str, Any]] = []
        if signals_measured and longest_blank >= blank_overlap_fail_s:
            failures.append({
                "kind": "blank_in_segment",
                "longest_blank_s": longest_blank,
                "blank_seconds": blank_seconds,
                "threshold_s": blank_overlap_fail_s,
            })
        if signals_measured and longest_silence > max_single_silence_s:
            failures.append({
                "kind": "long_silence_in_segment",
                "longest_silence_s": longest_silence,
                "silence_seconds": silence_seconds,
                "threshold_s": max_single_silence_s,
            })
        if signals_measured and silence_ratio > max_silence_ratio:
            failures.append({
                "kind": "silence_dominates_segment",
                "silence_ratio": silence_ratio,
                "threshold": max_silence_ratio,
            })
        if transcript_measured and transcript is not None:
            stumbles = (transcript["cuts"]["retake"]
                        + transcript["cuts"]["false_start"])
            if transcript["kept_words"] == 0 or stumbles >= max_stumbles:
                failures.append({
                    "kind": "awkward_delivery",
                    "kept_words": transcript["kept_words"],
                    "retakes": transcript["cuts"]["retake"],
                    "false_starts": transcript["cuts"]["false_start"],
                    "threshold_stumbles": max_stumbles,
                })
        measured = signals_measured or transcript_measured
        verdicts.append({
            "segment_id": segment_id,
            "index": index,
            "start_seconds": round(start, 3),
            "end_seconds": round(end, 3),
            "duration_seconds": window_s,
            "text": text,
            "signals_measured": signals_measured,
            "transcript_measured": transcript_measured,
            "blank_seconds": blank_seconds,
            "blank_ratio": blank_ratio,
            "longest_blank_s": longest_blank,
            "silence_seconds": silence_seconds,
            "silence_ratio": silence_ratio,
            "longest_silence_s": longest_silence,
            "transcript": transcript,
            "failures": failures,
            "passed": (not failures) if measured else None,
        })

    bad_ids = [v["segment_id"] for v in verdicts
               if v["passed"] is False]
    measured_count = sum(1 for v in verdicts
                         if v["signals_measured"]
                         or v["transcript_measured"])
    audio_context: dict[str, Any] | None = None
    if signals_measured:
        metrics = signal_analysis.get("audio_metrics")
        audio_context = {
            "scope": "whole-render — loudness and clipping "
                     "cannot be attributed to one segment",
            "integrated_loudness_lufs": (
                metrics.get("integrated_loudness_lufs")
                if isinstance(metrics, dict) else None),
            "true_peak_dbfs": (
                metrics.get("true_peak_dbfs")
                if isinstance(metrics, dict) else None),
            "clipped_samples": (
                metrics.get("clipped_samples")
                if isinstance(metrics, dict) else None),
        }
    if not verdicts and not skipped:
        status = "measured"
        passed: bool | None = True
        note = ("No caption segments supplied — nothing to "
                "judge; the missing-subtitle warning lives in "
                "the QA report's own checks.")
    elif measured_count == 0:
        status = "unavailable"
        passed = None
        note = ("No segment carried measured evidence — the "
                "signal scan was unavailable and no segment "
                "carried timed words; nothing is reported as "
                "passing.")
    else:
        status = "measured"
        passed = not bad_ids
        note = ("Per-segment verdicts over measured black / "
                "silence overlap and, where supplied, timed-word "
                "delivery; whole-render loudness / clipping ride "
                "as context only.")
    return {
        "kind": "bad_take_detection",
        "task": "TASK-VYR-060",
        "version": VERIFY_VERSION,
        "status": status,
        "passed": passed,
        "segment_count": len(verdicts),
        "bad_segment_count": len(bad_ids),
        "bad_segment_ids": bad_ids,
        "segments": verdicts,
        "skipped_segments": skipped,
        "audio_context": audio_context,
        "thresholds": {
            "blank_overlap_fail_s": blank_overlap_fail_s,
            "max_single_silence_s": max_single_silence_s,
            "max_silence_ratio": max_silence_ratio,
            "max_stumbles": max_stumbles,
        },
        "basis": note,
    }


def _candidate_segments(candidate: dict[str, Any]) -> list[dict[str, float]]:
    """Measured blank segments for one candidate, from whichever
    measured form the caller carries: ``blackdetect_output``
    (raw ffmpeg text), ``black_intervals`` (media_quality
    shape) or ``black_segments`` (gate shape). No measured form
    -> no segments claimed; the gate then judges an empty list,
    and the caller's evidence shows which form was supplied."""
    if candidate.get("blackdetect_output") is not None:
        return parse_blackdetect(str(candidate["blackdetect_output"]))
    if candidate.get("black_intervals") is not None:
        return blank_segments_from_intervals(candidate["black_intervals"])
    segments = candidate.get("black_segments") or []
    return [{"start": float(s["start"]), "end": float(s["end"]),
             "duration": float(s["duration"])}
            for s in segments if isinstance(s, dict)]


def select_verified_best_take(
        candidates: list[dict[str, Any]], *,
        max_single_blank_s: float = 1.5,
        max_blank_ratio: float = 0.05) -> dict[str, Any]:
    """Best-take selection with blank self-verification first.

    Each candidate is a take dict (``take_id``, ``timed_words``)
    plus its measured blank evidence and ``duration_s``.
    A candidate is excluded — with its evidence recorded — when
    it fails :func:`blank_gate` or carries no ``timed_words``
    to score (an unmeasured take cannot win). The winner is
    :func:`select_best_take` over the survivors. When no
    candidate survives, ``best_take_id`` is None: fail-closed,
    so a blank or unmeasured take is never selected by default.
    """
    if not candidates:
        raise ValueError("at least one candidate is required")
    survivors: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or "take_id" not in candidate:
            raise ValueError("each candidate must be an object with a take_id")
        take_id = str(candidate["take_id"])
        if "duration_s" not in candidate:
            excluded.append({
                "take_id": take_id,
                "reason": "no duration_s — blank gate cannot be "
                          "measured, candidate excluded",
                "blank_gate": None,
            })
            continue
        gate = blank_gate(_candidate_segments(candidate),
                          duration_s=float(candidate["duration_s"]),
                          max_single_blank_s=max_single_blank_s,
                          max_blank_ratio=max_blank_ratio)
        if not gate["passed"]:
            excluded.append({
                "take_id": take_id,
                "reason": "failed blank-frame self-verification",
                "blank_gate": gate,
            })
            continue
        if "timed_words" not in candidate:
            excluded.append({
                "take_id": take_id,
                "reason": "no timed_words — an unmeasured take "
                          "cannot be scored or selected",
                "blank_gate": gate,
            })
            continue
        survivors.append(candidate)
    result: dict[str, Any] = {
        "kind": "verified_best_take_selection",
        "task": "TASK-VYR-061",
        "version": VERIFY_VERSION,
        "excluded": excluded,
        "status": "pending_review",
        "publish": False,
    }
    if not survivors:
        result.update({
            "best_take_id": None,
            "ranking": [],
            "note": "No candidate passed blank-frame "
                    "self-verification with a scoreable "
                    "transcript — fail-closed: no take selected.",
        })
        return result
    selection = select_best_take(survivors)
    result.update({
        "best_take_id": selection["best_take_id"],
        "ranking": selection["ranking"],
        "note": "Winner passed the blank gate and ranked first "
                "on transcript evidence; excluded candidates "
                "carry their gate verdicts above.",
    })
    return result


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
