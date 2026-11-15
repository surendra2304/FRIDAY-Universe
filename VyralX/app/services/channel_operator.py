"""VyralX channel operator (TASK-IG-VYR-01).

The IG reference corpus (source Deg194ZD1eE, cluster with DeihbtONYtH
and DeLzxP1ky98) shows an agent running a YouTube channel end to end:
read the analytics, find the winning formats, write the next titles /
hooks / descriptions, schedule the week, and handle comments — with a
human approving before anything posts. The tool in the video (Uplika)
is a PAID hosted MCP service; the repo card's verdict is **adapt**, so
this module implements the *pattern* natively in VyralX and never
touches the service.

HARD LIMITS (owner direction, REMIX_POLICY, VYR-004/009 gates):

* The operator NEVER publishes, uploads, schedules with YouTube, posts
  a comment, or hides a comment. YouTube OAuth is dead; even when it
  returns, publishing is the owner's act. Every output below is a
  proposal carrying ``status="pending_review"`` and
  ``requires_approval=True``; schedule entries are plans with
  ``publish=False`` and the only privacy VyralX uses, ``unlisted``.
* Analytics honesty: production ``VIDEO_METRICS`` holds 0 rows
  (TASK-VYR-005 autopsy; TASK-VYR-010 banner). If a channel snapshot
  carries no metrics, :func:`analyse_channel` says so
  (``metrics_available=False``) and names NO winning format — a
  "winner" derived from no views would be a fabricated result. When
  metrics do exist, winners are simple stated aggregates over them,
  not a fitted model.
* Packaging proposals are screened with the compliance gate's
  finance-advice finder: a candidate whose text trips it is dropped
  and counted, never quietly kept. Money content is stories, never
  advice.

Pure functions over plain dicts; deterministic; no network, no clock
dependence except the caller-supplied timestamps. Python 3.10.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Iterable

from app.services import compliance_gate, publish_priority, remix_flow

OPERATOR_VERSION = "ig-vyr01-1"

# The three owner-approved lanes (2026-11-15) and the packaging shapes
# each lane publishes in. Titles are templates over a topic, never
# claims about performance.
LANES: dict[str, dict[str, Any]] = {
    "space_science": {
        "label": "Space & science",
        "title_templates": [
            "{topic} — What the Cameras Actually Caught",
            "The Untold Story of {topic}",
            "{topic}, Explained by the Footage Itself",
            "Why {topic} Still Amazes Scientists",
            "{topic}: A Front-Row Seat",
        ],
        "hook_templates": [
            "This is real footage — no CGI, no artist's impression.",
            "Watch what happens in the first ten seconds.",
            "Everything you are about to see actually happened.",
        ],
    },
    "history": {
        "label": "History / did-you-know",
        "title_templates": [
            "The Strange True Story of {topic}",
            "Did You Know? {topic}",
            "{topic} — The Part History Class Skipped",
            "How {topic} Changed Everything",
            "{topic}: A Story Nobody Believed at First",
        ],
        "hook_templates": [
            "This sounds made up. It is documented history.",
            "Stay for the twist at the end — it is the best part.",
            "Nobody believed this story until the records surfaced.",
        ],
    },
    "tech_ai": {
        "label": "Tech & AI explainers",
        "title_templates": [
            "{topic}, Explained Simply",
            "How {topic} Actually Works",
            "{topic} — Step by Step, No Jargon",
            "The Idea Behind {topic}, Visualised",
            "What Is {topic}? A Plain-English Tour",
        ],
        "hook_templates": [
            "No maths background needed — we build this from zero.",
            "By the end, this will feel obvious. Watch.",
            "One idea, built up piece by piece.",
        ],
    },
}

# Weekly posting slots (IST) the operator plans against. Planning only:
# an entry here is a proposal for the owner, not a YouTube schedule.
DEFAULT_SLOTS: tuple[tuple[int, str], ...] = (
    (0, "18:00"),  # Monday
    (2, "18:00"),  # Wednesday
    (4, "18:00"),  # Friday
)
IST = timezone(timedelta(hours=5, minutes=30))


# --------------------------------------------------------------------------- #
# Analytics
# --------------------------------------------------------------------------- #
def _metrics_of(video: dict[str, Any]) -> dict[str, Any] | None:
    m = video.get("metrics")
    if not isinstance(m, dict):
        return None
    views = m.get("views")
    if not isinstance(views, (int, float)) or views < 0:
        return None
    return m


def analyse_channel(videos: Iterable[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate a channel snapshot into per-format performance facts.

    ``videos`` are dicts with ``title``, ``lane``, ``format_name`` and
    an optional ``metrics`` dict (``views``, ``likes``, ``comments``).
    A format is only ranked when at least one of its videos carries
    metrics; with no metrics anywhere the result names no winner and
    explains why (see module docstring).
    """
    rows = list(videos)
    formats: dict[str, dict[str, Any]] = {}
    measured = 0
    for v in rows:
        fmt = str(v.get("format_name") or "unknown")
        slot = formats.setdefault(fmt, {
            "format_name": fmt, "videos": 0, "measured_videos": 0,
            "views_total": 0, "views_mean": None,
            "engagement_rate_mean": None, "_eng": [],
        })
        slot["videos"] += 1
        m = _metrics_of(v)
        if m is None:
            continue
        measured += 1
        slot["measured_videos"] += 1
        slot["views_total"] += int(m["views"])
        likes = m.get("likes") or 0
        comments = m.get("comments") or 0
        if m["views"]:
            slot["_eng"].append((likes + comments) / m["views"])
    for slot in formats.values():
        if slot["measured_videos"]:
            slot["views_mean"] = slot["views_total"] / slot["measured_videos"]
        if slot["_eng"]:
            slot["engagement_rate_mean"] = (
                sum(slot["_eng"]) / len(slot["_eng"]))
        del slot["_eng"]
    metrics_available = measured > 0
    ranked = sorted(
        (s for s in formats.values() if s["views_mean"] is not None),
        key=lambda s: (-s["views_mean"], s["format_name"]))
    notes: list[str] = []
    if not metrics_available:
        notes.append(
            "no video in this snapshot carries metrics — no winning "
            "format can be named (production VIDEO_METRICS is empty; "
            "see TASK-VYR-005/010). Winners appear here only when real "
            "view data does.")
    elif len(ranked) < len(formats):
        notes.append(
            "formats without measured videos are listed but unranked.")
    return {
        "operator_version": OPERATOR_VERSION,
        "video_count": len(rows),
        "measured_videos": measured,
        "metrics_available": metrics_available,
        "formats": [formats[k] for k in sorted(formats)],
        "winning_formats": [s["format_name"] for s in ranked],
        "basis": "measured_views" if metrics_available else "none",
        "notes": notes,
    }


