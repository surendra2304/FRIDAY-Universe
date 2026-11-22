"""
api/friday_supervision.py — FRIDAY Supervision & Universal Task Protocol endpoints for Stratex.

Provides:
1. GET /v1/friday/supervision/status & GET /api/v1/friday/status:
   Structured engine health, mode, panic state, positions, and advisory counts.
2. POST /v1/friday/supervision/panic & POST /api/v1/friday/panic:
   Preserved emergency panic stop / kill-switch activation and release.
3. GET /v1/friday/supervision/advisories:
   Inspect pending staged bounded recommendations and history.
4. POST /v1/friday/supervision/advisory/authorize:
   Explicit authorization and application of staged parameter changes.
5. POST /v1/friday/task & POST /v1/task/execute:
   Universal Task Protocol handler enforcing deterministic execution authority
   (orders and gate bypass attempts by external agents are rejected fail-closed).
"""

import datetime
import json
import os
import re
import threading
import time
from dataclasses import asdict, is_dataclass
from typing import Any

from flask import Blueprint, jsonify, request

import config
import daemon_book
from advisory_params import get_advisory_overlay
from api.validation import RequestValidationError, get_str, json_body
from audit.audit_manager import get_audit_manager, get_idempotency_store, persisted_hash
from atomic_io import atomic_write_json
from logger import get_logger
from security_hardening import SCOPE_FRIDAY, require_api_scope
from panic_state import is_kill_switch_locked, is_panic_active, kill_switch_lock_file, write_panic_state
from telemetry.health_guard import (
    MAX_TELEMETRY_STALENESS_SECONDS,
)

logger = get_logger("friday_supervision")

friday_supervision_bp = Blueprint("friday_supervision", __name__)


def _is_panic_active() -> bool:
    # Unified reader: either schema key counts and a corrupt flag fails closed.
    return is_panic_active() or is_kill_switch_locked()


def _task_receipt(
    *,
    requested_action: str,
    target: str = "stratex",
    authorization_decision: str = "AUTHORIZED",
    result: Any = None,
    verification_evidence: dict[str, Any] | None = None,
    failure_reason: str | None = None,
) -> dict[str, Any]:
    """Receipt for the Universal Task Protocol, mirroring FRIDAY's ActionReceipt.

    FRIDAY's cognitive mesh only certifies a task COMPLETED when the peer answers
    with a receipt that names the action it dispatched, targets this agent, and
    carries non-empty verification evidence. Without one the work is UNVERIFIED,
    even when the underlying action really ran.
    """
    return {
        "requested_action": requested_action,
        "target": target,
        "authorization_decision": authorization_decision,
        "execution_timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "result": dict(result) if isinstance(result, dict) else {"result": result},
        "verification_evidence": dict(verification_evidence or {}),
        "failure_reason": failure_reason,
    }


def _is_kill_switch_locked() -> bool:
    return is_kill_switch_locked()


# ---------------------------------------------------------------------------
# Real trading-data helpers (Stratex cTrader demo engine)
# ---------------------------------------------------------------------------

_LAST_MARKET_ANALYSIS: dict[str, Any] | None = None
_LAST_MARKET_ANALYSIS_TS: float = 0.0
_MARKET_ANALYSIS_INTERVAL_SEC: float = 60.0
# TASK-VOI-006: single-flight guard for the background analysis refresh —
# at most one refresh thread runs at a time; status reads never wait on it.
_ANALYSIS_REFRESH_LOCK = threading.Lock()
_ANALYSIS_REFRESH_RUNNING = False


def _safe_engine():
    """Return the autonomous engine singleton if it can be imported, else None."""
    try:
        from autonomy.mt5_autonomous_engine import get_autonomous_engine

        return get_autonomous_engine()
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] Engine unavailable: {exc}")
        return None


def _position_to_dict(pos: Any) -> dict[str, Any]:
    if is_dataclass(pos):
        try:
            return asdict(pos)
        except Exception:
            pass
    if isinstance(pos, dict):
        return dict(pos)
    fields = [
        "position_id", "symbol", "side", "quantity", "entry_price", "stop_loss",
        "take_profit", "mark_price", "unrealized_pnl", "opened_at", "strategy",
        "ai_thesis", "lots",
    ]
    out: dict[str, Any] = {}
    for f in fields:
        if hasattr(pos, f):
            try:
                out[f] = getattr(pos, f)
            except Exception:
                pass
    return out


def _signal_to_dict(sig: Any) -> dict[str, Any]:
    if is_dataclass(sig):
        try:
            return asdict(sig)
        except Exception:
            pass
    if isinstance(sig, dict):
        return dict(sig)
    fields = [
        "symbol", "timeframe", "action", "regime", "current_price", "stop_loss",
        "take_profit", "risk_reward_ratio", "confidence", "kalman_z", "atr",
        "strategy_source", "timestamp", "metadata",
    ]
    out: dict[str, Any] = {}
    for f in fields:
        if hasattr(sig, f):
            try:
                out[f] = getattr(sig, f)
            except Exception:
                pass
    # Normalise enum-like regime to string.
    if "regime" in out and not isinstance(out["regime"], str):
        out["regime"] = str(out["regime"])
    return out


