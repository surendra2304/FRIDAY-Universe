"""
measurement/fill_ledger.py — append-only measurement store for Stratex.

TASK-STR-PHASE2-001. Phase 1 of the profitability programme found that
Stratex's demo results could not be stated honestly: closes went
unrecorded (the shared ledger's last row was weeks old while trading
continued), no equity curve existed, daemon bookings were partly
fee-blind ticker estimates, and nothing attributed a fill to the strategy
that produced it.

This module is the single store both engines write to:

  state/fill_ledger.jsonl        one row per CLOSED trade, strategy-tagged
  state/equity_snapshots.jsonl   append-only equity snapshots per engine
  state/position_tags.jsonl      ownership tag for every position opened
  state/measurement_alerts.json  reconciliation / venue-health alert state

Design rules:
  * Append-only. Rows are never edited or deleted; corrections are new
    rows. A close that cannot be recorded raises a reconciliation alert
    instead of vanishing.
  * Every writer is best-effort for the TRADING path (a bookkeeping
    failure must never crash an engine) but LOUD: failures are logged at
    ERROR and latched into measurement_alerts.json.
  * Fees carry a source: "broker" (from exchange fill records) or
    "estimate" (ticker/spread model). Estimates are never presented as
    broker truth — the scorecard reports the mix.
  * Paths follow the fleet's existing convention: STRATEX_STATE_DIR env
    override, else Stratex/state/ (same rule as MultiVenueEngine).
"""
from __future__ import annotations

import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from atomic_io import append_jsonl, atomic_write_json
except Exception:  # pragma: no cover - fallback when Stratex/ is not on sys.path
    append_jsonl = None  # type: ignore
    atomic_write_json = None  # type: ignore

try:
    from logger import get_logger

    logger = get_logger("measurement_fill_ledger")
except Exception:  # pragma: no cover
    import logging

    logger = logging.getLogger("measurement_fill_ledger")

_LOCK = threading.Lock()

FILL_LEDGER_FILE = "fill_ledger.jsonl"
EQUITY_SNAPSHOT_FILE = "equity_snapshots.jsonl"
POSITION_TAGS_FILE = "position_tags.jsonl"
ALERTS_FILE = "measurement_alerts.json"

# Documented faucet rule for Binance demo/testnet equity: the only figure
# treated as trading equity is the USDT futures margin balance (wallet +
# unrealized PnL on USDT-margined positions). Faucet grants of other
# assets (the BTC and USDC airdrops visible in the demo wallet) are NOT
# trading equity and never enter a snapshot's equity figure.
FAUCET_EXCLUSION_RULE = (
    "binance demo/testnet equity = USDT futures margin balance only; "
    "non-USDT faucet assets (e.g. BTC/USDC grants) excluded"
)

_FILL_REQUIRED = (
    "strategy", "engine", "venue", "symbol", "side",
    "entry_price", "exit_price", "qty",
    "gross_pnl", "fees", "net_pnl", "exit_reason",
)


def state_dir() -> Path:
    """Stratex state directory (STRATEX_STATE_DIR override, else Stratex/state)."""
    override = os.getenv("STRATEX_STATE_DIR")
    if override:
        return Path(override)
    return Path(__file__).resolve().parent.parent / "state"


def _path(filename: str, env_var: str) -> Path:
    override = os.getenv(env_var)
    if override:
        return Path(override)
    return state_dir() / filename


def fill_ledger_path() -> Path:
    return _path(FILL_LEDGER_FILE, "STRATEX_FILL_LEDGER_FILE")


def equity_snapshot_path() -> Path:
    return _path(EQUITY_SNAPSHOT_FILE, "STRATEX_EQUITY_SNAPSHOT_FILE")


def position_tags_path() -> Path:
    return _path(POSITION_TAGS_FILE, "STRATEX_POSITION_TAGS_FILE")


def alerts_path() -> Path:
    return _path(ALERTS_FILE, "STRATEX_MEASUREMENT_ALERTS_FILE")


def _iso(ts: float) -> str:
    import datetime

    return datetime.datetime.fromtimestamp(ts, datetime.timezone.utc).isoformat()