# --------------------------------------------------------------------------- #
# Packaging proposals (titles / hooks / descriptions)
# --------------------------------------------------------------------------- #
def _screen_text(text: str) -> list[dict[str, str]]:
    """Finance-advice screen shared by every operator output."""
    return compliance_gate.find_finance_advice(text)


def propose_packaging(topic: str, lane: str, count: int = 5) -> dict[str, Any]:
    """Deterministic title/hook/description candidates for one topic.

    Candidates are template-built from the lane's shapes and scored
    with the VYR-010 title-strength heuristic (a stated heuristic, not
    a performance prediction). Any candidate whose combined text trips
    the compliance gate's finance-advice finder is dropped and
    counted in ``dropped_advice``.
    """
    lane_def = LANES.get(lane)
    if lane_def is None:
        raise ValueError(
            f"unknown lane {lane!r}; expected one of {sorted(LANES)}")
    topic = str(topic or "").strip()
    if not topic:
        raise ValueError("topic must not be empty")
    titles = lane_def["title_templates"]
    hooks = lane_def["hook_templates"]
    proposals: list[dict[str, Any]] = []
    dropped = 0
    for i in range(max(0, count)):
        title = titles[i % len(titles)].format(topic=topic)
        hook = hooks[i % len(hooks)]
        description = (
            f"{hook} {title}. Original commentary over properly "
            f"licensed footage; sources and licences are recorded in "
            f"the video's provenance record. {lane_def['label']} — "
            f"a VyralX short.")
        hits = _screen_text(f"{title}\n{hook}\n{description}")
        if hits:
            dropped += 1
            continue
        score, _flags = publish_priority.title_strength(title)
        proposals.append({
            "topic": topic,
            "lane": lane,
            "title": title,
            "hook": hook,
            "description": description,
            "title_strength": score,
            "status": "pending_review",
            "requires_approval": True,
            "publish": False,
        })
    return {
        "topic": topic,
        "lane": lane,
        "proposals": proposals,
        "dropped_advice": dropped,
    }