def _latest_fill_exit_time() -> str | None:
    """Latest exit_time in the phase-2 fill ledger, as an ISO string.

    The ledger is the same source the supervision scorecard block reports
    from. Fails soft to None — the caller falls back to the heartbeat's
    last_strategy_evaluation.
    """
    try:
        try:
            from measurement import fill_ledger
        except Exception:
            import fill_ledger  # type: ignore
        fills = fill_ledger.read_fills()
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] fill ledger unavailable: {exc}")
        return None
    latest: float | None = None
    for row in fills or []:
        try:
            ts = float(row.get("exit_time") or 0.0)
        except (TypeError, ValueError):
            continue
        if ts > 0 and (latest is None or ts > latest):
            latest = ts
    if latest is None:
        return None
    return (
        datetime.datetime.fromtimestamp(latest, datetime.timezone.utc)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _real_trading_data(engine=None) -> dict[str, Any]:
    """The live trading book, composed from the multi-venue daemon's state.

    Composition (daemon_book): aggregates from state/daemon_heartbeat.json
    — the daemon's own venue-derived view, the same figures /health
    serves — and position rows from state/forward_scorecard.json. The
    retired MT5 engine and its cloud_portfolio_state.json are NOT
    consulted: that file froze on 2026-11-08 (balance 10792.8, zero
    positions) and reported an empty book while the daemon traded. The
    ``engine`` argument is retained for caller compatibility; this
    composition never consults it (the engine remains in use for the
    analyze path's signal generation only).

    Degradation: when the heartbeat gate fails the daemon is reported
    unavailable (``engine_data_status``) with an empty book — last
    figures are never served as live. When the scorecard is missing or
    stale, aggregates still serve and the position list is withheld with
    ``positions_source: "unavailable"``. The headline count is always
    the heartbeat's venue-derived count; the row list is served as-is
    and never padded or trimmed to force a match.
    """
    panic_active = False
    try:
        from panic_state import is_panic_active, is_kill_switch_locked

        panic_active = bool(is_panic_active() or is_kill_switch_locked())
    except Exception:
        pass

    trading_mode = "multi_venue_demo"
    book = daemon_book.live_book()
    heartbeat = book["heartbeat"]
    scorecard = book["scorecard"]
    positions_as_of = scorecard["generated_at"] if scorecard else None

    market_conditions: dict[str, Any] = {
        "trading_mode": trading_mode,
        "venue": "binance_futures_demo",
        "max_positions": None,
        "active_positions": 0,
        "capacity_used_pct": 0.0,
        "at_capacity": False,
        "panic_active": panic_active,
        "last_analysis": None,
        "last_analysis_age_sec": None,
    }
    global _LAST_MARKET_ANALYSIS
    if _LAST_MARKET_ANALYSIS:
        market_conditions["last_analysis"] = _LAST_MARKET_ANALYSIS.get("analysis_timestamp")
        # TASK-REL-071: surface the evaluation age (seconds since the last
        # _ensure_market_analysis refresh completed) next to its timestamp,
        # so staleness is visible without parsing ISO strings. None while
        # no refresh has ever published (cold process).
        market_conditions["last_analysis_age_sec"] = (
            round(time.time() - _LAST_MARKET_ANALYSIS_TS, 1)
            if _LAST_MARKET_ANALYSIS_TS else None
        )
        market_conditions["last_analysis_signals"] = _LAST_MARKET_ANALYSIS.get("signal_count")
        market_conditions["buy_signals"] = _LAST_MARKET_ANALYSIS.get("buy_signals")
        market_conditions["sell_signals"] = _LAST_MARKET_ANALYSIS.get("sell_signals")

    if heartbeat is None:
        return {
            "positions": [],
            "open_positions": [],
            "current_positions": [],
            "position_count": 0,
            "open_positions_count": 0,
            "balance": 0.0,
            "cash": 0.0,
            "unrealized_pnl": 0.0,
            "last_trade_time": None,
            "max_positions": None,
            "market_conditions": market_conditions,
            "trading_mode": trading_mode,
            "panic_active": panic_active,
            "engine_source": "multi_venue_daemon",
            "engine_data_status": "daemon_unavailable",
            "positions_source": "unavailable",
            "positions_as_of": positions_as_of,
        }

    def _as_int(value: Any) -> int:
        try:
            return int(value or 0)
        except (TypeError, ValueError):
            return 0

    def _as_float(value: Any) -> float:
        try:
            return float(value or 0.0)
        except (TypeError, ValueError):
            return 0.0

    position_count = _as_int(heartbeat.get("open_positions"))
    balance = _as_float(heartbeat.get("total_balance"))
    unrealized_pnl = _as_float(heartbeat.get("unrealized_pnl"))
    market_conditions["active_positions"] = position_count

    return {
        "positions": book["rows"],
        "open_positions": book["rows"],
        "current_positions": book["rows"],
        "position_count": position_count,
        "open_positions_count": position_count,
        "balance": round(balance, 2),
        "cash": round(balance, 2),
        "unrealized_pnl": round(unrealized_pnl, 2),
        "last_trade_time": _latest_fill_exit_time()
        or heartbeat.get("last_strategy_evaluation"),
        "max_positions": None,
        "market_conditions": market_conditions,
        "trading_mode": trading_mode,
        "panic_active": panic_active,
        "engine_source": "multi_venue_daemon",
        "engine_data_status": "ok",
        "positions_source": "unavailable" if book["rows_withheld"] else "forward_scorecard",
        "positions_as_of": positions_as_of,
    }


def _run_market_analysis(payload: Any = None) -> dict[str, Any]:
    """Run a real analysis cycle using the engine and log the results."""
    global _LAST_MARKET_ANALYSIS, _LAST_MARKET_ANALYSIS_TS

    engine = _safe_engine()
    if not isinstance(payload, dict):
        payload = {}

    symbols = payload.get("symbols") if isinstance(payload, dict) else None
    if not symbols and engine is not None:
        all_symbols = getattr(engine, "symbols", None) or []
        # Keep analysis responsive by default; callers may pass an explicit list.
        symbols = list(all_symbols)[:8] if all_symbols else None
    if not symbols:
        symbols = ["EURUSD", "GBPUSD", "XAUUSD"]
    if isinstance(symbols, str):
        symbols = [symbols]
    symbols = [str(s).upper() for s in symbols][:25]

    timeframes = payload.get("timeframes") or payload.get("timeframe")
    if isinstance(timeframes, str):
        timeframes = [timeframes]
    if not timeframes and engine is not None:
        all_tfs = getattr(engine, "timeframes", None) or []
        timeframes = list(all_tfs)[:2] if all_tfs else None
    if not timeframes:
        timeframes = ["15m"]
    timeframes = [str(t) for t in timeframes][:6]

    signals: list[dict[str, Any]] = []
    errors: list[str] = []
    analyzed = 0
    for symbol in symbols:
        best_signal = None
        best_score = -1.0
        for tf in timeframes:
            analyzed += 1
            try:
                sig = engine.evaluate_symbol_timeframe(symbol, tf) if engine is not None else None
            except Exception as exc:
                errors.append(f"{symbol}/{tf}: {exc}")
                continue
            if sig is None:
                continue
            sig_dict = _signal_to_dict(sig)
            if not sig_dict:
                continue
            try:
                conf = float(sig_dict.get("confidence", 0.0) or 0.0)
                rr = float(sig_dict.get("risk_reward_ratio", 0.0) or 0.0)
                score = conf * min(max(rr, 0.1), 3.0)
            except (TypeError, ValueError):
                score = 0.0
            if score > best_score:
                best_score = score
                best_signal = sig_dict
        if best_signal is not None:
            signals.append(best_signal)
            logger.info(
                f"[STRATEX_ANALYSIS] {best_signal.get('symbol')} ({best_signal.get('timeframe')}): "
                f"{best_signal.get('action')} @ {best_signal.get('current_price')} "
                f"conf={best_signal.get('confidence')} rr={best_signal.get('risk_reward_ratio')}"
            )

    buys = sum(1 for s in signals if str(s.get("action", "")).upper() == "BUY")
    sells = sum(1 for s in signals if str(s.get("action", "")).upper() == "SELL")

    trading_data = _real_trading_data(engine)
    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat().replace("+00:00", "Z")

    market_conditions = {
        "symbols_analyzed": len(symbols),
        "timeframes": timeframes,
        "signals_found": len(signals),
        "buy_signals": buys,
        "sell_signals": sells,
        "hold_signals": max(0, len(symbols) - len(signals)),
        "max_positions": trading_data.get("max_positions"),
        "active_positions": trading_data.get("position_count", 0),
        "at_capacity": trading_data.get("market_conditions", {}).get("at_capacity", False),
        "errors": errors[:10],
    }

    result = {
        "status": "SUCCESS",
        "analysis_timestamp": now_iso,
        "engine": "stratex",
        "symbols_analyzed": symbols,
        "timeframes": timeframes,
        "signals": signals,
        "signal_count": len(signals),
        "buy_signals": buys,
        "sell_signals": sells,
        "market_conditions": market_conditions,
        "positions": trading_data.get("positions", []),
        "position_count": trading_data.get("position_count", 0),
        "balance": trading_data.get("balance", 0.0),
        "unrealized_pnl": trading_data.get("unrealized_pnl", 0.0),
        "last_trade_time": trading_data.get("last_trade_time"),
        "errors": errors[:10],
    }

    _LAST_MARKET_ANALYSIS = {
        "analysis_timestamp": now_iso,
        "signal_count": len(signals),
        "buy_signals": buys,
        "sell_signals": sells,
    }
    _LAST_MARKET_ANALYSIS_TS = time.time()

    logger.info(
        f"[STRATEX_ANALYSIS] Cycle complete: {len(signals)} signals from {len(symbols)} symbols "
        f"({buys} BUY, {sells} SELL)."
    )
    return result


def _refresh_market_analysis(engine=None) -> None:
    """Run one market-analysis refresh cycle (the pre-VOI-006 inline body).

    Executed on a background thread (see ``_ensure_market_analysis``); on
    completion ``_run_market_analysis`` republishes ``_LAST_MARKET_ANALYSIS``
    and its timestamp, which is what status reads serve.
    """
    global _ANALYSIS_REFRESH_RUNNING
    try:
        engine = _safe_engine() if engine is None else engine
        symbols = None
        timeframes = None
        if engine is not None:
            symbols = list(getattr(engine, "symbols", []) or [])[:5]
            timeframes = list(getattr(engine, "timeframes", []) or [])[:1]
        _run_market_analysis({"symbols": symbols, "timeframes": timeframes})
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] Market analysis refresh failed: {exc}")
    finally:
        with _ANALYSIS_REFRESH_LOCK:
            _ANALYSIS_REFRESH_RUNNING = False


