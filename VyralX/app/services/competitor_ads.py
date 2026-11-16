"""VyralX competitor-ad pattern intelligence (TASK-IG3-VYR-04).

Wave-2 clusters 116 (IG source DeihbtONYtH — scan competitor
ads, find the top performers, draft variants) and 126 (IG
source DdbljkbH5b2 — reverse-engineer viral ads so new creative
starts from proven structures) were both graded PARTIAL:
``creative_audit`` audits a creative the operator already has,
and the only other competitor code (pre-IG
``analytics_predictor.CompetitorInsight``) says in its own basis
line that no competitor data is fetched or measured by VyralX.
Neither scans a set of competitor ads, ranks them, or extracts
their shared pattern. This module does exactly that — over
records the operator supplies:

* :func:`rank_ads` ranks operator-supplied ad records by
  longevity x engagement, and every ranked entry carries the
  evidence the rank was computed from (the exact fields, the
  exact formula) — a rank without evidence is never emitted;
* :func:`extract_patterns` runs ``format_clone.score_hook``
  over the top ads' opening lines and aggregates which hook
  components the winners share;
* :func:`pattern_brief` assembles the draft-only brief: ranked
  table + pattern summary + variant guidance derived from the
  measured components.

Hard boundaries, stated in code and in every output: **no
platform calls, no scraping, no ad-account access, no spend.**
Records arrive from the operator (an ads-library export, a
manual log, a research note); this module measures what it is
given and invents nothing — an ad with no longevity and no
engagement data ranks last with its missing evidence flagged,
never with a fabricated score. The brief is ``draft_only``:
variant *guidance*, not copy, and nothing publishes.

The module carries its own FastAPI router, mounted by
``app.main`` at ``/api/v1`` (``POST /api/v1/competitor-ads/brief``,
``GET /api/v1/competitor-ads/policy``) — the AUDIT-2
production-caller standard.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import math
from datetime import date
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import format_clone

ADS_VERSION = "ig3-vyr04-1"
IG_SOURCES = ("DeihbtONYtH", "DdbljkbH5b2")

#: Engagement weights for the stated heuristic: a comment or a
#: share is a stronger signal than a passive like.
_ENGAGEMENT_WEIGHTS = {"likes": 1, "shares": 2, "comments": 3}


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
def normalise_ad(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Validate one operator-supplied ad record.

    ``advertiser`` and ``hook_text`` are required — an ad whose
    advertiser or opening line is unknown cannot be ranked or
    pattern-extracted, and guessing either would fabricate the
    evidence this module exists to carry.
    """
    if not isinstance(raw, dict):
        raise ValueError(f"ad record #{index} is not an object")
    advertiser = str(raw.get("advertiser") or "").strip()
    hook_text = str(raw.get("hook_text") or "").strip()
    if not advertiser:
        raise ValueError(f"ad record #{index} has no advertiser")
    if not hook_text:
        raise ValueError(
            f"ad record #{index} ({advertiser}) has no hook_text")
    engagement = raw.get("engagement")
    if not isinstance(engagement, dict):
        engagement = {k: raw[k] for k in _ENGAGEMENT_WEIGHTS
                      if raw.get(k) is not None}
    return {
        "advertiser": advertiser,
        "platform": str(raw.get("platform") or ""),
        "hook_text": hook_text,
        "body_text": str(raw.get("body_text") or ""),
        "first_seen": str(raw.get("first_seen") or ""),
        "last_seen": str(raw.get("last_seen") or ""),
        "days_running": raw.get("days_running"),
        "engagement": {k: engagement.get(k)
                       for k in _ENGAGEMENT_WEIGHTS},
        "source_note": str(raw.get("source_note") or ""),
    }


def longevity_days(ad: dict[str, Any]) -> int | None:
    """Days the ad has been running, from the record's own data.

    An explicit ``days_running`` wins; otherwise the span
    between ``first_seen`` and ``last_seen`` (ISO dates).
    ``None`` when the record carries neither — reported as
    missing evidence, never estimated.
    """
    if ad.get("days_running") is not None:
        return int(ad["days_running"])
    first, last = ad.get("first_seen"), ad.get("last_seen")
    if first and last:
        try:
            span = (date.fromisoformat(last)
                    - date.fromisoformat(first)).days
        except ValueError as exc:
            raise ValueError(
                f"ad by {ad['advertiser']!r}: bad ISO date in "
                f"first_seen/last_seen ({exc})") from exc
        return max(span, 0)
    return None


def engagement_score(ad: dict[str, Any]) -> int | None:
    """Weighted engagement total, or ``None`` if unmeasured.

    score = likes + 2*shares + 3*comments over the fields the
    record actually carries; a record with no engagement fields
    at all scores ``None`` (missing evidence), not zero.
    """
    eng = ad.get("engagement") or {}
    present = {k: eng[k] for k in _ENGAGEMENT_WEIGHTS
               if eng.get(k) is not None}
    if not present:
        return None
    return sum(_ENGAGEMENT_WEIGHTS[k] * int(v)
               for k, v in present.items())


