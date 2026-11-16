"""VyralX viral idea generator (TASK-IG3-VYR-08).

Cluster 125 (IG source DdbljkbH5b2 — the carousel's automation
7, "Viral YouTube Video Idea Generator") describes the shape
in one line: fetch top-performing videos in a niche, analyse
titles / keywords / engagement, generate fresh ideas. It was
graded PARTIAL: ``youtube_analytics.extract_top_performing_
topics`` reads the channel's OWN metrics records and
``channel_operator`` proposes packaging for the channel's own
stats, but nothing analysed a *niche's* top performers and
turned the analysis into ranked ideas — supervisor AUDIT-2
re-confirmed the gap.

This module is the analysis + generation half, built the way
the lane's other adapters are built:

* input is **operator-supplied niche top-performer records**
  (title plus whatever metrics the operator actually has —
  e.g. exported from the YouTube API by the operator). The
  module makes **no platform calls**: fetching is the
  operator's step, exactly as cluster 116/126's competitor
  module takes operator-supplied ad records;
* :func:`analyse_performers` extracts title keywords
  (deterministic tokenisation) and computes an engagement
  rate ONLY where the record carries the numbers for it
  (views + likes/comments). A record without metrics gets
  ``engagement_rate: None`` — never an invented figure;
* :func:`generate_ideas` recombines the niche's proven
  keywords into candidate titles using the title patterns
  observed in the supplied top performers themselves, scores
  each candidate's hook with ``format_clone.score_hook``, and
  ranks deterministically: evidence first (how many top
  performers carry the idea's keywords, weighted by their
  measured engagement where it exists), hook score as the
  tie-break. Every idea carries its provenance — the source
  titles it derives from.

Honesty boundaries: keyword frequency among supplied records
is evidence about THOSE records, not a virality prediction;
ideas are drafts for the review queue (``pending_review``,
``publish: False``), and an idea derived from unmeasured
records says so.

The module carries its own FastAPI router, mounted by
``app.main`` at ``/api/v1`` (``POST
/api/v1/idea-generator/analyse``, ``POST
/api/v1/idea-generator/generate``, ``GET
/api/v1/idea-generator/policy``) — the AUDIT-2
production-caller standard.

Pure stdlib + FastAPI router; Python 3.10.
"""
from __future__ import annotations

import re
from collections import Counter
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services import format_clone

IDEA_VERSION = "ig3-vyr08-1"
IG_SOURCES = ("DdbljkbH5b2",)

_WORD_RE = re.compile(r"[a-z0-9]+")
_STOPWORDS = frozenset({
    "a", "an", "the", "of", "to", "in", "on", "for", "and",
    "or", "with", "how", "why", "what", "is", "are", "was",
    "i", "you", "your", "my", "this", "that", "it", "its",
    "vs", "from", "at", "by", "do", "does", "did", "will",
    "can", "should", "top", "best",
})

#: Title patterns, each observed in real top-performer titles
#: or in the lane's own hook vocabulary. A pattern is only
#: used when it can be filled from niche evidence.
_PATTERNS = (
    "{kw1} — what nobody tells you",
    "{kw1} in {number} minutes: a beginner's guide",
    "Why {kw1} beats {kw2} (and when it doesn't)",
    "{number} {kw1} mistakes that kill your {kw2}",
    "How {kw1} actually works",
)


def _keywords(title: str) -> list[str]:
    return [w for w in _WORD_RE.findall(str(title).casefold())
            if w not in _STOPWORDS and len(w) > 2]


def _engagement_rate(record: dict[str, Any]) -> float | None:
    """(likes + comments) / views — only when measured.

    Returns None when the record does not carry the numbers;
    an unmeasured performer is reported as unmeasured, never
    assigned a plausible-looking rate.
    """
    views = record.get("views")
    if views is None or float(views) <= 0:
        return None
    likes = record.get("likes")
    comments = record.get("comments")
    if likes is None and comments is None:
        return None
    return round((float(likes or 0) + float(comments or 0))
                 / float(views), 4)


