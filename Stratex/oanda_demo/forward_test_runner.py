"""
oanda_demo/forward_test_runner.py — governed FORWARD_TEST engine for
OANDA forex legs (TASK-STR-FWD-019, Wave-2).

Why this engine exists: config_strategy.PRODUCTION_STRATEGY_REGISTRY
admits forex configurations to the FORWARD_TEST lane (status
"FORWARD_TEST", forward_protocol True, forward_venues
["oanda_practice"], lane_assets = the judged FOREX28 / forex12
universe). The existing OANDA engines cannot trade them:
oanda_demo.trader admits ONLY VALIDATED entries and runs the single
FX-MR-v4 strategy; oanda_demo.sleeve_runner admits ONLY the VALIDATED
sleeve leg sleeve_tsmom2_dual. This runner is the sleeve_runner
precedent applied to the lane: a SEPARATE engine, with separate
state / pause / kill files, that admits ONLY FORWARD_TEST forex
entries and nothing else. It never touches the FX-MR-v4 engine's or
the sleeve runner's state, pause files or positions.

Governance (fail closed on every leg):
  * An entry is admitted ONLY when ALL of these hold in the registry:
    status == "FORWARD_TEST", forward_protocol is True,
    "oanda_practice" in forward_venues, and lane_assets is non-empty.
    VALIDATED entries (fx_mr_v4, sleeve legs) are REFUSED here — they
    belong to their own engines — as are documentary FORWARD_TEST
    entries with forward_protocol False / empty lane_assets.
  * Practice account only, attested exactly as the sleeve runner /
    trader path attests it: the adapter is constructed from
    oanda_demo.credentials.load_oanda_credentials (practice flag) AND
    the adapter itself must resolve unambiguously to the practice
    environment (practice flag set AND api-fxpractice.oanda.com in
    its base URL — the same test OandaExchangeAdapter.
    _enforce_practice_only applies before any order). A non-practice
    resolution halts the scan before any evaluation or order.
  * Lane terms per strategy (TASK-STR-FWD-006 package, as registered):
    0.1% of account NAV risk per trade, 2% aggregate heat cap across
    THAT strategy's open trades, 25% notional cap, shared-account 3%
    daily breaker (NAV down 3% on the day -> no new entries), and the
    phase-3 kill criteria — expectancy < 0 or PF < 1.0 after >= 50
    closed trades, or mark-to-market drawdown > 5% of venue equity —
    evaluated on the scan cadence via measurement/forward_guard.py
    when importable (the same module the OANDA trader uses); when it
    is not importable the identical criteria are evaluated locally
    (_local_kill_decision) and that substitution is logged. A breached
    strategy is added to this runner's persisted killed_strategies
    list and never evaluated for entries again until a human removes
    it from the state file after review.
  * OANDA nets per instrument: an instrument with ANY open trade on
    the shared practice account (this runner's, FX-MR-v4's, the
    sleeve's, anyone's) is never traded, so a lane order can never
    merge into a foreign position.
  * Every open is recorded in this runner's trade log
    (data/forward_test_oanda/forward_test_trades.csv, override with
    STRATEX_FWDTEST_OANDA_DIR) with lane tag FORWARD_TEST, and every
    close is booked into the shared Phase-2 measurement fill ledger
    (measurement/fill_ledger.append_fill) with BOTH the lane tag
    ("lane": "FORWARD_TEST") and the strategy tag
    ("strategy": "strategy_<registry key>"), realised PnL read back
    from the broker's own closed-trade record — mirroring
    sleeve_runner's booking format and retry semantics (a close that
    cannot be booked yet stays in own_trades as the retry queue).

Evaluation: for each admitted entry the runner loads the governed
module Stratex/strategy_<key>.py (the same 1:1 module convention as
strategies/strategy_registry.py) and calls its get_signal(df) daemon
contract on OANDA candles fetched through the existing oanda_demo
data path (adapter._request candles endpoint, complete candles only,
dailyAlignment=0 / alignmentTimezone=UTC — the sleeve runner's
convention; supported granularities are the judged forex cells':
"1d" -> D and "4h" -> H4). The module returns side plus the judged
bracket DISTANCES (sl_dist / tp_dist); the runner anchors them to
the live pricing mid at order placement, exactly as sleeve_runner
anchors its distances, and attaches them as broker-native SL/TP.

This runner is INERT BY DEFAULT: importing it does nothing, and it
runs only when explicitly invoked from the command line (below).
No systemd unit, timer or env file references it; enabling it is a
separate deploy decision.

Usage (from the Stratex/ directory):
    python3 -m oanda_demo.forward_test_runner --status
    python3 -m oanda_demo.forward_test_runner --once [--dry-run]
    python3 -m oanda_demo.forward_test_runner --loop --interval 300
"""
from __future__ import annotations

