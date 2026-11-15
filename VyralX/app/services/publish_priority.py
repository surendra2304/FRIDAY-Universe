"""VyralX publish-priority model (TASK-VYR-010).

When the owner's YouTube re-auth lands, VyralX will hold a pool of
already-made videos waiting to go public. This module answers one
narrow question: **in what order should that pool publish?** It scores
every ready video from the production data VyralX actually stored and
ranks the pool strongest-first, with the per-component breakdown kept
visible so the order can be argued with.

HONESTY BANNER — read before trusting any number here. The autopilot
era recorded **no performance data at all**: ``VIDEO_METRICS`` holds
0 rows and ``CONTENT_PACKS`` holds 0 rows (TASK-VYR-005 autopsy,
``docs/AUTOPSY_29_UNLISTED.md``). There are no views, likes, comments,
watch time, or retention figures for any video, and the selection
fields are equally empty (``trend_score`` 0.0, ``trend_query`` and
``trend_source_video_id`` blank for all 46 projects). This model is
therefore **not** a fitted performance predictor and must never be
described as one. It is a transparent heuristic over production
metadata — duration, title packaging, source-title markers, format,
recency — of the kind the TASK-VYR-005 packaging system formalised.
Its weights are stated constants, not learned parameters; there was
nothing to learn them from. The day real metrics exist, the
``engagement`` component below starts firing (weight 0.35) and this
heuristic should be re-validated against them or replaced.

Two flags ride on every legacy-pool row and outrank the score:

* ``HOLD_PROVENANCE`` — the pool's only licence record is the blanket
  string the pre-publish checklist (``app.services.packaging``)
  rejects by name. A high score orders the queue; it does not clear
  the hold. Provenance is per-source evidence or the video does not
  publish.
* ``SYNC_UNVERIFIED`` — every legacy render predates the TASK-VYR-003
  sync fix; the one production render ever measured had 73.6%
  narration coverage. Unmeasured sync is a risk the score cannot see.

Nothing here uploads, schedules, flips privacy, or talks to YouTube.
Pure functions over plain dicts; deterministic; no network.
"""
from __future__ import annotations

import math
import re
from typing import Any, Iterable

MODEL_VERSION = "vyr010-1"

# The blanket self-attestation every legacy SOURCES row carries
# (TASK-VYR-005). The packaging checklist rejects this exact string;
# the priority model flags it instead of silently inheriting it.
BLANKET_LICENCE = (
    "Transformative commentary - original creator credited "
    "(operator policy)"
)

# Weights over the metadata components. Stated, not learned — there is
# no outcome data to learn from (see banner). They sum to 1.0 across
# the components that are present for a given video; a missing
# component renormalises the rest rather than zeroing the video.
WEIGHTS: dict[str, float] = {
    "duration_fit": 0.30,
    "title_strength": 0.30,
    "source_signal": 0.20,
    "format_fit": 0.10,
    "freshness": 0.10,
}

# When per-video metrics exist (views/likes), engagement takes this
# share and the metadata weights scale down by (1 - share). In the
# legacy pool this never fires: metrics coverage is 0 of 46.
ENGAGEMENT_WEIGHT = 0.35

TIER_A_MIN = 70.0
TIER_B_MIN = 55.0

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF☀-➿⬀-⯿️]"
)
_NUMBER_WORDS = {
    "one", "two", "three", "four", "five", "six", "seven", "eight",
    "nine", "ten", "first", "second", "third", "last", "only",
}
_CURIOSITY_WORDS = {
    "why", "secret", "truth", "until", "gone", "wrong", "never",
    "nobody", "no", "one", "knows", "real", "actually", "before",
    "after", "stole", "hidden",
}
_NEGATIONS = {"not", "didn't", "don't", "never", "no", "can't", "won't"}


def _clamp(x: float) -> float:
    return max(0.0, min(1.0, x))


# ---------------------------------------------------------------------------
# Components (each returns 0..1, or None when its input does not exist)
# ---------------------------------------------------------------------------

def duration_fit(seconds: float | None) -> float | None:
    """Fit of a Short's length to the retention-friendly band.

    Under ~15s there is too little to retain anyone; 25–45s is the
    band the owner's researched formats target (40–60s scripts, kept
    under the 60s claim-block line); past 60s a clip leaves the
    Shorts format entirely. A heuristic curve, stated as one.
    """
    if seconds is None or seconds <= 0:
        return None
    s = float(seconds)
    if s < 15:
        return 0.25 + 0.25 * (s / 15)
    if s < 25:
        return 0.5 + 0.3 * ((s - 15) / 10)
    if s <= 45:
        return 0.8 + 0.2 * ((s - 25) / 20)
    if s <= 60:
        return 1.0 - 0.3 * ((s - 45) / 15)
    return max(0.2, 0.7 - 0.02 * (s - 60))


def _emoji_count(text: str) -> int:
    return len(_EMOJI_RE.findall(text))