# --------------------------------------------------------------------------- #
# Schedule planning (never a platform schedule)
# --------------------------------------------------------------------------- #
def build_schedule(proposals: Iterable[dict[str, Any]],
                   start: datetime,
                   slots: tuple[tuple[int, str], ...] = DEFAULT_SLOTS
                   ) -> list[dict[str, Any]]:
    """Assign proposals to weekly slots from ``start`` (aware, IST).

    Returns plan entries only: ``publish`` is always False and privacy
    is always ``unlisted`` — the owner's review is what turns a plan
    into anything else, outside this module.
    """
    if start.tzinfo is None:
        raise ValueError("start must be timezone-aware")
    start = start.astimezone(IST)
    ordered_slots = sorted(slots)
    entries: list[dict[str, Any]] = []
    day = start.date()
    idx = 0
    pending = list(proposals)
    while pending:
        for weekday, hhmm in ordered_slots:
            if not pending:
                break
            delta = (weekday - day.weekday()) % 7
            when = datetime.combine(
                day + timedelta(days=delta),
                datetime.strptime(hhmm, "%H:%M").time(), tzinfo=IST)
            if when <= start and delta == 0:
                continue
            prop = pending.pop(0)
            entries.append({
                "slot": idx,
                "planned_for": when.isoformat(),
                "title": prop.get("title"),
                "topic": prop.get("topic"),
                "lane": prop.get("lane"),
                "privacy": "unlisted",
                "status": "pending_review",
                "requires_approval": True,
                "publish": False,
            })
            idx += 1
        day = day + timedelta(days=7)
    return entries


# --------------------------------------------------------------------------- #
# Comment handling (drafts and suggested actions — nothing is posted)
# --------------------------------------------------------------------------- #
_SPAM_MARKERS = ("subscribe back", "sub4sub", "check my channel",
                 "free money", "crypto giveaway", "whatsapp me")
_QUESTION_MARKERS = ("?", "how", "why", "what", "when", "which")


def draft_comment_replies(comments: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Draft a reply (or a suggested moderation action) per comment.

    Every draft is ``draft_pending_approval``; a spam-shaped comment
    gets a *suggested* ``hide`` action that is equally approval-gated.
    The operator posts nothing and hides nothing.
    """
    drafts: list[dict[str, Any]] = []
    for c in comments:
        text = str(c.get("text") or "")
        low = text.casefold()
        entry: dict[str, Any] = {
            "comment_id": c.get("comment_id"),
            "author": c.get("author"),
            "status": "draft_pending_approval",
            "requires_approval": True,
            "posted": False,
        }
        if any(m in low for m in _SPAM_MARKERS):
            entry["action"] = "hide"
            entry["reply"] = None
            entry["reason"] = "spam-shaped comment; hiding still needs approval"
        elif any(m in low for m in _QUESTION_MARKERS):
            entry["action"] = "reply"
            entry["reply"] = (
                "Great question — the sources and licences for the "
                "footage are listed in the video description, and a "
                "longer explainer on this is in the works. Thanks for "
                "watching!")
            entry["reason"] = "question; drafted an informational reply"
        else:
            entry["action"] = "reply"
            entry["reply"] = "Thanks for watching — glad it landed!"
            entry["reason"] = "general comment; drafted a thank-you reply"
        drafts.append(entry)
    return drafts


# --------------------------------------------------------------------------- #
# One full operator cycle
# --------------------------------------------------------------------------- #
def run_operator_cycle(snapshot: dict[str, Any],
                       start: datetime) -> dict[str, Any]:
    """Run one approval-gated operator cycle over a channel snapshot.

    ``snapshot``: ``{"videos": [...], "topics": [{"topic","lane"}...],
    "comments": [...]}``. Returns the full plan; enqueuing it (see
    :func:`enqueue_operator_plan`) is the caller's choice. The plan
    states on its face that it publishes nothing.
    """
    analysis = analyse_channel(snapshot.get("videos") or [])
    proposals: list[dict[str, Any]] = []
    dropped_total = 0
    for t in snapshot.get("topics") or []:
        pack = propose_packaging(str(t.get("topic") or ""),
                                 str(t.get("lane") or ""))
        proposals.extend(pack["proposals"])
        dropped_total += pack["dropped_advice"]
    schedule = build_schedule(proposals, start)
    drafts = draft_comment_replies(snapshot.get("comments") or [])
    return {
        "kind": "channel_operator_plan",
        "operator_version": OPERATOR_VERSION,
        "analysis": analysis,
        "proposals": proposals,
        "dropped_advice": dropped_total,
        "schedule": schedule,
        "comment_drafts": drafts,
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
    }


def enqueue_operator_plan(plan: dict[str, Any],
                          queue_path: Any = None) -> Any:
    """Append an operator plan to the VYR-004 review queue.

    The plan lands as a ``pending_review`` queue entry — the same
    human gate every remix render passes through.
    """
    entry = {
        "kind": "channel_operator_plan",
        "status": "pending_review",
        "requires_approval": True,
        "publishes_anything": False,
        "plan": plan,
    }
    return remix_flow.enqueue_review(entry, queue_path)
