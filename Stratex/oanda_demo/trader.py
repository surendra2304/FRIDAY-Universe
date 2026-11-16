"""
oanda_demo/trader.py — Live OANDA demo (practice) trading engine for Stratex.

Owner directive (2026-11-13): implement OANDA demo trading and make Stratex
take profitable trades.

What one scan (--once) does:
  1. Pull the real account state (balance / equity / margin).
  2. Daily-loss circuit breaker (-3% NAV) and max-position governor.
  3. Manage open trades: strategy exit rules (MR rule exit, Donchian
     chandelier trailing stop — OANDA-side, survives restarts), detect
     closes, apply per-instrument cooldowns.
  4. Scan the watchlist with the configured strategy engine
     (STRATEX_OANDA_STRATEGY; default FX-MR-v4 mean reversion).
  5. Size each entry to 0.1% account risk (venue basis — this account
     IS the venue account), under a 2% aggregate heat cap across this
     engine's own open trades and the 25%-of-equity notional cap
     (TASK-STR-FWD-006 decided package; was 1% per trade, no heat cap)
     and free margin, then fire a MARKET order with native SL/TP attached.
  6. Log to data/oanda_demo_trades.csv and notify the owner on Telegram.

Usage (from the Stratex/ directory):
    python3 -m oanda_demo.trader --status          # account + open trades
    python3 -m oanda_demo.trader --once            # one scan (act on signals)
    python3 -m oanda_demo.trader --once --dry-run  # signals only, no orders
    python3 -m oanda_demo.trader --loop --interval 300
    python3 -m oanda_demo.trader --flatten         # emergency: close all trades

Credentials: OANDA_API_KEY / OANDA_ACCOUNT_ID env vars, else credentials.md.

TASK-STR-FWD-004 (2026-11-15): the owner directed OANDA activation under
measurement. Three things changed; the trading logic did not:
  * Governance — entries may open only when the configured strategy is a
    VALIDATED forward-protocol entrant for this venue in
    config_strategy.PRODUCTION_STRATEGY_REGISTRY (governance_status).
    Unregistered/unclassified configurations fail closed, even with the
    manual entries pause lifted. The pause itself is unchanged and
    remains an authoritative manual override.
  * Measurement — opens are position-tagged and closes are booked into
    the shared Phase-2 fill ledger (measurement/fill_ledger.py) from the
    broker's closed-trade record (realized PL); an unbookable close is
    queued for retry and latches the measurement alert, never dropped.
  * Phase-3 guard — measurement/forward_guard.py kill criteria are
    evaluated on the scan cadence; a breach re-creates the entries-pause
    file (persisted auto-pause) with journal evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests

try:
    from logger import get_logger
except Exception:  # pragma: no cover - fallback when run outside Stratex/
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo.credentials import load_oanda_credentials
from oanda_demo.strategy import (
    DonchianTrendStrategy,
    MeanReversionStrategy,
    Signal,
)

logger = get_logger("oanda_demo_trader")

# --- Tunables (kept conservative: this is real-order demo trading) ----------
# FX-only: the practice account trades 68 currency pairs (no metals/indices).
WATCHLIST = [
    "EURUSD", "GBPUSD", "USDJPY", "AUDUSD", "USDCAD", "NZDUSD", "EURJPY", "EURGBP",
]
RISK_PER_TRADE_PCT = 0.001     # 0.1% of equity risked per trade (TASK-STR-FWD-006; was 1%)
MAX_HEAT_PCT = 0.02            # aggregate open-risk heat cap: 2% of equity (TASK-STR-FWD-006)
MAX_OPEN_TRADES = 4            # concurrent positions across the watchlist
MAX_NOTIONAL_PCT = 0.25        # notional cap: 25% of equity per position
MAX_LEVERAGE = 50.0            # OANDA demo margin rate 2% on majors
DAILY_LOSS_LIMIT_PCT = 0.03    # -3% NAV day: stop opening new trades
REENTRY_COOLDOWN_S = 3600      # 60 min cooldown per instrument after a close
STRATEGY_NAME = os.getenv("STRATEX_OANDA_STRATEGY", "mr").lower()
# NOTE: timeframes use the adapter's granularity-map keys ("15m","1h","4h","1d")
# — anything else silently falls back to M15 in get_historical_data.
_DEFAULT_TF = {"mr": "1d", "donchian": "4h"}
TIMEFRAME = os.getenv("STRATEX_OANDA_TF", _DEFAULT_TF.get(STRATEGY_NAME, "4h"))
HISTORY_BARS = 400

DATA_DIR = Path(os.getenv("STRATEX_OANDA_DATA_DIR", "data"))
STATE_FILE = DATA_DIR / "oanda_demo_state.json"
TRADES_CSV = DATA_DIR / "oanda_demo_trades.csv"
KILL_SWITCH = DATA_DIR / "oanda_demo_kill_switch"
ENTRIES_PAUSED_FILE = DATA_DIR / "oanda_demo_entries_paused"


def entries_paused() -> bool:
    """Entries pause (TASK-STR-PHASE2-001, Stratex profitability phase 2).

    This engine's verified record is 19 trades, -$167, negative on every
    instrument it touched. While the measurement programme runs, it must
    not open new trades — but unlike the kill switch (which halts the
    whole scan), the entries pause keeps the engine scanning, managing
    open trades and maintaining state; it only skips new entries.

    Set via the STRATEX_OANDA_ENTRIES_PAUSED env flag ("1"/"true"/"yes")
    or by creating the pause file in the data dir. Removing either
    resumes entries — the pause is reversible by design and changes no
    code, strategy, or sizing.

    TASK-STR-FWD-004 (2026-11-15): the owner directed OANDA activation
    under the phase-3 measurement protocol. This mechanism is unchanged
    and remains an authoritative manual override; entries ADDITIONALLY
    require the configured strategy to be governed (governance_status).
    The phase-3 forward guard re-creates the pause file automatically
    when a kill criterion breaches.
    """
    if os.getenv("STRATEX_OANDA_ENTRIES_PAUSED", "").lower() in ("1", "true", "yes"):
        return True
    return ENTRIES_PAUSED_FILE.exists()


# --- TASK-STR-FWD-004: governance (registry is the single source) -----------
# This engine historically chose its strategy from the environment alone.
# Since TASK-STR-FWD-004, config_strategy.PRODUCTION_STRATEGY_REGISTRY
# governs this engine too (the TASK-STR-SAFETY-001 pattern): entries may
# open only when the configured strategy is a VALIDATED forward-protocol
# entrant registered for the OANDA practice venue. Every other outcome —
# no mapping, missing entry, wrong status, unreadable registry — fails
# CLOSED (entries blocked), however the manual pause is set. Management
# of already-open trades is never gated.
ENGINE_NAME = "oanda_demo"
VENUE_NAME = "oanda_practice"
_STRATEGY_REGISTRY_KEYS = {
    "FX-MR-v4": "fx_mr_v4",
    "Donchian-Trend-v3": "donchian_trend_v3",
}


def strategy_registry_key(strategy=None) -> str:
    """Registry key for a strategy object ('' when it has no mapping)."""
    name = getattr(strategy, "name", "") if strategy is not None else ""
    return _STRATEGY_REGISTRY_KEYS.get(str(name), "")


def governance_status(strategy=None, registry=None) -> Dict:
    """Governance verdict for the configured strategy (fail-closed).

    governed=True only for a registry entry that is VALIDATED, carries
    forward_protocol, and is registered for this engine's venue (or
    declares no venue). The returned reason always says why, so the
    journal shows exactly which check kept entries closed.
    """
    key = strategy_registry_key(strategy)
    if not key:
        return {
            "registry_key": "",
            "governed": False,
            "reason": (
                f"strategy {getattr(strategy, 'name', '?')!r} has no "
                "governance mapping (UNREGISTERED — cannot execute)"
            ),
        }
    if registry is None:
        try:
            from config_strategy import PRODUCTION_STRATEGY_REGISTRY as registry
        except Exception as exc:  # registry unreadable -> fail closed
            return {
                "registry_key": key,
                "governed": False,
                "reason": f"strategy registry unreadable ({exc})",
            }
    entry = registry.get(key)
    if entry is None:
        return {
            "registry_key": key,
            "governed": False,
            "reason": f"strategy {key!r} is not in the registry (UNREGISTERED — cannot execute)",
        }
    if entry.get("status") != "VALIDATED":
        return {
            "registry_key": key,
            "governed": False,
            "reason": f"strategy {key!r} status is {entry.get('status')!r}, not VALIDATED",
        }
    if not entry.get("forward_protocol"):
        return {
            "registry_key": key,
            "governed": False,
            "reason": f"strategy {key!r} is not a forward-protocol entrant",
        }
    venue = entry.get("venue")
    if venue is not None and venue != VENUE_NAME:
        return {
            "registry_key": key,
            "governed": False,
            "reason": f"strategy {key!r} is registered for venue {venue!r}, not {VENUE_NAME!r}",
        }
    return {
        "registry_key": key,
        "governed": True,
        "reason": "VALIDATED forward-protocol entrant on oanda_practice (TASK-STR-FWD-004)",
    }


def _utc_day() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _rfc3339_to_unix(ts: str) -> float:
    """OANDA timestamps can carry nanoseconds; Python 3.10 needs truncation."""
    ts = (ts or "").strip()
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return datetime.fromisoformat(ts[:23] + "+00:00").timestamp()


def build_default_strategy():
    """Strategy selected by env (STRATEX_OANDA_STRATEGY). Default: MR —
    the only strategy class that survived 20y/2.9y validation on the FX
    practice basket (see data/oanda_demo_backtest_*.json).

    SMT-v2 was the third option ("smt") until TASK-STR-CLEANUP-002
    deleted it (2026-11-15) under the owner's PF < 1.2 removal rule;
    an unrecognised name now falls through to MR, as before."""
    if STRATEGY_NAME == "donchian":
        return DonchianTrendStrategy()
    return MeanReversionStrategy()


class OandaDemoTrader:
    """Risk-first OANDA practice-account trading engine."""

    def __init__(
        self,
        adapter: Optional[OandaExchangeAdapter] = None,
        strategy=None,
        timeframe: str = TIMEFRAME,
        dry_run: bool = False,
        state_file: Optional[Path] = None,
    ):
        if adapter is None:
            api_key, account_id, practice = load_oanda_credentials()
            adapter = OandaExchangeAdapter(
                api_key=api_key, account_id=account_id, practice=practice
            )
        self.adapter = adapter
        self.strategy = strategy or build_default_strategy()
        self.timeframe = timeframe
        self.dry_run = dry_run
        self.state_file = state_file or STATE_FILE

    # -- state ------------------------------------------------------------
    def _load_state(self) -> Dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    # -- helpers ------------------------------------------------------------
    @staticmethod
    def _quote_to_usd(quote: str, pricing: Dict[str, Dict[str, float]]) -> float:
        """Convert one unit of quote currency to account USD."""
        if quote == "USD":
            return 1.0
        if quote == "JPY":
            px = pricing.get("USDJPY")
            return 1.0 / px["mid"] if px else 0.0
        for cand in (quote + "USD", "USD" + quote):
            px = pricing.get(cand)
            if px:
                return px["mid"] if cand.startswith(quote) else 1.0 / px["mid"]
        return 0.0

    def _position_units(
        self,
        symbol: str,
        signal: Signal,
        pricing: Dict[str, Dict[str, float]],
        equity: float,
        free_margin: float,
        risk_budget_usd: Optional[float] = None,
    ) -> int:
        """Units so that SL hit = RISK_PER_TRADE_PCT of equity (capped).

        ``risk_budget_usd`` (TASK-STR-FWD-006 heat cap) replaces the
        plain per-trade risk budget when given: the caller passes the
        REMAINING aggregate heat budget for this engine's own book.
        """
        quote = symbol[3:]
        conv = self._quote_to_usd(quote, pricing)
        sl_dist = abs(signal.entry - signal.stop)
        if conv <= 0 or sl_dist <= 0:
            return 0
        risk_usd = equity * RISK_PER_TRADE_PCT
        if risk_budget_usd is not None:
            risk_usd = min(risk_usd, float(risk_budget_usd))
            if risk_usd <= 0:
                return 0
        units = int(risk_usd / (sl_dist * conv))
        mid = pricing.get(symbol, {}).get("mid", 0) or signal.entry
        if mid <= 0:
            return 0
        max_units_notional = int((equity * MAX_NOTIONAL_PCT) / mid)
        max_units_margin = int((free_margin * 0.5) * MAX_LEVERAGE / mid)
        return max(0, min(units, max_units_notional, max_units_margin))

    def _log_trade_csv(self, row: Dict) -> None:
        try:
            DATA_DIR.mkdir(parents=True, exist_ok=True)
            new_file = not TRADES_CSV.exists()
            with open(TRADES_CSV, "a", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as exc:
            logger.warning(f"[OANDA-DEMO] trade csv write failed: {exc}")

    def _telegram(self, text: str) -> None:
        token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        chat = os.getenv("TELEGRAM_CHAT_ID", "")
        if not token or not chat:
            return
        try:
            requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat, "text": text},
                timeout=8,
            )
        except Exception:
            pass

    # -- core scan ----------------------------------------------------------
    def run_once(self) -> Dict:
        summary: Dict = {"ts": datetime.now(timezone.utc).isoformat(), "actions": []}
        if KILL_SWITCH.exists():
            summary["halted"] = "kill switch present"
            logger.warning("[OANDA-DEMO] kill switch active — skipping scan")
            return summary

        acct = self.adapter.get_account_summary()
        if not acct:
            summary["error"] = "account summary unavailable"
            return summary
        equity = float(acct.get("equity", 0))
        free_margin = float(acct.get("margin_available", 0))
        summary["equity"] = round(equity, 2)
        summary["free_margin"] = round(free_margin, 2)

        state = self._load_state()
        today = _utc_day()
        if state.get("day") != today:
            state["day"] = today
            state["day_start_nav"] = equity
        day_start = float(state.get("day_start_nav", equity)) or equity
        daily_dd = (equity - day_start) / day_start if day_start else 0.0
        summary["daily_pnl_pct"] = round(daily_dd * 100, 2)

        trades = self.adapter.open_trades()
        summary["open_trades"] = len(trades)
        self._manage_open_trades(trades, pricing=None, state=state, summary=summary)

        # Re-read trades after management (SL updates) for accurate counts.
        trades = self.adapter.open_trades()
        open_instruments = {t["instrument"] for t in trades}

        # Dedupe (USDJPY is both a watchlist pair and the JPY-quote
        # conversion source — a duplicate instrument 400s the whole batch).
        pricing_symbols = list(dict.fromkeys(WATCHLIST + ["USDJPY"]))
        pricing = self.adapter.get_pricing(pricing_symbols)
        if not pricing:
            summary["error"] = "pricing unavailable"
            self._save_state(state)
            return summary
        summary["spreads"] = {s: round(p["spread"], 6) for s, p in pricing.items()}

        # Phase-3 forward guard (TASK-STR-FWD-004): kill criteria over
        # the fill ledger, evaluated every scan. A breach re-creates the
        # pause file, so the entries check below already sees it.
        self._apply_forward_guard(state, summary, equity)

        if entries_paused():
            # Entries pause (TASK-STR-PHASE2-001): account read, trade
            # management and state upkeep above still ran; only the
            # new-entry scan below is skipped.
            summary["entries_paused"] = True
            logger.warning(
                "[OANDA-DEMO] entries paused (TASK-STR-PHASE2-001 measurement "
                "programme) — managing open trades only, no new entries"
            )
            self._save_state(state)
            return summary

        gov = governance_status(self.strategy)
        summary["governance"] = gov
        if not gov["governed"]:
            # Governance gate (TASK-STR-FWD-004): the manual pause may
            # be lifted, but an ungoverned strategy still cannot open
            # entries. Management above already ran; only entries stop.
            summary["entries_blocked"] = f"governance: {gov['reason']}"
            logger.warning(
                f"[OANDA-DEMO] entries blocked by governance — {gov['reason']}"
            )
            self._save_state(state)
            return summary

        blockers: List[str] = []
        if len(trades) >= MAX_OPEN_TRADES:
            blockers.append(f"max open trades ({MAX_OPEN_TRADES})")
        if daily_dd <= -DAILY_LOSS_LIMIT_PCT:
            blockers.append(f"daily loss limit ({daily_dd*100:.1f}%)")
        now = time.time()
        cooldowns = state.get("cooldowns", {})

        # TASK-STR-FWD-006 heat cap: aggregate stop-risk over THIS
        # engine's own open trades (ownership-scoped, like trade
        # management — the sleeve leg on the same account carries its
        # own heat budget). Measured from the broker's live stops.
        own_ids_now = {str(x) for x in state.get("own_trade_ids", [])}
        running_heat = 0.0
        for t in trades:
            if str(t["id"]) not in own_ids_now:
                continue
            stop = float(t.get("stop_loss", 0) or 0)
            price = float(t.get("price", 0) or 0)
            if stop > 0 and price > 0:
                conv_t = self._quote_to_usd(t["instrument"][3:], pricing)
                if conv_t > 0:
                    running_heat += (
                        abs(float(t.get("units", 0) or 0))
                        * abs(price - stop)
                        * conv_t
                    )
        summary["open_risk_usd"] = round(running_heat, 2)
        summary["heat_cap_usd"] = round(equity * MAX_HEAT_PCT, 2)

        for symbol in WATCHLIST:
            if symbol in open_instruments:
                continue
            cd_until = cooldowns.get(symbol, 0)
            if isinstance(cd_until, (int, float)) and now < float(cd_until):
                continue
            if blockers:
                break

            candles = self.adapter.get_historical_data(symbol, self.timeframe, HISTORY_BARS)
            if not candles:
                continue
            df = pd.DataFrame(candles)
            spread = pricing.get(symbol, {}).get("spread")
            signal = self.strategy.evaluate(symbol, df, spread=spread)

            if not signal.side:
                continue

            remaining_heat = equity * MAX_HEAT_PCT - running_heat
            if remaining_heat <= 0:
                summary.setdefault("heat_capped", []).append(symbol)
                break
            units = self._position_units(
                symbol, signal, pricing, equity, free_margin,
                risk_budget_usd=remaining_heat,
            )
            if units < 1:
                continue

            side_word = "BUY" if signal.side == "LONG" else "SELL"
            exit_txt = (
                f"TP {signal.take:.5f} (R:R {signal.rr:.2f})" if signal.take
                else f"trail {getattr(self.strategy.cfg, 'trailing_atr', '?')}xATR"
            )
            summary["actions"].append(
                f"{side_word} {symbol} {units}u @~{signal.entry:.5f} "
                f"SL {signal.stop:.5f} {exit_txt}"
            )
            logger.info(
                f"[OANDA-DEMO] SIGNAL {side_word} {symbol} units={units} "
                f"entry~{signal.entry:.5f} sl={signal.stop:.5f} tp={signal.take:.5f} "
                f"rr={signal.rr:.2f} reason={signal.reason}"
            )
            if self.dry_run:
                summary["actions"][-1] = "[DRY] " + summary["actions"][-1]
                continue

            try:
                result = self.adapter.place_order(
                    symbol, side_word, "MARKET", units,
                    stop_loss=signal.stop, take_profit=signal.take,
                )
            except Exception as exc:
                logger.warning(f"[OANDA-DEMO] order failed for {symbol}: {exc}")
                summary["actions"].append(f"ORDER FAILED {symbol}: {exc}")
                continue

            row = {
                "ts": summary["ts"],
                "strategy": self.strategy.name,
                "symbol": symbol,
                "side": side_word,
                "units": units,
                "price": result.price,
                "sl": signal.stop,
                "tp": signal.take or "",
                "order_id": result.order_id,
                "trade_id": getattr(result, "trade_id", "") or "",
                "status": result.status,
                "timeframe": self.timeframe,
            }
            # Ownership record (TASK-STR-FWD-002): this engine manages
            # only trades it opened; persist the id at order time.
            if row["trade_id"]:
                own_ids = set(state.get("own_trade_ids", []))
                own_ids.add(str(row["trade_id"]))
                state["own_trade_ids"] = sorted(own_ids)
            self._log_trade_csv(row)
            # Measurement (TASK-STR-FWD-004): tag the position in the
            # shared Phase-2 store and remember the fill in engine state
            # so the eventual close can be booked to the fill ledger
            # with full attribution (strategy / entry / units).
            _trade_id = str(getattr(result, "trade_id", "") or "")
            if _trade_id:
                # Seed the close-detection set at order time too: it
                # is otherwise only refreshed during trade management,
                # so a position opened AND closed inside one scan
                # interval (e.g. a fast stop-out) would never be
                # detected as closed — and now never booked either.
                known_ids = set(state.get("known_trade_ids", []))
                known_ids.add(_trade_id)
                state["known_trade_ids"] = sorted(known_ids)
                state.setdefault("open_trade_meta", {})[_trade_id] = {
                    "strategy": strategy_registry_key(self.strategy),
                    "strategy_name": self.strategy.name,
                    "symbol": symbol,
                    "side": "LONG" if side_word == "BUY" else "SHORT",
                    "units": units,
                    "entry_price": float(result.price or signal.entry),
                    "entry_time": time.time(),
                    "order_id": str(result.order_id or ""),
                }
            _fl = self._ledger()
            if _fl is not None:
                _fl.append_position_tag({
                    "engine": ENGINE_NAME,
                    "venue": VENUE_NAME,
                    "symbol": symbol,
                    "strategy": strategy_registry_key(self.strategy) or "UNATTRIBUTED",
                    "timeframe": self.timeframe,
                    "side": side_word,
                    "qty": units,
                    "entry_price": float(result.price or signal.entry),
                    "order_id": _trade_id or str(result.order_id or ""),
                    "note": "TASK-STR-FWD-004 governed forward entrant",
                })
            self._telegram(
                f"Stratex OANDA demo: {side_word} {units} {symbol} @ {result.price}\n"
                f"SL {signal.stop:.5f} | {exit_txt}\n"
                f"Risk 0.1% of ${equity:,.0f} equity"
            )
            conv_new = self._quote_to_usd(symbol[3:], pricing)
            if conv_new > 0:
                running_heat += (
                    units * abs(signal.entry - signal.stop) * conv_new
                )
            open_instruments.add(symbol)
            trades = self.adapter.open_trades()  # refresh count
            if len(trades) >= MAX_OPEN_TRADES:
                blockers.append(f"max open trades ({MAX_OPEN_TRADES})")

        self._save_state(state)
        return summary

    # -- measurement: fill ledger + forward guard (TASK-STR-FWD-004) ---------
    def _ledger(self):
        """Lazy measurement.fill_ledger import (None when unavailable).

        The ledger module never raises on its write paths; an import
        failure is logged at ERROR and treated as 'cannot book' so the
        close-retry queue (not silence) carries the failure.
        """
        try:
            from measurement import fill_ledger

            return fill_ledger
        except Exception as exc:
            logger.error(f"[OANDA-DEMO] fill ledger unavailable: {exc}")
            return None

    def _record_close(self, trade_id: str, state: Dict, summary: Dict) -> bool:
        """Book one detected close into the shared Phase-2 fill ledger.

        The row is built from the broker's closed-trade record (realized
        PL + average close price) joined with the engine's own open-time
        meta. Returns False when the close cannot be booked from broker
        truth yet — the caller keeps the id in the unrecorded-close
        retry queue and the measurement alert latches, so a close is
        never silently dropped and never booked from a guess.
        """
        fl = self._ledger()
        if fl is None:
            return False
        try:
            if fl.fill_exists(order_id=trade_id):
                return True  # already booked (idempotent across retries)
        except Exception as exc:
            logger.error(f"[OANDA-DEMO] ledger idempotence check failed: {exc}")
            return False
        getter = getattr(self.adapter, "get_closed_trade", None)
        if not callable(getter):
            logger.warning(
                f"[OANDA-DEMO] adapter cannot fetch closed trades; "
                f"close of {trade_id} queued for retry"
            )
            return False
        try:
            closed = getter(trade_id)
        except Exception as exc:
            logger.warning(f"[OANDA-DEMO] closed-trade fetch failed {trade_id}: {exc}")
            closed = None
        meta = (state.get("open_trade_meta") or {}).get(trade_id) or {}
        if not closed:
            fl.raise_alert(
                "unrecorded_close",
                f"oanda trade {trade_id} closed but the broker record is "
                "unavailable; queued for retry (TASK-STR-FWD-004)",
            )
            return False
        symbol = (
            meta.get("symbol")
            or closed.get("instrument")
            or (state.get("trade_instruments") or {}).get(trade_id, "")
        )
        units = abs(float(meta.get("units") or closed.get("units") or 0))
        entry_price = float(meta.get("entry_price") or closed.get("entry_price") or 0)
        exit_price = float(closed.get("exit_price") or 0)
        if not symbol or units <= 0 or entry_price <= 0 or exit_price <= 0:
            fl.raise_alert(
                "unrecorded_close",
                f"oanda trade {trade_id} close lacks broker entry/exit "
                "data; queued for retry (TASK-STR-FWD-004)",
            )
            return False
        side = str(meta.get("side") or "")
        if side not in ("LONG", "SHORT"):
            side = "LONG" if float(closed.get("units") or 0) > 0 else "SHORT"
        net = float(closed.get("realized_pl") or 0)
        exit_time = _rfc3339_to_unix(str(closed.get("close_time") or "")) or time.time()
        row = fl.append_fill({
            "strategy": meta.get("strategy") or strategy_registry_key(self.strategy) or "UNATTRIBUTED",
            "engine": ENGINE_NAME,
            "venue": VENUE_NAME,
            "symbol": symbol,
            "side": side,
            "entry_price": entry_price,
            "exit_price": exit_price,
            "qty": units,
            "gross_pnl": net,
            "fees": 0.0,
            "fees_source": "broker",
            "net_pnl": net,
            "exit_reason": (state.get("pending_exit_reasons") or {}).get(
                trade_id, "BROKER_CLOSE"
            ),
            "entry_time": float(meta.get("entry_time") or 0),
            "exit_time": exit_time,
            "order_id": trade_id,
            "entry_order_id": str(meta.get("order_id") or ""),
            "pnl_basis": "oanda_realizedPL (broker figure, excl. financing)",
        })
        if row is None:
            return False
        summary.setdefault("ledger_fills", []).append(trade_id)
        logger.info(
            f"[OANDA-DEMO] ledger fill recorded: trade {trade_id} {symbol} "
            f"net {net:+.2f} reason={row['exit_reason']}"
        )
        return True

    def _apply_forward_guard(self, state: Dict, summary: Dict, equity: float) -> None:
        """Phase-3 kill criteria for this engine's governed strategy.

        Evaluated on every scan over the shared fill ledger — the same
        measurement/forward_guard.py the Binance daemon uses, with the
        OANDA account's own equity as the drawdown basis. A breach
        re-creates the persisted entries-pause file (the auto-pause
        survives restarts and lifts only by manual removal after
        review) and is journaled with its reasons. Never raises: a
        guard failure is logged loudly, it does not crash the scan.
        """
        key = strategy_registry_key(self.strategy)
        if not key:
            return
        try:
            from measurement import fill_ledger, forward_guard

            rows = fill_ledger.read_fills()
            decisions = forward_guard.evaluate(rows, equity, [key])
        except Exception as exc:
            logger.error(f"[OANDA-DEMO] forward guard evaluation failed: {exc}")
            return
        for d in decisions:
            pf = d["profit_factor"]
            summary.setdefault("forward_guard", []).append({
                "strategy": d["strategy"],
                "trades": d["trades"],
                "net_pnl": round(d["net_pnl"], 2),
                "profit_factor": round(pf, 3) if pf != float("inf") else "inf",
                "breached": d["breached"],
                "reasons": d["reasons"],
            })
            logger.info(
                f"[OANDA-DEMO] Forward guard: {d['strategy']} "
                f"trades={d['trades']} net=${d['net_pnl']:.2f} "
                f"pf={pf:.3f} dd=${d['max_drawdown_usd']:.2f}/"
                f"${d['drawdown_limit_usd']:.2f}"
            )
            if d["breached"]:
                try:
                    ENTRIES_PAUSED_FILE.parent.mkdir(parents=True, exist_ok=True)
                    ENTRIES_PAUSED_FILE.touch()
                except OSError as exc:
                    logger.error(
                        f"[OANDA-DEMO] forward guard could not persist "
                        f"the auto-pause: {exc}"
                    )
                summary["forward_guard_auto_paused"] = True
                logger.warning(
                    "[OANDA-DEMO] PHASE-3 KILL CRITERION — entries "
                    f"auto-paused for {d['strategy']}: "
                    + "; ".join(d["reasons"])
                )

    # -- trade management -----------------------------------------------------
    def _manage_open_trades(
        self,
        trades: List[Dict],
        pricing: Optional[Dict[str, Dict[str, float]]],
        state: Dict,
        summary: Dict,
    ) -> None:
        """Breakeven moves at +1R; close detection -> cooldowns.

        TASK-STR-FWD-002 ownership scoping: this engine manages ONLY
        trades it opened itself (state["own_trade_ids"], persisted at
        order time). The practice account is shared — the sleeve
        runner (oanda_demo/sleeve_runner.py) holds its own positions
        on it, and applying this engine's MR rule exits / trailing
        stops / cooldowns to foreign trades would confiscate them.
        Before this fix the loops below acted on every open trade in
        the account. Behaviour for this engine's OWN trades is
        unchanged; the entries pause is untouched. One-time migration:
        if the own-set has never been recorded, currently-open trades
        are adopted as own (they could only have been opened by this
        engine before the sleeve existed) and the adoption is logged.
        """
        known: set = set(state.get("known_trade_ids", []))
        current_ids = {t["id"] for t in trades}

        if "own_trade_ids" not in state:
            state["own_trade_ids"] = sorted(current_ids)
            if current_ids:
                logger.warning(
                    "[OANDA-DEMO] adopted %d existing open trades as own "
                    "(TASK-STR-FWD-002 ownership-scoping migration)",
                    len(current_ids),
                )
        own: set = set(state.get("own_trade_ids", []))
        summary["foreign_open_trades"] = len(current_ids - own)

        # TASK-STR-FWD-004: retry closes that could not be booked into
        # the fill ledger on the scan that detected them (e.g. the
        # broker record was briefly unavailable). They stay queued —
        # with the measurement alert latched — until booked.
        for pending_id in list(state.get("unrecorded_closes", [])):
            if self._record_close(pending_id, state, summary):
                state["unrecorded_closes"].remove(pending_id)
                (state.get("open_trade_meta") or {}).pop(pending_id, None)
                (state.get("pending_exit_reasons") or {}).pop(pending_id, None)

        # Trades that disappeared since last scan -> closed: instrument
        # cooldown. Only OWN closes are this engine's business; foreign
        # closes are booked by their own engine.
        if known:
            now = time.time()
            cooldowns = state.setdefault("cooldowns", {})
            for gone_id in (known & own) - current_ids:
                summary.setdefault("closes", []).append(gone_id)
                self._telegram(f"Stratex OANDA demo: trade {gone_id} closed.")
                # TASK-STR-FWD-004: book the close into the shared fill
                # ledger from the broker's closed-trade record; queue it
                # for retry (alert latched) when that is not yet possible.
                if self._record_close(gone_id, state, summary):
                    (state.get("open_trade_meta") or {}).pop(gone_id, None)
                    (state.get("pending_exit_reasons") or {}).pop(gone_id, None)
                else:
                    queue = state.setdefault("unrecorded_closes", [])
                    if gone_id not in queue:
                        queue.append(gone_id)
        state["known_trade_ids"] = sorted(current_ids)
        state["own_trade_ids"] = sorted(own & current_ids)

        # Remember id -> instrument so future closes can arm the cooldown.
        id_map: Dict[str, str] = state.setdefault("trade_instruments", {})
        for t in trades:
            id_map[t["id"]] = t["instrument"]
        if known:
            cooldowns = state.setdefault("cooldowns", {})
            for gone_id in (known & own) - current_ids:
                instrument = id_map.get(gone_id, "")
                if instrument:
                    cooldowns[instrument] = time.time() + REENTRY_COOLDOWN_S

        # Exit management: rule exit (MR) or chandelier trail (Donchian).
        # (SMT-v2's breakeven-at-+1R path was deleted with the strategy
        # itself by TASK-STR-CLEANUP-002, 2026-11-15.)
        rule_exit = getattr(self.strategy.cfg, "exit_rule", None) == "mr"
        trailing_mult = getattr(self.strategy.cfg, "trailing_atr", None)
        if pricing is None:
            need = [t["instrument"] for t in trades]
            pricing = self.adapter.get_pricing(need) if need else {}

        for t in trades:
            if t["id"] not in own:
                # Foreign position on the shared account (e.g. a sleeve
                # leg): never managed by this engine (TASK-STR-FWD-002).
                continue
            if not t["price"]:
                continue

            if rule_exit:
                # --- MR rule exit: close when close re-crosses EMA5, or time stop.
                candles = self.adapter.get_historical_data(
                    t["instrument"], self.timeframe, HISTORY_BARS
                )
                if not candles:
                    continue
                d = self.strategy.add_indicators(pd.DataFrame(candles))
                open_ts = _rfc3339_to_unix(t.get("open_time", ""))
                since = d[d["timestamp"] >= open_ts] if open_ts else d
                if since.empty:
                    continue
                held = len(since) - 1
                last = d.iloc[-1]
                c = float(last["close"])
                exit_level = float(last["ema_exit"])
                max_hold = getattr(self.strategy.cfg, "max_hold_bars", 10)
                direction = 1.0 if t["units"] > 0 else -1.0
                trigger = (
                    (direction > 0 and c > exit_level)
                    or (direction < 0 and c < exit_level)
                    or held >= max_hold
                )
                if not trigger:
                    continue
                closed = False
                if not self.dry_run:
                    try:
                        closed = self.adapter.close_trade(t["id"])
                    except Exception as exc:
                        logger.warning(f"[OANDA-DEMO] rule-exit close failed {t['id']}: {exc}")
                if closed or self.dry_run:
                    why = "RULE" if held < max_hold else "TIME"
                    if closed and not self.dry_run:
                        # Remember WHY we closed it; the fill ledger row
                        # written when the close is detected next scan
                        # carries this reason (TASK-STR-FWD-004).
                        state.setdefault("pending_exit_reasons", {})[t["id"]] = (
                            "MR_RULE_EXIT" if why == "RULE" else "TIME_EXIT"
                        )
                    summary.setdefault("rule_exits", []).append(t["id"])
                    logger.info(
                        f"[OANDA-DEMO] MR {why} exit on {t['instrument']} "
                        f"trade {t['id']} (close {c:.5f} vs EMA5 {exit_level:.5f})"
                    )
                continue

            if trailing_mult is not None:
                # --- chandelier trailing stop ---
                candles = self.adapter.get_historical_data(
                    t["instrument"], self.timeframe, HISTORY_BARS
                )
                if not candles:
                    continue
                d = self.strategy.add_indicators(pd.DataFrame(candles))
                open_ts = _rfc3339_to_unix(t.get("open_time", ""))
                since = d[d["timestamp"] >= open_ts] if open_ts else d
                if since.empty:
                    continue
                atr_now = float(d.iloc[-1]["atr"])
                if atr_now <= 0:
                    continue
                if t["units"] > 0:
                    extreme = float(since["close"].max())
                    new_sl = extreme - trailing_mult * atr_now
                    improve = new_sl > t["stop_loss"] if t["stop_loss"] else True
                else:
                    extreme = float(since["close"].min())
                    new_sl = extreme + trailing_mult * atr_now
                    improve = new_sl < t["stop_loss"] if t["stop_loss"] else False
                if not improve:
                    continue
                ok = False
                if not self.dry_run:
                    try:
                        ok = self.adapter.update_trade_stop_loss(
                            t["instrument"], t["id"], new_sl
                        )
                    except Exception as exc:
                        logger.warning(f"[OANDA-DEMO] trail update failed {t['id']}: {exc}")
                if ok or self.dry_run:
                    summary.setdefault("trailed", []).append(t["id"])
                    logger.info(
                        f"[OANDA-DEMO] chandelier trail on {t['instrument']} "
                        f"trade {t['id']} -> {new_sl:.5f} (extreme {extreme:.5f})"
                    )
                continue


    # -- utilities ------------------------------------------------------------
    def status(self) -> Dict:
        acct = self.adapter.get_account_summary()
        trades = self.adapter.open_trades()
        state = self._load_state()
        return {
            "account": acct,
            "entries_paused": entries_paused(),
            "governance": governance_status(self.strategy),
            "open_trades": trades,
            "daily_day": state.get("day"),
            "day_start_nav": state.get("day_start_nav"),
            "timeframe": self.timeframe,
            "watchlist": WATCHLIST,
        }

    def flatten(self) -> Dict:
        """Close every open trade (emergency control)."""
        trades = self.adapter.open_trades()
        results = {}
        for t in trades:
            try:
                results[t["id"]] = self.adapter.close_trade(t["id"])
            except Exception as exc:
                results[t["id"]] = f"error: {exc}"
        self._telegram(f"Stratex OANDA demo FLATTEN: closed {len(trades)} trades.")
        return {"closed": results}


def main() -> int:
    parser = argparse.ArgumentParser(description="Stratex OANDA demo trader")
    parser.add_argument("--once", action="store_true", help="run a single scan")
    parser.add_argument("--loop", action="store_true", help="run forever")
    parser.add_argument("--interval", type=int, default=300, help="loop seconds")
    parser.add_argument("--status", action="store_true", help="print account status")
    parser.add_argument("--flatten", action="store_true", help="close all open trades")
    parser.add_argument("--dry-run", action="store_true", help="no real orders")
    args = parser.parse_args()

    trader = OandaDemoTrader(dry_run=args.dry_run)

    if args.status:
        print(json.dumps(trader.status(), indent=2, default=str))
        return 0
    if args.flatten:
        print(json.dumps(trader.flatten(), indent=2, default=str))
        return 0
    if args.loop:
        logger.info("[OANDA-DEMO] loop mode starting")
        while True:
            try:
                out = trader.run_once()
                logger.info(f"[OANDA-DEMO] scan: {json.dumps(out, default=str)}")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.warning(f"[OANDA-DEMO] scan error: {exc}")
            time.sleep(max(30, args.interval))
        return 0
    if args.once or not any(vars(args).values()):
        out = trader.run_once()
        print(json.dumps(out, indent=2, default=str))
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
