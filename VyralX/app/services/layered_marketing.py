"""VyralX layered marketing architecture (TASK-VYR-082).

The seven-layer growth system on top of channel_operator, adapted from
the layered AI marketing-team reference architecture (vyralx package
V-03, item DeihbtONYtH), as recorded frame-verbatim on the board:

* Layer 01 SIGNALS — competitor ads, comments & DMs, website visitors,
  lead forms, reviews & mentions, sales calls.
* Layer 02 SYSTEM OF RECORD — customers & deals, ad accounts, content
  calendar, asset library.
* Layer 03 THE BRAIN / Growth Director.
* Layer 05 DEPARTMENTS — market intelligence, paid ads, content studio,
  publishing, lead capture, sales response, nurture & retargeting,
  reputation.
* Layer 06 DATA & OBSERVABILITY — cost per lead, speed to lead, booked
  & paid, ad to customer, agent activity log.
* Layer 07 HUMAN HANDOFF — approvals.

Two honest limits, stated here and in the evidence doc:

* The board record names six layers and skips number 04 — Layer 04 is
  unnamed in the source record, so no fourth layer is invented to fill
  it. The registry below carries the six named layers under their
  source numbers, and the weekly plan says so on its face.
* Only four of the source's eight departments map to VyralX (content
  studio, publishing, market intelligence, reputation). Paid ads, lead
  capture, sales response and nurture & retargeting have no VyralX
  function and are not built; they are listed as unmapped with the
  reason, never silently dropped. Likewise four of the five source
  KPIs (cost per lead, speed to lead, booked & paid, ad to customer)
  have no source data in VyralX — a YouTube channel with no leads
  funnel, no ad accounts and no bookings — so the observability layer
  reports them unavailable with the reason, never estimated.

HARD LIMITS (same as channel_operator, TASK-IG-VYR-01):

* Nothing in this module publishes, uploads, schedules with YouTube,
  posts a comment, or hides a comment. Every output is a proposal
  carrying ``status="pending_review"`` and ``requires_approval=True``;
  schedule entries are plans with ``publish=False`` and privacy
  ``unlisted``. The human handoff is the owner's unlisted review-first
  gate, unchanged: the plan enqueues into the VYR-004 review queue as
  ``pending_review``, and approval stays with the owner.
* Honesty: a layer with no source data says so and produces nothing
  from it — no winner without measured views, no brief without ad
  records, no KPI without a measurement.

Pure functions over plain dicts; deterministic; no network, no clock
dependence except caller-supplied timestamps. Python 3.10.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.services import channel_operator as operator
from app.services import competitor_ads
from app.services import remix_flow
from app.services import trends

LAYERED_VERSION = "vyr082-1"

#: The layers the board record names, under their source numbers.
#: Layer 04 is absent from the record (see LAYER_04_NOTE).
LAYER_NUMBERS: tuple[str, ...] = ("01", "02", "03", "05", "06", "07")

LAYERS: dict[str, dict[str, str]] = {
    "01": {"number": "01", "name": "SIGNALS",
           "description": "competitor ads, comments & DMs, website "
                          "visitors, lead forms, reviews & mentions, "
                          "sales calls"},
    "02": {"number": "02", "name": "SYSTEM OF RECORD",
           "description": "customers & deals, ad accounts, content "
                          "calendar, asset library"},
    "03": {"number": "03", "name": "THE BRAIN / GROWTH DIRECTOR",
           "description": "decides the week's priorities from "
                          "measured evidence"},
    "05": {"number": "05", "name": "DEPARTMENTS",
           "description": "market intelligence, paid ads, content "
                          "studio, publishing, lead capture, sales "
                          "response, nurture & retargeting, reputation"},
    "06": {"number": "06", "name": "DATA & OBSERVABILITY",
           "description": "cost per lead, speed to lead, booked & "
                          "paid, ad to customer, agent activity log"},
    "07": {"number": "07", "name": "HUMAN HANDOFF",
           "description": "approvals — the owner's unlisted "
                          "review-first gate"},
}

LAYER_04_NOTE = (
    "Layer 04 is unnamed in the board record's frame-verbatim source "
    "(vyralx package V-03, item DeihbtONYtH): the record lists layers "
    "01, 02, 03, 05, 06, 07. No fourth layer is invented to fill the "
    "gap; the weekly cycle covers the six named layers."
)

#: Source departments with no VyralX function — listed, never built.
UNMAPPED_DEPARTMENTS: dict[str, str] = {
    "paid_ads": "no ad accounts and no ad spend in VyralX — nothing "
                "to run paid ads against",
    "lead_capture": "no lead forms and no leads funnel in VyralX — "
                    "nothing to capture",
    "sales_response": "no sales calls and no deals pipeline in "
                      "VyralX — nothing to respond to",
    "nurture_retargeting": "no leads list and no retargeting audience "
                           "in VyralX — nobody to nurture",
}

#: Source KPIs with no source data in VyralX — reported, never estimated.
UNMEASURED_SOURCE_KPIS: dict[str, str] = {
    "cost_per_lead": "no leads and no ad spend recorded in VyralX",
    "speed_to_lead": "no leads recorded in VyralX",
    "booked_and_paid": "no bookings or payments in VyralX",
    "ad_to_customer": "no ad accounts in VyralX",
}

#: Platforms a scheduled item is a *candidate* for — plan only, the
#: packaging and cross-posting themselves are the owner's act.
DISTRIBUTION_PLATFORMS: tuple[str, ...] = (
    "youtube_shorts", "instagram_reels", "tiktok", "facebook_reels")

SIGNAL_KINDS: tuple[str, ...] = (
    "competitor_ads", "comments_dms", "website_visitors", "lead_forms",
    "reviews_mentions", "sales_calls")

#: Signal kinds with no VyralX source at all.
_NO_SOURCE_NOTE: dict[str, str] = {
    "website_visitors": "no website-analytics feed in VyralX",
    "lead_forms": "no lead forms in VyralX",
    "sales_calls": "no sales calls in VyralX",
}


# --------------------------------------------------------------------------- #
# Layer 01 — SIGNALS
# --------------------------------------------------------------------------- #
def collect_signals(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Normalise the six Layer 01 signal kinds from caller-supplied data.

    ``raw`` maps kind -> list of records (or None). Kinds with no VyralX
    source are reported ``available=False`` with the reason — never
    synthesised. Competitor-ad records are validated one by one; an
    invalid record is listed with its reason and excluded from the
    valid set, never silently dropped or repaired.
    """
    raw = raw or {}
    kinds: dict[str, Any] = {}
    for kind in SIGNAL_KINDS:
        items = raw.get(kind)
        if kind == "competitor_ads":
            valid: list[dict[str, Any]] = []
            invalid: list[dict[str, Any]] = []
            for i, rec in enumerate(items or []):
                try:
                    valid.append(competitor_ads.normalise_ad(rec, i))
                except ValueError as exc:
                    invalid.append({"index": i, "reason": str(exc)})
            kinds[kind] = {
                "kind": kind, "available": bool(valid),
                "count": len(valid), "items": valid, "invalid": invalid,
                "source": "operator-supplied ad records",
                "note": ("no competitor-ad records supplied — supply an "
                         "ads-library export, manual log or research note")
                        if not valid else None,
            }
        elif kind in _NO_SOURCE_NOTE:
            kinds[kind] = {
                "kind": kind, "available": False, "count": 0,
                "items": [], "invalid": [], "source": None,
                "note": _NO_SOURCE_NOTE[kind],
            }
        else:  # comments_dms, reviews_mentions: caller-supplied lists
            rows: list[dict[str, Any]] = []
            invalid = []
            for i, rec in enumerate(items or []):
                if isinstance(rec, dict):
                    rows.append(rec)
                else:
                    invalid.append({"index": i, "reason": "not an object"})
            kinds[kind] = {
                "kind": kind, "available": bool(rows), "count": len(rows),
                "items": rows, "invalid": invalid,
                "source": "caller-supplied snapshot",
                "note": (f"no {kind.replace('_', ' ')} supplied"
                         if not rows else None),
            }
    available = [k for k, v in kinds.items() if v["available"]]
    return {
        "layer": "01", "name": "SIGNALS", "kinds": kinds,
        "available_kinds": available,
        "missing_kinds": [k for k in SIGNAL_KINDS if k not in available],
    }