import argparse
import csv
import importlib
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

from config_strategy import PRODUCTION_STRATEGY_REGISTRY
from exchanges.oanda_adapter import OandaExchangeAdapter
from oanda_demo.credentials import load_oanda_credentials

logger = get_logger("oanda_forward_test_runner")

ENGINE_NAME = "oanda_forward_test"
VENUE_NAME = "oanda_practice"
LANE_TAG = "FORWARD_TEST"
TIMEFRAME_GRANULARITY = {"1d": "D", "4h": "H4"}
HISTORY_BARS = 400
RISK_PER_TRADE_PCT = 0.001     # lane term: 0.1% of account NAV per trade
MAX_HEAT_PCT = 0.02            # lane term: 2% aggregate heat cap per strategy
MAX_NOTIONAL_PCT = 0.25        # per-position notional cap (as sleeve runner)
DAILY_LOSS_LIMIT_PCT = 0.03    # lane term: shared-account 3% daily breaker
REENTRY_COOLDOWN_S = 3600      # per-instrument cooldown after a close

DATA_DIR = Path(os.getenv("STRATEX_FWDTEST_OANDA_DIR", "data/forward_test_oanda"))
STATE_FILE = DATA_DIR / "forward_test_state.json"
PAUSE_FILE = DATA_DIR / "forward_test_entries_paused"
KILL_FILE = DATA_DIR / "forward_test_kill_switch"
TRADE_LOG = DATA_DIR / "forward_test_trades.csv"


# ---------------------------------------------------------------------------
# Governance
# ---------------------------------------------------------------------------

def admitted_entries(registry: Optional[Dict] = None) -> Dict[str, Dict]:
    """Registry entries this engine may trade — fail closed.

    Admits ONLY entries carrying ALL of: status "FORWARD_TEST",
    forward_protocol True, "oanda_practice" in forward_venues, and a
    non-empty lane_assets list. Everything else — VALIDATED entrants,
    documentary FORWARD_TEST registrations (forward_protocol False or
    empty lane_assets), entries for other venues — is refused.
    """
    if registry is None:
        registry = PRODUCTION_STRATEGY_REGISTRY
    out: Dict[str, Dict] = {}
    for key, entry in (registry or {}).items():
        if not isinstance(entry, dict):
            continue
        if entry.get("status") != "FORWARD_TEST":
            continue
        if entry.get("forward_protocol") is not True:
            continue
        venues = entry.get("forward_venues") or []
        if VENUE_NAME not in venues:
            continue
        if not entry.get("lane_assets"):
            continue
        out[str(key)] = entry
    return out


def practice_attested(adapter) -> bool:
    """True only when the adapter resolves unambiguously to practice.

    Mirrors OandaExchangeAdapter._enforce_practice_only: the practice
    flag must be set AND the practice host must be in the base URL.
    Anything else (live flag, live host, missing attributes) fails
    closed.
    """
    practice = getattr(adapter, "practice", None)
    base_url = str(getattr(adapter, "base_url", "") or "")
    return bool(practice) and "api-fxpractice.oanda.com" in base_url


def load_strategy_module(key: str):
    """Load Stratex/strategy_<key>.py (the governed module convention).

    Returns the module, or None (logged) when it cannot be imported —
    an admitted entry whose module is absent is skipped, never
    substituted.
    """
    try:
        return importlib.import_module(f"strategy_{key}")
    except Exception as exc:
        logger.error(f"[FWDTEST] module strategy_{key} unavailable: {exc}")
        return None


def bracket_prices(side: str, mid: float, sl_dist: float, tp_dist: float):
    """Anchor judged bracket distances to a fill-side price.

    BUY: stop below, take above. SELL: mirrored. This is the exact
    arithmetic sleeve_runner applies to its signal distances.
    """
    if side == "BUY":
        return mid - sl_dist, mid + tp_dist
    return mid + sl_dist, mid - tp_dist


