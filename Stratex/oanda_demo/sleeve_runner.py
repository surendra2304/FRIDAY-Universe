"""
oanda_demo/sleeve_runner.py — governed sleeve engine for OANDA legs.

TASK-STR-FWD-002 (sleeve extension, owner approval 2026-11-15): the
forex leg of the RD-002 Stage-C best-per-class portfolio sleeve —
tsmom2_dual/roc90_ema200 @ FOREX28 1d — trades on the OANDA practice
account through THIS runner, and nothing else trades through it.

Governance: the leg is registered in config_strategy.
PRODUCTION_STRATEGY_REGISTRY ("sleeve_tsmom2_dual", status VALIDATED,
sleeve="best_per_class") — the single governance source shared with
the Binance daemon. This runner refuses entries unless that entry is
VALIDATED. It is a SEPARATE engine from oanda_demo.trader (FX-MR-v4):
separate state, separate pause/kill files, and it never touches the
FX-MR-v4 engine's pause (STRATEX_OANDA_ENTRIES_PAUSED / its data dir).

Safety rails:
  * Practice account only (the adapter enforces practice-only itself).
  * 0.1% of account NAV risk per trade (venue basis — this runner's
    account IS the venue account) with a 2% aggregate heat cap across
    the leg's open trades (TASK-STR-FWD-006 decided package); 25%
    notional cap; free-margin gate.
  * Shared-account daily breaker: account NAV down 3% on the day ->
    no new entries (same basis as the other forward entrants).
  * Sleeve pause: STRATEX_SLEEVE_ENTRIES_PAUSED env or the
    sleeve_entries_paused file in this runner's data dir — the file
    is what the daemon's forward guard writes when the sleeve-level
    kill rule (combined sleeve drawdown > 5% of equity) breaches.
  * OANDA nets per instrument: an instrument with ANY open trade
    (this runner's, FX-MR-v4's, or anyone's) is never traded, so a
    sleeve order can never merge into a foreign position.
  * Every close is booked into the phase-2 measurement fill ledger
    (measurement/fill_ledger.append_fill) tagged with BOTH the sleeve
    identity ("sleeve": "best_per_class") and the component strategy
    ("strategy_sleeve_tsmom2_dual"), with realised PnL read back from
    the broker's own closed-trade record.

Bars: OANDA daily candles requested with dailyAlignment=0 /
alignmentTimezone=UTC (UTC-midnight-aligned, complete candles only)
— the judged research bars were Yahoo calendar-day bars; the
alignment convention matches, the price source is the venue's own
(disclosed in the registry entry and the task board entry).

Usage (from the Stratex/ directory):
    python3 -m oanda_demo.sleeve_runner --status
    python3 -m oanda_demo.sleeve_runner --once [--dry-run]
    python3 -m oanda_demo.sleeve_runner --loop --interval 300
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

try:
    from logger import get_logger
except Exception:  # pragma: no cover - fallback when run outside Stratex/
    import logging

    def get_logger(name: str) -> logging.Logger:
        return logging.getLogger(name)

from config_strategy import FOREX28_SYMBOLS, PRODUCTION_STRATEGY_REGISTRY
from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo import sleeve_signals
from oanda_demo.credentials import load_oanda_credentials

logger = get_logger("oanda_sleeve_runner")

COMPONENT_KEY = "sleeve_tsmom2_dual"
STRATEGY_TAG = "strategy_sleeve_tsmom2_dual"
SLEEVE_TAG = "best_per_class"
TIMEFRAME = "1d"
HISTORY_BARS = 400
RISK_PER_TRADE_PCT = 0.001     # phase-3 per-trade risk: 0.1% of NAV (TASK-STR-FWD-006; was 1%)
MAX_HEAT_PCT = 0.02            # aggregate open-risk heat cap: 2% of NAV (TASK-STR-FWD-006)
MAX_NOTIONAL_PCT = 0.25        # per-position notional cap (as trader)
DAILY_LOSS_LIMIT_PCT = 0.03    # shared-account daily breaker
REENTRY_COOLDOWN_S = 3600      # per-instrument cooldown after a close
MAX_OPEN_TRADES = 28           # one per FOREX28 instrument at most

DATA_DIR = Path(os.getenv("STRATEX_SLEEVE_OANDA_DIR", "data/sleeve_oanda"))
STATE_FILE = DATA_DIR / "sleeve_state.json"
PAUSE_FILE = DATA_DIR / "sleeve_entries_paused"
KILL_FILE = DATA_DIR / "sleeve_kill_switch"


def sleeve_entries_paused() -> bool:
    """This runner's OWN pause (never the FX-MR-v4 engine's)."""
    if os.getenv("STRATEX_SLEEVE_ENTRIES_PAUSED", "").lower() in ("1", "true", "yes"):
        return True
    return PAUSE_FILE.exists()


def governance_ok() -> bool:
    entry = PRODUCTION_STRATEGY_REGISTRY.get(COMPONENT_KEY) or {}
    return entry.get("status") == "VALIDATED" and entry.get("sleeve") == SLEEVE_TAG


def _rfc3339_to_unix(ts: str) -> float:
    ts = (ts or "").strip()
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return datetime.fromisoformat(ts[:23] + "+00:00").timestamp()


class SleeveRunner:
    """Runs exactly one governed sleeve leg on the OANDA practice account."""

    def __init__(self, adapter: Optional[OandaExchangeAdapter] = None,
                 dry_run: bool = False, state_file: Optional[Path] = None,
                 data_dir: Optional[Path] = None):
        if adapter is None:
            api_key, account_id, practice = load_oanda_credentials()
            adapter = OandaExchangeAdapter(
                api_key=api_key, account_id=account_id, practice=practice
            )
        self.adapter = adapter
        self.account_id = getattr(adapter, "account_id", "")
        self.dry_run = dry_run
        self.data_dir = data_dir or DATA_DIR
        self.state_file = state_file or (self.data_dir / "sleeve_state.json")
        self.pause_file = self.data_dir / "sleeve_entries_paused"
        self.kill_file = self.data_dir / "sleeve_kill_switch"

    # -- state ------------------------------------------------------------
    def _load_state(self) -> Dict:
        try:
            return json.loads(self.state_file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}

    def _save_state(self, state: Dict) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.state_file.write_text(json.dumps(state, indent=2), encoding="utf-8")

    def _paused(self) -> bool:
        if os.getenv("STRATEX_SLEEVE_ENTRIES_PAUSED", "").lower() in ("1", "true", "yes"):
            return True
        return self.pause_file.exists()

    # -- market data --------------------------------------------------------
    def _daily_candles(self, symbol: str) -> List[Dict]:
        """Complete UTC-midnight-aligned daily candles (see module doc)."""
        oanda_sym = self.adapter.denormalize_symbol(
            self.adapter.normalize_symbol(symbol)
        )
        data = self.adapter._request(
            "GET", f"/instruments/{oanda_sym}/candles",
            params={
                "granularity": "D",
                "count": HISTORY_BARS,
                "price": "M",
                "dailyAlignment": 0,
                "alignmentTimezone": "UTC",
            },
        )
        if not data or "candles" not in data:
            return []
        out = []
        for c in data["candles"]:
            if not c.get("complete", False):
                continue
            mid = c.get("mid", {})
            ts = _rfc3339_to_unix(str(c.get("time", "")))
            out.append(
                {
                    "timestamp": int(ts),
                    "open": float(mid.get("o", 0)),
                    "high": float(mid.get("h", 0)),
                    "low": float(mid.get("l", 0)),
                    "close": float(mid.get("c", 0)),
                    "volume": int(c.get("volume", 0)),
                }
            )
        return out

    # -- sizing ---------------------------------------------------------------
    @staticmethod
    def _quote_to_usd(quote: str, pricing: Dict[str, Dict[str, float]]) -> float:
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

    def _position_units(self, symbol: str, sl_dist: float,
                        pricing: Dict[str, Dict[str, float]],
                        equity: float, free_margin: float,
                        margin_rate: float,
                        risk_budget_usd: Optional[float] = None) -> int:
        quote = symbol[3:]
        conv = self._quote_to_usd(quote, pricing)
        mid = pricing.get(symbol, {}).get("mid", 0)
        if conv <= 0 or sl_dist <= 0 or mid <= 0:
            return 0
        # Notional per unit in account currency (USD): price x quote
        # conversion. (Dividing caps by the raw pair price instead —
        # as a naive port of the MR trader's formula would — shrinks
        # JPY-pair sizes by the ~150x price factor and would silently
        # neuter 8 of the 28 judged instruments.)
        notional_per_unit = mid * conv
        risk_usd = equity * RISK_PER_TRADE_PCT
        if risk_budget_usd is not None:
            # TASK-STR-FWD-006 heat cap: the caller passes the REMAINING
            # aggregate heat budget; new size may not exceed it.
            risk_usd = min(risk_usd, float(risk_budget_usd))
            if risk_usd <= 0:
                return 0
        units = int(risk_usd / (sl_dist * conv))
        max_units_notional = int((equity * MAX_NOTIONAL_PCT) / notional_per_unit)
        lev = (1.0 / margin_rate) if margin_rate and margin_rate > 0 else 20.0
        max_units_margin = int((free_margin * 0.5) * lev / notional_per_unit)
        return max(0, min(units, max_units_notional, max_units_margin))

    # -- ledger booking ---------------------------------------------------------
    def _book_close(self, trade_id: str, meta: Dict) -> bool:
        """Book a detected close into the measurement fill ledger.

        Returns True only when the fill row is actually in the ledger.
        TASK-STR-FWD-007: this used to swallow every failure into an
        ERROR log while the caller had ALREADY popped the trade from
        own_trades — one transient broker-GET failure at close time
        permanently and silently lost the sleeve-attributed fill. Now
        the semantics mirror the FX-MR-v4 trader's FWD-004 close path:
        a close that cannot be booked from broker truth yet returns
        False, the caller keeps the trade in own_trades as the retry
        queue, and the unrecorded_close measurement alert latches, so
        the failure is visible and retried on the next scan instead of
        vanishing.

        TASK-STR-FWD-011: a CLOSED record with NO close fields at all
        (no closeTime AND no averageClosePrice) is also a
        cannot-book-yet case, not a $0.00 close — trade 470 was booked
        from exactly such a record while the venue position persisted.
        A record with SOME close fields still books, with the single
        missing field's fallback logged loudly (WARNING).
        """
        try:
            from measurement import fill_ledger
        except Exception as exc:  # ledger unavailable: retry next scan
            logger.error(f"[SLEEVE] fill ledger unavailable: {exc}")
            return False

        try:
            if meta.get("order_id") and fill_ledger.fill_exists(
                order_id=str(meta["order_id"])
            ):
                return True  # already booked (idempotent across retries)
        except Exception as exc:
            logger.error(
                f"[SLEEVE] ledger idempotence check failed for trade "
                f"{trade_id}: {exc}"
            )
            return False
        try:
            data = self.adapter._request(
                "GET", f"/accounts/{self.account_id}/trades/{trade_id}"
            )
            trade = (data or {}).get("trade") or {}
            if not trade or str(trade.get("state") or "").upper() != "CLOSED":
                fill_ledger.raise_alert(
                    "unrecorded_close",
                    f"sleeve trade {trade_id} ({meta.get('symbol')}) closed "
                    "but the broker record is unavailable; queued for retry "
                    "(TASK-STR-FWD-007)",
                )
                return False
            # TASK-STR-FWD-011 (trade 470): a CLOSED record carrying NO
            # close fields is not broker truth — the old code booked a
            # fallback fill here (exit = open price, realized = 0.0,
            # exit_time = now) and the sleeve believed the leg closed
            # while the venue position persisted. Refuse outright: keep
            # the trade in own_trades and retry next cycle.
            close_time_raw = str(trade.get("closeTime") or "").strip()
            close_price_raw = trade.get("averageClosePrice")
            has_close_time = bool(close_time_raw)
            has_close_price = (
                close_price_raw is not None
                and str(close_price_raw).strip() != ""
            )
            if not has_close_time and not has_close_price:
                fill_ledger.raise_alert(
                    "unrecorded_close",
                    f"sleeve trade {trade_id} ({meta.get('symbol')}) broker "
                    "record is CLOSED but carries no closeTime and no "
                    "averageClosePrice; refusing fallback fill, queued for "
                    "retry (TASK-STR-FWD-011)",
                )
                logger.error(
                    f"[SLEEVE] trade {trade_id} ({meta.get('symbol')}) "
                    "CLOSED record has no close fields; NOT booking a "
                    "fallback fill (TASK-STR-FWD-011)"
                )
                return False
            if not has_close_time or not has_close_price:
                missing = (
                    "averageClosePrice" if has_close_time else "closeTime"
                )
                present = (
                    "closeTime" if has_close_time else "averageClosePrice"
                )
                logger.warning(
                    f"[SLEEVE] trade {trade_id} ({meta.get('symbol')}) "
                    f"CLOSED record is missing {missing}; booking from the "
                    f"real {present} field with a FALLBACK for the missing "
                    "one (TASK-STR-FWD-011)"
                )
            realized = float(trade.get("realizedPL") or 0.0)
            exit_price = float(trade.get("averageClosePrice") or trade.get("price") or 0.0)
            exit_time = _rfc3339_to_unix(close_time_raw)

            row = fill_ledger.append_fill(
                {
                    "engine": "oanda_sleeve",
                    "venue": "oanda",
                    "strategy": STRATEGY_TAG,
                    "sleeve": SLEEVE_TAG,
                    "component": COMPONENT_KEY,
                    "symbol": meta["symbol"],
                    "side": meta["side"],
                    "qty": abs(float(meta["units"])),
                    "entry_price": float(meta["entry_price"]),
                    "exit_price": exit_price,
                    "gross_pnl": realized,
                    "fees": 0.0,
                    "fees_source": "broker_realized_pl_spread_embedded",
                    "net_pnl": realized,
                    "entry_time": float(meta["entry_time"]),
                    "exit_time": exit_time or time.time(),
                    "exit_reason": "BROKER_CLOSE",
                    "order_id": str(meta.get("order_id", "")),
                    "entry_order_id": str(meta.get("order_id", "")),
                }
            )
            if row is None:
                # append_fill already latched the unrecorded_close alert.
                logger.error(
                    f"[SLEEVE] close booking REJECTED for trade {trade_id}; "
                    "kept in own_trades for retry (TASK-STR-FWD-007)"
                )
                return False
            logger.info(
                f"[SLEEVE] booked close {meta['symbol']} trade {trade_id} "
                f"net=${realized:+.2f} (strategy={STRATEGY_TAG}, sleeve={SLEEVE_TAG})"
            )
            return True
        except Exception as exc:
            logger.error(f"[SLEEVE] close booking FAILED for trade {trade_id}: {exc}")
            try:
                fill_ledger.raise_alert(
                    "unrecorded_close",
                    f"sleeve close booking failed for trade {trade_id} "
                    f"({meta.get('symbol')}): {exc}; kept in own_trades "
                    "for retry (TASK-STR-FWD-007)",
                )
            except Exception:
                pass
            return False

    # -- core scan ------------------------------------------------------------
    def run_once(self) -> Dict:
        summary: Dict = {"ts": datetime.now(timezone.utc).isoformat(),
                         "component": COMPONENT_KEY, "actions": []}
        if self.kill_file.exists():
            summary["halted"] = "sleeve kill switch present"
            logger.warning("[SLEEVE] kill switch active — skipping scan")
            return summary
        if not governance_ok():
            summary["halted"] = "governance: component not VALIDATED sleeve member"
            logger.warning("[SLEEVE] governance refusal — component not VALIDATED")
            return summary

        acct = self.adapter.get_account_summary()
        if not acct:
            summary["error"] = "account summary unavailable"
            return summary
        equity = float(acct.get("equity", 0))
        free_margin = float(acct.get("margin_available", 0))
        margin_rate = float(acct.get("margin_rate", 0) or 0)
        summary["equity"] = round(equity, 2)

        state = self._load_state()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        if state.get("day") != today:
            state["day"] = today
            state["day_start_nav"] = equity
        day_start = float(state.get("day_start_nav", equity)) or equity
        daily_dd = (equity - day_start) / day_start if day_start else 0.0
        summary["daily_pnl_pct"] = round(daily_dd * 100, 2)

        own: Dict[str, Dict] = state.setdefault("own_trades", {})

        # Close detection + booking (runs even while entries are paused).
        # TASK-STR-FWD-007: book FIRST, pop only after the fill row is in
        # the ledger. A failed booking keeps the trade in own_trades —
        # own_trades IS the retry queue (mirrors the FX-MR-v4 trader's
        # FWD-004 semantics) — so a transient failure at close time can
        # no longer silently lose the fill.
        trades = self.adapter.open_trades()
        current_ids = {str(t["id"]) for t in trades}
        for tid in list(own):
            if tid not in current_ids:
                meta = own[tid]
                if not self.dry_run and not self._book_close(tid, meta):
                    summary.setdefault("closes_unbooked", []).append(tid)
                    continue
                own.pop(tid)
                summary.setdefault("closes", []).append(tid)
                state.setdefault("cooldowns", {})[meta["symbol"]] = (
                    time.time() + REENTRY_COOLDOWN_S
                )
        summary["own_open_trades"] = len(own)
        summary["account_open_trades"] = len(trades)

        # TASK-STR-FWD-006: publish this leg's mark-to-market so the
        # daemon's sleeve guard judges the sleeve on closed fills PLUS
        # unrealized PnL, both components combined (venue basis).
        state["unrealized_pnl_usd"] = round(
            sum(
                float(t.get("unrealized_pl", 0) or 0)
                for t in trades
                if str(t["id"]) in own
            ),
            4,
        )
        state["unrealized_ts"] = time.time()

        if self._paused():
            summary["entries_paused"] = True
            logger.info("[SLEEVE] entries paused (sleeve pause) — closes booked only")
            self._save_state(state)
            return summary
        if daily_dd <= -DAILY_LOSS_LIMIT_PCT:
            summary["blocked"] = f"daily loss limit ({daily_dd*100:.1f}%)"
            self._save_state(state)
            return summary
        if len(own) >= MAX_OPEN_TRADES:
            summary["blocked"] = f"max open sleeve trades ({MAX_OPEN_TRADES})"
            self._save_state(state)
            return summary

        occupied = {t["instrument"] for t in trades}  # netting protection
        # Dedupe: USDJPY is already in FOREX28 — a duplicate instrument
        # 400s the OANDA pricing batch (observed live 2026-11-15).
        wanted = list(dict.fromkeys(list(FOREX28_SYMBOLS) + ["USDJPY"]))
        pricing = self.adapter.get_pricing(wanted)
        if not pricing:
            summary["error"] = "pricing unavailable"
            self._save_state(state)
            return summary

        # TASK-STR-FWD-006 heat cap: aggregate stop-risk of this leg's
        # open trades. Entries placed by this runner carry their
        # committed risk_usd; legacy entries (placed before FWD-006)
        # are measured from the broker's live stop distance.
        trades_by_id = {str(t["id"]): t for t in trades}

        def _open_risk_usd() -> float:
            total = 0.0
            for tid, meta in own.items():
                if meta.get("risk_usd") is not None:
                    total += float(meta["risk_usd"] or 0)
                    continue
                t = trades_by_id.get(tid)
                if not t:
                    continue
                stop = float(t.get("stop_loss", 0) or 0)
                price = float(t.get("price", 0) or 0)
                u = abs(float(t.get("units", 0) or 0))
                sym = str(t.get("instrument", ""))
                conv = (
                    self._quote_to_usd(sym[3:], pricing) if len(sym) > 3 else 0.0
                )
                if stop > 0 and price > 0 and conv > 0:
                    total += u * abs(price - stop) * conv
            return total

        running_heat = _open_risk_usd()
        summary["open_risk_usd"] = round(running_heat, 2)
        summary["heat_cap_usd"] = round(equity * MAX_HEAT_PCT, 2)

        now = time.time()
        cooldowns = state.get("cooldowns", {})
        for symbol in FOREX28_SYMBOLS:
            if symbol in occupied:
                continue
            if now < float(cooldowns.get(symbol, 0) or 0):
                continue
            candles = self._daily_candles(symbol)
            if len(candles) < sleeve_signals.WARMUP_BARS + 1:
                continue
            df = pd.DataFrame(candles)
            df.index = pd.to_datetime(df["timestamp"], unit="s", utc=True)
            sig = sleeve_signals.evaluate_last_bar(df)
            summary["evaluated"] = summary.get("evaluated", 0) + 1
            if sig is None:
                continue
            mid = pricing.get(symbol, {}).get("mid", 0)
            if mid <= 0:
                continue
            if sig["side"] == "BUY":
                stop = mid - sig["sl_dist"]
                take = mid + sig["tp_dist"]
            else:
                stop = mid + sig["sl_dist"]
                take = mid - sig["tp_dist"]
            remaining_heat = equity * MAX_HEAT_PCT - running_heat
            if remaining_heat <= 0:
                summary.setdefault("heat_capped", []).append(symbol)
                continue
            units = self._position_units(
                symbol, sig["sl_dist"], pricing, equity, free_margin,
                margin_rate, risk_budget_usd=remaining_heat,
            )
            if units < 1:
                continue
            summary["actions"].append(
                f"{sig['side']} {symbol} {units}u @~{mid:.5f} SL {stop:.5f} TP {take:.5f}"
            )
            logger.info(
                f"[SLEEVE] SIGNAL {sig['side']} {symbol} units={units} mid={mid:.5f} "
                f"sl={stop:.5f} tp={take:.5f} atr={sig['atr']:.5f} (strategy={STRATEGY_TAG})"
            )
            if self.dry_run:
                summary["actions"][-1] = "[DRY] " + summary["actions"][-1]
                continue
            try:
                result = self.adapter.place_order(
                    symbol, sig["side"], "MARKET", units,
                    stop_loss=stop, take_profit=take,
                )
            except Exception as exc:
                logger.warning(f"[SLEEVE] order failed for {symbol}: {exc}")
                summary["actions"].append(f"ORDER FAILED {symbol}: {exc}")
                # Back off this instrument (e.g. MARKET_HALTED over the
                # weekend): retrying every scan would spam the broker
                # with rejected orders. The signal is re-evaluated on
                # the next daily bar regardless — entries are judged on
                # closed bars, so an hourly retry loses nothing.
                state.setdefault("cooldowns", {})[symbol] = (
                    time.time() + REENTRY_COOLDOWN_S
                )
                continue
            trade_id = str(getattr(result, "trade_id", "") or "")
            if trade_id:
                committed = (
                    units
                    * sig["sl_dist"]
                    * self._quote_to_usd(symbol[3:], pricing)
                )
                own[trade_id] = {
                    "symbol": symbol,
                    "side": sig["side"],
                    "units": units,
                    "entry_price": float(getattr(result, "price", mid) or mid),
                    "entry_time": time.time(),
                    "order_id": str(getattr(result, "order_id", "") or ""),
                    # Committed stop-risk (TASK-STR-FWD-006 heat cap).
                    "risk_usd": round(committed, 4),
                }
                running_heat += committed
            occupied.add(symbol)
            if len(own) >= MAX_OPEN_TRADES:
                break

        self._save_state(state)
        return summary

    def status(self) -> Dict:
        return {
            "component": COMPONENT_KEY,
            "strategy_tag": STRATEGY_TAG,
            "sleeve": SLEEVE_TAG,
            "governance_ok": governance_ok(),
            "entries_paused": self._paused(),
            "account": self.adapter.get_account_summary(),
            "own_open_trades": len(self._load_state().get("own_trades", {})),
            "watchlist": list(FOREX28_SYMBOLS),
            "timeframe": TIMEFRAME,
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Stratex OANDA sleeve runner")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runner = SleeveRunner(dry_run=args.dry_run)
    if args.status:
        print(json.dumps(runner.status(), indent=2, default=str))
        return 0
    if args.loop:
        logger.info("[SLEEVE] loop mode starting (component=%s)", COMPONENT_KEY)
        while True:
            try:
                out = runner.run_once()
                logger.info(f"[SLEEVE] scan: {json.dumps(out, default=str)}")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.warning(f"[SLEEVE] scan error: {exc}")
            time.sleep(max(30, args.interval))
        return 0
    out = runner.run_once()
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