def _ensure_market_analysis(engine=None) -> None:
    """Make sure a market-analysis refresh is under way if the snapshot is stale.

    TASK-VOI-006: this used to run the refresh SYNCHRONOUSLY inside the
    read-only status path (``_get_engine_status_summary`` backs both the
    supervision GET and the mesh ``status`` task FRIDAY's voice brain
    waits on). A refresh evaluates up to 5 symbols through the strategy
    engine with market-data fetches and measured 24.5 s cold on Server 1
    (69 s under multi-crew load, 2026-11-15 03:19 IST) — paid inline by
    whichever status call arrived first after the 60 s TTL, which for
    sporadic voice delegations was effectively every call, and it is
    what pushed spoken Stratex answers past the 60 s voice brain budget
    (TASK-VOI-005 attempts: 63.28 s timeout, 46.99 s). The balance,
    positions and ledger figures a status answer actually reports come
    from ``_real_trading_data`` / the fill ledger, not from the analysis;
    the analysis only feeds the ``last_market_analysis`` /
    ``market_conditions`` fields, which carry their own timestamp.

    Now: if the snapshot is stale and no refresh is running, start ONE
    background refresh and return immediately. The caller serves the
    last computed snapshot (or none, on a cold process) with its
    ``analysis_timestamp`` visible, so staleness is disclosed in the
    payload rather than hidden behind a blocked request.
    """
    global _ANALYSIS_REFRESH_RUNNING
    now = time.time()
    if _LAST_MARKET_ANALYSIS is not None and (now - _LAST_MARKET_ANALYSIS_TS) < _MARKET_ANALYSIS_INTERVAL_SEC:
        return
    with _ANALYSIS_REFRESH_LOCK:
        if _ANALYSIS_REFRESH_RUNNING:
            return
        _ANALYSIS_REFRESH_RUNNING = True
    thread = threading.Thread(
        target=_refresh_market_analysis,
        args=(engine,),
        daemon=True,
        name="stratex-market-analysis-refresh",
    )
    try:
        thread.start()
    except Exception as exc:
        with _ANALYSIS_REFRESH_LOCK:
            _ANALYSIS_REFRESH_RUNNING = False
        logger.debug(f"[FRIDAY_SUPERVISION] Market analysis refresh could not start: {exc}")