def title_strength(title: str | None) -> tuple[float | None, list[str]]:
    """Packaging quality of the upload title, per PACKAGING.md rules.

    Sub-scores: length fit (lint caps titles at 60 chars), emoji load
    (1–2 is the researched norm; 0 is plain, 3+ is spam), a concrete
    anchor (a digit, a number word, or a capitalised specific), a
    curiosity device (question, negation, revelation word), and
    clarity (the autopsy era's multi-scene word-salads — three
    unrelated fragments bolted together — are penalised by length in
    words, their most reliable tell).
    """
    if not title or not title.strip():
        return None, ["no title recorded"]
    notes: list[str] = []
    text = title.strip()
    bare = re.sub(r"#\w+", "", text).strip()  # hashtags are not title
    words = bare.split()
    lowered = {w.strip(".,!?:;\"'").lower() for w in words}

    n_chars = len(text)
    if 35 <= n_chars <= 60:
        length_fit = 1.0
    elif n_chars < 35:
        length_fit = 0.5 + 0.5 * (n_chars / 35)
        notes.append("short title")
    elif n_chars <= 80:
        length_fit = 1.0 - 0.4 * ((n_chars - 60) / 20)
        notes.append("over the 60-char lint")
    else:
        length_fit = 0.4
        notes.append("far over the 60-char lint")

    n_emoji = _emoji_count(text)
    if 1 <= n_emoji <= 2:
        emoji_fit = 1.0
    elif n_emoji == 0:
        emoji_fit = 0.55
        notes.append("no emoji (below the formula norm)")
    elif n_emoji == 3:
        emoji_fit = 0.5
        notes.append("emoji-heavy")
    else:
        emoji_fit = 0.25
        notes.append("emoji spam")

    if re.search(r"\d", bare):
        anchor = 1.0
    elif lowered & _NUMBER_WORDS:
        anchor = 0.8
    elif len([w for w in words[1:] if w[:1].isupper()]) >= 2:
        anchor = 0.55
    else:
        anchor = 0.35
        notes.append("no concrete anchor")

    if "?" in bare:
        curiosity = 1.0
    elif lowered & _NEGATIONS:
        curiosity = 0.9
    elif lowered & _CURIOSITY_WORDS:
        curiosity = 0.8
    else:
        curiosity = 0.45
        notes.append("no curiosity device")

    if len(words) > 11:
        clarity = 0.3
        notes.append("word-salad length (multi-fragment title)")
    elif len(words) >= 9:
        clarity = 0.6
    else:
        clarity = 1.0

    score = (length_fit + emoji_fit + anchor + curiosity + clarity) / 5
    return _clamp(score), notes


def source_signal(source_title: str | None) -> float | None:
    """The only demand proxy that exists for the legacy pool.

    Every legacy source was itself a viral video — but its virality
    was never recorded (no source id, no score, no counts), so all
    this component can read is the source title's own packaging
    markers. It is deliberately the second-weakest-weighted
    component and is labelled a proxy wherever it is reported.
    """
    if not source_title or not source_title.strip():
        return None
    text = source_title.strip()
    score = 0.45
    if 1 <= _emoji_count(text) <= 3:
        score += 0.15
    if "!" in text or "?" in text:
        score += 0.15
    if re.search(r"\d", text):
        score += 0.15
    words = text.split()
    if 3 <= len(words) <= 9:
        score += 0.10
    return _clamp(score)


def format_fit(width: int | None, height: int | None) -> float | None:
    """1080x1920 is the pool standard; anything else is a defect."""
    if not width or not height:
        return None
    if (width, height) == (1080, 1920):
        return 1.0
    ratio = width / height
    if height > width and abs(ratio - 0.5625) <= 0.03:
        return 0.85  # 9:16 vertical at another resolution
    if height > width:
        return 0.6  # vertical but off-format (e.g. the 480x600 outlier)
    return 0.3  # landscape / square in a Shorts pool


def freshness(rank_fraction: float | None) -> float | None:
    """Recency within the pool as a weak tiebreak, nothing more.

    ``rank_fraction`` is the video's position between the pool's
    oldest (0.0) and newest (1.0) creation times. The spread is kept
    narrow (0.6..1.0): newer is not better, merely marginally more
    likely to reflect the current pipeline.
    """
    if rank_fraction is None:
        return None
    return 0.6 + 0.4 * _clamp(rank_fraction)


def engagement(metrics: dict[str, Any] | None) -> float | None:
    """Real performance, when it exists. In the legacy pool it doesn't.

    Expects optional ``views`` / ``likes`` keys, log-scaled against
    pool maxima supplied by the caller as ``_pool_max_views`` /
    ``_pool_max_likes``. Returns None when no metrics are present —
    which, for all 46 legacy videos, is always (VIDEO_METRICS is
    empty). Never invent a number to fill this in.
    """
    if not metrics:
        return None
    views = metrics.get("views")
    likes = metrics.get("likes")
    if views is None and likes is None:
        return None
    parts = []
    if views is not None and metrics.get("_pool_max_views"):
        parts.append(
            math.log1p(views) / math.log1p(metrics["_pool_max_views"]))
    if views and likes is not None:
        parts.append(_clamp((likes / views) * 20))  # 5% like-rate -> 1.0
    if not parts:
        return None
    return _clamp(sum(parts) / len(parts))


