"""B8 — Memory importance scoring: trivial facts age out, core facts pinned.

Every fact the owner asks FRIDAY to remember is scored on a deterministic
0.0-1.0 scale BEFORE it is stored:

- ``pinned`` (>= 0.90): identity, contact, preferences, relationships,
  schedule, health and goal facts — the core of what FRIDAY must never
  forget. These carry the importance the remember path used to give
  everything blindly (0.98) and are exempt from aging.
- ``normal`` (0.55): substantive statements that are neither core identity
  nor small talk. They age only if they go unrecalled for a long time
  (currently: they are kept — aging only removes the trivial tier).
- ``trivial`` (<= 0.30): greetings, acknowledgements, transient states
  ("I'm tired today"), questions, agent-log noise and sub-15-character
  fragments. Stored (the owner asked for it) but marked low; the nightly
  pass ages them out (soft supersede, auditable) once they are older than
  ``AGE_OUT_DAYS`` days.

Scoring is pure string analysis — no model calls, no network, deterministic
for tests. Aging is executed through the same auditable supersede lifecycle
B7/B10 use (``MemoraClient.supersede_fact``), never a hard delete.
"""

from __future__ import annotations

import datetime as _dt
from dataclasses import dataclass, field
from typing import Any, Protocol

# --- Tunables -----------------------------------------------------------------

PINNED_THRESHOLD = 0.90
TRIVIAL_THRESHOLD = 0.30
NORMAL_SCORE = 0.55
PINNED_SCORE = 0.98
TRIVIAL_SCORE = 0.20
#: Trivial facts older than this many days are aged out by the nightly pass.
AGE_OUT_DAYS = 7

# --- Pattern tables (lowercase, matched on the cleaned text) ------------------

_IDENTITY = (
    "my name is", "call me", "i am surendra", "i'm surendra", "this is surendra",
    "i am your boss", "i'm your boss", "i am the owner", "i am your owner",
)
_CONTACT = (
    "my number is", "my phone", "my email", "my address", "my birthday",
    "my whatsapp", "my telegram", "my github", "my account",
)
_PREFERENCE = (
    "favorite", "favourite", "i prefer", "i like", "i love", "i hate",
    "i can't stand", "i cant stand", "allergic", "allergy", "i always",
    "i never", "my diet", "i'm vegetarian", "im vegetarian", "i drink",
)
_RELATIONSHIP = (
    "my wife", "my husband", "my mom", "my mother", "my dad", "my father",
    "my brother", "my sister", "my son", "my daughter", "my friend",
    "my girlfriend", "my boyfriend", "my family", "my dog", "my cat",
)
_SCHEDULE = (
    "every morning", "every day", "every evening", "every night", "every monday",
    "every tuesday", "every wednesday", "every thursday", "every friday",
    "every saturday", "every sunday", "every week", "each morning", "each day",
    "my schedule", "my routine", "i wake up", "i review",
)
_HEALTH = ("my health", "i have diabetes", "my back", "i take", "my medication")
_GOAL = ("my goal", "i want to", "i'm planning", "im planning", "i plan to",
         "i'm going to", "im going to", "by friday", "this week i")

_PINNED_TABLES = (
    ("identity", _IDENTITY),
    ("contact", _CONTACT),
    ("preference", _PREFERENCE),
    ("relationship", _RELATIONSHIP),
    ("schedule", _SCHEDULE),
    ("health", _HEALTH),
    ("goal", _GOAL),
)

_TRIVIAL_MARKERS = (
    "lol", "lmao", "haha", "hehe", "nice", "cool", "okay", "ok", "fine",
    "good", "great", "thanks", "thank you", "whatever", "sure", "yep", "nope",
    "bye", "goodbye", "see you", "good talk",
)
_TRANSIENT = (
    "today", "right now", "this morning", "this afternoon", "tonight",
    "i'm tired", "im tired", "i feel", "i'm feeling", "im feeling", "i'm sleepy",
    "the weather", "it's raining", "its raining", "it's hot", "it's cold",
    "later", "just now", "at the moment",
)
_AGENT_LOG_NOISE = (
    " executed ", "[agent task", "bundle id", "http 200", "[memora response",
    "task_", "dispatch", "workflow run",
)


@dataclass
class ImportanceVerdict:
    """Deterministic importance classification of one candidate fact."""

    score: float
    tier: str  # "pinned" | "normal" | "trivial"
    reasons: list[str] = field(default_factory=list)

    @property
    def is_pinned(self) -> bool:
        return self.tier == "pinned"

    @property
    def is_trivial(self) -> bool:
        return self.tier == "trivial"


def _clean(text: str) -> str:
    return " ".join(str(text or "").strip().lower().split())


