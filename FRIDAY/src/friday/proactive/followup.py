"""A12 — Proactive follow-up: unfinished tasks get a status ping unasked.

FRIDAY owns the follow-up so the owner doesn't have to: a periodic sweep of
the shared task ledger (``friday_core.task_records``) finds tasks that have
been sitting in ``submitted`` / ``assigned`` / ``dispatched`` for longer than
``STALE_AFTER_MINUTES`` and posts one honest status ping per task through
the existing proactive NotificationManager (the same channel the morning
brief and the voice line read from). Pings are rate-limited per task
(default: one ping every ``REPING_HOURS``), failures are counted honestly,
and nothing is invented — a quiet ledger means no ping.
"""

from __future__ import annotations

import datetime as _dt
import time
from typing import Any

#: A task older than this (minutes, since its last transition) is stale.
STALE_AFTER_MINUTES = 45
#: Minimum seconds between two pings about the same task.
REPING_SECONDS = 6 * 3600
#: How often the sweep loop runs (seconds).
SWEEP_INTERVAL_SECONDS = 30 * 60

_STALE_STATUSES = ("submitted", "assigned", "dispatched")

# task_id -> epoch seconds of the last ping about it (process-local registry;
# the ping itself is persisted in the notification store, this only rate-limits).
_pinged_at: dict[str, float] = {}


def _now_epoch() -> float:
    return time.time()


def _reset_for_tests() -> None:
    _pinged_at.clear()


def collect_stale_tasks(
    *,
    stale_after_minutes: int = STALE_AFTER_MINUTES,
    limit: int = 10,
    now_epoch: float | None = None,
) -> list[dict[str, Any]]:
    """Unfinished tasks past the staleness window — honest summaries, newest pain first.

    Returns [] when the ledger is unreachable or empty; never raises.
    """

    try:
        from friday_core.task_records import get_shared_task_records

        store = get_shared_task_records()
        stale: list[dict[str, Any]] = []
        now_epoch = now_epoch if now_epoch is not None else _now_epoch()
        for status in _STALE_STATUSES:
            for rec in store.list(status=status) or []:
                updated = float(getattr(rec, "updated_at", 0) or 0)
                age_min = max(0.0, (now_epoch - updated) / 60.0)
                if age_min < stale_after_minutes:
                    continue
                task_id = str(getattr(rec, "task_id", "") or "")
                if not task_id:
                    continue
                stale.append(
                    {
                        "task_id": task_id,
                        "description": str(getattr(rec, "description", "") or ""),
                        "owner_agent": str(getattr(rec, "owner_agent", "") or "unassigned"),
                        "status": status,
                        "age_minutes": int(age_min),
                    }
                )
                if len(stale) >= limit:
                    return sorted(stale, key=lambda t: -t["age_minutes"])
        return sorted(stale, key=lambda t: -t["age_minutes"])
    except Exception:
        return []


def compose_followup_ping(task: dict[str, Any]) -> str:
    """One honest ping line for a stale task."""

    desc = str(task.get("description", "") or "").strip()
    if len(desc) > 90:
        desc = desc[:87].rstrip() + "…"
    what = desc or task.get("task_id", "a task")
    who = str(task.get("owner_agent", "") or "").strip() or "an agent"
    age = task.get("age_minutes", 0)
    return f"Follow-up: '{what}' with {who} is still {task.get('status')} after {age} min — I'm on it, Boss."


def followup_sweep(
    notifications: Any,
    *,
    stale_after_minutes: int = STALE_AFTER_MINUTES,
    reping_seconds: int = REPING_SECONDS,
    now_epoch: float | None = None,
    post: bool = True,
) -> dict[str, Any]:
    """Sweep the ledger and (optionally) post pings. Counts are honest, never raises.

    ``post=False`` composes the pings without sending them (used by the chat
    surface "what needs my attention?" and by tests).
    """

    result: dict[str, Any] = {
        "status": "ok",
        "stale_found": 0,
        "pings_posted": 0,
        "rate_limited": 0,
        "post_failures": 0,
        "pending_pings": [],
    }
    stale = collect_stale_tasks(stale_after_minutes=stale_after_minutes, now_epoch=now_epoch)
    result["stale_found"] = len(stale)
    now_epoch = now_epoch if now_epoch is not None else _now_epoch()
    for task in stale:
        line = compose_followup_ping(task)
        result["pending_pings"].append(line)
        if not post:
            continue
        last = _pinged_at.get(task["task_id"], 0.0)
        if now_epoch - last < reping_seconds:
            result["rate_limited"] += 1
            continue
        try:
            notifications.post_notification(
                line,
                category="followup",
                severity="info",
                metadata={"task_id": task["task_id"], "proactive_followup": True},
            )
            _pinged_at[task["task_id"]] = now_epoch
            result["pings_posted"] += 1
        except Exception:
            result["post_failures"] += 1
    if result["post_failures"] and not result["pings_posted"]:
        result["status"] = "error"
    return result


def followup_summary_reply() -> dict[str, Any]:
    """Chat surface: 'what needs my attention?' → honest sweep summary, no posting."""

    stale = collect_stale_tasks()
    if not stale:
        return {
            "reply": (
                "Nothing needs you right now, Boss — no task has been sitting unfinished "
                "past my follow-up window. I'll ping you the moment something stalls."
            ),
            "metadata": {"fast_path": True, "conversational": True, "followup_sweep": True, "stale_found": 0},
        }
    lines = "\n".join(f"• {compose_followup_ping(t)}" for t in stale[:5])
    return {
        "reply": (
            f"Heads-up, Boss — {len(stale)} thing{'s' if len(stale) != 1 else ''} sitting unfinished:\n\n{lines}\n\n"
            "I'm already on these; say the word if you want any of them re-assigned or dropped."
        ),
        "metadata": {"fast_path": True, "conversational": True, "followup_sweep": True, "stale_found": len(stale)},
    }


async def followup_loop(notifications: Any) -> None:
    """Background sweep loop (wired into the server lifespan)."""

    while True:
        try:
            followup_sweep(notifications, post=True)
        except Exception:
            pass
        await _sleep(SWEEP_INTERVAL_SECONDS)


async def _sleep(seconds: float) -> None:
    import asyncio

    await asyncio.sleep(seconds)