def extract_signal(res, last_close: float) -> Optional[Dict]:
    """Normalise a governed module's get_signal result.

    Accepts the daemon contract dict {side, sl_dist, tp_dist} (side
    BUY/SELL or LONG/SHORT) and the gov2-style object/dict carrying
    absolute sl/tp levels (converted to distances from the signal
    bar's close, as the adx_ema_bare wrapper does). Returns
    {"side": "BUY"/"SELL", "sl_dist": float, "tp_dist": float} with
    strictly positive distances, or None for no/invalid signal.
    """
    if res is None:
        return None
    get = (lambda k: res.get(k)) if isinstance(res, dict) else (
        lambda k: getattr(res, k, None))
    side = get("side")
    if side == "LONG":
        side = "BUY"
    elif side == "SHORT":
        side = "SELL"
    if side not in ("BUY", "SELL"):
        return None
    sl_dist = get("sl_dist")
    tp_dist = get("tp_dist")
    if sl_dist is None or tp_dist is None:
        sl, tp = get("sl"), get("tp")
        if sl is None or tp is None or not last_close:
            return None
        if side == "BUY":
            sl_dist, tp_dist = last_close - float(sl), float(tp) - last_close
        else:
            sl_dist, tp_dist = float(sl) - last_close, last_close - float(tp)
    try:
        sl_dist, tp_dist = float(sl_dist), float(tp_dist)
    except (TypeError, ValueError):
        return None
    if sl_dist <= 0 or tp_dist <= 0:
        return None
    return {"side": side, "sl_dist": sl_dist, "tp_dist": tp_dist}


# ---------------------------------------------------------------------------
# Kill criteria (measurement/forward_guard.py when importable; the local
# fallback implements the identical criteria and says so in the log)
# ---------------------------------------------------------------------------