# ---------------------------------------------------------------------------
# Scoring
# ---------------------------------------------------------------------------

def score_video(row: dict[str, Any],
                pool_oldest: float | None = None,
                pool_newest: float | None = None) -> dict[str, Any]:
    """Score one ready video. ``row`` is a plain dict of stored fields:

    job_id, upload_title, source_title, duration_seconds, width,
    height, created_epoch, job_status, license_name, sync_measured,
    metrics (optional). Missing fields degrade the score by
    renormalisation and are reported in ``missing`` — never invented.
    """
    components: dict[str, float | None] = {}
    notes: list[str] = []

    components["duration_fit"] = duration_fit(row.get("duration_seconds"))

    t_score, t_notes = title_strength(row.get("upload_title"))
    components["title_strength"] = t_score
    notes.extend(t_notes)

    components["source_signal"] = source_signal(row.get("source_title"))
    components["format_fit"] = format_fit(row.get("width"),
                                          row.get("height"))

    frac = None
    created = row.get("created_epoch")
    if (created is not None and pool_oldest is not None
            and pool_newest is not None and pool_newest > pool_oldest):
        frac = (created - pool_oldest) / (pool_newest - pool_oldest)
    components["freshness"] = freshness(frac)

    eng = engagement(row.get("metrics"))
    if eng is not None:
        components["engagement"] = eng

    weights = dict(WEIGHTS)
    if eng is not None:
        weights = {k: v * (1 - ENGAGEMENT_WEIGHT)
                   for k, v in weights.items()}
        weights["engagement"] = ENGAGEMENT_WEIGHT

    present = {k: v for k, v in components.items() if v is not None}
    missing = sorted(set(components) - set(present))
    if eng is None:
        missing.append("engagement (no metrics recorded)")
    total_w = sum(weights[k] for k in present)
    score = (sum(weights[k] * present[k] for k in present) / total_w
             if total_w else 0.0)

    flags: list[str] = []
    if row.get("license_name") == BLANKET_LICENCE:
        flags.append("HOLD_PROVENANCE")
    if not row.get("sync_measured"):
        flags.append("SYNC_UNVERIFIED")
    if eng is None:
        flags.append("METRICS_NO_DATA")
    if row.get("job_status") and row.get("job_status") != "uploaded":
        flags.append("NOT_UPLOADED")

    score100 = round(score * 100, 1)
    tier = ("A" if score100 >= TIER_A_MIN
            else "B" if score100 >= TIER_B_MIN else "C")
    return {
        "job_id": row.get("job_id"),
        "youtube_video_id": row.get("youtube_video_id"),
        "upload_title": row.get("upload_title"),
        "job_status": row.get("job_status"),
        "score": score100,
        "tier": tier,
        "components": {k: (round(v, 3) if v is not None else None)
                       for k, v in components.items()},
        "missing": missing,
        "flags": flags,
        "notes": notes,
        "model_version": MODEL_VERSION,
    }


def rank_videos(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank a pool of ready videos, strongest first.

    Deterministic: score descending, then job_id ascending as the
    tiebreak. Ranks are 1-based positions in publish order — rank 1
    is the video that should go public first once publishing is
    possible AND its flags are cleared.
    """
    rows = list(rows)
    epochs = [r["created_epoch"] for r in rows
              if r.get("created_epoch") is not None]
    oldest = min(epochs) if epochs else None
    newest = max(epochs) if epochs else None
    scored = [score_video(r, oldest, newest) for r in rows]
    scored.sort(key=lambda s: (-s["score"], s["job_id"] or 0))
    for i, s in enumerate(scored, start=1):
        s["rank"] = i
    return scored


def pool_data_profile(rows: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """How much evidence the pool actually carries — for reports.

    This is the honesty instrument: it counts what exists rather than
    letting a ranking imply knowledge the pool does not contain.
    """
    rows = list(rows)
    n = len(rows)
    with_metrics = sum(1 for r in rows if engagement(r.get("metrics")))
    with_source = sum(1 for r in rows if r.get("source_title"))
    trend_scores = {r.get("trend_score") for r in rows}
    return {
        "videos": n,
        "metrics_coverage": f"{with_metrics}/{n}",
        "source_title_coverage": f"{with_source}/{n}",
        "trend_score_values": sorted(
            str(t) for t in trend_scores),
        "engagement_component_active": with_metrics > 0,
        "verdict": (
            "NO outcome data exists for this pool; the ranking is a "
            "metadata heuristic, not a performance prediction."
            if with_metrics == 0 else
            "Partial outcome data exists; validate the heuristic "
            "against it before trusting the order."),
    }
