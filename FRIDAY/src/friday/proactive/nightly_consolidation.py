"""Checklist B7 (MASTER_COMPLETION_CHECKLIST): nightly memory consolidation.

While the owner sleeps (02:00–05:00 IST window), FRIDAY tidies the day's
memories so tomorrow's recall leads with the essence, not the noise:

- near-duplicate facts are MERGED — the best copy is kept and the other is
  retired through the same auditable ``superseded`` lifecycle the owner's own
  corrections (B10) use (MemoraClient.supersede_fact);
- a one-line day summary is stored, marked so it is recognizable and never
  consolidated again ("Daily memory summary (auto) …").

Honesty rules (identical to the morning brief, TASK-VOI-002):
- the summary only counts and lists what the recall path actually returned —
  consolidation never invents content;
- every component failure is honest and isolated: a failed merge never fails
  the run (it is reported in ``merges_skipped``), a failed summary is
  reported as ``summary_stored: False``, never faked;
- the window gate fires at most once per night. A process restart may re-run
  once — acceptable: merges are idempotent (superseding an already-superseded
  record is a no-op) and a second summary is recognizable and skipped.
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from friday.core.logging import get_logger
from friday.core.owner_time import now_owner_tz

logger = get_logger("proactive.nightly_consolidation")

#: Marker prefix of an auto day summary. Consolidation never merges or
#: re-summarizes its own summaries; recall can find them by this prefix.
SUMMARY_PREFIX = "Daily memory summary (auto)"

#: Merge similarity threshold — matches Memora's own consolidation engine
#: default (memory_consolidation_engine.py: merge_similarity_threshold 0.85).
MERGE_SIMILARITY_THRESHOLD = 0.85

#: Night window (owner asleep): 02:00–05:00 IST.
NIGHT_WINDOW_START = 2
NIGHT_WINDOW_END = 5

#: In-memory record of the last consolidated night (YYYY-MM-DD IST). A process
#: restart may consolidate once more — by design (see module docstring).
_last_night_date: Optional[str] = None


def _in_night_window(now: Optional[datetime] = None) -> bool:
    """True inside 02:00–05:00 IST (the owner's sleep window)."""
    moment = now or now_owner_tz()
    return NIGHT_WINDOW_START <= moment.hour < NIGHT_WINDOW_END


def _tokens(text: str) -> set[str]:
    """Lowercased word tokens (letters/digits), stop-ish words kept (Jaccard
    stays symmetric and content-free tokens dilute both sides equally)."""
    return set(re.findall(r"[a-z0-9]+", (text or "").lower()))


def _similarity(a: str, b: str) -> float:
    """Near-duplicate score (0.0–1.0): Jaccard, softened by containment.

    A short fact that is a SUBSET of a richer statement ("my favorite chai is
    masala chai" ⊂ "my favorite chai is masala chai and I review the fleet
    every morning at 9") is a duplicate for memory-keeping purposes, but pure
    Jaccard scores it 5/14 ≈ 0.36. The score is therefore max(Jaccard,
    containment), where containment = |A∩B| / min(|A|,|B|). Distinct facts
    about different subjects stay well below the merge threshold.
    """
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    inter = len(ta & tb)
    jaccard = inter / len(ta | tb)
    containment = inter / min(len(ta), len(tb))
    return max(jaccard, containment)


def _record_text(record: Dict[str, Any]) -> str:
    return str(record.get("content_text", "") or "").strip()


def _record_id(record: Dict[str, Any]) -> str:
    return str(record.get("id") or record.get("memory_id") or "")


def _is_prior_summary(text: str) -> bool:
    return text.lower().startswith(SUMMARY_PREFIX.lower())


def _gather_days_memories(client: Any, agent_name: str, day: str) -> List[Dict[str, Any]]:
    """The day's live memories through the real client — date-filtered, not keyword-guessed.

    ``recent_memories`` (B7) lists the newest ACTIVE records; the IST-day
    prefix filter keeps today's. Records without a parseable date, empties
    and prior auto-summaries are dropped. Never raises.
    """
    try:
        rows = client.recent_memories(agent_name, limit=100, since=day) or []
    except Exception as exc:  # a store outage is an honest empty day, never a crash
        logger.debug(f"consolidation recent_memories failed: {type(exc).__name__}")
        return []
    gathered: List[Dict[str, Any]] = []
    for hit in rows:
        rid = _record_id(hit)
        text = _record_text(hit)
        if not rid or len(text) <= 6 or _is_prior_summary(text):
            continue
        gathered.append({"id": rid, "text": text})
    return gathered


def _merge_duplicates(
    client: Any,
    agent_name: str,
    records: List[Dict[str, Any]],
    threshold: float,
) -> Dict[str, int]:
    """Merge near-duplicate facts: keep the richest copy, supersede the rest.

    Returns honest counters: ``duplicates_merged`` (superseded through the
    auditable lifecycle) and ``merges_skipped`` (a supersede that honestly
    failed — reported, never faked, never fatal).
    """
    merged = 0
    skipped = 0
    superseded_ids: set[str] = set()
    for i, a in enumerate(records):
        if a["id"] in superseded_ids:
            continue
        for b in records[i + 1:]:
            if b["id"] in superseded_ids or a["id"] in superseded_ids:
                continue
            if _similarity(a["text"], b["text"]) < threshold:
                continue
            # keep the richest statement as the winner
            winner, loser = (a, b) if len(a["text"]) >= len(b["text"]) else (b, a)
            try:
                result = client.supersede_fact(
                    agent_name=agent_name,
                    memory_id=loser["id"],
                    winner_id=winner["id"],
                    reason="nightly consolidation (B7)",
                )
            except Exception as exc:
                logger.debug(f"supersede_fact raised: {type(exc).__name__}")
                result = {"status": "error"}
            if str((result or {}).get("status")) == "superseded":
                superseded_ids.add(loser["id"])
                merged += 1
            else:
                skipped += 1
    return {
        "duplicates_merged": merged,
        "merges_skipped": skipped,
        "superseded_ids": superseded_ids,
    }


def _compose_summary(day: str, live_records: List[Dict[str, Any]]) -> str:
    """One honest line about the day's memories — counts and short excerpts."""
    if not live_records:
        return f"{SUMMARY_PREFIX} {day}: nothing worth keeping from today."
    excerpts = "; ".join(r["text"].rstrip(".!? ") for r in live_records[:5])
    if len(excerpts) > 320:
        excerpts = excerpts[:317].rstrip() + "…"
    more = "" if len(live_records) <= 5 else f" (+{len(live_records) - 5} more)"
    return f"{SUMMARY_PREFIX} {day}: {len(live_records)} memories kept{more} — {excerpts}."


def _todays_summary_exists(client: Any, agent_name: str, day: str) -> bool:
    """True when a marked day summary for ``day`` is already stored.

    Makes the summary write idempotent: a second pass the same night (process
    restart) recognizes its own summary instead of stacking another one.
    Never raises — an unreadable store just means the summary is re-written.
    """
    try:
        rows = client.recent_memories(agent_name, limit=100, since=day) or []
    except Exception as exc:
        logger.debug(f"summary existence check failed: {type(exc).__name__}")
        return False
    prefix = f"{SUMMARY_PREFIX} {day}".lower()
    for row in rows:
        text = _record_text(row)
        if text and text.lower().startswith(prefix):
            return True
    return False


def consolidate_day_memories(
    client: Any,
    now: Optional[datetime] = None,
    *,
    agent_name: str = "friday",
    threshold: float = MERGE_SIMILARITY_THRESHOLD,
) -> Dict[str, Any]:
    """Run one consolidation pass over the day's memories. Never raises.

    Returns an honest report: ``status`` is ``consolidated`` (work done or
    checked), ``error`` (the pass could not even gather memories), with
    per-component counters.
    """
    moment = now or now_owner_tz()
    day = moment.strftime("%Y-%m-%d")
    try:
        records = _gather_days_memories(client, agent_name, day)
    except Exception as exc:  # gather is already defensive; belt for tests
        logger.warning(f"nightly consolidation gather failed: {type(exc).__name__}")
        return {"status": "error", "day": day, "error": type(exc).__name__}

    if not records:
        return {
            "status": "consolidated",
            "day": day,
            "records_examined": 0,
            "duplicates_merged": 0,
            "merges_skipped": 0,
            "summary_stored": False,
            "note": "no live memories found for the day",
        }

    merge_report = _merge_duplicates(client, agent_name, records, threshold)
    # the summary counts only what stays live after the merge pass
    superseded = merge_report["superseded_ids"]
    live_records = [r for r in records if r["id"] not in superseded]

    summary_text = _compose_summary(day, live_records)
    summary_stored = False
    summary_id = ""
    if _todays_summary_exists(client, agent_name, day):
        # idempotent: this day's summary is already stored — recognized, not
        # duplicated (a restart-triggered second pass lands here)
        summary_stored = True
        summary_text = f"{SUMMARY_PREFIX} {day}: already stored — re-run recognized it."
    else:
        try:
            stored = client.record_fact(
                agent_name=agent_name,
                fact_text=summary_text,
                category="consolidation",
                importance=0.5,
            )
            summary_stored = bool(stored) and str((stored or {}).get("status")) != "error"
            summary_id = str((stored or {}).get("id") or (stored or {}).get("memory_id") or "")
        except Exception as exc:
            logger.warning(f"nightly consolidation summary store failed: {type(exc).__name__}")

    # B8: importance aging — trivial-tier facts past AGE_OUT_DAYS retire
    # through the same auditable supersede lifecycle (pinned facts are
    # never touched). Runs after the day's merge so the day summary and the
    # aging report land together; honest counters, never fatal.
    aging_report: Dict[str, Any] = {"aged_out": 0, "examined": 0, "status": "skipped"}
    if not records:
        aging_report["status"] = "skipped_empty_day"
    else:
        try:
            from friday.memory.importance import age_out_trivial_memories

            aging_report = age_out_trivial_memories(client, agent_name=agent_name)
        except Exception as exc:
            aging_report = {"aged_out": 0, "examined": 0, "status": f"error:{type(exc).__name__}"}
            logger.warning(f"nightly importance aging failed: {type(exc).__name__}")

    return {
        "status": "consolidated",
        "day": day,
        "records_examined": len(records),
        "duplicates_merged": merge_report["duplicates_merged"],
        "merges_skipped": merge_report["merges_skipped"],
        "summary_stored": summary_stored,
        "summary_id": summary_id,
        "summary_text": summary_text,
        "aged_out": aging_report.get("aged_out", 0),
        "aging_examined": aging_report.get("examined", 0),
        "aging_status": aging_report.get("status", "skipped"),
    }


def maybe_run_nightly_consolidation(
    client: Any,
    now: Optional[datetime] = None,
    *,
    agent_name: str = "friday",
) -> Optional[Dict[str, Any]]:
    """Gate: run consolidation at most once per night, inside the sleep window.

    Returns the consolidation report when it ran, ``None`` when gated out
    (outside 02:00–05:00 IST, or this night already consolidated).
    """
    global _last_night_date
    moment = now or now_owner_tz()
    if not _in_night_window(moment):
        return None
    day = moment.strftime("%Y-%m-%d")
    if _last_night_date == day:
        return None
    _last_night_date = day
    try:
        return consolidate_day_memories(client, now=moment, agent_name=agent_name)
    except Exception as exc:  # never propagate into a caller's loop
        logger.warning(f"nightly consolidation run failed: {type(exc).__name__}")
        return {"status": "error", "day": day, "error": type(exc).__name__}


def reset_for_tests() -> None:
    """Clear the once-per-night latch (test isolation only)."""
    global _last_night_date
    _last_night_date = None