def _finite(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except (TypeError, ValueError):
        return default
    return out if math.isfinite(out) else default


def _append(path: Path, record: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    line = json.dumps(record, default=str)
    with _LOCK:
        if append_jsonl is not None:
            append_jsonl(str(path), record, fsync=True)
        else:  # pragma: no cover - fallback path
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
                fh.flush()
                os.fsync(fh.fileno())


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    except FileNotFoundError:
        return []
    return rows


# ---------------------------------------------------------------------------
# Fill ledger
# ---------------------------------------------------------------------------
def append_fill(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Validate and append one closed-trade record. Returns the stored row.

    Never raises: on failure the miss is logged at ERROR and latched as a
    reconciliation alert (kind=unrecorded_close) — a close that cannot be
    recorded must be visible, never silent.
    """
    row = dict(record)
    missing = [k for k in _FILL_REQUIRED if row.get(k) in (None, "")]
    if missing:
        logger.error(f"[MEASUREMENT] Fill rejected, missing fields {missing}: {row}")
        raise_alert("unrecorded_close", f"fill rejected, missing {missing}: {row.get('symbol')}")
        return None
    now = time.time()
    row["record_type"] = "FILL"
    row["strategy"] = str(row["strategy"])
    row["engine"] = str(row["engine"])
    row["venue"] = str(row["venue"])
    row["symbol"] = str(row["symbol"])
    row["side"] = str(row["side"]).upper()
    row["qty"] = abs(_finite(row["qty"]))
    row["entry_price"] = _finite(row["entry_price"])
    row["exit_price"] = _finite(row["exit_price"])
    row["gross_pnl"] = _finite(row["gross_pnl"])
    row["fees"] = abs(_finite(row["fees"]))
    row["net_pnl"] = _finite(row["net_pnl"])
    row["fees_source"] = str(row.get("fees_source") or "broker")
    row["exit_reason"] = str(row["exit_reason"])
    row["entry_time"] = _finite(row.get("entry_time"), 0.0)
    row["exit_time"] = _finite(row.get("exit_time"), now)
    row["order_id"] = str(row.get("order_id") or "")
    row["entry_order_id"] = str(row.get("entry_order_id") or "")
    row["signal_id"] = str(row.get("signal_id") or "")
    row["recorded_at"] = _iso(now)
    try:
        _append(fill_ledger_path(), row)
    except Exception as e:
        logger.error(f"[MEASUREMENT] Fill append FAILED for {row.get('symbol')}: {e}")
        raise_alert("unrecorded_close", f"fill append failed for {row.get('symbol')}: {e}")
        return None
    logger.info(
        f"[MEASUREMENT] Fill recorded: {row['engine']} {row['strategy']} "
        f"{row['symbol']} net=${row['net_pnl']:+.2f} fees=${row['fees']:.2f} "
        f"({row['fees_source']}) reason={row['exit_reason']}"
    )
    return row


def read_fills() -> List[Dict[str, Any]]:
    return read_jsonl(fill_ledger_path())


def fill_exists(order_id: str = "", entry_order_id: str = "", symbol: str = "") -> bool:
    """Idempotence check (legacy import, recovery mirrors)."""
    for row in read_fills():
        if order_id and str(row.get("order_id") or "") == order_id:
            return True
        if entry_order_id and str(row.get("entry_order_id") or "") == entry_order_id:
            return True
    return False


def fill_recorded_since(engine: str, symbol: str, since_ts: float) -> bool:
    """True if a fill for (engine, symbol) was recorded at/after since_ts."""
    for row in read_fills():
        if row.get("engine") != engine or row.get("symbol") != symbol:
            continue
        if _finite(row.get("exit_time"), 0.0) >= since_ts:
            return True
    return False


# ---------------------------------------------------------------------------
# Equity snapshots
# ---------------------------------------------------------------------------
def append_equity_snapshot(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Append one equity snapshot. Never raises (alert on failure)."""
    now = time.time()
    row = {
        "record_type": "EQUITY_SNAPSHOT",
        "ts": _finite(record.get("ts"), now),
        "timestamp": _iso(_finite(record.get("ts"), now)),
        "engine": str(record.get("engine") or "unknown"),
        "trigger": str(record.get("trigger") or "manual"),
        "total_equity": _finite(record.get("total_equity")),
        "venues": record.get("venues") or {},
        "excluded_venues": list(record.get("excluded_venues") or []),
        "faucet_exclusion": record.get("faucet_exclusion") or "",
    }
    if record.get("realized_pnl") is not None:
        row["realized_pnl"] = _finite(record["realized_pnl"])
    if record.get("daily_realized_pnl") is not None:
        row["daily_realized_pnl"] = _finite(record["daily_realized_pnl"])
    try:
        _append(equity_snapshot_path(), row)
    except Exception as e:
        logger.error(f"[MEASUREMENT] Equity snapshot append FAILED: {e}")
        raise_alert("snapshot_failed", f"equity snapshot append failed: {e}")
        return None
    return row


def append_reset_boundary(
    *,
    actor: str,
    venues_pre: Dict[str, Any],
    venues_post: Dict[str, Any],
    note: str = "",
) -> Optional[Dict[str, Any]]:
    """Append a RESET_BOUNDARY marker to the equity snapshot stream.

    An account reset (owner action on a demo/testnet account) changes
    balances without any trading. Without an explicit boundary, the jump
    between the last pre-reset snapshot and the first post-reset snapshot
    is indistinguishable from profit. The boundary row keeps pre-reset
    records as history and marks where forward measurement re-baselines.
    Never raises (alert on failure).
    """
    now = time.time()
    row = {
        "record_type": "RESET_BOUNDARY",
        "ts": now,
        "timestamp": _iso(now),
        "actor": str(actor or "unknown"),
        "venues_pre": venues_pre or {},
        "venues_post": venues_post or {},
        "note": str(note or ""),
    }
    try:
        _append(equity_snapshot_path(), row)
        logger.warning(
            "[MEASUREMENT] RESET BOUNDARY recorded by %s — forward "
            "measurement re-baselines at the post-reset equity; pre-boundary "
            "records are history only. %s",
            row["actor"],
            row["note"],
        )
    except Exception as e:
        logger.error(f"[MEASUREMENT] Reset boundary append FAILED: {e}")
        raise_alert("snapshot_failed", f"reset boundary append failed: {e}")
        return None
    return row


def read_boundaries() -> List[Dict[str, Any]]:
    """All RESET_BOUNDARY markers from the snapshot stream, oldest first."""
    return [
        row
        for row in read_jsonl(equity_snapshot_path())
        if row.get("record_type") == "RESET_BOUNDARY"
    ]


def read_equity_snapshots() -> List[Dict[str, Any]]:
    return read_jsonl(equity_snapshot_path())


# ---------------------------------------------------------------------------
# Position ownership tags
# ---------------------------------------------------------------------------
def append_position_tag(record: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Record who opened a position: engine + strategy + venue + order id.

    Both engines trade Binance demo environments; the tag log is what lets
    a position found at the exchange be reconciled to the engine and
    strategy that own it. Never raises.
    """
    now = time.time()
    row = {
        "record_type": "POSITION_TAG",
        "ts": _finite(record.get("ts"), now),
        "timestamp": _iso(_finite(record.get("ts"), now)),
        "engine": str(record.get("engine") or "unknown"),
        "venue": str(record.get("venue") or ""),
        "venue_env": str(record.get("venue_env") or ""),
        "symbol": str(record.get("symbol") or ""),
        "strategy": str(record.get("strategy") or "UNATTRIBUTED"),
        "timeframe": str(record.get("timeframe") or ""),
        "side": str(record.get("side") or "").upper(),
        "qty": abs(_finite(record.get("qty"))),
        "entry_price": _finite(record.get("entry_price")),
        "order_id": str(record.get("order_id") or ""),
        "client_order_id": str(record.get("client_order_id") or ""),
        "note": str(record.get("note") or ""),
    }
    try:
        _append(position_tags_path(), row)
    except Exception as e:
        logger.error(f"[MEASUREMENT] Position tag append FAILED: {e}")
        return None
    return row


def read_position_tags() -> List[Dict[str, Any]]:
    return read_jsonl(position_tags_path())


# ---------------------------------------------------------------------------
# Alerts (reconciliation / venue health)
# ---------------------------------------------------------------------------
def _load_alerts() -> Dict[str, Any]:
    try:
        with open(alerts_path(), "r", encoding="utf-8") as fh:
            data = json.load(fh) or {}
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_alerts(data: Dict[str, Any]) -> None:
    path = alerts_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    if atomic_write_json is not None:
        atomic_write_json(str(path), data, indent=2)
    else:  # pragma: no cover - fallback path
        tmp = path.with_suffix(".json.tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        os.replace(tmp, path)


def raise_alert(kind: str, detail: str) -> None:
    """Latch an alert kind active. Logged at ERROR on first raise."""
    try:
        with _LOCK:
            data = _load_alerts()
            alerts = data.setdefault("alerts", {})
            current = alerts.get(kind) or {}
            first = not current.get("active")
            alerts[kind] = {
                "active": True,
                "since": current.get("since") or _iso(time.time()),
                "updated_at": _iso(time.time()),
                "detail": str(detail)[:500],
                "count": int(current.get("count", 0) or 0) + 1,
            }
            _save_alerts(data)
        if first:
            logger.error(f"[MEASUREMENT] ALERT {kind}: {detail}")
    except Exception as e:  # alerts must never crash an engine
        logger.error(f"[MEASUREMENT] raise_alert({kind}) failed: {e}")


def clear_alert(kind: str) -> None:
    try:
        with _LOCK:
            data = _load_alerts()
            alerts = data.setdefault("alerts", {})
            if kind in alerts and alerts[kind].get("active"):
                alerts[kind]["active"] = False
                alerts[kind]["updated_at"] = _iso(time.time())
                _save_alerts(data)
                logger.info(f"[MEASUREMENT] Alert cleared: {kind}")
    except Exception as e:
        logger.error(f"[MEASUREMENT] clear_alert({kind}) failed: {e}")


def active_alerts() -> Dict[str, Any]:
    data = _load_alerts()
    return {
        kind: info
        for kind, info in (data.get("alerts") or {}).items()
        if info.get("active")
    }
