"""Checklists F8/F9/F14/F15/F20 (MASTER_COMPLETION_CHECKLIST) — Batch 6, ZAI Agent 2.

The agent-depth watch module: FRIDAY watches what the owner cares about,
through the fleet's REAL agents, and reports only what actually changed.

- F8  Watchlist: the owner parks topics in chat ("watch topic X"), FRIDAY
  asks IntelX for a daily evidence-based brief on each (17:30 IST, before
  the 21:00 self-report), and delivers it via the owner's Telegram channel
  plus the proactive notifications surface.
- F9  Change detection: each topic stores the content hash + extracted
  headline lines of its LAST brief; today's brief reports what is NEW or
  unchanged — no "here's the same summary again" noise.
- F14/F15 Site health: daily 08:00 IST sweep of the owned properties (the
  public gateway routes + Cortex's governed properties), honest per-site
  status/latency, alerts only on degradation or first failure.
- F20 Sentinel digest: weekly Monday 09:30 IST vulnerability digest from
  Sentinel's real posture + open-findings engines (read-only), delivered to
  Telegram. Findings stay factual: scores, severities, and counts as
  reported — never interpreted into "everything is fine".

Honesty rules (identical to every FRIDAY surface):
- every source failure becomes an honest "could not check X" line;
- an agent that returns nothing contributes "no findings reported", not a
  fabricated all-clear;
- every scheduled pass is latched per period (once per day / week) and a
  send failure retries next cycle without latching (same as G7/G8).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import threading
import time
from datetime import datetime
from typing import Any, Awaitable, Callable

from friday.core.owner_time import OWNER_TZ, now_owner_tz, owner_today

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# windows (owner's IST clock; see owner_time module docstring)
# ---------------------------------------------------------------------------
#: F8: daily watchlist briefing fires between 17:30 and 20:00 IST.
WATCH_WINDOW_START = (17, 30)
WATCH_WINDOW_END = (20, 0)
#: F14/F15: site health sweep fires between 08:00 and 12:00 IST.
SITE_SWEEP_WINDOW_START = (8, 0)
SITE_SWEEP_WINDOW_END = (12, 0)
#: F20: Sentinel digest fires Monday 09:30–14:00 IST.
SENTINEL_DIGEST_DAY = 0  # Monday (weekday(): Monday=0)
SENTINEL_DIGEST_WINDOW_START = (9, 30)
SENTINEL_DIGEST_WINDOW_END = (14, 0)

#: Max topics per daily brief so one runaway watchlist can never wedge the pass.
MAX_TOPICS_PER_BRIEF = 6
#: Owned properties for the site sweep: the public gateway routes (all ten
#: agents live behind https://friday-universe.duckdns.org/<route>/health).
GATEWAY_ROUTES = (
    "friday", "inference", "memora", "stratex", "futuris",
    "intelx", "forge", "cortex", "sentinel", "vyralx",
)
PUBLIC_GATEWAY = "https://friday-universe.duckdns.org"


def _in_window(now: datetime, start: tuple[int, int], end: tuple[int, int]) -> bool:
    moment = now.astimezone(OWNER_TZ)
    current = (moment.hour, moment.minute)
    return start <= current < end


# ---------------------------------------------------------------------------
# watchlist store (F8/F9) — same file-backed pattern as the mission queue
# ---------------------------------------------------------------------------

def _default_store_path() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "watchlist", "watchlist.json"))
    here = os.path.dirname(__file__)  # .../friday/proactive
    return os.path.abspath(os.path.join(here, "..", "..", ".data", "watchlist", "watchlist.json"))


class WatchlistStore:
    """File-backed watchlist: topics + each one's last brief hash/lines."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _default_store_path()
        self._lock = threading.RLock()
        self._cache: dict[str, Any] | None = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = data if isinstance(data, dict) else {"topics": {}}
        except FileNotFoundError:
            self._cache = {"topics": {}}
        except Exception as exc:
            logger.warning("[WATCH] store unreadable (%s) — starting empty", exc)
            self._cache = {"topics": {}}
        self._cache.setdefault("topics", {})
        return self._cache

    def _save(self) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, sort_keys=True)
        os.replace(tmp, self._path)

    # -- topic CRUD -------------------------------------------------------
    def add_topic(self, topic: str) -> dict[str, Any]:
        topic = (topic or "").strip()
        if not topic:
            raise ValueError("empty topic")
        with self._lock:
            data = self._load()
            topics = data["topics"]
            key = topic.lower()
            entry = topics.get(key)
            if entry is None:
                entry = {
                    "topic": topic,
                    "created_ist": now_owner_tz().isoformat(),
                    "last_hash": "",
                    "last_lines": [],
                    "last_brief_ist": "",
                    "brief_count": 0,
                }
                topics[key] = entry
                self._save()
            return dict(entry)

    def remove_topic(self, topic: str) -> bool:
        with self._lock:
            data = self._load()
            key = (topic or "").strip().lower()
            if key in data["topics"]:
                del data["topics"][key]
                self._save()
                return True
            return False

    def topics(self) -> list[dict[str, Any]]:
        with self._lock:
            return [dict(v) for v in self._load()["topics"].values()]

    def record_brief(self, topic: str, brief_text: str) -> None:
        """F9: store the brief's fingerprint for tomorrow's change report."""
        lines = _headline_lines(brief_text)
        digest = hashlib.sha256((brief_text or "").encode("utf-8")).hexdigest()
        with self._lock:
            data = self._load()
            entry = data["topics"].get((topic or "").strip().lower())
            if entry is None:
                return
            entry["last_hash"] = digest
            entry["last_lines"] = lines[:8]
            entry["last_brief_ist"] = now_owner_tz().isoformat()
            entry["brief_count"] = int(entry.get("brief_count", 0)) + 1
            self._save()

    def reset_for_tests(self, path: str | None = None) -> None:
        self._path = path or self._path
        self._cache = None