def _local_kill_decision(rows: List[Dict], equity: float, strategy_tag: str,
                         unrealized: float = 0.0) -> Dict:
    """forward_guard.evaluate's criteria, implemented locally.

    Closed-trade statistics only for expectancy / PF; the drawdown is
    the peak-to-trough of the closed PnL curve marked to market with
    the current unrealized PnL. Breach: >= 50 closed trades AND
    (expectancy < 0 OR PF < 1.0), OR MTM drawdown > 5% of equity.
    """
    fills = [r for r in rows
             if r.get("strategy") == strategy_tag and r.get("net_pnl") is not None]
    fills.sort(key=lambda r: float(r.get("exit_time") or 0.0))
    pnls = [float(r["net_pnl"]) for r in fills]
    n = len(pnls)
    net = sum(pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    if gross_loss > 0:
        pf = gross_profit / gross_loss
    elif gross_profit > 0:
        pf = float("inf")
    else:
        pf = 0.0
    cumulative = peak = max_dd = 0.0
    for p in pnls:
        cumulative += p
        peak = max(peak, cumulative)
        max_dd = max(max_dd, peak - cumulative)
    mtm_dd = max(max_dd, max(0.0, peak - (cumulative + float(unrealized or 0.0))))
    expectancy = (net / n) if n else 0.0
    dd_limit = max(0.0, float(equity)) * 0.05
    reasons: List[str] = []
    if n >= 50:
        if expectancy < 0:
            reasons.append(f"expectancy {expectancy:.4f} < 0 after {n} closed trades")
        if pf < 1.0:
            reasons.append(f"profit factor {pf:.3f} < 1.0 after {n} closed trades")
    if dd_limit > 0 and mtm_dd > dd_limit:
        reasons.append(
            f"strategy drawdown ${mtm_dd:.2f} exceeds 5% of venue equity "
            f"(${dd_limit:.2f})"
        )
    return {
        "strategy": strategy_tag,
        "trades": n,
        "net_pnl": net,
        "expectancy": expectancy,
        "profit_factor": pf,
        "max_drawdown_usd": mtm_dd,
        "drawdown_limit_usd": dd_limit,
        "breached": bool(reasons),
        "reasons": reasons,
        "evaluator": "local (measurement/forward_guard.py not importable)",
    }


def evaluate_kill(rows: List[Dict], equity: float, strategy_tag: str,
                  unrealized: float = 0.0) -> Dict:
    """Kill decision for one strategy tag, forward_guard first.

    measurement/forward_guard.py IS importable from the oanda_demo
    context (the OANDA trader uses it the same way), so it is the
    primary evaluator; the local fallback above implements the same
    criteria and is used — and logged — only if that import fails.
    """
    try:
        from measurement import forward_guard

        decisions = forward_guard.evaluate(
            rows, equity, [strategy_tag],
            unrealized_by_strategy={strategy_tag: float(unrealized or 0.0)},
        )
        if decisions:
            d = dict(decisions[0])
            d["evaluator"] = "measurement/forward_guard.py"
            return d
    except Exception as exc:
        logger.error(
            f"[FWDTEST] forward_guard unavailable ({exc}); evaluating "
            "the phase-3 kill criteria locally (identical criteria)"
        )
    return _local_kill_decision(rows, equity, strategy_tag, unrealized)


def _rfc3339_to_unix(ts: str) -> float:
    ts = (ts or "").strip()
    if not ts:
        return 0.0
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00")).timestamp()
    except ValueError:
        return datetime.fromisoformat(ts[:23] + "+00:00").timestamp()


class ForwardTestRunner:
    """Runs the governed OANDA FORWARD_TEST forex lane, and only it."""

    def __init__(self, adapter: Optional[OandaExchangeAdapter] = None,
                 dry_run: bool = False, state_file: Optional[Path] = None,
                 data_dir: Optional[Path] = None, registry: Optional[Dict] = None,
                 module_loader=None):
        if adapter is None:
            api_key, account_id, practice = load_oanda_credentials()
            adapter = OandaExchangeAdapter(
                api_key=api_key, account_id=account_id, practice=practice
            )
        self.adapter = adapter
        self.account_id = getattr(adapter, "account_id", "")
        self.dry_run = dry_run
        self.data_dir = data_dir or DATA_DIR
        self.state_file = state_file or (self.data_dir / "forward_test_state.json")
        self.pause_file = self.data_dir / "forward_test_entries_paused"
        self.kill_file = self.data_dir / "forward_test_kill_switch"
        self.trade_log = self.data_dir / "forward_test_trades.csv"
        self.registry = registry
        self._module_loader = module_loader or load_strategy_module
        self._modules: Dict[str, object] = {}

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
        if os.getenv("STRATEX_FWDTEST_ENTRIES_PAUSED", "").lower() in ("1", "true", "yes"):
            return True
        return self.pause_file.exists()

    def _module(self, key: str):
        if key not in self._modules:
            self._modules[key] = self._module_loader(key)
        return self._modules[key]

    # -- trade log ----------------------------------------------------------
    def _log_trade(self, row: Dict) -> None:
        """Append one row to this runner's own trade log (lane-tagged)."""
        try:
            self.trade_log.parent.mkdir(parents=True, exist_ok=True)
            new_file = not self.trade_log.exists()
            with open(self.trade_log, "a", newline="") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(row.keys()))
                if new_file:
                    writer.writeheader()
                writer.writerow(row)
        except OSError as exc:
            logger.warning(f"[FWDTEST] trade log write failed: {exc}")

    # -- market data --------------------------------------------------------
    def _candles(self, symbol: str, timeframe: str) -> List[Dict]:
        """Complete candles via the oanda_demo data path (sleeve-style).

        dailyAlignment=0 / alignmentTimezone=UTC, the sleeve runner's
        convention: UTC-midnight-aligned daily bars, and 4h bars on
        the UTC grid. Complete candles only — the last bar of the
        frame IS the last closed bar, as the governed modules expect.
        """
        granularity = TIMEFRAME_GRANULARITY.get(timeframe)
        if granularity is None:
            return []
        oanda_sym = self.adapter.denormalize_symbol(
            self.adapter.normalize_symbol(symbol)
        )
        params = {
            "granularity": granularity,
            "count": HISTORY_BARS,
            "price": "M",
            "alignmentTimezone": "UTC",
        }
        if granularity == "D":
            params["dailyAlignment"] = 0
        data = self.adapter._request(
            "GET", f"/instruments/{oanda_sym}/candles", params=params
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

    # -- sizing (sleeve_runner arithmetic, per-strategy heat) ---------------
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
        notional_per_unit = mid * conv
        risk_usd = equity * RISK_PER_TRADE_PCT
        if risk_budget_usd is not None:
            risk_usd = min(risk_usd, float(risk_budget_usd))
            if risk_usd <= 0:
                return 0
        units = int(risk_usd / (sl_dist * conv))
        max_units_notional = int((equity * MAX_NOTIONAL_PCT) / notional_per_unit)
        lev = (1.0 / margin_rate) if margin_rate and margin_rate > 0 else 20.0
        max_units_margin = int((free_margin * 0.5) * lev / notional_per_unit)
        return max(0, min(units, max_units_notional, max_units_margin))

    # -- ledger booking (sleeve_runner format + lane tag) -------------------
    def _book_close(self, trade_id: str, meta: Dict) -> bool:
        """Book a detected close into the measurement fill ledger.

        Mirrors sleeve_runner._book_close: broker-truth realised PnL,
        idempotent, and False (keep the trade in own_trades as the
        retry queue, alert latched) when the close cannot be booked
        yet — a lane close is never silently dropped.
        """
        try:
            from measurement import fill_ledger
        except Exception as exc:
            logger.error(f"[FWDTEST] fill ledger unavailable: {exc}")
            return False
        try:
            if meta.get("order_id") and fill_ledger.fill_exists(
                order_id=str(meta["order_id"])
            ):
                return True
        except Exception as exc:
            logger.error(
                f"[FWDTEST] ledger idempotence check failed for trade "
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
                    f"forward-test trade {trade_id} ({meta.get('symbol')}) "
                    "closed but the broker record is unavailable; queued "
                    "for retry (TASK-STR-FWD-019)",
                )
                return False
            realized = float(trade.get("realizedPL") or 0.0)
            exit_price = float(trade.get("averageClosePrice") or trade.get("price") or 0.0)
            exit_time = _rfc3339_to_unix(str(trade.get("closeTime") or ""))
            row = fill_ledger.append_fill(
                {
                    "engine": ENGINE_NAME,
                    "venue": VENUE_NAME,
                    "lane": LANE_TAG,
                    "strategy": f"strategy_{meta['strategy']}",
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
                logger.error(
                    f"[FWDTEST] close booking REJECTED for trade {trade_id}; "
                    "kept in own_trades for retry (TASK-STR-FWD-019)"
                )
                return False
            logger.info(
                f"[FWDTEST] booked close {meta['symbol']} trade {trade_id} "
                f"net=${realized:+.2f} (strategy=strategy_{meta['strategy']}, "
                f"lane={LANE_TAG})"
            )
            return True
        except Exception as exc:
            logger.error(f"[FWDTEST] close booking FAILED for trade {trade_id}: {exc}")
            try:
                fill_ledger.raise_alert(
                    "unrecorded_close",
                    f"forward-test close booking failed for trade {trade_id} "
                    f"({meta.get('symbol')}): {exc}; kept in own_trades for "
                    "retry (TASK-STR-FWD-019)",
                )
            except Exception:
                pass
            return False

    # -- core scan ------------------------------------------------------------
    def run_once(self) -> Dict:
        summary: Dict = {"ts": datetime.now(timezone.utc).isoformat(),
                         "engine": ENGINE_NAME, "actions": []}
        if self.kill_file.exists():
            summary["halted"] = "forward-test kill switch present"
            logger.warning("[FWDTEST] kill switch active — skipping scan")
            return summary
        admitted = admitted_entries(self.registry)
        summary["admitted"] = sorted(admitted)
        if not admitted:
            summary["halted"] = (
                "governance: no FORWARD_TEST entry admitted for "
                "oanda_practice (fail closed)"
            )
            logger.warning("[FWDTEST] governance refusal — no admitted entries")
            return summary
        if not practice_attested(self.adapter):
            summary["halted"] = (
                "attestation: adapter is not unambiguously on the OANDA "
                "practice environment (fail closed)"
            )
            logger.warning("[FWDTEST] practice attestation FAILED — scan halted")
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

        # Close detection + booking (runs even while entries are paused;
        # book FIRST, pop only after the fill row is in the ledger).
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
                self._log_trade({
                    "ts": summary["ts"], "event": "CLOSE", "lane": LANE_TAG,
                    "strategy": meta["strategy"],
                    "strategy_tag": f"strategy_{meta['strategy']}",
                    "symbol": meta["symbol"], "side": meta["side"],
                    "units": meta["units"], "price": "",
                    "sl": "", "tp": "",
                    "order_id": str(meta.get("order_id", "")),
                    "trade_id": tid, "timeframe": meta.get("timeframe", ""),
                })
        summary["own_open_trades"] = len(own)
        summary["account_open_trades"] = len(trades)

        # Mark-to-market per strategy (kill evaluation + reporting).
        unrealized_by_key: Dict[str, float] = {}
        for t in trades:
            meta = own.get(str(t["id"]))
            if meta:
                unrealized_by_key[meta["strategy"]] = (
                    unrealized_by_key.get(meta["strategy"], 0.0)
                    + float(t.get("unrealized_pl", 0) or 0)
                )
        state["unrealized_pnl_usd"] = {
            k: round(v, 4) for k, v in unrealized_by_key.items()
        }
        state["unrealized_ts"] = time.time()

        # Kill evaluation on the scan cadence (per admitted strategy).
        killed = set(state.get("killed_strategies", []))
        try:
            from measurement import fill_ledger

            ledger_rows = fill_ledger.read_fills()
        except Exception:
            ledger_rows = []
        for key in sorted(admitted):
            if key in killed:
                continue
            decision = evaluate_kill(
                ledger_rows, equity, f"strategy_{key}",
                unrealized=unrealized_by_key.get(key, 0.0),
            )
            summary.setdefault("kill_evaluation", []).append({
                "strategy": key,
                "trades": decision["trades"],
                "breached": decision["breached"],
                "reasons": decision["reasons"],
            })
            if decision["breached"]:
                killed.add(key)
                logger.warning(
                    f"[FWDTEST] KILL CRITERION breached for {key}: "
                    + "; ".join(decision["reasons"])
                )
        state["killed_strategies"] = sorted(killed)
        summary["killed_strategies"] = sorted(killed)

        if self._paused():
            summary["entries_paused"] = True
            logger.info("[FWDTEST] entries paused — closes booked only")
            self._save_state(state)
            return summary
        if daily_dd <= -DAILY_LOSS_LIMIT_PCT:
            summary["blocked"] = f"daily loss limit ({daily_dd*100:.1f}%)"
            self._save_state(state)
            return summary

        occupied = {t["instrument"] for t in trades}  # netting protection
        wanted = sorted({s for e in admitted.values() for s in e["lane_assets"]})
        pricing = self.adapter.get_pricing(list(dict.fromkeys(wanted + ["USDJPY"])))
        if not pricing:
            summary["error"] = "pricing unavailable"
            self._save_state(state)
            return summary

        trades_by_id = {str(t["id"]): t for t in trades}

        def _open_risk_usd(key: str) -> float:
            total = 0.0
            for tid, meta in own.items():
                if meta.get("strategy") != key:
                    continue
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
                conv = self._quote_to_usd(sym[3:], pricing) if len(sym) > 3 else 0.0
                if stop > 0 and price > 0 and conv > 0:
                    total += u * abs(price - stop) * conv
            return total

        now = time.time()
        cooldowns = state.get("cooldowns", {})
        candle_cache: Dict = {}

        for key in sorted(admitted):
            if key in killed:
                continue
            entry = admitted[key]
            timeframe = str(entry.get("timeframe") or "")
            if timeframe not in TIMEFRAME_GRANULARITY:
                summary.setdefault("unsupported_timeframe", []).append(
                    f"{key}:{timeframe}"
                )
                continue
            module = self._module(key)
            if module is None or not callable(getattr(module, "get_signal", None)):
                summary.setdefault("module_unavailable", []).append(key)
                continue
            running_heat = _open_risk_usd(key)
            summary.setdefault("open_risk_usd", {})[key] = round(running_heat, 2)
            for symbol in entry["lane_assets"]:
                if symbol in occupied:
                    continue
                if now < float(cooldowns.get(symbol, 0) or 0):
                    continue
                cache_key = (symbol, timeframe)
                if cache_key not in candle_cache:
                    candle_cache[cache_key] = self._candles(symbol, timeframe)
                candles = candle_cache[cache_key]
                if not candles:
                    continue
                df = pd.DataFrame(candles)
                df.index = pd.to_datetime(df["timestamp"], unit="s", utc=True)
                try:
                    raw = module.get_signal(df)
                except Exception as exc:
                    logger.warning(f"[FWDTEST] {key} get_signal failed on {symbol}: {exc}")
                    continue
                summary["evaluated"] = summary.get("evaluated", 0) + 1
                sig = extract_signal(raw, float(df["close"].iloc[-1]))
                if sig is None:
                    continue
                mid = pricing.get(symbol, {}).get("mid", 0)
                if mid <= 0:
                    continue
                stop, take = bracket_prices(
                    sig["side"], mid, sig["sl_dist"], sig["tp_dist"]
                )
                remaining_heat = equity * MAX_HEAT_PCT - running_heat
                if remaining_heat <= 0:
                    summary.setdefault("heat_capped", []).append(f"{key}:{symbol}")
                    continue
                units = self._position_units(
                    symbol, sig["sl_dist"], pricing, equity, free_margin,
                    margin_rate, risk_budget_usd=remaining_heat,
                )
                if units < 1:
                    continue
                summary["actions"].append(
                    f"{sig['side']} {symbol} {units}u @~{mid:.5f} "
                    f"SL {stop:.5f} TP {take:.5f} ({key})"
                )
                logger.info(
                    f"[FWDTEST] SIGNAL {sig['side']} {symbol} units={units} "
                    f"mid={mid:.5f} sl={stop:.5f} tp={take:.5f} "
                    f"(strategy=strategy_{key}, lane={LANE_TAG})"
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
                    logger.warning(f"[FWDTEST] order failed for {symbol}: {exc}")
                    summary["actions"].append(f"ORDER FAILED {symbol}: {exc}")
                    state.setdefault("cooldowns", {})[symbol] = (
                        time.time() + REENTRY_COOLDOWN_S
                    )
                    continue
                trade_id = str(getattr(result, "trade_id", "") or "")
                if trade_id:
                    committed = (
                        units * sig["sl_dist"]
                        * self._quote_to_usd(symbol[3:], pricing)
                    )
                    own[trade_id] = {
                        "strategy": key,
                        "symbol": symbol,
                        "side": sig["side"],
                        "units": units,
                        "entry_price": float(getattr(result, "price", mid) or mid),
                        "entry_time": time.time(),
                        "order_id": str(getattr(result, "order_id", "") or ""),
                        "risk_usd": round(committed, 4),
                        "timeframe": timeframe,
                    }
                    running_heat += committed
                    self._log_trade({
                        "ts": summary["ts"], "event": "OPEN", "lane": LANE_TAG,
                        "strategy": key, "strategy_tag": f"strategy_{key}",
                        "symbol": symbol, "side": sig["side"],
                        "units": units,
                        "price": float(getattr(result, "price", mid) or mid),
                        "sl": stop, "tp": take,
                        "order_id": str(getattr(result, "order_id", "") or ""),
                        "trade_id": trade_id, "timeframe": timeframe,
                    })
                    try:
                        from measurement import fill_ledger

                        fill_ledger.append_position_tag({
                            "engine": ENGINE_NAME,
                            "venue": VENUE_NAME,
                            "lane": LANE_TAG,
                            "symbol": symbol,
                            "strategy": f"strategy_{key}",
                            "timeframe": timeframe,
                            "side": sig["side"],
                            "qty": units,
                            "entry_price": float(
                                getattr(result, "price", mid) or mid
                            ),
                            "order_id": trade_id,
                            "note": "TASK-STR-FWD-019 governed FORWARD_TEST entrant",
                        })
                    except Exception:
                        pass
                occupied.add(symbol)

        summary["own_open_trades"] = len(own)
        self._save_state(state)
        return summary

    def status(self) -> Dict:
        admitted = admitted_entries(self.registry)
        return {
            "engine": ENGINE_NAME,
            "venue": VENUE_NAME,
            "lane": LANE_TAG,
            "practice_attested": practice_attested(self.adapter),
            "admitted": sorted(admitted),
            "entries_paused": self._paused(),
            "account": self.adapter.get_account_summary(),
            "own_open_trades": len(self._load_state().get("own_trades", {})),
            "killed_strategies": self._load_state().get("killed_strategies", []),
            "trade_log": str(self.trade_log),
        }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Stratex OANDA FORWARD_TEST forex runner (TASK-STR-FWD-019)"
    )
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--loop", action="store_true")
    parser.add_argument("--interval", type=int, default=300)
    parser.add_argument("--status", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    runner = ForwardTestRunner(dry_run=args.dry_run)
    if args.status:
        print(json.dumps(runner.status(), indent=2, default=str))
        return 0
    if args.loop:
        logger.info("[FWDTEST] loop mode starting (engine=%s)", ENGINE_NAME)
        while True:
            try:
                out = runner.run_once()
                logger.info(f"[FWDTEST] scan: {json.dumps(out, default=str)}")
            except KeyboardInterrupt:
                break
            except Exception as exc:
                logger.warning(f"[FWDTEST] scan error: {exc}")
            time.sleep(max(30, args.interval))
        return 0
    out = runner.run_once()
    print(json.dumps(out, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
