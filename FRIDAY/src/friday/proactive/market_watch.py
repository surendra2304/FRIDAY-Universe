"""Checklists F5/F6/F11/F12 (MASTER_COMPLETION_CHECKLIST) — Batch 7, ZAI Agent 2.

Scheduled market surfaces:

- F5  Daily portfolio report (09:00 IST): the same Stratex snapshot the chat
  tool returns, pushed to the owner's Telegram channel.
- F6  Alert rules ("alert me when BTC > 100k", "watch NIFTY dip < 24500"):
  file-backed rules, periodic check loop reading the live Stratex market
  analysis, Telegram push when a rule fires. One rule = one line, one
  trigger = one message (latched per rule+day so a flapping market does not
  spam). Read-only by construction — queries go through ask_stratex.
- F11 Forecast refresh (09:30 + 18:30 IST): twice-daily Futuris forecasts
  on owner-tracked markets, stored for the F12 accuracy check.
- F12 Prediction accuracy: every stored forecast is checked at its horizon
  end against the actual price/movement; logged HIT/MISS/PARTIAL with the
  delta; surfaced in the F3 usage dashboard and the daily self-report.

Honesty rules (identical to every FRIDAY surface): a market query that
fails or returns no signal is reported as such, never invented into an
all-clear. An alert that cannot be evaluated is silent (it does not fire
on a missing reading).
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
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable

from friday.core.owner_time import OWNER_TZ, now_owner_tz, owner_today

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# windows (IST clock)
# ---------------------------------------------------------------------------
PORTFOLIO_REPORT_WINDOW = (9, 0)   # 09:00–12:00 IST
PORTFOLIO_REPORT_END = (12, 0)
FORECAST_REFRESH_WINDOWS = ((9, 30), (18, 30))  # twice daily
FORECAST_REFRESH_END = (10, 30), (19, 30)
PREDICTION_SCORE_WINDOW = (21, 0)  # 21:00–23:00 IST: score matured forecasts
PREDICTION_SCORE_END = (23, 0)
ALERT_CHECK_INTERVAL_SEC = 600  # every 10 minutes
#: Markets tracked by default (used by F11 if the owner hasn't queued any).
DEFAULT_TRACKED_MARKETS = ("BTCUSDT", "ETHUSDT", "NIFTY")


def _in_window(now: datetime, start: tuple[int, int], end: tuple[int, int]) -> bool:
    moment = now.astimezone(OWNER_TZ)
    current = (moment.hour, moment.minute)
    return start <= current < end


# ---------------------------------------------------------------------------
# F3 — usage tracker (separate from the watch loop's responsibility)
# ---------------------------------------------------------------------------

def _usage_store_path() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "usage", "usage.json"))
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "..", "..", ".data", "usage", "usage.json"))


#: Free-tier soft limits (per agent, per day) — owner-tunable via env.
FREE_TIER_LIMITS: dict[str, dict[str, int]] = {
    "intelx": {"calls_per_day": 200, "tokens_per_day": 200_000},
    "stratex": {"calls_per_day": 200, "tokens_per_day": 0},
    "futuris": {"calls_per_day": 100, "tokens_per_day": 100_000},
    "cortex": {"calls_per_day": 300, "tokens_per_day": 0},
    "forge": {"calls_per_day": 50, "tokens_per_day": 0},
    "sentinel": {"calls_per_day": 100, "tokens_per_day": 0},
    "vyralx": {"calls_per_day": 30, "tokens_per_day": 0},
    "inference": {"calls_per_day": 500, "tokens_per_day": 500_000},
    "memora": {"calls_per_day": 1000, "tokens_per_day": 0},
}


class UsageTracker:
    """File-backed call/token counters per agent per day (F3)."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _usage_store_path()
        self._lock = threading.RLock()
        self._cache: dict[str, Any] | None = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load(self) -> dict[str, Any]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                self._cache = json.load(f)
        except FileNotFoundError:
            self._cache = {"days": {}}
        except Exception as exc:
            logger.warning("[USAGE] store unreadable (%s) — starting empty", exc)
            self._cache = {"days": {}}
        self._cache.setdefault("days", {})
        return self._cache

    def _save(self) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._cache, f, indent=2, sort_keys=True)
        os.replace(tmp, self._path)

    def record(self, agent_id: str, *, tokens: int = 0, calls: int = 1) -> None:
        """Increment the daily counters for ``agent_id`` (F3 source of truth)."""
        if not agent_id:
            return
        today = owner_today()
        with self._lock:
            data = self._load()
            day = data["days"].setdefault(today, {"agents": {}, "totals": {"calls": 0, "tokens": 0}})
            agent = day["agents"].setdefault(agent_id, {"calls": 0, "tokens": 0})
            agent["calls"] += int(calls)
            agent["tokens"] += int(tokens)
            day["totals"]["calls"] += int(calls)
            day["totals"]["tokens"] += int(tokens)
            # Keep only the last 14 days so the store stays bounded.
            if len(data["days"]) > 14:
                for old in sorted(data["days"])[:-14]:
                    del data["days"][old]
            self._save()

    def today_summary(self) -> dict[str, Any]:
        today = owner_today()
        with self._lock:
            data = self._load()
            day = data["days"].get(today, {"agents": {}, "totals": {"calls": 0, "tokens": 0}})
        per_agent: dict[str, Any] = {}
        for agent_id, stats in day.get("agents", {}).items():
            limits = FREE_TIER_LIMITS.get(agent_id, {})
            calls_cap = limits.get("calls_per_day", 0)
            tokens_cap = limits.get("tokens_per_day", 0)
            pct_calls = (100 * stats["calls"] / calls_cap) if calls_cap else 0
            pct_tokens = (100 * stats["tokens"] / tokens_cap) if tokens_cap else 0
            per_agent[agent_id] = {
                "calls": stats["calls"],
                "tokens": stats["tokens"],
                "calls_cap": calls_cap,
                "tokens_cap": tokens_cap,
                "calls_pct": round(pct_calls, 1),
                "tokens_pct": round(pct_tokens, 1),
                "calls_state": _rate_limit_state(pct_calls),
                "tokens_state": _rate_limit_state(pct_tokens),
            }
        return {
            "date": today,
            "totals": day.get("totals", {"calls": 0, "tokens": 0}),
            "agents": per_agent,
            "limits": {k: v for k, v in FREE_TIER_LIMITS.items()},
        }

    def rate_limit_guard(self) -> dict[str, Any]:
        """F3: return the agents currently above their soft (80%) or hard (100%) limits."""
        s = self.today_summary()
        warnings: list[dict[str, Any]] = []
        blocked: list[dict[str, Any]] = []
        for agent_id, a in s["agents"].items():
            if a["calls_state"] == "hard_stop":
                blocked.append({"agent": agent_id, "dimension": "calls", "pct": a["calls_pct"]})
            elif a["calls_state"] == "soft_warn":
                warnings.append({"agent": agent_id, "dimension": "calls", "pct": a["calls_pct"]})
            if a["tokens_state"] == "hard_stop":
                blocked.append({"agent": agent_id, "dimension": "tokens", "pct": a["tokens_pct"]})
            elif a["tokens_state"] == "soft_warn":
                warnings.append({"agent": agent_id, "dimension": "tokens", "pct": a["tokens_pct"]})
        return {
            "date": s["date"],
            "soft_warnings": warnings,
            "hard_blocks": blocked,
            "status": "blocked" if blocked else ("warning" if warnings else "ok"),
        }

    def reset_for_tests(self, path: str | None = None) -> None:
        self._path = path or self._path
        self._cache = None