# --------------------------------------------------------------------------- #
# Layer 02 — SYSTEM OF RECORD
# --------------------------------------------------------------------------- #
def build_system_of_record(snapshot: dict[str, Any] | None,
                           signals: dict[str, Any] | None = None
                           ) -> dict[str, Any]:
    """Assemble the Layer 02 record from caller-supplied stores.

    ``snapshot`` maps store -> rows (list) or None. Customers & deals
    and ad accounts have no VyralX store and are always unavailable.
    The per-domain pattern (ads / leads / sales) is represented as
    record domains with row counts — the record itself is a plain-dict
    snapshot; persistence stays with the caller's existing database
    (VyralX persists through database.py / Oracle), so no sidecar
    SQLite files are created by this layer.
    """
    snapshot = snapshot or {}
    stores: dict[str, Any] = {}
    for name, note in (
            ("customers_deals", "no CRM store in VyralX"),
            ("ad_accounts", "no ad accounts in VyralX")):
        stores[name] = {"store": name, "available": False, "rows": 0,
                        "items": [], "source": None, "note": note}
    for name in ("content_calendar", "asset_library"):
        rows = [r for r in (snapshot.get(name) or [])
                if isinstance(r, dict)]
        stores[name] = {
            "store": name, "available": bool(rows), "rows": len(rows),
            "items": rows, "source": "caller-supplied snapshot",
            "note": (f"no {name.replace('_', ' ')} supplied"
                     if not rows else None),
        }
    kinds = (signals or {}).get("kinds") or {}
    ads_count = int((kinds.get("competitor_ads") or {}).get("count") or 0)
    domains = {
        "ads": {"domain": "ads", "available": ads_count > 0,
                "rows": ads_count,
                "note": (None if ads_count else
                         "no competitor-ad records in this cycle")},
        "leads": {"domain": "leads", "available": False, "rows": 0,
                  "note": "no leads funnel in VyralX"},
        "sales": {"domain": "sales", "available": False, "rows": 0,
                  "note": "no deals or bookings in VyralX"},
    }
    return {
        "layer": "02", "name": "SYSTEM OF RECORD", "stores": stores,
        "domains": domains,
        "available_stores": [n for n, s in stores.items()
                             if s["available"]],
        "missing_stores": [n for n, s in stores.items()
                           if not s["available"]],
    }


