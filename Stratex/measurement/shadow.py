"""
measurement/shadow.py — shadow-trade logging for OBSERVE_ONLY strategies.

TASK-STR-PHASE2-001, build item 6. OBSERVE_ONLY strategies (post-incident
supertrend, adx_ema) evaluate and signal but never place orders. Until now
their signals were only log lines, so no forward evidence accumulated.
This tracker keeps a paper lifecycle for every would-be trade:

  * on_signal() opens a shadow position (one per strategy+venue+symbol —
    no pyramiding, mirroring the engine's own anti-pyramiding rule);
  * update() checks the strategy's own SL/TP against subsequent bars and
    closes the shadow when either is touched;
  * an opposite signal closes the open shadow at the signal price;
  * a shadow still open after MAX_HOLD_DAYS closes at the last seen price.

Results are expressed in percent and R terms (a shadow has no real
quantity). Fees are modelled — Binance futures taker 0.05%/side for
futures venues, a 0.02%/side spread proxy elsewhere — and every record is
labelled fees_source="ESTIMATE". Shadow results live in their own ledger
(state/shadow_trades.jsonl) and are NEVER mixed into the fill ledger or
the scorecard: they are evidence about signals, not trading results.

State: open shadows persist in state/shadow_open.json so a daemon restart
does not orphan them. All operations are best-effort: a shadow failure
must never break the scan loop, so public methods swallow exceptions
after logging them.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, Dict, Optional

try:
    from measurement import fill_ledger
except ImportError:  # pragma: no cover - flat layout fallback
    import fill_ledger  # type: ignore

try:
    from atomic_io import atomic_write_json
except Exception:  # pragma: no cover
    atomic_write_json = None  # type: ignore

try:
    from logger import get_logger

    logger = get_logger("measurement_shadow")
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger("measurement_shadow")

SHADOW_TRADES_FILE = "shadow_trades.jsonl"
SHADOW_OPEN_FILE = "shadow_open.json"

MAX_HOLD_DAYS = 7.0
_FEE_PER_SIDE = {"binance_futures": 0.0005}  # Binance USD-M taker 0.05%
_DEFAULT_FEE_PER_SIDE = 0.0002  # spread proxy for non-futures venues


def shadow_trades_path() -> Path:
    override = os.getenv("STRATEX_SHADOW_LEDGER_FILE")
    if override:
        return Path(override)
    return fill_ledger.state_dir() / SHADOW_TRADES_FILE


def shadow_open_path() -> Path:
    override = os.getenv("STRATEX_SHADOW_OPEN_FILE")
    if override:
        return Path(override)
    return fill_ledger.state_dir() / SHADOW_OPEN_FILE


def _fee_rate(venue: str) -> float:
    return _FEE_PER_SIDE.get(venue, _DEFAULT_FEE_PER_SIDE)


class ShadowTracker:
    """Persistent shadow-position lifecycle for OBSERVE_ONLY signals."""

    def __init__(self) -> None:
        self._open: Dict[str, Dict[str, Any]] = {}
        self._load()

    # -- persistence ------------------------------------------------------
    def _load(self) -> None:
        try:
            with open(shadow_open_path(), "r", encoding="utf-8") as fh:
                data = json.load(fh) or {}
            positions = data.get("positions") or {}
            if isinstance(positions, dict):
                self._open = positions
        except (OSError, ValueError):
            self._open = {}

    def _save(self) -> None:
        try:
            path = shadow_open_path()
            path.parent.mkdir(parents=True, exist_ok=True)
            payload = {"positions": self._open, "updated_at": time.time()}
            if atomic_write_json is not None:
                atomic_write_json(str(path), payload, indent=2)
            else:  # pragma: no cover
                tmp = path.with_suffix(".json.tmp")
                with open(tmp, "w", encoding="utf-8") as fh:
                    json.dump(payload, fh, indent=2)
                os.replace(tmp, path)
        except Exception as e:
            logger.debug(f"[SHADOW] state save failed: {e}")

    # -- lifecycle ----------------------------------------------------------
    @staticmethod
    def _key(strategy: str, venue: str, symbol: str) -> str:
        return f"{strategy}|{venue}|{symbol}"

    def on_signal(
        self,
        strategy: str,
        venue: str,
        symbol: str,
        side: str,
        price: float,
        stop_loss: Optional[float] = None,
        take_profit: Optional[float] = None,
        timeframe: str = "",
        ts: Optional[float] = None,
    ) -> None:
        """Open (or reverse) a shadow position from an OBSERVE_ONLY signal."""
        try:
            side = str(side or "").upper()
            if side not in ("BUY", "SELL", "LONG", "SHORT"):
                return
            direction = "LONG" if side in ("BUY", "LONG") else "SHORT"
            price = float(price or 0.0)
            if price <= 0:
                return
            now = float(ts if ts is not None else time.time())
            key = self._key(strategy, venue, symbol)
            existing = self._open.get(key)
            if existing:
                if existing.get("side") == direction:
                    return  # already shadowing this direction; no pyramiding
                self._close(key, price, "OPPOSITE_SIGNAL", now)
            self._open[key] = {
                "strategy": strategy,
                "venue": venue,
                "symbol": symbol,
                "timeframe": timeframe,
                "side": direction,
                "entry_price": price,
                "stop_loss": float(stop_loss) if stop_loss else None,
                "take_profit": float(take_profit) if take_profit else None,
                "entry_time": now,
                "last_price": price,
            }
            self._save()
            logger.info(
                f"[SHADOW] Opened {strategy} {direction} {venue}:{symbol} "
                f"@ {price:.5f} SL={stop_loss} TP={take_profit} (paper only)"
            )
        except Exception as e:
            logger.debug(f"[SHADOW] on_signal failed: {e}")

    def update(
        self,
        venue: str,
        symbol: str,
        high: float,
        low: float,
        close: float,
        ts: Optional[float] = None,
    ) -> None:
        """Advance open shadows on (venue, symbol) with a new bar."""
        try:
            now = float(ts if ts is not None else time.time())
            changed = False
            for key, pos in list(self._open.items()):
                if pos.get("venue") != venue or pos.get("symbol") != symbol:
                    continue
                pos["last_price"] = float(close or pos.get("last_price") or 0.0)
                changed = True
                sl = pos.get("stop_loss")
                tp = pos.get("take_profit")
                exit_price = None
                reason = ""
                if pos.get("side") == "LONG":
                    if sl and low and float(low) <= float(sl):
                        exit_price, reason = float(sl), "SL"
                    elif tp and high and float(high) >= float(tp):
                        exit_price, reason = float(tp), "TP"
                else:  # SHORT
                    if sl and high and float(high) >= float(sl):
                        exit_price, reason = float(sl), "SL"
                    elif tp and low and float(low) <= float(tp):
                        exit_price, reason = float(tp), "TP"
                if exit_price is None and now - float(pos.get("entry_time", now)) > MAX_HOLD_DAYS * 86400:
                    exit_price, reason = float(close or pos["last_price"]), "TIME"
                if exit_price is not None:
                    self._close(key, exit_price, reason, now)
            if changed:
                self._save()
        except Exception as e:
            logger.debug(f"[SHADOW] update failed: {e}")

    def _close(self, key: str, exit_price: float, reason: str, ts: float) -> None:
        pos = self._open.pop(key, None)
        if not pos:
            return
        entry = float(pos.get("entry_price") or 0.0)
        if entry <= 0 or exit_price <= 0:
            self._save()
            return
        sign = 1.0 if pos.get("side") == "LONG" else -1.0
        gross_pct = sign * (exit_price - entry) / entry
        fees_pct = 2.0 * _fee_rate(str(pos.get("venue") or ""))
        net_pct = gross_pct - fees_pct
        sl = pos.get("stop_loss")
        r_multiple = None
        if sl:
            risk_pct = abs(entry - float(sl)) / entry
            if risk_pct > 0:
                r_multiple = round(net_pct / risk_pct, 3)
        row = {
            "record_type": "SHADOW_FILL",
            "strategy": pos.get("strategy"),
            "engine": "daemon",
            "venue": pos.get("venue"),
            "symbol": pos.get("symbol"),
            "timeframe": pos.get("timeframe", ""),
            "side": pos.get("side"),
            "entry_price": entry,
            "exit_price": float(exit_price),
            "entry_time": float(pos.get("entry_time", ts)),
            "exit_time": ts,
            "gross_pct": round(gross_pct, 6),
            "fees_pct": round(fees_pct, 6),
            "fees_source": "ESTIMATE",
            "net_pct": round(net_pct, 6),
            "r_multiple": r_multiple,
            "exit_reason": reason,
        }
        try:
            fill_ledger._append(shadow_trades_path(), row)
        except Exception as e:
            logger.error(f"[SHADOW] close record append failed for {key}: {e}")
            fill_ledger.raise_alert("unrecorded_close", f"shadow close append failed for {key}: {e}")
        self._save()
        logger.info(
            f"[SHADOW] Closed {key} @ {exit_price:.5f} reason={reason} "
            f"net={net_pct * 100:+.2f}% (fees ESTIMATE)"
        )

    def open_positions(self) -> Dict[str, Dict[str, Any]]:
        return dict(self._open)


def read_shadow_trades() -> list:
    return fill_ledger.read_jsonl(shadow_trades_path())
