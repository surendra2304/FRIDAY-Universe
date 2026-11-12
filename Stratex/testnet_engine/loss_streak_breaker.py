"""
loss_streak_breaker.py — Consecutive-loss circuit breaker (2026-11-13)

Why this exists: the daily-loss breaker (RC1) halts on a PERCENT of day-start
equity, so a losing streak of small trades never trips it. The demo ledger's
tail (2026-09-26) shows exactly that shape: six consecutive losses in one
session totalling only -$0.61 — pennies, far under any percent limit — while
the strategy was clearly misaligned with the market that day. A prop desk
stops a bleeding strategy on the STREAK, not only on the amount.

Mechanics (mirrors daily_loss_breaker on purpose — one pattern, two triggers):
  * The ledger (testnet_trade_ledger.jsonl) is the single source of truth for
    closed-trade net PnL. Each close is consulted via ``check_close()``.
  * After LOSS_STREAK_LIMIT consecutive losing trades (default 5):
      - ALL new entries are paused via the same battle-tested trading_pause
        flag the daily-loss breaker uses (fail-closed, file-backed, already
        consulted by the execution path before every entry)
      - a Telegram alert is sent (best-effort, never fatal)
      - a loud log line is written
  * A winning trade resets the streak.
  * The streak counter is persisted (loss_streak_breaker_state.json) so an
    engine restart cannot forget a running streak — a restart mid-streak is
    exactly when forgetting is most dangerous.
  * The breaker never touches OPEN positions or their protective orders.
    It only stops NEW entries.
  * Release: like any pause — /resume on the Telegram bot or the control API
    (owner decision, by design). The alert states the streak and the pause
    actor so the owner knows why the bot went quiet.
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

logger = get_logger("loss_streak_breaker")

DEFAULT_STATE_FILE = "loss_streak_breaker_state.json"
#: After how many consecutive losing trades new entries are paused.
DEFAULT_STREAK_LIMIT = 5
PAUSE_ACTOR = "loss_streak_breaker"


def _state_file() -> Path:
    return Path(os.getenv("LOSS_STREAK_BREAKER_STATE_FILE", DEFAULT_STATE_FILE))


def _load_state() -> dict:
    path = _state_file()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


class LossStreakBreaker:
    """Halts ALL new entries after too many consecutive losing trades."""

    def __init__(
        self,
        streak_limit: int = DEFAULT_STREAK_LIMIT,
        *,
        alerter: Callable[[str], None] | None = None,
        state_file: str | None = None,
    ):
        self.streak_limit = int(streak_limit)
        if self.streak_limit < 1:
            raise ValueError(f"LOSS_STREAK_LIMIT must be >= 1, got {streak_limit}")
        self.alerter = alerter
        if state_file:
            os.environ["LOSS_STREAK_BREAKER_STATE_FILE"] = state_file

    # ------------------------------------------------------------------
    # State (persisted, restart-safe)
    # ------------------------------------------------------------------
    def _read_streak(self) -> int:
        state = _load_state()
        streak = state.get("consecutive_losses")
        return streak if isinstance(streak, int) and streak >= 0 else 0

    def _write_streak(self, streak: int) -> None:
        state = {
            "consecutive_losses": int(streak),
            "updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }
        try:
            atomic_write_json(str(_state_file()), state)
        except OSError as exc:
            logger.error(f"[LOSS_STREAK_BREAKER] state persist failed: {exc}")

    # ------------------------------------------------------------------
    # The check — called once per CLOSED trade, with its net PnL
    # ------------------------------------------------------------------
    def check_close(self, net_pnl_raw: float) -> dict:
        """Fold one closed trade's net PnL into the streak; pause on breach.

        Returns the decision record (logged, testable). Never raises.
        """
        pnl = finite_float(net_pnl_raw)
        if pnl is None:
            # Unreadable PnL can't prove a loss OR a win; skip it loudly.
            logger.warning(f"[LOSS_STREAK_BREAKER] unreadable net_pnl {net_pnl_raw!r}; skipped")
            return {"checked": False, "reason": "UNREADABLE_PNL"}

        streak = self._read_streak()
        streak = streak + 1 if pnl < 0 else 0
        self._write_streak(streak)

        result = {
            "checked": True,
            "net_pnl": pnl,
            "consecutive_losses": streak,
            "streak_limit": self.streak_limit,
            "breached": streak >= self.streak_limit,
            "paused": is_trading_paused(),
        }
        if not result["breached"]:
            return result

        # --- BREACHED: pause ALL new entries + alert -------------------
        # Alert exactly ONCE per pause episode: only the check that CAUSES
        # the transition into paused sends the Telegram alert. Further
        # losses while already paused deepen the logged streak silently
        # (it is in the log and the state file); a win resets the streak,
        # and the next trip alerts again.
        was_paused = is_trading_paused()
        set_trading_paused(True, actor=PAUSE_ACTOR)
        logger.critical(
            f"[LOSS_STREAK_BREAKER] STREAK LIMIT BREACHED: {streak} consecutive "
            f"losing trades (limit {self.streak_limit}). ALL new entries paused "
            "(open positions keep their protective brackets). Release with "
            "/resume when you decide."
        )
        if not was_paused:
            message = (
                "STOP: Stratex loss-streak circuit breaker tripped.\n"
                f"Consecutive losing trades: {streak} (limit {self.streak_limit})\n"
                f"Last trade net PnL: {pnl:+.2f} USD\n"
                "New entries are paused until you send /resume.\n"
                "Open positions keep their protective SL/TP brackets."
            )
            if self.alerter:
                try:
                    self.alerter(message)
                except Exception as exc:  # never fatal
                    logger.error(f"[LOSS_STREAK_BREAKER] alert failed: {exc}")
        return result

    # ------------------------------------------------------------------
    # test hook
    # ------------------------------------------------------------------
    def reset_for_tests(self) -> None:
        self._write_streak(0)