def _headline_lines(brief_text: str) -> list[str]:
    """Extract short informative lines for the change comparison (F9)."""
    out: list[str] = []
    for raw in (brief_text or "").splitlines():
        line = raw.strip().lstrip("-•* ").strip()
        if not line or len(line) < 12 or len(line) > 200:
            continue
        if re.match(r"^[\W\d]+$", line):
            continue
        out.append(line)
    return out


#: Process-wide singleton (server loop + chat fast-path share one store).
watchlist_store = WatchlistStore()


# ---------------------------------------------------------------------------
# F8/F9 — daily watchlist briefing through IntelX
# ---------------------------------------------------------------------------

async def _intelx_brief(topic: str) -> str | None:
    """One topic's brief through the REAL IntelX dispatch (TaskEnvelope)."""
    from friday.core.task_envelope import TaskEnvelope
    from friday.ecosystem.fleet_client import FleetClient

    envelope = TaskEnvelope(
        capability="intelx.research",
        objective=f"Watchlist brief: {topic}",
        action="research",
        target_agent="intelx",
        payload={"topic": topic, "scope": "daily watch brief"},
    )
    client = FleetClient()
    try:
        result = await client.dispatch_task(envelope)
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
    reply = str((result and result.to_dict().get("result")) or "")
    # TaskResult shape fallback: some envelopes carry the reply at top level.
    if not reply and hasattr(result, "content"):
        reply = str(result.content or "")
    if not reply:
        d = result.to_dict() if hasattr(result, "to_dict") else {}
        reply = str(d.get("reply") or d.get("result") or "")
    return reply or None