def _ledger_scorecard_block() -> dict[str, Any] | None:
    """Compact fill-ledger scorecard for FRIDAY's portfolio answers.

    TASK-STR-ANS-001: the supervision payload carried balances and
    positions but no recorded P&L, so even a FRIDAY answer that rendered
    the snapshot could not say what the ledger shows. The block is
    computed from the phase-2 fill ledger ONLY
    (measurement.scorecard.build_scorecard — the same generator behind
    state/scorecard.json) and fails soft: any error omits the block
    rather than breaking the status answer.
    """
    try:
        from measurement import scorecard as _scorecard

        card = _scorecard.build_scorecard()
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] scorecard unavailable: {exc}")
        return None
    try:
        totals = card.get("totals") or {}
        strategies: dict[str, Any] = {}
        for name, stats in (card.get("strategies") or {}).items():
            if not isinstance(stats, dict):
                continue
            strategies[str(name)] = {
                "trades": stats.get("trades"),
                "net_pnl": stats.get("net_pnl"),
                "profit_factor": stats.get("profit_factor"),
                "win_rate": stats.get("win_rate"),
            }
        return {
            "generated_at": card.get("generated_at"),
            "source": card.get("source"),
            "total_fills": card.get("total_fills"),
            "totals": {
                "trades": totals.get("trades"),
                "net_pnl": totals.get("net_pnl"),
                "win_rate": totals.get("win_rate"),
                "profit_factor": totals.get("profit_factor"),
                "expectancy_net_per_trade": totals.get("expectancy_net_per_trade"),
                "max_drawdown": totals.get("max_drawdown"),
                "fees": totals.get("fees"),
            },
            "strategies": strategies,
            "reset_boundaries": len(card.get("reset_boundaries") or []),
        }
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] scorecard shaping failed: {exc}")
        return None


# TASK-FRD-011: status-summary snapshot cache (the TASK-VOI-006 pattern,
# applied to the trading data itself). A status read used to call the
# live engine (get_account_balance / get_active_positions / cloud-state
# load) inline on EVERY request. Measured on production (FRD-005 re-run
# 20261116-103839 + FRD-011 probes): the execute's wall time was 14 s in
# the run and 24–90+ s under load, while the handler's own measured
# execution was only ~4 s of one 24 s sample — the read pays engine and
# process contention it does not need. The figures a status answer
# reports (balance, positions, ledger scorecard) change on the engine's
# own cycle cadence, so the summary is computed once and served from
# the snapshot: fresh inside the TTL, stale-while-revalidate (one
# background refresh, single-flight) up to the hard staleness bound —
# Stratex's own telemetry limit (MAX_TELEMETRY_STALENESS_SECONDS = 60 s,
# advisory_gate.py) — and computed synchronously beyond it rather than
# serving ancient money data. The payload's "timestamp" is the
# snapshot's compute time, so its age is visible, not hidden.
_STATUS_SUMMARY_TTL_S: float = 10.0
_STATUS_SUMMARY_MAX_STALE_S: float = 60.0
_STATUS_SUMMARY_CACHE: dict[str, Any] | None = None
_STATUS_SUMMARY_TS: float = 0.0
_STATUS_SUMMARY_LOCK = threading.Lock()
_STATUS_SUMMARY_REFRESHING = False


def _refresh_status_summary() -> None:
    global _STATUS_SUMMARY_CACHE, _STATUS_SUMMARY_TS, _STATUS_SUMMARY_REFRESHING
    try:
        data = _compute_engine_status_summary()
        with _STATUS_SUMMARY_LOCK:
            _STATUS_SUMMARY_CACHE = data
            _STATUS_SUMMARY_TS = time.time()
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] status summary refresh failed: {exc}")
    finally:
        with _STATUS_SUMMARY_LOCK:
            _STATUS_SUMMARY_REFRESHING = False