# --------------------------------------------------------------------------- #
# Layer 03 — THE BRAIN / Growth Director
# --------------------------------------------------------------------------- #
def _views_of(video: dict[str, Any]) -> float | None:
    """Measured views for one video, or None when unmeasured."""
    m = video.get("metrics")
    if not isinstance(m, dict):
        return None
    views = m.get("views")
    if not isinstance(views, (int, float)) or views < 0:
        return None
    return float(views)


def _lane_priorities(videos: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank lanes by measured mean views; unmeasured lanes last."""
    totals: dict[str, dict[str, Any]] = {}
    for lane in operator.LANES:
        totals[lane] = {"lane": lane,
                        "label": operator.LANES[lane]["label"],
                        "measured_videos": 0, "views_total": 0,
                        "views_mean": None}
    for v in videos or []:
        lane = str(v.get("lane") or "")
        if lane not in totals:
            continue
        views = _views_of(v)
        if views is None:
            continue
        slot = totals[lane]
        slot["measured_videos"] += 1
        slot["views_total"] += int(views)
    for slot in totals.values():
        if slot["measured_videos"]:
            slot["views_mean"] = (
                slot["views_total"] / slot["measured_videos"])
    ranked = sorted(
        totals.values(),
        key=lambda s: (s["views_mean"] is None,
                       -(s["views_mean"] or 0.0), s["lane"]))
    return ranked


def growth_director_decide(signals: dict[str, Any],
                           record: dict[str, Any],
                           videos: list[dict[str, Any]],
                           candidate_topics: list[dict[str, Any]],
                           *,
                           now: datetime) -> dict[str, Any]:
    """Layer 03: decide the week's priorities from measured evidence.

    Winners and lane priorities come only from measured views; with no
    metrics the decision names no winner and says so. ``next_topics``
    is capped at the weekly slot count and ordered by lane priority.
    Candidates with an unknown lane or an empty topic are skipped with
    the reason recorded — a bad candidate never kills the cycle.
    Recommendations are continue / review / explore; stopping anything
    is a human decision and is never recommended here.
    """
    analysis = operator.analyse_channel(videos or [])
    priorities = _lane_priorities(videos or [])
    lane_rank = {p["lane"]: i for i, p in enumerate(priorities)}
    winning = list(analysis.get("winning_formats") or [])
    chosen: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    slots = len(operator.DEFAULT_SLOTS)
    ordered = sorted(
        enumerate(candidate_topics or []),
        key=lambda pair: (lane_rank.get(str(pair[1].get("lane") or ""), 99),
                          pair[0]))
    for _, cand in ordered:
        if len(chosen) >= slots:
            break
        topic = str(cand.get("topic") or "").strip()
        lane = str(cand.get("lane") or "")
        if not topic:
            skipped.append({"topic": cand.get("topic"), "lane": lane,
                            "reason": "empty topic"})
            continue
        if lane not in operator.LANES:
            skipped.append({"topic": topic, "lane": lane,
                            "reason": f"unknown lane {lane!r}"})
            continue
        chosen.append({"topic": topic, "lane": lane})
    recommendations: list[dict[str, Any]] = []
    if winning:
        recommendations.append({
            "action": "continue", "subject": winning[0],
            "reason": "top measured format by mean views",
            "evidence": {"winning_formats": winning}})
        for fmt in winning[1:]:
            recommendations.append({
                "action": "review", "subject": fmt,
                "reason": "measured but below the top format",
                "evidence": {"winning_formats": winning}})
    formats = analysis.get("formats") or []
    for slot in formats:
        if slot.get("videos") and not slot.get("measured_videos"):
            recommendations.append({
                "action": "explore", "subject": slot["format_name"],
                "reason": "format has videos but no measured views — "
                          "unmeasured, try with measurement",
                "evidence": {"videos": slot["videos"],
                             "measured_videos": 0}})
    for p in priorities:
        if not p["measured_videos"]:
            recommendations.append({
                "action": "explore", "subject": p["lane"],
                "reason": "lane has no measured videos — untried",
                "evidence": {"measured_videos": 0}})
    gaps: list[str] = []
    if not analysis.get("metrics_available"):
        gaps.append("no video in this snapshot carries metrics — no "
                    "winning format can be named")
    for kind in (signals or {}).get("missing_kinds") or []:
        gaps.append(f"signal kind missing: {kind}")
    for store in (record or {}).get("missing_stores") or []:
        gaps.append(f"record store missing: {store}")
    return {
        "layer": "03", "name": "THE BRAIN / GROWTH DIRECTOR",
        "decided_at": now.isoformat(),
        "analysis": analysis,
        "lane_priorities": priorities,
        "winning_formats": winning,
        "next_topics": chosen,
        "skipped_topics": skipped,
        "recommendations": recommendations,
        "gaps": gaps,
    }


# --------------------------------------------------------------------------- #
# Layer 05 — DEPARTMENTS
# --------------------------------------------------------------------------- #
def market_intelligence(valid_ads: list[dict[str, Any]],
                        trend_candidates: list[dict[str, Any]] | None,
                        *,
                        now: datetime) -> dict[str, Any]:
    """Market-intelligence department: competitor brief + trend watch.

    The brief is built only from validated ad records (see Layer 01);
    with none supplied there is no brief — nothing is invented. Trend
    candidates are ranked by the stated heuristic; the ranking is a
    watch list, not a virality prediction.
    """
    brief = None
    note = None
    if valid_ads:
        brief = competitor_ads.pattern_brief(list(valid_ads))
    else:
        note = ("no validated competitor-ad records — supply an "
                "ads-library export, manual log or research note")
    ranked_trends = trends.rank_candidates(
        [c for c in (trend_candidates or []) if isinstance(c, dict)],
        now=now)
    return {
        "department": "market_intelligence",
        "available": bool(brief or ranked_trends),
        "brief": brief,
        "trend_watch": ranked_trends,
        "note": note,
    }


def reputation(comments: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Reputation department: comment drafts + moderation summary.

    Drafts only — nothing is posted or hidden by this layer.
    """
    drafts = operator.draft_comment_replies(comments or [])
    flagged = sum(1 for d in drafts if d.get("action") == "hide")
    return {
        "department": "reputation",
        "available": bool(drafts),
        "drafts": drafts,
        "flagged_hide_suggested": flagged,
        "note": None if drafts else "no comments supplied",
    }


def run_departments(decision: dict[str, Any],
                    week_input: dict[str, Any],
                    signals: dict[str, Any],
                    *,
                    start: datetime,
                    now: datetime) -> dict[str, Any]:
    """Layer 05: the four departments that map to VyralX.

    Content studio drafts packaging for the Brain's chosen topics (one
    proposal per topic — one week of slots). Publishing turns those
    proposals into plan-only schedule entries plus a distribution plan
    (candidate platforms per entry; packaging and cross-posting are the
    owner's act, never executed here). Market intelligence and
    reputation run on the cycle's signals. The four source departments
    with no VyralX function are listed as unmapped with the reason.
    """
    proposals: list[dict[str, Any]] = []
    dropped = 0
    for topic in decision.get("next_topics") or []:
        pack = operator.propose_packaging(
            topic["topic"], topic["lane"], count=1)
        proposals.extend(pack["proposals"])
        dropped += pack["dropped_advice"]
    studio = {
        "department": "content_studio",
        "available": bool(proposals),
        "proposals": proposals,
        "dropped_advice": dropped,
        "topics": decision.get("next_topics") or [],
        "note": None if proposals else "no topics chosen by the Brain",
    }
    schedule = operator.build_schedule(proposals, start)
    distribution = [{
        "slot": entry["slot"],
        "planned_for": entry["planned_for"],
        "title": entry["title"],
        "platforms": list(DISTRIBUTION_PLATFORMS),
        "distribution_planned": True,
        "distribution_executed": False,
        "note": "plan only — packaging and cross-posting are the "
                "owner's act",
    } for entry in schedule]
    publishing = {
        "department": "publishing",
        "available": bool(schedule),
        "schedule": schedule,
        "distribution": distribution,
        "note": None if schedule else "no proposals to schedule",
    }
    kinds = (signals or {}).get("kinds") or {}
    valid_ads = (kinds.get("competitor_ads") or {}).get("items") or []
    intel = market_intelligence(
        valid_ads, (week_input or {}).get("trend_candidates"), now=now)
    rep = reputation((week_input or {}).get("comments"))
    return {
        "layer": "05", "name": "DEPARTMENTS",
        "mapped": {
            "content_studio": studio,
            "publishing": publishing,
            "market_intelligence": intel,
            "reputation": rep,
        },
        "unmapped": dict(UNMAPPED_DEPARTMENTS),
    }


# --------------------------------------------------------------------------- #
# Layer 06 — DATA & OBSERVABILITY
# --------------------------------------------------------------------------- #
def observe_layer_kpis(layers: dict[str, Any],
                       activity_log: list[dict[str, Any]]
                       ) -> dict[str, Any]:
    """Layer 06: per-layer KPIs + the source KPI table.

    The four funnel KPIs have no source data in VyralX and are
    reported unavailable with the reason — never estimated. The agent
    activity log is the one source KPI that is measurable: it is the
    cycle's own log, counted per layer here and carried in full on the
    plan. Channel-native KPIs (measured videos, proposals, schedule
    entries, drafts) are reported alongside.
    """
    source_kpis: dict[str, Any] = {}
    for name, reason in UNMEASURED_SOURCE_KPIS.items():
        source_kpis[name] = {"kpi": name, "available": False,
                             "value": None, "reason": reason}
    by_layer: dict[str, int] = {}
    for entry in activity_log or []:
        layer = str(entry.get("layer") or "?")
        by_layer[layer] = by_layer.get(layer, 0) + 1
    source_kpis["agent_activity_log"] = {
        "kpi": "agent_activity_log", "available": True,
        "value": len(activity_log or []), "by_layer": by_layer,
        "reason": None,
        "note": "full entries are carried on the plan's activity_log",
    }
    signals = layers.get("01") or {}
    record = layers.get("02") or {}
    decision = layers.get("03") or {}
    departments = (layers.get("05") or {}).get("mapped") or {}
    studio = departments.get("content_studio") or {}
    publishing = departments.get("publishing") or {}
    intel = departments.get("market_intelligence") or {}
    rep = departments.get("reputation") or {}
    channel_kpis = {
        "signals_available_kinds":
            len(signals.get("available_kinds") or []),
        "signals_total_items": sum(
            (k.get("count") or 0)
            for k in (signals.get("kinds") or {}).values()),
        "record_available_stores":
            len(record.get("available_stores") or []),
        "winning_formats": len(decision.get("winning_formats") or []),
        "next_topics": len(decision.get("next_topics") or []),
        "proposals": len(studio.get("proposals") or []),
        "dropped_advice": studio.get("dropped_advice") or 0,
        "schedule_entries": len(publishing.get("schedule") or []),
        "comment_drafts": len(rep.get("drafts") or []),
        "flagged_hide_suggested":
            rep.get("flagged_hide_suggested") or 0,
        "trend_watch_items": len(intel.get("trend_watch") or []),
        "brief_available": intel.get("brief") is not None,
    }
    per_layer = {
        "01": {"signals_available_kinds": channel_kpis[
            "signals_available_kinds"],
            "signals_total_items": channel_kpis["signals_total_items"]},
        "02": {"record_available_stores": channel_kpis[
            "record_available_stores"]},
        "03": {"winning_formats": channel_kpis["winning_formats"],
               "next_topics": channel_kpis["next_topics"]},
        "05": {"proposals": channel_kpis["proposals"],
               "schedule_entries": channel_kpis["schedule_entries"],
               "comment_drafts": channel_kpis["comment_drafts"],
               "brief_available": channel_kpis["brief_available"]},
        "06": {"source_kpis_available": sum(
            1 for k in source_kpis.values() if k["available"]),
            "source_kpis_total": len(source_kpis)},
        "07": {"gate": "owner_unlisted_review_first"},
    }
    return {
        "layer": "06", "name": "DATA & OBSERVABILITY",
        "source_kpis": source_kpis,
        "channel_kpis": channel_kpis,
        "per_layer": per_layer,
    }


# --------------------------------------------------------------------------- #
# Layer 07 — HUMAN HANDOFF
# --------------------------------------------------------------------------- #
def human_handoff(plan_kind: str, week_start: datetime) -> dict[str, Any]:
    """Layer 07: the owner's unlisted review-first gate, unchanged.

    Returns the gate record only — approval itself stays with the
    owner. Nothing in the plan this gate covers publishes, uploads or
    schedules with YouTube.
    """
    return {
        "layer": "07", "name": "HUMAN HANDOFF",
        "gate": "owner_unlisted_review_first",
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
        "plan_kind": plan_kind,
        "week_start": week_start.isoformat(),
        "note": "Nothing in this plan publishes, uploads or schedules "
                "with YouTube. The plan enqueues into the VYR-004 "
                "review queue as pending_review; the owner approves "
                "or rejects each item.",
    }


def enqueue_growth_plan(plan: dict[str, Any],
                        queue_path: Path | None = None) -> Path:
    """Append a layered growth plan to the VYR-004 review queue.

    The plan lands as a ``pending_review`` queue entry — the same
    human gate every remix render and operator plan passes through.
    """
    entry = {
        "kind": "layered_marketing_plan",
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
        "plan": plan,
    }
    return remix_flow.enqueue_review(entry, queue_path)


# --------------------------------------------------------------------------- #
# One full weekly cycle
# --------------------------------------------------------------------------- #
def run_weekly_cycle(week_input: dict[str, Any],
                     start: datetime,
                     *,
                     now: datetime | None = None) -> dict[str, Any]:
    """Run one approval-gated weekly cycle and return the growth plan.

    ``week_input``: ``{"videos": [...], "topics": [{"topic","lane"}...],
    "comments": [...], "signals": {kind: [...]}, "record": {store: [...]},
    "trend_candidates": [...]}``. ``start`` is the week start (aware,
    IST); ``now`` defaults to ``start`` so the cycle is deterministic.
    The plan states on its face that it publishes nothing; enqueuing
    it (see :func:`enqueue_growth_plan`) is the caller's choice.
    """
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    now = now or start
    week_input = week_input or {}
    log: list[dict[str, Any]] = []

    def _log(layer: str, action: str, detail: dict[str, Any]) -> None:
        log.append({"layer": layer, "action": action,
                    "at": now.isoformat(), "detail": detail})

    signals = collect_signals(week_input.get("signals"))
    _log("01", "collect_signals", {
        "available_kinds": signals["available_kinds"],
        "total_items": sum(k["count"] for k in signals["kinds"].values())})
    record = build_system_of_record(week_input.get("record"), signals)
    _log("02", "build_system_of_record", {
        "available_stores": record["available_stores"]})
    videos = week_input.get("videos") or []
    decision = growth_director_decide(
        signals, record, videos, week_input.get("topics") or [], now=now)
    _log("03", "growth_director_decide", {
        "winning_formats": decision["winning_formats"],
        "next_topics": len(decision["next_topics"])})
    departments = run_departments(decision, week_input, signals,
                                  start=start, now=now)
    studio = departments["mapped"]["content_studio"]
    publishing = departments["mapped"]["publishing"]
    _log("05", "run_departments", {
        "proposals": len(studio["proposals"]),
        "schedule_entries": len(publishing["schedule"])})
    layers: dict[str, Any] = {
        "01": signals, "02": record, "03": decision, "05": departments,
    }
    handoff = human_handoff("layered_marketing_plan", start)
    # Log the last two steps first: the observability layer reports the
    # activity log, so the log must already hold every entry — including
    # this step and the handoff — when it is counted. Both steps run
    # immediately after their entries are written.
    _log("06", "observe_layer_kpis", {"step": "per-layer KPIs + source "
                                              "KPI table"})
    _log("07", "human_handoff", {"gate": handoff["gate"]})
    kpis = observe_layer_kpis(layers, log)
    layers["06"] = kpis
    layers["07"] = handoff
    mapped = departments["mapped"]
    plan = {
        "kind": "layered_marketing_plan",
        "version": LAYERED_VERSION,
        "week_start": start.isoformat(),
        "layers": layers,
        "layer_numbers": list(LAYER_NUMBERS),
        "layer_04": {"number": "04", "name": None,
                     "status": "unnamed_in_source_record",
                     "note": LAYER_04_NOTE},
        "growth_plan": {
            "topics": decision["next_topics"],
            "proposals": studio["proposals"],
            "schedule": publishing["schedule"],
            "distribution": publishing["distribution"],
            "comment_drafts": mapped["reputation"]["drafts"],
            "trend_watch": mapped["market_intelligence"]["trend_watch"],
            "recommendations": decision["recommendations"],
            "gaps": decision["gaps"],
        },
        "activity_log": log,
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
    }
    return plan