async def run_watchlist_briefing(
    deliver: Callable[[str], Awaitable[bool]] | None = None,
    *,
    brief_fn: Callable[[str], Awaitable[str | None]] | None = None,
) -> dict[str, Any]:
    """Compose and deliver today's watchlist briefing (F8 + F9). Never raises.

    ``deliver``: async callable returning True when the owner received the
    message (the server wires the Telegram gateway + notifications surface).
    """
    if deliver is None:
        async def deliver(text: str) -> bool:  # noqa: F811
            from friday.proactive.telegram_gateway import send_owner_message

            try:
                return bool(send_owner_message(text))
            except Exception:
                return False

    report: dict[str, Any] = {"date": owner_today(), "topics": 0, "delivered": False, "lines": []}
    entries = watchlist_store.topics()
    if not entries:
        return report  # nothing watched — no message, no noise
    topics = entries[:MAX_TOPICS_PER_BRIEF]
    sections: list[str] = [f"📡 Watchlist brief — {owner_today()} (IST):"]
    for entry in topics:
        topic = entry["topic"]
        try:
            brief = await (brief_fn or _intelx_brief)(topic)
        except Exception as exc:
            brief = None
            logger.warning("[WATCH] IntelX brief failed for %r: %s", topic, exc)
        if not brief:
            sections.append(f"• {topic}: I could not get a brief from IntelX today — reported honestly, not guessed.")
            continue
        report["topics"] += 1
        lines = _headline_lines(brief)
        prev_hash = entry.get("last_hash") or ""
        prev_lines = list(entry.get("last_lines") or [])
        new_digest = hashlib.sha256(brief.encode("utf-8")).hexdigest()
        if not prev_hash:
            sections.append(f"• {topic} (first brief):\n" + "\n".join(f"  - {ln}" for ln in lines[:4]))
        elif new_digest == prev_hash:
            sections.append(f"• {topic}: no change since yesterday's brief.")
        else:
            fresh = [ln for ln in lines if ln not in prev_lines]
            if fresh:
                sections.append(f"• {topic} — what's new:\n" + "\n".join(f"  - {ln}" for ln in fresh[:4]))
            else:
                sections.append(f"• {topic}: the brief refreshed but the key points are unchanged.")
        watchlist_store.record_brief(topic, brief)
    text = "\n".join(sections)
    report["lines"] = sections
    try:
        report["delivered"] = bool(await deliver(text))
    except Exception as exc:
        logger.warning("[WATCH] delivery failed: %s", exc)
    return report


# ---------------------------------------------------------------------------
# F14/F15 — daily site health sweep
# ---------------------------------------------------------------------------

async def _probe_url(url: str, timeout: float = 8.0) -> tuple[bool, int, str]:
    """One honest HTTP probe: (ok, status_code, note). Never raises."""
    import httpx

    try:
        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            resp = await client.get(url)
        ok = 200 <= resp.status_code < 400
        return ok, resp.status_code, f"{resp.status_code} in {resp.elapsed.total_seconds():.2f}s"
    except Exception as exc:
        return False, 0, f"unreachable ({type(exc).__name__})"


async def run_site_health_sweep(
    deliver: Callable[[str], Awaitable[bool]] | None = None,
    *,
    probe_fn: Callable[[str], Awaitable[tuple[bool, int, str]]] | None = None,
) -> dict[str, Any]:
    """Daily 08:00 IST sweep of owned properties (F14/F15). Alerts only on
    degradation; a fully healthy fleet produces ONE compact line."""
    if deliver is None:
        async def deliver(text: str) -> bool:  # noqa: F811
            from friday.proactive.telegram_gateway import send_owner_message

            try:
                return bool(send_owner_message(text))
            except Exception:
                return False

    probe = probe_fn or (lambda url: _probe_url(url))
    results: dict[str, Any] = {"date": owner_today(), "checked": 0, "healthy": 0, "degraded": [], "delivered": False}

    # 1. Public gateway routes (the owned ingress + every agent behind it).
    for route in GATEWAY_ROUTES:
        ok, code, note = await probe(f"{PUBLIC_GATEWAY}/{route}/health")
        results["checked"] += 1
        if ok:
            results["healthy"] += 1
        else:
            results["degraded"].append(f"{route}: {note}")

    # 2. Cortex's governed properties (read through the same read-only path
    # the cortex_web_ops chat tool uses — one truth, two surfaces).
    try:
        from friday.ecosystem.fleet_client import FleetClient

        client = FleetClient()
        try:
            summary = await client.request_cortex_web_ops()
        finally:
            await client.aclose()
        results["cortex_summary"] = summary.get("reply")
    except Exception as exc:
        results["cortex_summary"] = f"Cortex monitoring could not be read ({type(exc).__name__})."

    # Compose: healthy → one line; degraded → per-site lines (alert).
    lines: list[str] = []
    if results["degraded"]:
        lines.append(f"🚨 Site sweep {owner_today()}: {results['healthy']}/{results['checked']} healthy — DEGRADED:")
        lines.extend(f"  ! {d}" for d in results["degraded"])
    else:
        lines.append(f"✅ Site sweep {owner_today()}: {results['healthy']}/{results['checked']} gateway routes healthy.")
    text = "\n".join(lines)
    try:
        results["delivered"] = bool(await deliver(text))
    except Exception as exc:
        logger.warning("[WATCH] site sweep delivery failed: %s", exc)
    return results