def _rate_limit_state(pct: float) -> str:
    if pct >= 100.0:
        return "hard_stop"
    if pct >= 80.0:
        return "soft_warn"
    return "ok"


#: Process-wide singleton.
usage_tracker = UsageTracker()


# ---------------------------------------------------------------------------
# F6 — alert rules engine
# ---------------------------------------------------------------------------

def _alerts_store_path() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "alerts", "alerts.json"))
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "..", "..", ".data", "alerts", "alerts.json"))


_ALERT_PATTERN = re.compile(
    r"(?P<symbol>[A-Za-z][A-Za-z0-9]+)\s+(?P<direction>above|below|>|<|>=|<=|crosses)\s+"
    r"(?P<target>[\d.,]+)",
    re.IGNORECASE,
)


class AlertRule:
    """One owner-defined price alert (F6)."""

    __slots__ = ("symbol", "direction", "target", "created_ist", "rule_id", "last_fired_ist")

    def __init__(
        self,
        symbol: str,
        direction: str,
        target: float,
        *,
        created_ist: str = "",
        rule_id: str = "",
        last_fired_ist: str = "",
    ) -> None:
        self.symbol = symbol.upper()
        self.direction = direction.lower().replace("crosses", "above")
        # Normalize the operator forms into {above, below}
        if self.direction in (">", ">="):
            self.direction = "above"
        elif self.direction in ("<", "<="):
            self.direction = "below"
        self.target = float(target)
        self.created_ist = created_ist or now_owner_tz().isoformat()
        self.rule_id = rule_id or hashlib.sha256(
            f"{self.symbol}:{self.direction}:{self.target}".encode()
        ).hexdigest()[:10]
        self.last_fired_ist = last_fired_ist

    def evaluate(self, last_price: float | None) -> tuple[bool, str]:
        """Return (fires, reason). ``last_price`` is None when the market query
        returned no reading — the alert does NOT fire on missing data."""
        if last_price is None:
            return False, "no market reading available (alert did not fire on missing data)"
        if self.direction == "above" and last_price >= self.target:
            return True, f"{self.symbol} at {last_price} crossed above {self.target}"
        if self.direction == "below" and last_price <= self.target:
            return True, f"{self.symbol} at {last_price} crossed below {self.target}"
        return False, f"{self.symbol} at {last_price} not yet {self.direction} {self.target}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "direction": self.direction,
            "target": self.target,
            "created_ist": self.created_ist,
            "rule_id": self.rule_id,
            "last_fired_ist": self.last_fired_ist,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "AlertRule":
        return cls(
            d["symbol"], d["direction"], float(d["target"]),
            created_ist=d.get("created_ist", ""),
            rule_id=d.get("rule_id", ""),
            last_fired_ist=d.get("last_fired_ist", ""),
        )