# --------------------------------------------------------------------------- #
# Ranking (evidence-carrying)
# --------------------------------------------------------------------------- #
def rank_ads(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank operator-supplied ads, longest-proven first.

    rank_score = longevity_days * (1 + log10(1 + engagement))
    when both are measured; with only one measured, the rank
    rests on that component alone and the basis says so; with
    neither, the ad ranks last with ``rank_score: None``.
    Deterministic: ties break on advertiser, then hook text.
    """
    ranked = []
    for i, raw in enumerate(records):
        ad = normalise_ad(raw, i)
        longevity = longevity_days(ad)
        engagement = engagement_score(ad)
        if longevity is not None and engagement is not None:
            rank_score = round(
                longevity * (1 + math.log10(1 + engagement)), 3)
            basis = "longevity_days x (1 + log10(1 + engagement_score))"
        elif longevity is not None:
            rank_score = float(longevity)
            basis = "longevity_days only — engagement unmeasured"
        elif engagement is not None:
            rank_score = float(engagement)
            basis = "engagement_score only — longevity unmeasured"
        else:
            rank_score = None
            basis = "unrankable — no longevity or engagement evidence"
        ranked.append({
            **ad,
            "evidence": {
                "longevity_days": longevity,
                "engagement_score": engagement,
                "rank_score": rank_score,
                "basis": basis,
            },
        })
    ranked.sort(key=lambda a: (
        a["evidence"]["rank_score"] is None,
        -(a["evidence"]["rank_score"] or 0.0),
        a["advertiser"].casefold(), a["hook_text"].casefold()))
    for position, entry in enumerate(ranked, start=1):
        entry["rank"] = position
    return ranked


# --------------------------------------------------------------------------- #
# Pattern extraction
# --------------------------------------------------------------------------- #
def extract_patterns(ranked: list[dict[str, Any]], *,
                     top_n: int = 5) -> dict[str, Any]:
    """The hook pattern shared by the top-ranked ads.

    Each top ad's opening line is scored by
    ``format_clone.score_hook`` (the fleet's stated hook
    heuristic — named in the output, not a virality predictor);
    the aggregate reports how often each component fires among
    the winners.
    """
    top = ranked[:top_n]
    per_ad = []
    for entry in top:
        hook = format_clone.score_hook(entry["hook_text"])
        per_ad.append({
            "advertiser": entry["advertiser"],
            "rank": entry["rank"],
            "hook_score": hook["score"],
            "checks": hook["checks"],
            "hook_text": hook["hook_text"],
        })
    components = ("question_form", "curiosity_marker",
                  "second_person", "concrete_number", "hook_present")
    rates = {}
    if per_ad:
        for name in components:
            rates[name] = round(
                sum(1 for a in per_ad if a["checks"][name])
                / len(per_ad), 3)
    return {
        "ads_considered": len(per_ad),
        "per_ad": per_ad,
        "component_rates": rates,
        "mean_hook_score": round(
            sum(a["hook_score"] for a in per_ad) / len(per_ad), 3
        ) if per_ad else None,
        "basis": "format_clone.score_hook — stated heuristic, "
                 "not a virality predictor",
    }


def _variant_guidance(patterns: dict[str, Any]) -> list[str]:
    """Draft guidance derived from the measured components.

    Only components the winners actually share (>= 60%) become
    guidance; a component the winners do not share is reported
    as absent, never recommended.
    """
    rates = patterns.get("component_rates") or {}
    guidance = []
    labels = {
        "question_form": "open with a question",
        "curiosity_marker": "include a curiosity marker "
                            "(secret / nobody tells you / stop)",
        "second_person": "address the viewer directly (you/your)",
        "concrete_number": "name a concrete number early",
        "hook_present": "land the hook inside the first "
                        "~3 seconds of speech",
    }
    for name, label in labels.items():
        rate = rates.get(name)
        if rate is not None and rate >= 0.6:
            guidance.append(f"{label} — shared by {rate:.0%} of "
                            f"the top ads measured")
    if not guidance:
        guidance.append(
            "no hook component is shared by >= 60% of the top "
            "ads — the winners do not agree on a hook pattern; "
            "draft variants per-ad from the per-ad table instead")
    return guidance


def pattern_brief(records: list[dict[str, Any]], *,
                  top_n: int = 5) -> dict[str, Any]:
    """The draft-only competitor pattern brief."""
    if not records:
        raise ValueError("at least one ad record is required")
    ranked = rank_ads(records)
    patterns = extract_patterns(ranked, top_n=top_n)
    return {
        "kind": "competitor_ad_pattern_brief",
        "version": ADS_VERSION,
        "ig_sources": list(IG_SOURCES),
        "records_received": len(records),
        "ranked": ranked,
        "patterns": patterns,
        "variant_guidance": _variant_guidance(patterns),
        "status": "draft_only",
        "publish": False,
        "platform_calls": "none — records are operator-supplied; "
                          "no platform was queried",
        "spend": "none",
        "note": "Ranks rest only on the evidence each record "
                "carries; unmeasured ads are flagged, never "
                "scored by invention.",
    }


# --------------------------------------------------------------------------- #
# Router (mounted by app.main — the production path)
# --------------------------------------------------------------------------- #
router = APIRouter()


class BriefRequest(BaseModel):
    ads: list[dict[str, Any]]
    top_n: int = 5


@router.get("/competitor-ads/policy")
def competitor_ads_policy() -> dict[str, Any]:
    return {
        "version": ADS_VERSION,
        "ig_sources": list(IG_SOURCES),
        "input": "operator-supplied ad records only",
        "platform_calls": "none",
        "spend": "none",
        "status": "draft_only",
        "publish": False,
        "engagement_weights": dict(_ENGAGEMENT_WEIGHTS),
        "note": "This measures ads the operator supplies (an "
                "ads-library export or a manual log). It never "
                "queries a platform, accesses an ad account, or "
                "spends anything.",
    }


@router.post("/competitor-ads/brief")
def competitor_ads_brief(req: BriefRequest) -> dict[str, Any]:
    try:
        return pattern_brief(req.ads, top_n=req.top_n)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