# ---------------------------------------------------------------------------
# F20 — weekly Sentinel vulnerability digest
# ---------------------------------------------------------------------------

async def run_sentinel_digest(
    deliver: Callable[[str], Awaitable[bool]] | None = None,
    *,
    sentinel_fn: Callable[[], Awaitable[tuple[dict[str, Any], dict[str, Any]]]] | None = None,
) -> dict[str, Any]:
    """Weekly Monday digest from Sentinel's REAL posture + findings (F20)."""
    if deliver is None:
        async def deliver(text: str) -> bool:  # noqa: F811
            from friday.proactive.telegram_gateway import send_owner_message

            try:
                return bool(send_owner_message(text))
            except Exception:
                return False

    if sentinel_fn is None:
        async def sentinel_fn() -> tuple[dict[str, Any], dict[str, Any]]:  # noqa: F811
            from friday.ecosystem.fleet_client import FleetClient

            client = FleetClient()
            try:
                posture, findings = await asyncio.gather(
                    client.ask_sentinel("weekly posture digest"),
                    client.ask_sentinel_findings(limit=10),
                )
            finally:
                await client.aclose()
            return posture, findings

    results: dict[str, Any] = {"date": owner_today(), "delivered": False}
    try:
        posture, findings = await sentinel_fn()
    except Exception as exc:
        logger.warning("[WATCH] Sentinel digest failed: %s", exc)
        posture, findings = {}, {}

    if not posture and not findings:
        text = (
            f"🛡️ Sentinel weekly digest {owner_today()}: I could not reach Sentinel's "
            "posture or findings engines — no numbers this week. Reported honestly, not guessed."
        )
    else:
        lines = [f"🛡️ Sentinel weekly digest — {owner_today()} (IST):"]
        p_reply = str(posture.get("reply") or "").strip()
        if p_reply:
            lines.append(p_reply.split("Read-only")[0].strip()[:1200])
        else:
            lines.append("Posture: not reported by Sentinel this week.")
        f_reply = str(findings.get("reply") or "").strip()
        if f_reply:
            lines.append("Open findings:")
            lines.append(f_reply[:1200])
        else:
            lines.append("Open findings: none reported.")
        text = "\n".join(lines)
    try:
        results["delivered"] = bool(await deliver(text))
    except Exception as exc:
        logger.warning("[WATCH] sentinel digest delivery failed: %s", exc)
    return results


# ---------------------------------------------------------------------------
# the scheduler (one server lifespan task owns all three passes)
# ---------------------------------------------------------------------------

_last_watch_date: str | None = None
_last_site_date: str | None = None
_last_sentinel_date: str | None = None
_last_portfolio_date: str | None = None
_last_forecast_am_date: str | None = None
_last_forecast_pm_date: str | None = None
_last_prediction_date: str | None = None
_last_alert_check_ts: float = 0.0
_latch_lock = threading.Lock()

#: How often the alert check actually fires (every tick would be too chatty;
#: the rule fires once per day per rule, but we don't need to query Stratex
#: 144 times a day either).
ALERT_CHECK_MIN_INTERVAL_SEC = 3600  # once per hour


