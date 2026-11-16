"""VyralX measured-style editing recipes — "cooked" pattern (TASK-IG2-VYR-06).

Pattern adapted from nextwork-projects/ai-video-editor-cooked (MIT;
spec card ``ai-video-editor-cooked.md``, IG source DeihXkGDQV0):
analyse reference videos that share one editing format ONCE into a
saved, reusable **style profile** (cut speed, zooms, captions, cards,
graphics, sound), clean a talking-head transcript (retakes / false
starts / pauses), then apply the style through STAGED approvals —
cut -> look -> render.

BINDING ADAPTATION RULE: upstream is driven by a PAID Claude plan/API.
That driver is not used here — measurement and application are
deterministic VyralX-native code over supplied edit/transcript data
(the fleet's own tooling), so the recipe runs FREE and unattended.
The ~1.5GB Remotion render stack likewise stays off the fleet: this
module emits render PLANS for the existing VyralX renderer, gated by
the staged approvals.

A stage cannot be skipped: :func:`advance_stage` only moves
cut -> look -> render in order, each transition is an explicit
approval record, and a plan at any stage stays ``pending_review``
until its current stage is approved. No network. Python 3.10.
"""
from __future__ import annotations

import re
from statistics import median
from typing import Any

RECIPE_VERSION = "ig2-vyr06-1"
STAGES = ("cut", "look", "render")


def measure_style(references: list[dict[str, Any]], *, name: str) -> dict[str, Any]:
    """Measure 3-6 same-format references into one reusable style.

    Each reference supplies MEASURED data (from VyralX's own analysis
    tooling — format_clone keyframes/transcripts, media probes):
    ``{"duration_seconds", "cuts", "zooms", "caption_words",
    "caption_seconds", "cards", "graphics", "sound_cues"}``.
    Medians are used so one outlier reference cannot bend the style.
    Fewer than 3 references is refused: a style from one video is an
    anecdote, not a format.
    """
    if not (3 <= len(references) <= 6):
        raise ValueError("a style needs 3-6 reference videos sharing one format")
    def per_min(key: str) -> float:
        vals = [float(r[key]) / (float(r["duration_seconds"]) / 60.0)
                for r in references if float(r.get("duration_seconds", 0)) > 0]
        return round(median(vals), 3) if vals else 0.0
    total_cap_words = sum(float(r.get("caption_words", 0)) for r in references)
    total_cap_secs = sum(float(r.get("caption_seconds", 0)) for r in references)
    return {"version": RECIPE_VERSION, "name": name,
            "references": len(references),
            "cuts_per_minute": per_min("cuts"),
            "zooms_per_minute": per_min("zooms"),
            "cards_per_minute": per_min("cards"),
            "graphics_per_minute": per_min("graphics"),
            "sound_cues_per_minute": per_min("sound_cues"),
            "caption_coverage": round(total_cap_words / total_cap_secs, 2)
            if total_cap_secs else 0.0,
            "measured": True,
            "basis": "medians of supplied per-reference measurements; "
                     "no reference media or words are stored"}


_FALSE_STARTS = ("um", "uh", "er", "like i said", "wait no", "sorry")


def clean_transcript(timed_words: list[dict[str, Any]], *,
                     pause_gap: float = 1.0) -> dict[str, Any]:
    """Cut retakes/false starts/pauses from a timed transcript.

    Deterministic rules: a word repeated immediately (retake) drops
    the first take; a false-start marker drops itself and the word
    before it restarts cleanly; gaps >= ``pause_gap`` become explicit
    pause cuts. Returns the kept words + a cut list — the raw
    transcript is never mutated.
    """
    kept, cuts, prev = [], [], None
    for i, w in enumerate(timed_words):
        word = str(w["word"]).lower()
        if prev is not None and word == str(prev["word"]).lower():
            cuts.append({"kind": "retake", "word": word, "at": w["start"],
                         "dropped_index": i - 1})
            kept.pop()  # drop first take, keep the retake
        if word in _FALSE_STARTS:
            cuts.append({"kind": "false_start", "word": word, "at": w["start"]})
            prev = w
            continue
        if prev is not None and float(w["start"]) - float(prev["end"]) >= pause_gap:
            cuts.append({"kind": "pause", "at": prev["end"],
                         "seconds": round(float(w["start"]) - float(prev["end"]), 2)})
        kept.append(w)
        prev = w
    return {"kept_words": kept, "cuts": cuts,
            "kept_count": len(kept), "cut_count": len(cuts)}


def apply_style(style: dict[str, Any], cleaned: dict[str, Any], *,
                duration_seconds: float, lane: str = "tech_ai") -> dict[str, Any]:
    """Apply a measured style to cleaned footage -> staged edit plan."""
    if not style.get("measured"):
        raise ValueError("only a measured style profile can be applied")
    mins = max(duration_seconds / 60.0, 0.01)
    plan = {"version": RECIPE_VERSION, "style": style["name"], "lane": lane,
            "duration_seconds": duration_seconds,
            "target_cuts": round(style["cuts_per_minute"] * mins),
            "target_zooms": round(style["zooms_per_minute"] * mins),
            "target_cards": round(style["cards_per_minute"] * mins),
            "caption_words_per_second": style["caption_coverage"],
            "transcript_cuts": cleaned["cuts"],
            "stage": "cut", "approvals": [], "status": "pending_review",
            "privacy": "unlisted", "publish": False,
            "driver": "vyralx_deterministic",
            "paid_driver_used": False}
    return plan


def advance_stage(plan: dict[str, Any], *, approved_by: str) -> dict[str, Any]:
    """Approve the current stage and advance cut -> look -> render.

    Skipping is impossible by construction: the only transition is
    from the plan's current stage to the next one, and the final
    stage's approval marks the plan ``approved_for_render`` — it
    still publishes nothing.
    """
    stage = plan["stage"]
    if stage == "done":
        raise ValueError("plan already completed all stages")
    out = {**plan, "approvals": plan.get("approvals", []) +
           [{"stage": stage, "approved_by": approved_by}]}
    idx = STAGES.index(stage)
    if idx == len(STAGES) - 1:
        out["stage"] = "done"
        out["status"] = "approved_for_render"
    else:
        out["stage"] = STAGES[idx + 1]
        out["status"] = "pending_review"
    return out