def analyse_performers(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Analyse supplied niche top performers.

    Returns per-record evidence (keywords + measured
    engagement or None) and the niche keyword table ranked by
    how many top performers carry each keyword.
    """
    if not records:
        raise ValueError("at least one performer record is "
                         "required — an empty niche proves "
                         "nothing")
    analysed = []
    counts: Counter[str] = Counter()
    for record in records:
        title = str(record.get("title", "")).strip()
        if not title:
            raise ValueError("each performer record must "
                             "carry a title")
        kws = _keywords(title)
        counts.update(set(kws))
        analysed.append({
            "title": title,
            "channel": record.get("channel"),
            "keywords": kws,
            "engagement_rate": _engagement_rate(record),
        })
    keyword_table = [
        {"keyword": kw, "performer_count": n}
        for kw, n in sorted(counts.items(),
                            key=lambda kv: (-kv[1], kv[0]))
    ]
    return {
        "kind": "niche_performer_analysis",
        "version": IDEA_VERSION,
        "ig_sources": list(IG_SOURCES),
        "performer_count": len(analysed),
        "measured_count": sum(
            1 for a in analysed
            if a["engagement_rate"] is not None),
        "performers": analysed,
        "keywords": keyword_table,
        "basis": "keyword frequency among the supplied "
                 "records; engagement computed only from "
                 "supplied views/likes/comments — unmeasured "
                 "records carry None, never an estimate",
    }


def generate_ideas(records: list[dict[str, Any]], *,
                   max_ideas: int = 10) -> dict[str, Any]:
    """Ranked fresh ideas from the niche's own evidence.

    Deterministic: candidates are pattern fills over the
    niche's top keyword pairs; the evidence score is the
    number of supplied top performers carrying the idea's
    keywords (plus their measured engagement where it
    exists); ``format_clone.score_hook`` breaks ties. Same
    records -> same ideas, same order.
    """
    analysis = analyse_performers(records)
    keywords = [k["keyword"] for k in analysis["keywords"]]
    if len(keywords) < 2:
        raise ValueError("the supplied performers share too "
                         "few keywords to recombine — supply "
                         "more niche records")
    ideas: list[dict[str, Any]] = []
    seen: set[str] = set()
    pairs = [(keywords[i], keywords[j])
             for i in range(min(4, len(keywords)))
             for j in range(i + 1, min(5, len(keywords)))]
    for kw1, kw2 in pairs:
        for pattern in _PATTERNS:
            title = pattern.format(
                kw1=kw1.title(), kw2=kw2, number=5)
            if title in seen:
                continue
            seen.add(title)
            sources = [a for a in analysis["performers"]
                       if kw1 in a["keywords"]
                       or kw2 in a["keywords"]]
            measured = [a["engagement_rate"] for a in sources
                        if a["engagement_rate"] is not None]
            evidence = len(sources) + (
                round(sum(measured), 4) if measured else 0.0)
            ideas.append({
                "title": title,
                "keywords": [kw1, kw2],
                "evidence_score": round(evidence, 4),
                "measured_support": len(measured),
                "hook": format_clone.score_hook(title),
                "derived_from": [a["title"] for a in sources],
                "basis": "keyword overlap with supplied top "
                         "performers"
                         + (" + their measured engagement"
                            if measured else
                            " (sources unmeasured — no "
                            "engagement claimed)"),
            })
    ideas.sort(key=lambda idea: (
        -idea["evidence_score"],
        -idea["hook"]["score"],
        idea["title"]))
    for position, idea in enumerate(ideas[:max_ideas], start=1):
        idea["rank"] = position
    return {
        "kind": "viral_idea_generation",
        "version": IDEA_VERSION,
        "ig_sources": list(IG_SOURCES),
        "niche_performer_count": analysis["performer_count"],
        "ideas": ideas[:max_ideas],
        "status": "pending_review",
        "publish": False,
        "note": "Ideas are drafts ranked by evidence from the "
                "supplied records — keyword overlap is not a "
                "virality prediction, and no idea publishes "
                "from here.",
    }


# --------------------------------------------------------------------------- #
# Router (mounted by app.main — the production path)
# --------------------------------------------------------------------------- #
router = APIRouter()


class PerformersRequest(BaseModel):
    records: list[dict[str, Any]]
    max_ideas: int = 10


@router.get("/idea-generator/policy")
def idea_generator_policy() -> dict[str, Any]:
    return {
        "version": IDEA_VERSION,
        "ig_sources": list(IG_SOURCES),
        "input": "operator-supplied niche top-performer "
                 "records — this module makes no platform "
                 "calls",
        "metrics": "engagement computed only from supplied "
                   "numbers; unmeasured records carry None",
        "status": "pending_review",
        "publish": False,
    }


@router.post("/idea-generator/analyse")
def idea_generator_analyse(req: PerformersRequest) -> dict[str, Any]:
    try:
        return analyse_performers(req.records)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@router.post("/idea-generator/generate")
def idea_generator_generate(req: PerformersRequest) -> dict[str, Any]:
    try:
        return generate_ideas(req.records,
                              max_ideas=req.max_ideas)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
