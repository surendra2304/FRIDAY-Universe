"""
notifications/price_alerts.py — Owner-defined price alert rules -> Telegram push.

F6 (batch 2): alert rules live in ``data/price_alert_rules.json`` and are
evaluated against live scanner prices. A triggered rule pushes one Telegram
message per trigger; ``rearm`` controls whether it fires once ("once") or once
per UTC day ("daily").

Rule shape:
    {
      "id": "btc-75k",            # unique, slug-style
      "symbol": "BTCUSDT",
      "type": "above" | "below" | "pct_change_24h",
      "threshold": 75000.0,       # price for above/below; percent for pct_change_24h
      "note": "resistance breakout watch",
      "active": true,
      "rearm": "once" | "daily",
      "triggered_at": null,       # last trigger ISO-UTC
      "last_trigger_day": null    # UTC date string, for daily re-arm
    }

Every file operation is fail-soft: a corrupt rules file never crashes the
engine — it is reported and skipped, never silently rewritten with fewer rules.
"""

from __future__ import annotations

import datetime
import json
import os
import re
from pathlib import Path

from logger import get_logger

logger = get_logger("price_alerts")

RULES_FILE = Path(os.getenv("PRICE_ALERT_RULES_FILE", "data/price_alert_rules.json"))

_VALID_TYPES = ("above", "below", "pct_change_24h")
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", str(text).lower()).strip("-") or "alert"


class PriceAlertEngine:
    """Evaluates owner price-alert rules against live prices."""

    def __init__(self, rules_file: Path | None = None):
        self.rules_file = rules_file or RULES_FILE

    # ------------------------------------------------------------------ rules
    def load_rules(self) -> list[dict]:
        try:
            raw = json.loads(self.rules_file.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return []
        except (OSError, json.JSONDecodeError) as exc:
            logger.error(f"[PRICE_ALERTS] rules file unreadable ({exc}); skipping this cycle")
            return []
        if not isinstance(raw, list):
            logger.error("[PRICE_ALERTS] rules file is not a list; skipping this cycle")
            return []
        return [r for r in raw if isinstance(r, dict)]

    def _save_rules(self, rules: list[dict]) -> bool:
        try:
            self.rules_file.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.rules_file.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(rules, indent=2), encoding="utf-8")
            tmp.replace(self.rules_file)
            return True
        except OSError as exc:
            logger.error(f"[PRICE_ALERTS] failed to persist rules: {exc}")
            return False

    def add_rule(self, symbol: str, rule_type: str, threshold: float,
                 note: str = "", rearm: str = "once", rule_id: str | None = None) -> tuple[bool, str, dict | None]:
        symbol = str(symbol).upper().strip()
        rule_type = str(rule_type).lower().strip()
        if rule_type in ("pct", "pct24h", "pct_24h", "change24h"):
            rule_type = "pct_change_24h"
        if rule_type not in _VALID_TYPES:
            return False, f"type must be one of {', '.join(_VALID_TYPES)} (got {rule_type!r})", None
        try:
            threshold = float(threshold)
        except (TypeError, ValueError):
            return False, f"threshold must be a number (got {threshold!r})", None
        if not symbol:
            return False, "symbol is required", None
        rules = self.load_rules()
        rule_id = rule_id or _slug(f"{symbol}-{rule_type}-{threshold}-{len(rules) + 1}")
        if any(r.get("id") == rule_id for r in rules):
            return False, f"rule id {rule_id!r} already exists", None
        rule = {
            "id": rule_id,
            "symbol": symbol,
            "type": rule_type,
            "threshold": threshold,
            "note": str(note or ""),
            "active": True,
            "rearm": "daily" if str(rearm).lower() == "daily" else "once",
            "triggered_at": None,
            "last_trigger_day": None,
        }
        rules.append(rule)
        if not self._save_rules(rules):
            return False, "could not persist the rules file", None
        return True, "added", rule

    def remove_rule(self, rule_id: str) -> tuple[bool, str]:
        rules = self.load_rules()
        remaining = [r for r in rules if r.get("id") != rule_id]
        if len(remaining) == len(rules):
            return False, f"no rule with id {rule_id!r}"
        self._save_rules(remaining)
        return True, f"removed {rule_id}"

    # ------------------------------------------------------------- evaluation
    def evaluate(self, prices: dict[str, float], pct_changes: dict[str, float] | None = None) -> list[dict]:
        """Evaluate all rules; returns triggered rule dicts (and persists state).

        ``prices``: symbol -> latest price. ``pct_changes``: symbol -> 24h
        percent change (e.g. -2.5 for -2.5%). Missing data never triggers.
        """
        pct_changes = pct_changes or {}
        rules = self.load_rules()
        if not rules:
            return []
        now = datetime.datetime.now(datetime.timezone.utc)
        today = now.date().isoformat()
        triggered: list[dict] = []
        changed = False

        for rule in rules:
            if not rule.get("active", True):
                continue
            symbol = str(rule.get("symbol", "")).upper()
            rtype = rule.get("type")
            threshold = rule.get("threshold")
            try:
                threshold = float(threshold)
            except (TypeError, ValueError):
                continue

            if rtype in ("above", "below"):
                price = prices.get(symbol)
                try:
                    price = float(price)
                except (TypeError, ValueError):
                    continue
                fired = price > threshold if rtype == "above" else price < threshold
                detail = f"price {price:,.4f} {'>' if rtype == 'above' else '<'} {threshold:,.4f}"
            elif rtype == "pct_change_24h":
                pct = pct_changes.get(symbol)
                try:
                    pct = float(pct)
                except (TypeError, ValueError):
                    continue
                fired = pct >= threshold if threshold >= 0 else pct <= threshold
                detail = f"24h change {pct:+.2f}% crossed {threshold:+.2f}%"
            else:
                continue

            if not fired:
                continue
            # Daily re-arm: only one trigger per UTC day.
            if rule.get("rearm") == "daily" and rule.get("last_trigger_day") == today:
                continue

            rule["triggered_at"] = now.isoformat()
            rule["last_trigger_day"] = today
            if rule.get("rearm") != "daily":
                rule["active"] = False
            changed = True
            rule["_detail"] = detail
            triggered.append(rule)

        if changed:
            self._save_rules(rules)
        for rule in triggered:
            logger.info(
                f"[PRICE_ALERT] TRIGGERED {rule.get('id')} {rule.get('symbol')} "
                f"{rule.get('type')} {rule.get('threshold')} ({rule.get('_detail')})"
            )
        return triggered

    @staticmethod
    def format_trigger(rule: dict) -> str:
        note = f" — {rule['note']}" if rule.get("note") else ""
        return (
            f"🔔 <b>PRICE ALERT</b> {rule.get('symbol')}\n"
            f"{rule.get('_detail', '')}{note}\n"
            f"<i>{rule.get('id')} · rearm: {rule.get('rearm', 'once')}</i>"
        )


def format_rules_help() -> str:
    return (
        "🔔 <b>Price alerts</b>\n"
        "• <code>/alert add SYMBOL above|below PRICE [note]</code>\n"
        "• <code>/alert add SYMBOL pct24h PERCENT [note]</code> (e.g. -5 for -5%)\n"
        "• <code>/alert add ... --daily</code> to re-arm daily\n"
        "• <code>/alert list</code> · <code>/alert del ID</code>\n\n"
        "<i>Alerts push to Telegram the moment a scanner price crosses a rule.</i>"
    )