class AlertStore:
    """File-backed price-alert rules (F6)."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _alerts_store_path()
        self._lock = threading.RLock()
        self._cache: list[dict[str, Any]] | None = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = data.get("rules", []) if isinstance(data, dict) else []
        except FileNotFoundError:
            self._cache = []
        except Exception as exc:
            logger.warning("[ALERT] store unreadable (%s) — starting empty", exc)
            self._cache = []
        return self._cache

    def _save(self) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"rules": self._cache}, f, indent=2, sort_keys=True)
        os.replace(tmp, self._path)

    def add(self, rule: AlertRule) -> dict[str, Any]:
        with self._lock:
            rules = self._load()
            for r in rules:
                if r["rule_id"] == rule.rule_id:
                    return r  # idempotent
            d = rule.to_dict()
            rules.append(d)
            self._cache = rules
            self._save()
            return d

    def remove(self, rule_id: str) -> bool:
        with self._lock:
            rules = self._load()
            for i, r in enumerate(rules):
                if r["rule_id"] == rule_id:
                    del rules[i]
                    self._cache = rules
                    self._save()
                    return True
            return False

    def list(self) -> list[dict[str, Any]]:
        with self._lock:
            return list(self._load())

    def mark_fired(self, rule_id: str) -> None:
        with self._lock:
            for r in self._load():
                if r["rule_id"] == rule_id:
                    r["last_fired_ist"] = now_owner_tz().isoformat()
            self._save()

    def reset_for_tests(self, path: str | None = None) -> None:
        self._path = path or self._path
        self._cache = None


#: Process-wide singleton.
alert_store = AlertStore()


def parse_alert_rule(text: str) -> AlertRule | None:
    """Parse 'alert me when BTC > 100k' / 'watch NIFTY dip below 24500'.

    Returns None for messages that don't look like alert rules.
    """
    if not text:
        return None
    low = text.lower()
    # Strip the leading phrase the owner uses; we only need the condition.
    for prefix in (
        "alert me when ", "alert me if ", "alert when ", "alert if ",
        "watch for ", "watch ", "notify me when ", "notify me if ",
        "ping me when ", "ping me if ", "tell me when ", "tell me if ",
    ):
        if low.startswith(prefix):
            text = text[len(prefix):]
            low = text.lower()
            break
    # Replace common natural-language operators
    low_norm = (
        low.replace("dips below", "below")
        .replace("dip below", "below")
        .replace("drops below", "below")
        .replace("drop below", "below")
        .replace("falls below", "below")
        .replace("fall below", "below")
        .replace("rises above", "above")
        .replace("rise above", "above")
        .replace("crosses above", "above")
        .replace("cross above", "above")
        .replace("crosses below", "below")
        .replace("cross below", "below")
    )
    # Strip thousands separators so '100k' or '100,000' parse
    cleaned = low_norm.replace("k", "000").replace("m", "000000")
    m = _ALERT_PATTERN.search(cleaned)
    if not m:
        return None
    try:
        target = float(m.group("target").replace(",", ""))
    except ValueError:
        return None
    return AlertRule(m.group("symbol"), m.group("direction"), target)


# ---------------------------------------------------------------------------
# F11/F12 — forecasts store + prediction scoring
# ---------------------------------------------------------------------------

def _forecasts_store_path() -> str:
    cwd = os.getcwd()
    if os.path.basename(cwd) == "FRIDAY" or os.path.isdir(os.path.join(cwd, ".data")):
        return os.path.abspath(os.path.join(cwd, ".data", "forecasts", "forecasts.json"))
    here = os.path.dirname(__file__)
    return os.path.abspath(os.path.join(here, "..", "..", ".data", "forecasts", "forecasts.json"))


#: Map a Futuris horizon to the seconds the prediction must mature before scoring.
HORIZON_SECONDS: dict[str, int] = {
    "1h": 3600,
    "24h": 24 * 3600,
    "7d": 7 * 24 * 3600,
    "30d": 30 * 24 * 3600,
}


class ForecastStore:
    """File-backed forecast log + accuracy scoring (F11/F12)."""

    def __init__(self, path: str | None = None) -> None:
        self._path = path or _forecasts_store_path()
        self._lock = threading.RLock()
        self._cache: list[dict[str, Any]] | None = None
        os.makedirs(os.path.dirname(self._path), exist_ok=True)

    def _load(self) -> list[dict[str, Any]]:
        if self._cache is not None:
            return self._cache
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self._cache = data.get("forecasts", []) if isinstance(data, dict) else []
        except FileNotFoundError:
            self._cache = []
        except Exception as exc:
            logger.warning("[FORECAST] store unreadable (%s) — starting empty", exc)
            self._cache = []
        return self._cache

    def _save(self) -> None:
        tmp = f"{self._path}.tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"forecasts": self._cache}, f, indent=2, sort_keys=True)
        os.replace(tmp, self._path)

    def record(self, target: str, horizon: str, predicted: str, *, raw_text: str = "") -> dict[str, Any]:
        """Log a fresh forecast (F11). Returns the stored record."""
        today = now_owner_tz()
        rec = {
            "id": hashlib.sha256(f"{target}:{horizon}:{today.isoformat()}".encode()).hexdigest()[:10],
            "target": target,
            "horizon": horizon,
            "horizon_seconds": HORIZON_SECONDS.get(horizon, 0),
            "predicted": predicted,
            "raw_text": (raw_text or "")[:500],
            "issued_ist": today.isoformat(),
            "matures_ist": (today + timedelta(seconds=HORIZON_SECONDS.get(horizon, 0))).isoformat(),
            "status": "pending",
            "actual": None,
            "scored_ist": "",
            "delta": None,
        }
        with self._lock:
            forecasts = self._load()
            forecasts.append(rec)
            # Keep only the last 200 forecasts.
            if len(forecasts) > 200:
                forecasts = forecasts[-200:]
            self._cache = forecasts
            self._save()
        return rec

    def matured_unscored(self) -> list[dict[str, Any]]:
        """F12: forecasts whose horizon has elapsed but still pending."""
        now = now_owner_tz()
        out: list[dict[str, Any]] = []
        with self._lock:
            for f in self._load():
                if f.get("status") != "pending":
                    continue
                try:
                    matures = datetime.fromisoformat(f["matures_ist"])
                except Exception:
                    continue
                if now >= matures:
                    out.append(f)
        return out

    def score(self, forecast_id: str, actual: str, delta: float | None = None) -> dict[str, Any] | None:
        """Mark a forecast with its actual outcome (F12)."""
        with self._lock:
            for f in self._load():
                if f["id"] == forecast_id:
                    f["actual"] = actual
                    f["delta"] = delta
                    # HIT if predicted direction matches actual; PARTIAL on close.
                    f["status"] = _classify_accuracy(f.get("predicted", ""), actual, delta)
                    f["scored_ist"] = now_owner_tz().isoformat()
                    self._save()
                    return dict(f)
        return None

    def summary(self) -> dict[str, Any]:
        with self._lock:
            forecasts = list(self._load())
        scored = [f for f in forecasts if f["status"] in {"hit", "miss", "partial"}]
        hits = sum(1 for f in scored if f["status"] == "hit")
        misses = sum(1 for f in scored if f["status"] == "miss")
        partials = sum(1 for f in scored if f["status"] == "partial")
        return {
            "total": len(forecasts),
            "pending": len(forecasts) - len(scored),
            "scored": len(scored),
            "hits": hits,
            "misses": misses,
            "partials": partials,
            "accuracy": round(100 * hits / max(1, len(scored)), 1),
        }

    def reset_for_tests(self, path: str | None = None) -> None:
        self._path = path or self._path
        self._cache = None


def _classify_accuracy(predicted: str, actual: str, delta: float | None) -> str:
    """Heuristic: HIT when the prediction's direction matches the actual;
    PARTIAL when both move together but the magnitude is close (|delta| small);
    MISS otherwise. The actual scoring keeps Futuris honest — it never
    invents a HIT."""
    p = (predicted or "").lower()
    a = (actual or "").lower()
    p_up = any(w in p for w in ("up", "rise", "rise", "bull", "increase", "higher", "growth"))
    p_down = any(w in p for w in ("down", "fall", "drop", "bear", "decrease", "lower", "decline"))
    a_up = any(w in a for w in ("up", "rise", "bull", "increase", "higher", "growth"))
    a_down = any(w in a for w in ("down", "fall", "drop", "bear", "decrease", "lower", "decline"))
    if (p_up and a_up) or (p_down and a_down):
        if delta is not None and abs(delta) <= 0.05:
            return "partial"
        return "hit"
    return "miss"


#: Process-wide singleton.
forecast_store = ForecastStore()


# ---------------------------------------------------------------------------
# the scheduled passes (driven by the agent_watch lifespan loop)
# ---------------------------------------------------------------------------

async def _portfolio_snapshot() -> str:
    """Real Stratex portfolio snapshot via the same dispatch the chat tool uses."""
    from friday.ecosystem.fleet_client import FleetClient

    client = FleetClient()
    try:
        result = await client.ask_stratex("daily portfolio report")
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
    reply = (result or {}).get("reply") or ""
    if not reply:
        reply = "Stratex did not return a portfolio snapshot — reported honestly, not guessed."
    usage_tracker.record("stratex", calls=1)
    return reply


async def run_daily_portfolio_report(
    deliver: Callable[[str], Awaitable[bool]] | None = None,
    *,
    snapshot_fn: Callable[[], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """F5: push the live Stratex snapshot to the owner at 09:00 IST."""
    if deliver is None:
        async def deliver(text: str) -> bool:  # noqa: F811
            from friday.proactive.telegram_gateway import send_owner_message

            try:
                return bool(send_owner_message(text))
            except Exception:
                return False

    results: dict[str, Any] = {"date": owner_today(), "delivered": False}
    try:
        snapshot = await (snapshot_fn or _portfolio_snapshot)()
    except Exception as exc:
        logger.warning("[F5] portfolio snapshot failed: %s", exc)
        snapshot = f"Stratex portfolio report could not be generated ({type(exc).__name__}). Reported honestly."
    text = f"💼 Daily portfolio report — {owner_today()} (IST):\n\n{snapshot}\n\nRead-only snapshot; no orders were placed (fail-closed, D-015)."
    try:
        results["delivered"] = bool(await deliver(text))
    except Exception as exc:
        logger.warning("[F5] delivery failed: %s", exc)
    return results


async def _stratex_market_query(symbol: str) -> dict[str, Any]:
    """One market signal query through the same Stratex dispatch."""
    from friday.ecosystem.fleet_client import FleetClient

    client = FleetClient()
    try:
        result = await client.ask_stratex(f"analyze current market signals for {symbol}")
    finally:
        try:
            await client.aclose()
        except Exception:
            pass
    usage_tracker.record("stratex", calls=1)
    return result or {}


async def _extract_last_price(symbol: str, stratex_result: dict[str, Any]) -> float | None:
    """Pull the most recent price from a Stratex analysis result. Honest None
    when no price is reported — never invented."""
    if not isinstance(stratex_result, dict):
        return None
    # Walk the common shapes: signals[].price, signals[].last_price, data.price.
    sigs = stratex_result.get("signals")
    if isinstance(sigs, list):
        for s in sigs:
            if not isinstance(s, dict):
                continue
            for k in ("price", "last_price", "last"):
                v = s.get(k)
                if isinstance(v, (int, float)) and v > 0:
                    return float(v)
            txt = str(s.get("text") or "")
            m = re.search(rf"{symbol}[^0-9]*\$?([\d.,]+)", txt, re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except ValueError:
                    pass
    data = stratex_result.get("data")
    if isinstance(data, dict):
        v = data.get("price") or data.get("last_price")
        if isinstance(v, (int, float)) and v > 0:
            return float(v)
    return None


async def run_alert_check(
    deliver: Callable[[str], Awaitable[bool]] | None = None,
    *,
    query_fn: Callable[[str], Awaitable[dict[str, Any]]] | None = None,
) -> dict[str, Any]:
    """F6: evaluate every alert rule against the live market; fire+push when
    a rule crosses its threshold. Once per rule per day (latched)."""
    if deliver is None:
        async def deliver(text: str) -> bool:  # noqa: F811
            from friday.proactive.telegram_gateway import send_owner_message

            try:
                return bool(send_owner_message(text))
            except Exception:
                return False

    query = query_fn or _stratex_market_query
    rules = alert_store.list()
    results: dict[str, Any] = {"date": owner_today(), "evaluated": 0, "fired": 0, "deliveries": 0, "skipped_missing": 0}
    today = owner_today()
    for r_dict in rules:
        rule = AlertRule.from_dict(r_dict)
        results["evaluated"] += 1
        # Latch: a rule fires once per day.
        if (r_dict.get("last_fired_ist") or "")[:10] == today:
            continue
        try:
            stratex_result = await query(rule.symbol)
        except Exception as exc:
            logger.warning("[F6] market query failed for %s: %s", rule.symbol, exc)
            results["skipped_missing"] += 1
            continue
        last_price = await _extract_last_price(rule.symbol, stratex_result)
        if last_price is None:
            results["skipped_missing"] += 1
            continue
        fires, reason = rule.evaluate(last_price)
        if fires:
            results["fired"] += 1
            alert_store.mark_fired(rule.rule_id)
            text = (
                f"🔔 Alert fired — {owner_today()} (IST):\n"
                f"• Rule: {rule.symbol} {rule.direction} {rule.target}\n"
                f"• {reason}\n"
                f"Read-only market query; no orders were placed (fail-closed, D-015)."
            )
            try:
                if await deliver(text):
                    results["deliveries"] += 1
            except Exception as exc:
                logger.warning("[F6] delivery failed: %s", exc)
    return results


async def run_forecast_refresh(
    deliver: Callable[[str], Awaitable[bool]] | None = None,
    *,
    forecast_fn: Callable[[str, str], Awaitable[dict[str, Any]]] | None = None,
    tracked: tuple[str, ...] = DEFAULT_TRACKED_MARKETS,
    horizon: str = "24h",
) -> dict[str, Any]:
    """F11: twice-daily forecast refresh on tracked markets. Stores each one
    for the F12 accuracy check. No delivery (the owner gets the daily
    self-report digest); the deliver arg is accepted for parity/tests."""
    results: dict[str, Any] = {"date": owner_today(), "issued": 0, "stored": 0, "errors": []}

    async def default_forecast(target: str, h: str) -> dict[str, Any]:
        from friday.ecosystem.fleet_client import FleetClient

        client = FleetClient()
        try:
            r = await client.request_futuris_forecast(target=target, horizon=h)
        finally:
            try:
                await client.aclose()
            except Exception:
                pass
        usage_tracker.record("futuris", calls=1)
        return r or {}

    ff = forecast_fn or default_forecast
    for target in tracked:
        results["issued"] += 1
        try:
            r = await ff(target, horizon)
        except Exception as exc:
            results["errors"].append(f"{target}: {type(exc).__name__}")
            continue
        predicted = str((r or {}).get("reply") or "")[:500]
        if predicted:
            forecast_store.record(target, horizon, predicted, raw_text=predicted)
            results["stored"] += 1
    if deliver is not None and results["stored"]:
        try:
            await deliver(f"🔮 {results['stored']} forecast(s) refreshed for {', '.join(tracked)} ({horizon}).")
        except Exception:
            pass
    return results


async def run_prediction_scoring(
    *,
    actual_fn: Callable[[str], Awaitable[str]] | None = None,
) -> dict[str, Any]:
    """F12: score every forecast whose horizon has elapsed. Honest when
    the actual-price query fails (the forecast stays pending, not a fake MISS)."""
    async def default_actual(target: str) -> str:
        # Reuse the Stratex market query — same read-only path, price extraction.
        r = await _stratex_market_query(target)
        price = await _extract_last_price(target, r)
        return f"{target} at {price}" if price is not None else ""

    actual_fn = actual_fn or default_actual
    results: dict[str, Any] = {"date": owner_today(), "scored": 0, "skipped": 0, "summary": forecast_store.summary()}
    for f in forecast_store.matured_unscored():
        try:
            actual = await actual_fn(f["target"])
        except Exception as exc:
            logger.warning("[F12] actual query failed for %s: %s", f["target"], exc)
            results["skipped"] += 1
            continue
        if not actual:
            results["skipped"] += 1
            continue
        forecast_store.score(f["id"], actual)
        results["scored"] += 1
    results["summary"] = forecast_store.summary()
    return results


# ---------------------------------------------------------------------------
# chat intents (used by the server's fast-path chain)
# ---------------------------------------------------------------------------

_ALERT_ADD_PATTERNS = (
    "alert me when ", "alert me if ", "alert when ", "alert if ",
    "watch for ", "notify me when ", "notify me if ",
    "ping me when ", "ping me if ", "tell me when ", "tell me if ",
)
_ALERT_LIST_PATTERNS = ("my alerts", "show my alerts", "list my alerts", "what am i alerting on", "alerts list")
_ALERT_REMOVE_PATTERNS = ("cancel alert ", "remove alert ", "delete alert ", "stop alerting on ")


def parse_alert_add(text: str) -> AlertRule | None:
    """Return an AlertRule when the message adds one, else None."""
    low = (text or "").lower()
    if not any(low.startswith(p) for p in _ALERT_ADD_PATTERNS) and "alert me when" not in low and "alert when" not in low:
        return None
    return parse_alert_rule(text)


def is_alert_list_query(low: str) -> bool:
    return any(p in low for p in _ALERT_LIST_PATTERNS)


def parse_alert_remove(text: str) -> str | None:
    low = (text or "").lower()
    for p in _ALERT_REMOVE_PATTERNS:
        if low.startswith(p):
            tail = text[len(p):].strip()
            return tail or None
    return None