async def agent_watch_tick(
    *,
    now: datetime | None = None,
    watch_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    site_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    sentinel_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    portfolio_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    alert_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    forecast_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
    prediction_coro_factory: Callable[[], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """One gate-check: run whichever scheduled pass is due and unlatched.

    Called every 10 minutes by the server's lifespan loop. Never raises —
    a pass failure is reported inside its own result dict. Batch 7 adds the
    market-watch passes (F5 portfolio, F6 alerts, F11 forecast refresh,
    F12 prediction scoring) into the same single lifespan task.
    """
    global _last_watch_date, _last_site_date, _last_sentinel_date
    global _last_portfolio_date, _last_alert_check_ts
    global _last_forecast_am_date, _last_forecast_pm_date, _last_prediction_date
    outcome: dict[str, Any] = {
        "watch": None, "site": None, "sentinel": None,
        "portfolio": None, "alerts": None,
        "forecast": None, "prediction": None,
    }
    moment = (now or now_owner_tz()).astimezone(OWNER_TZ)
    today = owner_today()
    now_ts = time.time()

    with _latch_lock:
        # Site sweep first (08:00–12:00): the morning line everyone reads.
        if (
            _in_window(moment, SITE_SWEEP_WINDOW_START, SITE_SWEEP_WINDOW_END)
            and _last_site_date != today
        ):
            _last_site_date = today
            try:
                outcome["site"] = await (site_coro_factory or run_site_health_sweep)()
            except Exception as exc:
                logger.exception("[WATCH] site sweep crashed")
                outcome["site"] = {"error": type(exc).__name__}

        # F5: daily portfolio report (09:00–12:00 IST, before the 09:30 forecast).
        if (
            _in_window(moment, (9, 0), (12, 0))
            and _last_portfolio_date != today
        ):
            _last_portfolio_date = today
            try:
                from friday.proactive.market_watch import run_daily_portfolio_report
                outcome["portfolio"] = await (portfolio_coro_factory or run_daily_portfolio_report)()
            except Exception as exc:
                logger.exception("[WATCH] portfolio report crashed")
                outcome["portfolio"] = {"error": type(exc).__name__}

        # F11: forecast refresh — AM (09:30–10:30) and PM (18:30–19:30) passes.
        if (
            _in_window(moment, (9, 30), (10, 30))
            and _last_forecast_am_date != today
        ):
            _last_forecast_am_date = today
            try:
                from friday.proactive.market_watch import run_forecast_refresh
                outcome["forecast"] = await (forecast_coro_factory or run_forecast_refresh)()
            except Exception as exc:
                logger.exception("[WATCH] AM forecast refresh crashed")
                outcome["forecast"] = {"error": type(exc).__name__}
        elif (
            _in_window(moment, (18, 30), (19, 30))
            and _last_forecast_pm_date != today
        ):
            _last_forecast_pm_date = today
            try:
                from friday.proactive.market_watch import run_forecast_refresh
                outcome["forecast"] = await (forecast_coro_factory or run_forecast_refresh)()
            except Exception as exc:
                logger.exception("[WATCH] PM forecast refresh crashed")
                outcome["forecast"] = {"error": type(exc).__name__}

        # F12: prediction scoring — 21:00–23:00 IST, score matured forecasts.
        if (
            _in_window(moment, (21, 0), (23, 0))
            and _last_prediction_date != today
        ):
            _last_prediction_date = today
            try:
                from friday.proactive.market_watch import run_prediction_scoring
                outcome["prediction"] = await (prediction_coro_factory or run_prediction_scoring)()
            except Exception as exc:
                logger.exception("[WATCH] prediction scoring crashed")
                outcome["prediction"] = {"error": type(exc).__name__}

        # F6: alert-rule check — runs every hour (no day latch; rules fire
        # once per day per rule via the alert store's last_fired_ist field).
        if (now_ts - _last_alert_check_ts) >= ALERT_CHECK_MIN_INTERVAL_SEC:
            _last_alert_check_ts = now_ts
            try:
                from friday.proactive.market_watch import run_alert_check
                outcome["alerts"] = await (alert_coro_factory or run_alert_check)()
            except Exception as exc:
                logger.exception("[WATCH] alert check crashed")
                outcome["alerts"] = {"error": type(exc).__name__}

        # Watchlist briefing (17:30–20:00): before the 21:00 self-report.
        if (
            _in_window(moment, WATCH_WINDOW_START, WATCH_WINDOW_END)
            and _last_watch_date != today
        ):
            _last_watch_date = today
            try:
                outcome["watch"] = await (watch_coro_factory or run_watchlist_briefing)()
            except Exception as exc:
                logger.exception("[WATCH] briefing crashed")
                outcome["watch"] = {"error": type(exc).__name__}

        # Sentinel digest (Monday 09:30–14:00).
        if (
            moment.weekday() == SENTINEL_DIGEST_DAY
            and _in_window(moment, SENTINEL_DIGEST_WINDOW_START, SENTINEL_DIGEST_WINDOW_END)
            and _last_sentinel_date != today
        ):
            _last_sentinel_date = today
            try:
                outcome["sentinel"] = await (sentinel_coro_factory or run_sentinel_digest)()
            except Exception as exc:
                logger.exception("[WATCH] sentinel digest crashed")
                outcome["sentinel"] = {"error": type(exc).__name__}

        # A pass that failed to deliver unlatches so the next tick retries.
        if isinstance(outcome.get("site"), dict) and outcome["site"].get("delivered") is False:
            _last_site_date = None
        if isinstance(outcome.get("watch"), dict) and outcome["watch"].get("delivered") is False:
            _last_watch_date = None
        if isinstance(outcome.get("sentinel"), dict) and outcome["sentinel"].get("delivered") is False:
            _last_sentinel_date = None
        if isinstance(outcome.get("portfolio"), dict) and outcome["portfolio"].get("delivered") is False:
            _last_portfolio_date = None
        # Forecast passes: re-latch only on a clean run with stored forecasts.
        if isinstance(outcome.get("forecast"), dict) and outcome["forecast"].get("error"):
            if _in_window(moment, (9, 30), (10, 30)):
                _last_forecast_am_date = None
            else:
                _last_forecast_pm_date = None
    return outcome


def reset_latches_for_tests() -> None:
    global _last_watch_date, _last_site_date, _last_sentinel_date
    global _last_portfolio_date, _last_alert_check_ts
    global _last_forecast_am_date, _last_forecast_pm_date, _last_prediction_date
    with _latch_lock:
        _last_watch_date = None
        _last_site_date = None
        _last_sentinel_date = None
        _last_portfolio_date = None
        _last_alert_check_ts = 0.0
        _last_forecast_am_date = None
        _last_forecast_pm_date = None
        _last_prediction_date = None


# ---------------------------------------------------------------------------
# chat intents (used by the server's dispatch chain)
# ---------------------------------------------------------------------------

_WATCH_ADD_PATTERNS = (
    "watch topic",
    "watch this topic",
    "add to my watchlist",
    "add to the watchlist",
    "watch the topic",
    "keep an eye on",
    "keep watching",
    "watch for",
    "start watching",
)

_WATCH_REMOVE_PATTERNS = (
    "stop watching",
    "remove from my watchlist",
    "remove from the watchlist",
    "unwatch",
    "drop the watch",
)

_WATCH_LIST_PATTERNS = (
    "my watchlist",
    "show my watchlist",
    "what am i watching",
    "what's on my watchlist",
    "whats on my watchlist",
    "list my watchlist",
    "watchlist status",
    "what topics am i watching",
)


def parse_watch_add(text: str) -> str | None:
    """Topic text when the message adds a watch; None otherwise.

    Matches on the lowercased form, slices from the original so the topic
    keeps the owner's casing (same rule as missions/memories).
    """
    low = (text or "").lower()
    for pattern in _WATCH_ADD_PATTERNS:
        idx = low.find(pattern)
        if idx < 0:
            continue
        after = text[idx + len(pattern):].lstrip(" :,-")
        if after.strip():
            return after.strip()
    return None


def parse_watch_remove(text: str) -> str | None:
    low = (text or "").lower()
    for pattern in _WATCH_REMOVE_PATTERNS:
        idx = low.find(pattern)
        if idx < 0:
            continue
        after = text[idx + len(pattern):].lstrip(" :,-")
        if after.strip():
            return after.strip()
    return None


def is_watchlist_query(low: str) -> bool:
    return any(p in low for p in _WATCH_LIST_PATTERNS)