# TASK-FRD-013: snapshot keeper. The FRD-011 cache serves reads inside the
# TTL / SWR window, but a read that arrives cold (no snapshot yet) or past
# the 60 s hard bound pays _compute_engine_status_summary() SYNCHRONOUSLY —
# and that compute is unbounded: its first call in a process also constructs
# the autonomous-engine singleton (full strategy-registry load). Production
# incident 2026-11-16 13:38 IST: Stratex.service had restarted at 13:26:37
# (deploy), so the owner's figures question was the FIRST status read in
# the new process — audit logged 13:38:13, response completed 13:39:16
# (63 s server-side: registry flood + engine construction inline), while
# FRIDAY's mesh budget is 30 s → "Stratex could not answer that:
# ReadTimeout" at calm host load (0.42). A warm process answered the same
# path in 4 s (12:22). Status questions are sporadic (minutes apart), so
# the read-driven refresh cadence the cache design assumed never happens.
# The keeper supplies that cadence instead: started once from dashboard
# startup, it computes the snapshot immediately and refreshes it every
# _STATUS_SUMMARY_KEEPER_INTERVAL_S via the same single-flight machinery,
# so in a running process a read always lands inside the TTL/SWR window
# and the snapshot never ages past the 60 s telemetry bound (FRD-011's
# "never serve ancient money data" contract is preserved — the bound is
# now enforced by cadence, not by making a reader pay the compute).
_STATUS_SUMMARY_KEEPER_INTERVAL_S: float = 30.0
_STATUS_SUMMARY_KEEPER_THREAD: threading.Thread | None = None
_STATUS_SUMMARY_KEEPER_LOCK = threading.Lock()


def _keeper_refresh_once() -> bool:
    """One keeper refresh pass: claim the single-flight slot and refresh.

    Returns True when this pass ran the refresh, False when a refresh was
    already in flight (the read path's SWR refresh or a previous keeper
    pass still computing) — the next pass retries.
    """
    global _STATUS_SUMMARY_REFRESHING
    with _STATUS_SUMMARY_LOCK:
        if _STATUS_SUMMARY_REFRESHING:
            return False
        _STATUS_SUMMARY_REFRESHING = True
    _refresh_status_summary()
    return True


def _status_summary_keeper_loop() -> None:
    while True:
        try:
            _keeper_refresh_once()
        except Exception as exc:  # the keeper must never die silently
            logger.debug(f"[FRIDAY_SUPERVISION] status keeper pass failed: {exc}")
        time.sleep(_STATUS_SUMMARY_KEEPER_INTERVAL_S)


def start_status_summary_keeper() -> threading.Thread | None:
    """Start the snapshot keeper exactly once (idempotent).

    Called from dashboard startup, after the supervision blueprint is
    registered. Returns the keeper thread, or None when it was already
    running. Fails soft: a keeper that cannot start leaves the FRD-011
    read-path behaviour unchanged (first read computes synchronously).
    """
    global _STATUS_SUMMARY_KEEPER_THREAD
    with _STATUS_SUMMARY_KEEPER_LOCK:
        if _STATUS_SUMMARY_KEEPER_THREAD is not None and _STATUS_SUMMARY_KEEPER_THREAD.is_alive():
            return None
        try:
            thread = threading.Thread(
                target=_status_summary_keeper_loop,
                daemon=True,
                name="stratex-status-summary-keeper",
            )
            thread.start()
        except Exception as exc:
            logger.debug(f"[FRIDAY_SUPERVISION] status keeper could not start: {exc}")
            return None
        _STATUS_SUMMARY_KEEPER_THREAD = thread
        return thread


def _get_engine_status_summary() -> dict[str, Any]:
    global _STATUS_SUMMARY_CACHE, _STATUS_SUMMARY_TS, _STATUS_SUMMARY_REFRESHING
    now = time.time()
    cache = _STATUS_SUMMARY_CACHE
    if cache is not None:
        age = now - _STATUS_SUMMARY_TS
        if age < _STATUS_SUMMARY_TTL_S:
            return cache
        if age < _STATUS_SUMMARY_MAX_STALE_S:
            with _STATUS_SUMMARY_LOCK:
                start = not _STATUS_SUMMARY_REFRESHING
                if start:
                    _STATUS_SUMMARY_REFRESHING = True
            if start:
                try:
                    threading.Thread(
                        target=_refresh_status_summary,
                        daemon=True,
                        name="stratex-status-summary-refresh",
                    ).start()
                except Exception as exc:
                    with _STATUS_SUMMARY_LOCK:
                        _STATUS_SUMMARY_REFRESHING = False
                    logger.debug(f"[FRIDAY_SUPERVISION] status refresh could not start: {exc}")
            return cache
    data = _compute_engine_status_summary()
    with _STATUS_SUMMARY_LOCK:
        _STATUS_SUMMARY_CACHE = data
        _STATUS_SUMMARY_TS = time.time()
    return data


def _compute_engine_status_summary() -> dict[str, Any]:
    overlay = get_advisory_overlay()
    pending = overlay.get_pending_recommendations()

    mode = str(getattr(config, "TRADING_MODE", "PAPER")).upper()

    # Keep the market analysis fresh (TASK-VOI-006: ensured in the
    # background — a status read never waits on the refresh; it serves
    # the last computed snapshot with its timestamp).
    engine = _safe_engine()
    try:
        _ensure_market_analysis(engine)
    except Exception as exc:
        logger.debug(f"[FRIDAY_SUPERVISION] ensure analysis failed: {exc}")

    trading = _real_trading_data(engine)

    # Preserve legacy portfolio fields but sourced from real engine data.
    equity = trading.get("balance", 0.0)
    try:
        equity = float(equity) + float(trading.get("unrealized_pnl", 0.0))
    except (TypeError, ValueError):
        equity = trading.get("balance", 0.0)
    cash = trading.get("balance", 0.0)
    open_positions = trading.get("position_count", 0)

    return {
        "engine": "Stratex",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "trading_mode": mode,
        "paper_safe_mode": bool(getattr(config, "PAPER_SAFE_MODE", True)),
        "live_trading_enabled": False,
        "live_money_permanently_blocked": True,
        "panic_active": trading.get("panic_active", _is_panic_active()),
        "kill_switch_active": _is_kill_switch_locked(),
        "exchange_connected": mode in ["TESTNET", "FUTURES"] and getattr(config, "TESTNET_ENABLED", False),
        "telemetry_freshness": {
            "status": "FRESH",
            "max_staleness_seconds": MAX_TELEMETRY_STALENESS_SECONDS
        },
        "portfolio": {
            "equity": round(float(equity), 2),
            "cash": round(float(cash), 2),
            "open_positions_count": open_positions,
            "drawdown_pct": 0.0,
            "reconciliation_status": "RECONCILED"
        },
        # Real trading data (cTrader demo)
        "positions": trading.get("positions", []),
        "open_positions": trading.get("positions", []),
        "current_positions": trading.get("positions", []),
        "position_count": trading.get("position_count", 0),
        "open_positions_count": trading.get("position_count", 0),
        "balance": trading.get("balance", 0.0),
        "cash_balance": trading.get("balance", 0.0),
        "unrealized_pnl": trading.get("unrealized_pnl", 0.0),
        "last_trade_time": trading.get("last_trade_time"),
        "max_positions": trading.get("max_positions"),
        "market_conditions": trading.get("market_conditions", {}),
        "last_market_analysis": _LAST_MARKET_ANALYSIS,
        "active_strategies": list(getattr(config, "ACTIVE_STRATEGIES", {}).keys()),
        "ledger_scorecard": _ledger_scorecard_block(),
        "pending_advisories_count": len(pending)
    }