def score_importance(text: str) -> ImportanceVerdict:
    """Score one candidate fact. Pure function; never raises on text input."""

    low = _clean(text)
    reasons: list[str] = []

    # Stored goal records (A11) are pinned by construction — importance 1.0
    # was assigned at store time; the scorer must agree so the browser and
    # the aging pass treat active goals as core facts.
    if low.startswith("goal (active):"):
        reasons.append("pinned:goal-record")
        return ImportanceVerdict(PINNED_SCORE, "pinned", reasons)

    # Pinned: any core-life signal wins immediately.
    for label, table in _PINNED_TABLES:
        for pat in table:
            if pat in low:
                reasons.append(f"pinned:{label}")
                return ImportanceVerdict(PINNED_SCORE, "pinned", reasons)
    # "boss" ownership phrasing is identity-adjacent core.
    if "boss" in low and any(k in low for k in ("i am", "i'm", "im", "this is")):
        reasons.append("pinned:boss-identity")
        return ImportanceVerdict(PINNED_SCORE, "pinned", reasons)

    # Trivial: questions are never facts worth keeping long-term.
    if low.endswith("?"):
        reasons.append("trivial:question")
        return ImportanceVerdict(TRIVIAL_SCORE, "trivial", reasons)
    # Greetings / acknowledgements / filler words.
    if low in _TRIVIAL_MARKERS:
        reasons.append("trivial:marker-word")
        return ImportanceVerdict(TRIVIAL_SCORE, "trivial", reasons)
    # Transient state — true today, meaningless next week.
    for pat in _TRANSIENT:
        if pat in low:
            reasons.append("trivial:transient-state")
            return ImportanceVerdict(TRIVIAL_SCORE, "trivial", reasons)
    # Agent-log noise that leaks into the store via auto-recording.
    for pat in _AGENT_LOG_NOISE:
        if pat in f" {low} ":
            reasons.append("trivial:agent-log-noise")
            return ImportanceVerdict(TRIVIAL_SCORE, "trivial", reasons)
    # Too short to carry a durable fact.
    if len(low) < 15:
        reasons.append("trivial:too-short")
        return ImportanceVerdict(TRIVIAL_SCORE, "trivial", reasons)

    # Everything else substantive: normal tier.
    reasons.append("normal:substantive")
    return ImportanceVerdict(NORMAL_SCORE, "normal", reasons)


class _AgingClient(Protocol):
    """The subset of MemoraClient the aging pass needs (test fakes implement it)."""

    def recent_memories(self, agent_name: str, limit: int = 100, since: str = "") -> list[dict[str, Any]]: ...

    def supersede_fact(self, agent_name: str, memory_id: str, winner_id: str = "", reason: str = "") -> dict[str, Any]: ...


def _parse_created(stamp: str) -> _dt.datetime | None:
    """Parse 'YYYY-MM-DD HH:MM:SS' or ISO stamps; None when unreadable."""
    raw = str(stamp or "").strip()
    if not raw:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d"):
        try:
            return _dt.datetime.strptime(raw[: len(fmt) + 2].strip(), fmt)
        except ValueError:
            continue
    try:
        return _dt.datetime.fromisoformat(raw.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def age_out_trivial_memories(
    client: _AgingClient,
    *,
    agent_name: str = "friday",
    max_age_days: int = AGE_OUT_DAYS,
    limit: int = 200,
    now: _dt.datetime | None = None,
) -> dict[str, Any]:
    """Retire trivial-tier memories older than ``max_age_days`` (B8).

    Walks the recent ACTIVE records, scores each, and softly supersedes the
    trivial ones past the age window through the auditable lifecycle. Pinned
    and normal facts are never touched. Never raises — every failure is an
    honest count in the result dict.
    """
    result: dict[str, Any] = {
        "status": "ok",
        "examined": 0,
        "aged_out": 0,
        "pinned_kept": 0,
        "normal_kept": 0,
        "trivial_kept_young": 0,
        "supersede_failures": 0,
        "unreadable_timestamps": 0,
    }
    try:
        rows = client.recent_memories(agent_name, limit=limit) or []
    except Exception as exc:  # store outage — honest empty pass
        result["status"] = "error"
        result["error"] = type(exc).__name__
        return result

    now = now or _dt.datetime.now()
    for row in rows:
        text = str(row.get("content_text", "") or "").strip()
        if not text:
            continue
        # Daily-summary records B7 stores are consolidated artifacts, not facts
        # to age; leave them to their own lifecycle.
        if text.lower().startswith("daily memory summary (auto)"):
            continue
        result["examined"] += 1
        verdict = score_importance(text)
        if verdict.is_pinned:
            result["pinned_kept"] += 1
            continue
        if verdict.tier == "normal":
            result["normal_kept"] += 1
            continue
        created = _parse_created(row.get("created_at", ""))
        if created is None:
            result["unreadable_timestamps"] += 1
            continue
        age_days = (now - created).total_seconds() / 86400.0
        if age_days < max_age_days:
            result["trivial_kept_young"] += 1
            continue
        mem_id = str(row.get("id") or row.get("memory_id") or "")
        if not mem_id:
            result["supersede_failures"] += 1
            continue
        try:
            res = client.supersede_fact(
                agent_name,
                mem_id,
                reason=f"importance aging (B8): trivial fact aged out after {int(age_days)} days",
            ) or {}
        except Exception:
            res = {"status": "error"}
        if str(res.get("status")) == "superseded":
            result["aged_out"] += 1
        else:
            result["supersede_failures"] += 1

    if not result["examined"] and result["status"] == "ok":
        result["status"] = "empty"
    return result
