"""
daily_loss_breaker.py — Daily-loss circuit breaker (2026-11-11 incident fix)

Why this exists: the engine lost >$2,000 in 12 hours on the demo account with
nothing stopping it (see Stratex/docs/INCIDENT_2026-11-11_LOSSES.md RC1).
Per-trade risk caps exist, but repeated re-entries compound through a whole
losing day with no stop. A LiveRiskEnforcer with daily limits exists in
risk/live_risk_enforcer.py but is not wired into the testnet execution path —
this module is the wiring that actually halts trading.

Mechanics:
  * Day-start equity is captured once per IST day and persisted
    (daily_loss_breaker_state.json) so engine restarts keep the same baseline.
  * Day PnL = current_equity - day_start_equity. Because the equity source
    (futures totalMarginBalance) already includes unrealized PnL, this single
    number covers realized + open losses.
  * When day PnL falls to <= -DAILY_LOSS_LIMIT_PCT of day-start equity:
      - ALL new entries are paused via the battle-tested trading_pause flag
        (fail-closed, file-backed, already consulted by the execution path)
      - a Telegram alert is sent (best-effort, never fatal)
      - a loud log line is written
  * The breaker never touches OPEN positions or their protective orders —
    risk gates and brackets keep managing them. It only stops NEW entries.
  * The pause is released the same way any pause is: /resume on the Telegram
    bot or the control API (owner decision, by design).
"""
from __future__ import annotations

import datetime
import json
import os
from pathlib import Path
from typing import Callable

from atomic_io import atomic_write_json
from logger import get_logger
from numeric_safety import finite_float
from trading_pause import is_trading_paused, set_trading_paused

logger = get_logger("daily_loss_breaker")

DEFAULT_STATE_FILE = "daily_loss_breaker_state.json"
IST = datetime.timezone(datetime.timedelta(hours=5, minutes=30))


def _state_file() -> Path:
    return Path(os.getenv("DAILY_LOSS_BREAKER_STATE_FILE", DEFAULT_STATE_FILE))


def _today_ist() -> str:
    return datetime.datetime.now(IST).date().isoformat()


def _load_state() -> dict:
    path = _state_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class DailyLossBreaker:
    """Halts ALL new entries after the daily loss limit is breached."""

    def __init__(
        self,
        loss_limit_pct: float,
        *,
        alerter: Callable[[str], None] | None = None,
        state_file: str | None = None,
    ):
        self.loss_limit_pct = float(loss_limit_pct)
        if not (0.0 < self.loss_limit_pct <= 0.50):
            raise ValueError(f"DAILY_LOSS_LIMIT_PCT must be in (0, 0.50], got {loss_limit_pct}")
        self.alerter = alerter
        if state_file:
            os.environ["DAILY_LOSS_BREAKER_STATE_FILE"] = state_file
        self._alerted_today: str | None = None

    # ------------------------------------------------------------------
    # State: day-start equity baseline (persisted, restart-safe)
    # ------------------------------------------------------------------
    def _day_start_equity(self, current_equity: float) -> float:
        state = _load_state()
        today = _today_ist()
        if state.get("day") == today and finite_float(state.get("day_start_equity")):
            return float(state["day_start_equity"])
        # New IST day (or first run): capture the baseline.
        state = {
            "day": today,
            "day_start_equity": current_equity,
            "updated_at": datetime.datetime.now(IST).isoformat(),
        }
        try:
            atomic_write_json(str(_state_file()), state)
        except OSError as exc:
            logger.error(f"[DAILY_LOSS_BREAKER] state persist failed: {exc}")
        return current_equity

    # ------------------------------------------------------------------
    # The check — called from the position monitor loop each cycle
    # ------------------------------------------------------------------
    def check(self, current_equity_raw: float) -> dict:
        equity = finite_float(current_equity_raw)
        if equity is None or equity <= 0:
            # Unreadable equity can't prove safety; keep the current pause
            # state but never trigger on garbage.
            logger.warning(f"[DAILY_LOSS_BREAKER] unreadable equity {current_equity_raw!r}; skipping check")
            return {"checked": False, "reason": "UNREADABLE_EQUITY"}

        day_start = self._day_start_equity(equity)
        if day_start <= 0:
            return {"checked": False, "reason": "INVALID_DAY_START"}

        day_pnl = equity - day_start
        day_pnl_pct = day_pnl / day_start
        today = _today_ist()

        result = {
            "checked": True,
            "day": today,
            "day_start_equity": day_start,
            "current_equity": equity,
            "day_pnl": round(day_pnl, 4),
            "day_pnl_pct": round(day_pnl_pct, 6),
            "loss_limit_pct": self.loss_limit_pct,
            "breached": day_pnl_pct <= -self.loss_limit_pct,
            "paused": is_trading_paused(),
        }

        if not result["breached"]:
            return result

        # --- BREACHED: pause ALL new entries + alert -------------------
        if not is_trading_paused():
            set_trading_paused(True, actor="daily_loss_breaker")
            logger.critical(
                f"[DAILY_LOSS_BREAKER] DAILY LOSS LIMIT BREACHED: day PnL "
                f"{day_pnl:+.2f} ({day_pnl_pct*100:.2f}%) <= -{self.loss_limit_pct*100:.1f}% of "
                f"day-start equity {day_start:.2f}. ALL new entries paused (open positions keep "
                f"their protective brackets). Release with /resume when you decide."
            )

        if self._alerted_today != today:
            self._alerted_today = today
            message = (
                "STOP: Stratex daily-loss circuit breaker tripped.\n"
                f"Day PnL: {day_pnl:+.2f} USD ({day_pnl_pct*100:.2f}%)\n"
                f"Limit: -{self.loss_limit_pct*100:.1f}% | Day-start equity: {day_start:.2f}\n"
                "All NEW entries paused. Open positions keep protective brackets.\n"
                "Release with /resume if you want trading to continue today."
            )
            if self.alerter is not None:
                try:
                    self.alerter(message)
                except Exception as exc:  # alerting must never break trading logic
                    logger.error(f"[DAILY_LOSS_BREAKER] alert failed: {exc}")

        result["paused"] = True
        return result