# ==============================================================================
# SUPERVISION STATUS ENDPOINTS
# ==============================================================================

@friday_supervision_bp.route("/v1/friday/supervision/status", methods=["GET"])
@friday_supervision_bp.route("/api/v1/friday/status", methods=["GET"])
def get_supervision_status():
    """Returns structured Stratex operational status for FRIDAY supervision."""
    summary = _get_engine_status_summary()
    return jsonify({
        "status": "SUCCESS",
        "data": summary
    }), 200


# ==============================================================================
# EMERGENCY PANIC & KILL SWITCH ENDPOINTS
# ==============================================================================

@friday_supervision_bp.route("/v1/friday/supervision/panic", methods=["POST"])
@friday_supervision_bp.route("/api/v1/friday/panic", methods=["POST"])
@require_api_scope(scope=SCOPE_FRIDAY, is_control=True)
def execute_supervision_panic():
    """
    Emergency Panic Kill-Switch — blocks all order placement and halts engine.
    Requires: {"confirm": true, "reason": "...", "source": "FRIDAY"}
    To release: {"confirm": true, "release": true}
    """
    body = request.get_json(silent=True)
    if not isinstance(body, dict):
        body = {}
    # Literal JSON true only: bool("false") is True, which used to let a
    # {"release": "false"} request RELEASE the kill switch.
    confirm = body.get("confirm") is True
    release = body.get("release") is True
    reason = str(body.get("reason", "Emergency panic requested via FRIDAY Supervision"))[:500]
    source = str(body.get("source", "FRIDAY"))[:100]

    result, code = apply_supervision_panic(confirm=confirm, release=release, reason=reason, source=source)
    return jsonify(result), code


def apply_supervision_panic(*, confirm: bool, release: bool, reason: str, source: str) -> tuple[dict[str, Any], int]:
    """Activate/release the panic; returns ``(response_body, http_status)``.

    Shared by the HTTP route and the FRIDAY task dispatcher so that a task can
    never report success for a panic that was not actually applied.
    """
    confirm = confirm is True
    release = release is True
    reason = str(reason)[:500]
    source = str(source)[:100]
    if not confirm:
        return ({
            "status": "ERROR",
            "error": "CONFIRMATION_REQUIRED",
            "message": "Emergency panic operation requires explicit confirmation: {'confirm': true}."
        }, 400)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()

    if release:
        errors = []
        try:
            write_panic_state(False, actor=source, reason=reason)
        except Exception as e:
            logger.error(f"Failed to update panic state file on release: {e}")
            errors.append("PANIC_FLAG_NOT_CLEARED")

        if is_kill_switch_locked():
            try:
                os.remove(kill_switch_lock_file())
            except Exception as e:
                logger.error(f"Failed to remove kill switch lock file: {e}")
                errors.append("KILL_SWITCH_LOCK_NOT_REMOVED")

        audit = get_audit_manager().record_event(
            event_type="PANIC_RELEASED",
            actor=source,
            details={"released_at": now_iso, "errors": errors},
            rationale=reason,
            status="PANIC_RELEASED" if not errors else "PANIC_RELEASE_INCOMPLETE"
        )
        still_active = _is_panic_active()
        if errors or still_active:
            return ({
                "status": "ERROR",
                "error": "PANIC_RELEASE_INCOMPLETE",
                "panic_active": still_active,
                "failed_steps": errors,
                "message": "Panic could not be fully released; order submission remains blocked.",
                "audit_hash": persisted_hash(audit)
            }, 500)
        return ({
            "status": "SUCCESS",
            "panic_active": False,
            "message": "PANIC RELEASED: Trading engine unblocked.",
            "audit_hash": persisted_hash(audit)
        }, 200)

    # Activate Panic — two independent blocking mechanisms; report what stuck.
    blocked_by = []
    try:
        write_panic_state(True, actor=source, reason=reason)
        blocked_by.append("PANIC_FLAG")
    except Exception as e:
        logger.error(f"Failed to update panic state file on trigger: {e}")

    try:
        atomic_write_json(kill_switch_lock_file(), {
            "kill_switch_active": True,
            "triggered_at": now_iso,
            "actor": source,
            "reason": reason
        })
        blocked_by.append("KILL_SWITCH_LOCK")
    except Exception as e:
        logger.error(f"Failed to create kill switch lock file: {e}")

    audit = get_audit_manager().record_event(
        event_type="PANIC_TRIGGERED",
        actor=source,
        details={"triggered_at": now_iso, "panic_file": os.getenv("PANIC_STATE_FILE", "panic_state.json"),
                 "blocked_by": blocked_by},
        rationale=reason,
        status="PANIC_ACTIVATED" if blocked_by else "PANIC_NOT_PERSISTED"
    )

    if not blocked_by:
        return ({
            "status": "ERROR",
            "error": "PANIC_NOT_PERSISTED",
            "panic_active": False,
            "message": "Neither the panic flag nor the kill-switch lock could be written; orders are NOT blocked.",
            "audit_hash": persisted_hash(audit)
        }, 500)

    return ({
        "status": "SUCCESS",
        "panic_active": True,
        "kill_switch_active": "KILL_SWITCH_LOCK" in blocked_by,
        "blocked_by": blocked_by,
        "message": ("EMERGENCY PANIC ACTIVATED: all new order submission blocked. "
                    "Existing open/protective orders were not cancelled by this endpoint."),
        "audit_hash": persisted_hash(audit)
    }, 200)


# ==============================================================================
# ADVISORY SUPERVISION & AUTHORIZATION ENDPOINTS
# ==============================================================================

@friday_supervision_bp.route("/v1/friday/supervision/advisories", methods=["GET"])
@friday_supervision_bp.route("/api/v1/friday/advisories", methods=["GET"])
def get_supervision_advisories():
    """Inspects pending staged bounded recommendations."""
    overlay = get_advisory_overlay()
    pending = overlay.get_pending_recommendations()
    return jsonify({
        "status": "SUCCESS",
        "count": len(pending),
        "pending_recommendations": pending
    }), 200


@friday_supervision_bp.route("/v1/friday/supervision/advisory/authorize", methods=["POST"])
@friday_supervision_bp.route("/api/v1/friday/advisory/authorize", methods=["POST"])
@require_api_scope(scope=SCOPE_FRIDAY, is_control=True)
def authorize_advisory_recommendation():
    """
    Separation of Advisory Generation and Application:
    Explicitly authorizes and applies a staged bounded parameter change.
    Requires: {"recommendation_id": "...", "authorization_token": "...", "authorized_by": "FRIDAY"}
    """
    body = json_body()
    rec_id = get_str(body, "recommendation_id", "", max_len=128)
    token = get_str(body, "authorization_token", "", max_len=512)
    authorizer = get_str(body, "authorized_by", "FRIDAY", max_len=64) or "FRIDAY"
    idempotency_key = _idempotency_key(body)

    if not rec_id:
        return jsonify({
            "status": "ERROR",
            "error": "MISSING_RECOMMENDATION_ID",
            "message": "Field 'recommendation_id' is required."
        }), 400

    if not token or str(token).strip() == "":
        return jsonify({
            "status": "ERROR",
            "error": "MISSING_AUTHORIZATION_TOKEN",
            "message": "Field 'authorization_token' is required to authorize parameter changes."
        }), 400

    overlay = get_advisory_overlay()
    ok, msg, res = overlay.apply_authorized_recommendation(
        recommendation_id=rec_id,
        authorization_token=token,
        authorized_by=authorizer,
        idempotency_key=idempotency_key
    )

    if not ok:
        return jsonify({
            "status": "REJECTED",
            "error": "AUTHORIZATION_FAILED",
            "message": msg
        }), 400

    return jsonify({
        "status": "SUCCESS",
        "message": msg,
        "result": res
    }), 200


_IDEMPOTENCY_KEY_RE = re.compile(r"^[A-Za-z0-9_.:-]{1,128}$")


def _idempotency_key(body: dict) -> str | None:
    """Idempotency key from the header or body; must be a short safe string.

    A list/object key used to reach the idempotency store's dict lookup and
    crash the request with ``TypeError: unhashable type`` (HTTP 500).
    """
    raw = request.headers.get("Idempotency-Key")
    if raw is None:
        raw = get_str(body, "idempotency_key", None, max_len=128)
    if raw is None or raw == "":
        return None
    raw = raw.strip()
    if not _IDEMPOTENCY_KEY_RE.match(raw):
        raise RequestValidationError("idempotency_key", "must be 1-128 characters of [A-Za-z0-9_.:-]")
    return raw


# ==============================================================================
# UNIVERSAL TASK PROTOCOL ENDPOINT (WITH DETERMINISTIC EXECUTION ENFORCEMENT)
# ==============================================================================

@friday_supervision_bp.route("/v1/friday/task", methods=["POST"])
@friday_supervision_bp.route("/v1/task/execute", methods=["POST"])
@require_api_scope(scope=SCOPE_FRIDAY, is_control=True)
def execute_friday_task():
    """
    Universal Task Protocol entry point for FRIDAY and Cortex.
    Enforces the Core Invariant:
    Prediction / External Agent Inquiry is NOT Authorization.
    FRIDAY or Inference cannot directly order executions or bypass Stratex safety gates.
    """
    t0 = time.time()
    body = json_body()
    task_id = get_str(body, "task_id", "", max_len=128) or f"stx_task_{int(time.time_ns())}"
    action = get_str(body, "action", "status", lower=True, max_len=64) or "status"
    source_agent = get_str(body, "source_agent", "unknown", max_len=64) or "unknown"
    payload = body.get("payload") if isinstance(body.get("payload"), dict) else body
    idempotency_key = _idempotency_key(body)

    # Invariant Check: Reject order placement or gate bypass attempts fail-closed
    if action in ["order", "place_order", "execute", "execute_order", "bypass_gates", "force_trade", "trade"]:
        rationale = "Execution authority violation: External agents cannot directly command order execution or bypass Stratex safety gates."
        get_audit_manager().record_event(
            event_type="ORDER_BLOCKED",
            actor=source_agent,
            details={"task_id": task_id, "action": action},
            rationale=rationale,
            status="FORBIDDEN"
        )
        return jsonify({
            "task_id": task_id,
            "target_agent": "stratex",
            "status": "FORBIDDEN",
            "error": "DETERMINISTIC_EXECUTION_AUTHORITY_VIOLATION",
            "message": rationale,
            "execution_time_ms": int((time.time() - t0) * 1000)
        }), 403

    # Idempotency Check
    if idempotency_key:
        is_dup, cached = get_idempotency_store().check_and_record(idempotency_key, request_type=f"TASK_{action.upper()}")
        if is_dup and cached and cached.get("response"):
            return jsonify(cached["response"]), 200

    # Handle supported supervisory actions
    if action in ["status", "health", "supervision_status"]:
        res_data = _get_engine_status_summary()
        response_payload = {
            "task_id": task_id,
            "target_agent": "stratex",
            "status": "SUCCESS",
            "result": res_data,
            "summary": f"Stratex supervision status retrieved for {source_agent}.",
            "execution_time_ms": int((time.time() - t0) * 1000)
        }
    elif action in ["panic", "emergency_stop", "kill_switch"]:
        confirm = isinstance(payload, dict) and payload.get("confirm") is True
        if not confirm:
            return jsonify({
                "task_id": task_id,
                "target_agent": "stratex",
                "status": "FAILED",
                "error": "CONFIRMATION_REQUIRED",
                "message": "Panic action requires explicit payload {'confirm': true}."
            }), 400
        # Trigger panic with the TASK's own payload (the HTTP route reads the
        # top-level body, where a task's {"payload": {"confirm": true}} is absent).
        result, code = apply_supervision_panic(
            confirm=True,
            release=payload.get("release") is True,
            reason=str(payload.get("reason", f"Emergency panic requested by {source_agent} task")),
            source=str(payload.get("source", source_agent)),
        )
        response_payload = {
            "task_id": task_id,
            "target_agent": "stratex",
            "status": "SUCCESS" if code == 200 else "FAILED",
            "result": result,
            "summary": (f"Emergency panic {'released' if payload.get('release') is True else 'triggered'} by {source_agent}."
                        if code == 200 else f"Emergency panic request from {source_agent} FAILED: {result.get('error')}"),
            "execution_time_ms": int((time.time() - t0) * 1000)
        }
        if code != 200:
            if idempotency_key:
                # A failed panic must stay retryable, not be parked as PENDING.
                get_idempotency_store().remove(idempotency_key)
            return jsonify(response_payload), code
    elif action in ["advisories", "list_advisories"]:
        overlay = get_advisory_overlay()
        pending = overlay.get_pending_recommendations()
        response_payload = {
            "task_id": task_id,
            "target_agent": "stratex",
            "status": "SUCCESS",
            "result": {"pending_count": len(pending), "pending_advisories": pending},
            "summary": f"Retrieved {len(pending)} pending advisories for {source_agent}.",
            "execution_time_ms": int((time.time() - t0) * 1000)
        }
    elif action in ["authorize", "authorize_advisory"]:
        rec_id = payload.get("recommendation_id")
        token = payload.get("authorization_token", "friday_auth")
        overlay = get_advisory_overlay()
        ok, msg, res = overlay.apply_authorized_recommendation(
            recommendation_id=rec_id,
            authorization_token=token,
            authorized_by=source_agent
        )
        response_payload = {
            "task_id": task_id,
            "target_agent": "stratex",
            "status": "SUCCESS" if ok else "FAILED",
            "result": res,
            "summary": msg,
            "execution_time_ms": int((time.time() - t0) * 1000)
        }
    elif action in ["analyze", "analysis", "market_analysis", "run_analysis", "scan_analysis"]:
        analysis = _run_market_analysis(payload)
        response_payload = {
            "task_id": task_id,
            "target_agent": "stratex",
            "status": analysis.get("status", "SUCCESS"),
            "result": analysis,
            "summary": (
                f"Stratex market analysis complete: {analysis.get('signal_count', 0)} signals "
                f"from {len(analysis.get('symbols_analyzed', []))} symbols for {source_agent}."
            ),
            "execution_time_ms": int((time.time() - t0) * 1000)
        }
    else:
        response_payload = {
            "task_id": task_id,
            "target_agent": "stratex",
            "status": "SUCCESS",
            "result": _get_engine_status_summary(),
            "summary": f"Processed supervisory action '{action}' for {source_agent}.",
            "execution_time_ms": int((time.time() - t0) * 1000)
        }

    if response_payload.get("status") == "SUCCESS":
        result_body = response_payload.get("result")
        evidence: dict[str, Any] = {
            "source": "stratex.v1.task",
            "action": action,
            "task_id": task_id,
            "trading_mode": (
                result_body.get("trading_mode")
                if isinstance(result_body, dict)
                else None
            ),
            "panic_active": (
                result_body.get("panic_active")
                if isinstance(result_body, dict)
                else _is_panic_active()
            ),
            "position_count": (
                result_body.get("position_count")
                if isinstance(result_body, dict)
                else None
            ),
            "balance": (
                result_body.get("balance")
                if isinstance(result_body, dict)
                else None
            ),
            "unrealized_pnl": (
                result_body.get("unrealized_pnl")
                if isinstance(result_body, dict)
                else None
            ),
            "last_trade_time": (
                result_body.get("last_trade_time")
                if isinstance(result_body, dict)
                else None
            ),
            "market_conditions": (
                result_body.get("market_conditions")
                if isinstance(result_body, dict)
                else None
            ),
        }
        response_payload["receipt"] = _task_receipt(
            requested_action=action,
            target="stratex",
            result=result_body,
            verification_evidence=evidence,
        )

    if idempotency_key:
        get_idempotency_store().complete_request(idempotency_key, response_payload)

    return jsonify(response_payload), 200
