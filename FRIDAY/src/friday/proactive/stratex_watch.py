"""TASK-PRO-001: proactive Stratex watch — FRIDAY speaks first.

FRIDAY does not wait to be asked about Stratex. A background cycle (wired
into ``api/server.py``'s lifespan beside the other proactive loops) diffs
Stratex's own measurement state and posts a proactive notification through
the REAL notification path — ``observability.notifications.NotificationManager``
(the durable Oracle-backed queue the greeting/chat surfaces pop from) — when:

* a governed strategy **opens** a trade (new row in ``position_tags.jsonl``);
* a governed strategy **closes** a trade (new row in ``fill_ledger.jsonl`` —
  the message carries the fill's net PnL and the running ledger totals);
* a **kill criterion trips** (a strategy name appears in the persisted
  ``strategy_denylist.json`` — the phase-3 forward guard's own auto-pause
  act; the message carries that strategy's ledger statistics);
* the **daily loss breaker trips** (``daemon_heartbeat.json``'s
  ``daily_loss_limit_hit`` flips False -> True);
* Stratex raises a **measurement alert** (new/changed active kind in
  ``measurement_alerts.json`` — e.g. an unrecorded close).

Plus the morning self-check: once per IST day, inside 07:30-12:00, FRIDAY
composes fleet health (FleetStatusTool — the same truth as
/api/agents/status) + Stratex state (daemon heartbeat + fill ledger) and
STORES it as a ``morning_self_check`` notification for the owner.

Anti-spam contract (hard rules, TASK-PRO-001):
- every event carries a stable dedupe key; a re-cycle never posts the
  same event twice, across restarts (watcher state is persisted);
- the first cycle on a fresh watcher state is a silent BASELINE — the
  existing history is recorded as seen, never announced;
- quiet hours 23:00-07:00 IST hold every event except breaker trips;
  held events flush as ONE digest notification at/after 07:00;
- every proactive message is logged with its trigger (notification
  metadata + a bounded alert log inside the watcher state);
- kill switch: ``FRIDAY_PROACTIVE_STRATEX_WATCH`` env flag. The code
  default is OFF (fail-safe); production enables it only after the
  task's live proof (see the TASK-PRO-001 PR / board entry).

Sources are read-only and resolved exactly the way the fleet already
resolves them: Stratex root from ``FRIDAY_STRATEX_STATE_DIR`` or the
sibling ``Stratex/`` checkout (the ``stratex_portfolio`` tool's rule);
measurement state dir from ``STRATEX_STATE_DIR`` or ``<root>/state``;
per-file overrides ``STRATEX_FILL_LEDGER_FILE`` /
``STRATEX_POSITION_TAGS_FILE`` / ``STRATEX_MEASUREMENT_ALERTS_FILE`` /
``STRATEX_STRATEGY_DENYLIST_FILE`` (Stratex's own env names).

Truthfulness: every figure in every message comes from the rows/files
named above; a source that cannot be read contributes an honest
"could not read" outcome (a skipped line in alerts, an explicit line in
the morning summary) — never an invented number. This module never
writes to Stratex state and never places, pauses or modifies a trade;
governance stays with Stratex's daemon and forward guard.

TASK-FRD-021 adds ``read_status_snapshot`` below: the same source
files compose the status figures Stratex's /v1/task/execute summary
serves (cloud portfolio state + fill-ledger scorecard), gated on the
daemon heartbeat's freshness (60 s, Stratex's own telemetry bound),
so FRIDAY's read-only portfolio answers can be served locally when
the live round trip is the slow path. It is a pure reader — the
caller falls back to the live query whenever it returns None.
"""

from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from datetime import datetime, time as dtime
from pathlib import Path
from typing import Any, Callable

from friday.core.owner_time import OWNER_TZ, now_owner_tz, owner_today

logger = logging.getLogger(__name__)

#: Quiet hours (owner-local): hold everything except breaker trips.
QUIET_START = dtime(23, 0)
QUIET_END = dtime(7, 0)

#: Morning self-check window: compose once per day inside it.
SUMMARY_WINDOW_START = dtime(7, 30)
SUMMARY_WINDOW_END = dtime(12, 0)

#: Bounds so watcher state can never grow without limit.
MAX_SEEN_KEYS = 1000
MAX_ALERT_LOG = 200
MAX_HELD = 50

SOURCE_TAG = "TASK-PRO-001"


def watch_enabled() -> bool:
    """Kill switch: FRIDAY_PROACTIVE_STRATEX_WATCH in {1,true,yes,on}."""
    return os.getenv("FRIDAY_PROACTIVE_STRATEX_WATCH", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def in_quiet_hours(now: datetime | None = None) -> bool:
    """23:00-07:00 IST — the owner's sleep window."""
    moment = (now or now_owner_tz()).astimezone(OWNER_TZ)
    return moment.time() >= QUIET_START or moment.time() < QUIET_END


# ---------------------------------------------------------------------------
# source resolution (read-only)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StratexPaths:
    fills: Path
    tags: Path
    alerts: Path
    denylist: Path
    heartbeat: Path
    #: Stratex/state/cloud_portfolio_state.json — the API engine's
    #: persisted balance/positions (TASK-FRD-021 status snapshot source).
    #: Optional so existing constructions keep working; the snapshot
    #: reader derives it from the heartbeat's directory when unset.
    cloud_state: Path | None = None
    #: <Stratex root>/panic_state.json + KILL_SWITCH_ACTIVE.lock — the
    #: halt state (TASK-FRD-021 follow-up). These live at the Stratex
    #: ROOT, not in the state dir: panic_state.py resolves its default
    #: relative filenames against the process working directory and
    #: both Stratex services run with the root as WorkingDirectory.
    #: Optional like cloud_state; the snapshot reader derives them
    #: from the heartbeat's directory when unset.
    panic_state: Path | None = None
    kill_switch_lock: Path | None = None


def _stratex_root() -> Path | None:
    override = (os.getenv("FRIDAY_STRATEX_STATE_DIR") or "").strip()
    if override:
        p = Path(override)
        return p if p.is_dir() else None
    try:
        # this file: FRIDAY/src/friday/proactive/stratex_watch.py
        # parents[4] is the repo root; Stratex/ is FRIDAY's sibling there.
        candidate = Path(__file__).resolve().parents[4] / "Stratex"
        return candidate if candidate.is_dir() else None
    except IndexError:  # pragma: no cover - layout changed
        return None


def resolve_stratex_paths(root: Path | None = None) -> StratexPaths | None:
    """Locate Stratex's measurement state files, or None if no checkout."""
    root = root or _stratex_root()
    if root is None:
        return None
    state_override = (os.getenv("STRATEX_STATE_DIR") or "").strip()
    state_dir = Path(state_override) if state_override else root / "state"

    def pick(env_var: str, filename: str) -> Path:
        override = (os.getenv(env_var) or "").strip()
        return Path(override) if override else state_dir / filename

    def pick_root(env_var: str, filename: str) -> Path:
        override = (os.getenv(env_var) or "").strip()
        return Path(override) if override else root / filename

    return StratexPaths(
        fills=pick("STRATEX_FILL_LEDGER_FILE", "fill_ledger.jsonl"),
        tags=pick("STRATEX_POSITION_TAGS_FILE", "position_tags.jsonl"),
        alerts=pick("STRATEX_MEASUREMENT_ALERTS_FILE", "measurement_alerts.json"),
        denylist=pick("STRATEX_STRATEGY_DENYLIST_FILE", "strategy_denylist.json"),
        heartbeat=state_dir / "daemon_heartbeat.json",
        cloud_state=state_dir / "cloud_portfolio_state.json",
        panic_state=pick_root("STRATEX_PANIC_STATE_FILE", "panic_state.json"),
        kill_switch_lock=pick_root(
            "STRATEX_KILL_SWITCH_LOCK_FILE", "KILL_SWITCH_ACTIVE.lock"
        ),
    )


def _read_jsonl(path: Path) -> list[dict[str, Any]] | None:
    """Rows of a JSONL file; None when unreadable, [] when absent/empty."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return []
    except OSError as exc:
        logger.warning(f"proactive watch: cannot read {path}: {exc}")
        return None
    rows: list[dict[str, Any]] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError as exc:
        logger.warning(f"proactive watch: cannot read {path}: {exc}")
        return None
    try:
        return json.loads(text)
    except ValueError:
        logger.warning(f"proactive watch: corrupt JSON in {path}")
        return None


# ---------------------------------------------------------------------------
# formatting + statistics (presentation only — governance stays in Stratex)
# ---------------------------------------------------------------------------


def _num(value: Any) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "?"
    if f == int(f) and abs(f) >= 100:
        return f"{f:,.0f}"
    return f"{f:,.4f}".rstrip("0").rstrip(".")


def _money(value: Any, signed: bool = False) -> str:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return "$?"
    if signed:
        return f"{'+' if f >= 0 else '-'}${abs(f):,.2f}"
    return f"${f:,.2f}"


def _pf_text(gross_profit: float, gross_loss: float) -> str:
    if gross_loss > 0:
        return f"{gross_profit / gross_loss:.2f}"
    if gross_profit > 0:
        return "no losing trades yet"
    return "0"


def ledger_stats(rows: list[dict[str, Any]], strategy: str | None = None) -> dict[str, Any]:
    """Pooled (or per-strategy) closed-trade statistics from fill rows.

    Same arithmetic the forward guard reports (net, expectancy, profit
    factor) — used ONLY to word notifications, never to govern.
    """
    fills = [
        r
        for r in rows
        if r.get("net_pnl") is not None
        and (strategy is None or str(r.get("strategy")) == strategy)
    ]
    pnls: list[float] = []
    for r in fills:
        try:
            pnls.append(float(r["net_pnl"]))
        except (TypeError, ValueError):
            continue
    net = sum(pnls)
    gross_profit = sum(p for p in pnls if p > 0)
    gross_loss = -sum(p for p in pnls if p < 0)
    return {
        "trades": len(pnls),
        "net": net,
        "expectancy": (net / len(pnls)) if pnls else 0.0,
        "profit_factor_text": _pf_text(gross_profit, gross_loss),
        "wins": sum(1 for p in pnls if p > 0),
    }


def _tag_key(row: dict[str, Any]) -> str:
    oid = str(row.get("order_id") or row.get("client_order_id") or "")
    if oid:
        return f"tag:{oid}"
    return f"tag:{row.get('strategy')}|{row.get('symbol')}|{row.get('ts')}"


def _fill_key(row: dict[str, Any]) -> str:
    oid = str(row.get("order_id") or "")
    if oid:
        return f"fill:{oid}"
    return (
        f"fill:{row.get('entry_order_id')}|{row.get('symbol')}|"
        f"{row.get('exit_time')}"
    )


# ---------------------------------------------------------------------------
# status snapshot (TASK-FRD-021) — FRIDAY-side serve for read-only
# portfolio/status questions, from the same state files this watch
# family already reads. Stratex's /v1/task/execute status path does
# 0-7 ms of its own work (its FRD-011 keeper snapshot) but the round
# trip episodically walls 1-10 s on in-process contention in
# Stratex's swapped Werkzeug process, so the delegation path serves
# these figures locally and falls back to the live round trip
# whenever the snapshot cannot be served truthfully.
# ---------------------------------------------------------------------------

#: Freshness bound for the status snapshot — mirrors Stratex's own
#: telemetry hard bound (MAX_TELEMETRY_STALENESS_SECONDS = 60 s, the
#: FRD-011 status cache's max-stale): a local view older than this
#: is not served; the caller falls back to the live query.
STATUS_SNAPSHOT_MAX_AGE_S = 60.0


@dataclass(frozen=True)
class StatusSnapshot:
    """FRIDAY's local view of the figures Stratex's status summary serves.

    ``data`` is shaped exactly like the result dict of Stratex's
    /v1/task/execute status summary that FRIDAY's portfolio formatter
    consumes (balance, cash_balance, current_positions,
    unrealized_pnl, ledger_scorecard, panic_active,
    kill_switch_active) — the same formatter renders both sources,
    so a snapshot-served answer carries the same figures as a
    live-served one, including the HALTED line when Stratex is
    halted. ``age_seconds`` is the age of the freshness pulse (the
    daemon heartbeat) at read time.
    """

    data: dict[str, Any]
    age_seconds: float


def _scorecard_block(fills: list[dict[str, Any]]) -> dict[str, Any]:
    """Fill-ledger scorecard with measurement.scorecard's arithmetic.

    Mirrors Stratex/measurement/scorecard.py ``_stats()`` over ALL
    fill rows for the fields the portfolio formatter renders
    (trades, net_pnl, win_rate, profit_factor): trades = row count,
    net = rounded sum of ``net_pnl or 0``, win_rate = wins/trades,
    profit factor = gross profit / gross loss (None when no losing
    trades). ``ledger_stats`` above deliberately differs (it skips
    net_pnl-None rows) — it words notifications; this block must
    match the served scorecard, so it follows the scorecard.
    """

    def stats(rows: list[dict[str, Any]]) -> dict[str, Any]:
        nets: list[float] = []
        for r in rows:
            try:
                nets.append(float(r.get("net_pnl") or 0.0))
            except (TypeError, ValueError):
                nets.append(0.0)
        wins = [n for n in nets if n > 0]
        losses = [n for n in nets if n < 0]
        gross_profit = sum(wins)
        gross_loss = abs(sum(losses))
        return {
            "trades": len(rows),
            "net_pnl": round(sum(nets), 2),
            "win_rate": round(len(wins) / len(rows), 4) if rows else 0.0,
            "profit_factor": (
                round(gross_profit / gross_loss, 3) if gross_loss > 0 else None
            ),
        }

    by_strategy: dict[str, list[dict[str, Any]]] = {}
    for row in fills:
        by_strategy.setdefault(str(row.get("strategy") or "UNATTRIBUTED"), []).append(row)
    return {
        "totals": stats(fills),
        "strategies": {
            name: stats(rows) for name, rows in sorted(by_strategy.items())
        },
    }


def _panic_flag_active(path: Path) -> bool:
    """Stratex's panic flag with panic_state.read_panic_state's semantics.

    A missing file means no panic. A file that exists but cannot be
    read or parsed (or is not a JSON object) FAILS CLOSED — panic
    assumed — exactly as Stratex's own reader treats it: a corrupt
    halt flag must never read as "safe" on either side of the wire.
    Otherwise the flag is set when either schema key is truthy
    (``active`` / ``panic_active``; every writer emits both).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    except UnicodeDecodeError as exc:
        logger.warning(
            f"stratex status snapshot: panic flag {path} is not valid "
            f"UTF-8 ({exc}); failing closed (panic assumed), as Stratex does"
        )
        return True
    except OSError as exc:
        logger.warning(
            f"stratex status snapshot: panic flag {path} unreadable "
            f"({exc}); failing closed (panic assumed), as Stratex does"
        )
        return True
    try:
        data = json.loads(text)
    except ValueError:
        logger.warning(
            f"stratex status snapshot: panic flag {path} is corrupt; "
            "failing closed (panic assumed), as Stratex does"
        )
        return True
    if not isinstance(data, dict):
        logger.warning(
            f"stratex status snapshot: panic flag {path} is not a JSON "
            "object; failing closed (panic assumed), as Stratex does"
        )
        return True
    return bool(data.get("active")) or bool(data.get("panic_active"))


def _halt_flags(paths: StratexPaths) -> tuple[bool, bool]:
    """(panic_active, kill_switch_active) as the live summary composes them.

    Mirrors Stratex/api/friday_supervision._compute_engine_status_summary:
    ``kill_switch_active`` is the lock file's existence
    (panic_state.is_kill_switch_locked — the file's content is
    irrelevant), and ``panic_active`` folds the lock in
    (_real_trading_data computes is_panic_active() OR
    is_kill_switch_locked()). The files live at the Stratex ROOT —
    both Stratex services run with that WorkingDirectory and
    panic_state.py resolves its default relative filenames against
    it — not in the measurement state dir. Paths derive from the
    heartbeat's directory when a hand-built StratexPaths leaves
    them unset (the cloud_state pattern).
    """
    root = paths.heartbeat.parent.parent
    panic_path = paths.panic_state or (root / "panic_state.json")
    lock_path = paths.kill_switch_lock or (root / "KILL_SWITCH_ACTIVE.lock")
    kill_switch_active = lock_path.exists()
    panic_active = _panic_flag_active(panic_path) or kill_switch_active
    return panic_active, kill_switch_active


def read_status_snapshot(
    paths: StratexPaths | None = None,
    *,
    now: datetime | None = None,
) -> StatusSnapshot | None:
    """Compose the status snapshot, or None when it cannot be served.

    Sources — the files Stratex's own served status summary is
    computed from, resolved exactly as this watch family resolves
    them:

    * balance + open positions: ``cloud_portfolio_state.json`` (the
      API engine's ``cloud_balance`` / ``cloud_positions`` load from
      it; the served balance is that file's ``balance``);
    * closed trades + recorded P&L: ``fill_ledger.jsonl``, scored
      with measurement.scorecard's arithmetic;
    * freshness pulse: ``daemon_heartbeat.json``, rewritten by
      Stratex-Daemon every scan cycle. The heartbeat's own figures
      are the daemon's multi-venue view — DIFFERENT numbers from
      the API engine's served figures — so the heartbeat is used
      ONLY as the pulse, never as a figure source.
    * halt state: ``panic_state.json`` + ``KILL_SWITCH_ACTIVE.lock``
      at the Stratex root (Stratex/panic_state.py is the single
      source of truth for the flag; both Stratex services run with
      the root as WorkingDirectory, so its relative defaults land
      there). Composed exactly as the live summary composes them
      (see _halt_flags): kill_switch_active = the lock file
      exists; panic_active = the panic flag (missing file =
      inactive; an unreadable/corrupt flag file FAILS CLOSED, as
      Stratex's reader treats it) or the lock. The portfolio
      formatter renders the HALTED line from these two flags, so
      a snapshot-served answer says HALTED when Stratex is halted.

    Returns None (the caller falls back to the live query) when: no
    Stratex checkout resolves; the heartbeat is missing/corrupt,
    not RUNNING, or older than STATUS_SNAPSHOT_MAX_AGE_S; the cloud
    state is missing/corrupt or its balance is not numeric; the
    cloud positions are not a map; or the fill ledger is unreadable.
    An empty ledger and an empty positions map are valid (0 closed
    trades / no open positions). Never raises.
    """
    try:
        return _read_status_snapshot(paths, now=now)
    except Exception as exc:  # a snapshot failure must never break the answer path
        logger.warning(f"stratex status snapshot: read failed ({exc}); live fallback")
        return None


def _read_status_snapshot(
    paths: StratexPaths | None,
    *,
    now: datetime | None = None,
) -> StatusSnapshot | None:
    paths = paths if paths is not None else resolve_stratex_paths()
    if paths is None:
        logger.info("stratex status snapshot: no Stratex checkout resolved")
        return None

    heartbeat = _read_json(paths.heartbeat)
    if not isinstance(heartbeat, dict):
        logger.info("stratex status snapshot: daemon heartbeat missing/unreadable")
        return None
    if str(heartbeat.get("status") or "") != "RUNNING":
        logger.info(
            "stratex status snapshot: daemon not RUNNING "
            f"(status={heartbeat.get('status')!r})"
        )
        return None
    ts_raw = heartbeat.get("updated_at")
    ts: float | None = None
    if isinstance(ts_raw, (int, float)):
        ts = float(ts_raw)
    else:
        try:
            ts = datetime.fromisoformat(
                str(heartbeat.get("timestamp") or "").replace("Z", "+00:00")
            ).timestamp()
        except ValueError:
            ts = None
    if ts is None:
        logger.info("stratex status snapshot: heartbeat carries no usable timestamp")
        return None
    age = (now or now_owner_tz()).timestamp() - ts
    if age < 0:  # same-host writer/reader; a negative age is clock noise
        age = 0.0
    if age > STATUS_SNAPSHOT_MAX_AGE_S:
        logger.info(
            f"stratex status snapshot: heartbeat stale ({age:.1f}s > "
            f"{STATUS_SNAPSHOT_MAX_AGE_S:.0f}s); live fallback"
        )
        return None

    cloud_path = paths.cloud_state or (
        paths.heartbeat.parent / "cloud_portfolio_state.json"
    )
    cloud = _read_json(cloud_path)
    if not isinstance(cloud, dict):
        logger.info("stratex status snapshot: cloud portfolio state missing/unreadable")
        return None
    try:
        balance = float(cloud.get("balance"))
    except (TypeError, ValueError):
        logger.info("stratex status snapshot: cloud balance is not numeric")
        return None
    raw_positions = cloud.get("positions")
    if raw_positions is None:
        raw_positions = {}
    if not isinstance(raw_positions, dict):
        logger.info("stratex status snapshot: cloud positions are not a map")
        return None
    positions: list[dict[str, Any]] = []
    for symbol, pdata in raw_positions.items():
        if isinstance(pdata, dict):
            pos = dict(pdata)
            pos.setdefault("symbol", symbol)
            positions.append(pos)

    fills = _read_jsonl(paths.fills)
    if fills is None:
        logger.info("stratex status snapshot: fill ledger unreadable")
        return None

    unrealized = 0.0
    for pos in positions:
        try:
            unrealized += float(pos.get("unrealized_pnl") or 0.0)
        except (TypeError, ValueError):
            continue

    panic_active, kill_switch_active = _halt_flags(paths)
    if panic_active or kill_switch_active:
        logger.info(
            "stratex status snapshot: halt state active "
            f"(panic_active={panic_active}, "
            f"kill_switch_active={kill_switch_active})"
        )

    data: dict[str, Any] = {
        "engine": "Stratex",
        "balance": round(balance, 2),
        "cash_balance": round(balance, 2),
        "current_positions": positions,
        "unrealized_pnl": round(unrealized, 2),
        "panic_active": panic_active,
        "kill_switch_active": kill_switch_active,
        "ledger_scorecard": _scorecard_block(fills),
    }
    return StatusSnapshot(data=data, age_seconds=age)


# ---------------------------------------------------------------------------
# the watcher
# ---------------------------------------------------------------------------


def _default_state_path() -> Path:
    override = (os.getenv("FRIDAY_PROACTIVE_WATCH_STATE_FILE") or "").strip()
    if override:
        return Path(override)
    # FRIDAY/state/ beside src/ (parents[3] is the FRIDAY directory).
    return Path(__file__).resolve().parents[3] / "state" / "proactive_stratex_watch.json"


def _empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "baseline_done": False,
        "seen_tag_keys": [],
        "seen_fill_keys": [],
        "tag_count": 0,
        "fill_count": 0,
        "denylist": [],
        "breaker_hit": False,
        "measurement_alerts": {},
        "held": [],
        "alert_log": [],
        "last_summary_date": None,
        "last_morning_summary": None,
    }


class StratexWatcher:
    """Diffs Stratex measurement state and posts proactive notifications.

    One instance per process; ``run_cycle`` is lock-guarded and never
    raises. ``notifications`` is anything with the NotificationManager
    ``post_notification(message, category=..., severity=..., metadata=...)``
    shape — production passes the agent's durable manager.
    """

    def __init__(
        self,
        *,
        paths: StratexPaths | None = None,
        state_path: Path | None = None,
        enabled_fn: Callable[[], bool] = watch_enabled,
    ) -> None:
        self._paths = paths if paths is not None else resolve_stratex_paths()
        self._state_path = state_path if state_path is not None else _default_state_path()
        self._enabled_fn = enabled_fn
        self._lock = threading.Lock()
        self._state: dict[str, Any] | None = None

    # -- state ------------------------------------------------------------

    def _load_state(self) -> dict[str, Any]:
        if self._state is not None:
            return self._state
        state = _empty_state()
        try:
            raw = json.loads(self._state_path.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                state.update({k: raw[k] for k in state if k in raw})
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.warning(f"proactive watch: watcher state unreadable ({exc}); starting fresh")
        self._state = state
        return state

    def _persist_state(self) -> None:
        if self._state is None:
            return
        try:
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self._state_path.with_suffix(".json.tmp")
            tmp.write_text(json.dumps(self._state, default=str, indent=1), encoding="utf-8")
            os.replace(tmp, self._state_path)
        except OSError as exc:
            logger.warning(f"proactive watch: could not persist watcher state: {exc}")

    # -- delivery ---------------------------------------------------------

    def _post(
        self,
        notifications: Any,
        state: dict[str, Any],
        *,
        message: str,
        severity: str,
        trigger: str,
        dedupe_key: str,
        extra: dict[str, Any] | None = None,
        now: datetime,
    ) -> bool:
        metadata = {
            "source": SOURCE_TAG,
            "trigger": trigger,
            "dedupe_key": dedupe_key,
        }
        if extra:
            metadata.update(extra)
        try:
            notifications.post_notification(
                message,
                category="stratex_alert" if trigger != "morning_self_check" else "morning_self_check",
                severity=severity,
                metadata=metadata,
            )
        except Exception as exc:
            logger.warning(f"proactive watch: notification post failed ({trigger}): {exc}")
            return False
        state["alert_log"].append(
            {
                "ts": now.astimezone(OWNER_TZ).isoformat(),
                "trigger": trigger,
                "dedupe_key": dedupe_key,
                "severity": severity,
                "message": message,
                "delivery": "posted",
            }
        )
        state["alert_log"] = state["alert_log"][-MAX_ALERT_LOG:]
        logger.info(f"proactive watch [{trigger}] {message}")
        return True

    def _deliver(
        self,
        notifications: Any,
        state: dict[str, Any],
        event: dict[str, Any],
        *,
        now: datetime,
        report: dict[str, Any],
    ) -> None:
        """Post now, or hold through quiet hours (breaker trips exempt)."""
        if event["severity"] == "critical" or not in_quiet_hours(now):
            if self._post(notifications, state, now=now, **event):
                report["posted"] += 1
            return
        state["held"].append({**event, "queued_at": now.astimezone(OWNER_TZ).isoformat()})
        state["held"] = state["held"][-MAX_HELD:]
        state["alert_log"].append(
            {
                "ts": now.astimezone(OWNER_TZ).isoformat(),
                "trigger": event["trigger"],
                "dedupe_key": event["dedupe_key"],
                "severity": event["severity"],
                "message": event["message"],
                "delivery": "held_quiet_hours",
            }
        )
        state["alert_log"] = state["alert_log"][-MAX_ALERT_LOG:]
        report["held"] += 1

    def _flush_held(
        self, notifications: Any, state: dict[str, Any], *, now: datetime, report: dict[str, Any]
    ) -> None:
        if not state["held"] or in_quiet_hours(now):
            return
        held = state["held"]
        lines = [h["message"] for h in held[:6]]
        digest = "While you were away, Stratex did the following:\n" + "\n".join(
            f"- {line}" for line in lines
        )
        if len(held) > len(lines):
            digest += f"\n(+ {len(held) - len(lines)} more events)"
        if self._post(
            notifications,
            state,
            message=digest,
            severity="info",
            trigger="quiet_hours_digest",
            dedupe_key=f"digest:{held[0]['dedupe_key']}..{held[-1]['dedupe_key']}",
            now=now,
        ):
            report["flushed"] = len(held)
            report["posted"] += 1  # the digest itself is one posted notification
            state["held"] = []

    # -- event detection ----------------------------------------------------

    def _detect_events(
        self,
        state: dict[str, Any],
        *,
        tags: list[dict[str, Any]],
        fills: list[dict[str, Any]],
        denylist: list[str] | None,
        heartbeat: dict[str, Any] | None,
        alerts: dict[str, Any] | None,
    ) -> list[dict[str, Any]]:
        # denylist/alerts = None means "source unreadable this cycle":
        # skip that diff entirely rather than treating the world as empty
        # (which would re-arm every alert once the file recovers).
        events: list[dict[str, Any]] = []

        seen_tags = set(state["seen_tag_keys"])
        for row in tags:
            key = _tag_key(row)
            if key in seen_tags:
                continue
            seen_tags.add(key)
            events.append(
                {
                    "message": (
                        f"Stratex: {row.get('strategy') or 'a strategy'} opened "
                        f"{row.get('side') or ''} {row.get('symbol') or '?'} @ "
                        f"{_num(row.get('entry_price'))} (qty {_num(row.get('qty'))})"
                        f" on {row.get('venue') or 'the demo venue'} — forward demo trade."
                    ).replace("  ", " "),
                    "severity": "info",
                    "trigger": "trade_opened",
                    "dedupe_key": key,
                    "extra": {"strategy": str(row.get("strategy") or ""), "symbol": str(row.get("symbol") or "")},
                }
            )
        state["seen_tag_keys"] = sorted(seen_tags)[-MAX_SEEN_KEYS:]
        state["tag_count"] = len(tags)

        seen_fills = set(state["seen_fill_keys"])
        pooled = ledger_stats(fills)
        for row in fills:
            key = _fill_key(row)
            if key in seen_fills:
                continue
            seen_fills.add(key)
            events.append(
                {
                    "message": (
                        f"Stratex: {row.get('strategy') or 'a strategy'} closed "
                        f"{row.get('side') or ''} {row.get('symbol') or '?'} @ "
                        f"{_num(row.get('exit_price'))} — net "
                        f"{_money(row.get('net_pnl'), signed=True)} "
                        f"(exit: {row.get('exit_reason') or 'n/a'}). "
                        f"Ledger now: {pooled['trades']} closed trades, net "
                        f"{_money(pooled['net'], signed=True)}, PF {pooled['profit_factor_text']}."
                    ).replace("  ", " "),
                    "severity": "info",
                    "trigger": "trade_closed",
                    "dedupe_key": key,
                    "extra": {"strategy": str(row.get("strategy") or ""), "symbol": str(row.get("symbol") or "")},
                }
            )
        state["seen_fill_keys"] = sorted(seen_fills)[-MAX_SEEN_KEYS:]
        state["fill_count"] = len(fills)

        known_denied = set(state["denylist"])
        for name in denylist or []:
            if name in known_denied:
                continue
            stats = ledger_stats(fills, strategy=name)
            events.append(
                {
                    "message": (
                        f"Stratex: KILL CRITERION TRIPPED — {name} has been "
                        f"auto-paused by Stratex governance (the phase-3 "
                        f"forward guard / expectancy prune) and added to the "
                        f"strategy denylist. Its ledger: "
                        f"{stats['trades']} closed trades, net "
                        f"{_money(stats['net'], signed=True)}, expectancy "
                        f"{_money(stats['expectancy'], signed=True)}/trade, PF "
                        f"{stats['profit_factor_text']}. It will not trade "
                        f"again until it is reviewed and unpaused."
                    ),
                    "severity": "warning",
                    "trigger": "kill_criterion_tripped",
                    "dedupe_key": f"kill:{name}",
                    "extra": {"strategy": name},
                }
            )
        if denylist is not None:
            state["denylist"] = list(denylist)

        if heartbeat is not None:
            hit = bool(heartbeat.get("daily_loss_limit_hit"))
            if hit and not state["breaker_hit"]:
                events.append(
                    {
                        "message": (
                            f"Stratex: DAILY LOSS BREAKER TRIPPED — the daily "
                            f"loss limit was hit (day-start equity "
                            f"{_money(heartbeat.get('daily_start_equity'))}, "
                            f"equity now {_money(heartbeat.get('total_equity'))}). "
                            f"The daemon stops opening new trades for the day."
                        ),
                        "severity": "critical",
                        "trigger": "daily_breaker_tripped",
                        "dedupe_key": f"breaker:{owner_today()}",
                        "extra": {},
                    }
                )
            state["breaker_hit"] = hit

        known_alerts: dict[str, str] = state["measurement_alerts"]
        current_alerts: dict[str, str] = {}
        for kind, info in (alerts or {}).items():
            detail = str((info or {}).get("detail") or "")
            current_alerts[kind] = detail
            if known_alerts.get(kind) != detail:
                events.append(
                    {
                        "message": (
                            f"Stratex measurement alert — {kind}: "
                            f"{detail or 'no detail recorded'}"
                        ),
                        "severity": "warning",
                        "trigger": "measurement_alert",
                        "dedupe_key": f"alert:{kind}:{detail[:80]}",
                        "extra": {"alert_kind": kind},
                    }
                )
        if alerts is not None:
            state["measurement_alerts"] = current_alerts

        return events

    # -- morning self-check -------------------------------------------------

    def _fleet_line(self) -> str:
        try:
            from friday.tools.builtin.fleet_status import FleetStatusTool

            result = FleetStatusTool().execute(detail="summary")
            if result.is_error:
                return "Fleet: I could not probe the agents just now, so I won't guess."
            return result.content.split("Attention:")[0].strip().rstrip(".")
        except Exception as exc:
            return f"Fleet: probe failed ({type(exc).__name__}), so I won't guess."

    def compose_morning_summary(
        self,
        *,
        fills: list[dict[str, Any]] | None,
        heartbeat: dict[str, Any] | None,
        denylist: list[str],
        alerts: dict[str, Any],
        now: datetime,
    ) -> str:
        lines = [f"Morning self-check — {owner_today()} (composed by FRIDAY, unprompted):"]
        lines.append(self._fleet_line())
        if heartbeat is None:
            lines.append(
                "Stratex: I could not read the daemon heartbeat, so I won't invent its status."
            )
        else:
            positions = heartbeat.get("open_positions")
            if isinstance(positions, list):
                pos_text = str(len(positions))
            elif isinstance(positions, (int, float)):
                pos_text = str(int(positions))
            else:
                pos_text = "unreported"
            breaker = (
                "TRIPPED (daily loss limit hit)"
                if heartbeat.get("daily_loss_limit_hit")
                else "armed, not hit"
            )
            lines.append(
                f"Stratex daemon: {heartbeat.get('status') or 'UNREPORTED'}, equity "
                f"{_money(heartbeat.get('total_equity'))}, open positions {pos_text}, "
                f"daily breaker {breaker}."
            )
        if fills is None:
            lines.append("Stratex ledger: I could not read the fill ledger this morning.")
        else:
            pooled = ledger_stats(fills)
            lines.append(
                f"Stratex ledger: {pooled['trades']} closed trades, net "
                f"{_money(pooled['net'], signed=True)}, PF {pooled['profit_factor_text']}, "
                f"{pooled['wins']} winning trades."
            )
        if denylist:
            lines.append(f"Auto-paused strategies (kill criteria): {', '.join(denylist)}.")
        if alerts:
            lines.append(f"Active measurement alerts: {', '.join(sorted(alerts))}.")
        return "\n".join(lines)

    def _maybe_morning_summary(
        self,
        notifications: Any,
        state: dict[str, Any],
        *,
        fills: list[dict[str, Any]] | None,
        heartbeat: dict[str, Any] | None,
        denylist: list[str],
        alerts: dict[str, Any],
        now: datetime,
        report: dict[str, Any],
    ) -> None:
        local = now.astimezone(OWNER_TZ)
        if not (SUMMARY_WINDOW_START <= local.time() <= SUMMARY_WINDOW_END):
            return
        if state["last_summary_date"] == owner_today():
            return
        summary = self.compose_morning_summary(
            fills=fills, heartbeat=heartbeat, denylist=denylist, alerts=alerts, now=now
        )
        if self._post(
            notifications,
            state,
            message=summary,
            severity="info",
            trigger="morning_self_check",
            dedupe_key=f"morning:{owner_today()}",
            now=now,
        ):
            state["last_summary_date"] = owner_today()
            state["last_morning_summary"] = summary
            report["summary"] = True

    # -- the cycle ------------------------------------------------------------

    def run_cycle(self, notifications: Any, *, now: datetime | None = None) -> dict[str, Any]:
        """One watch cycle. Never raises; returns a report dict."""
        report: dict[str, Any] = {
            "enabled": False,
            "baseline": False,
            "events_detected": 0,
            "posted": 0,
            "held": 0,
            "flushed": 0,
            "summary": False,
            "source_errors": [],
        }
        if notifications is None:
            report["source_errors"].append("no notification manager")
            return report
        with self._lock:
            try:
                if not self._enabled_fn():
                    return report
                report["enabled"] = True
                if self._paths is None:
                    report["source_errors"].append("stratex checkout not found")
                    return report
                moment = now or now_owner_tz()
                state = self._load_state()

                tags = _read_jsonl(self._paths.tags)
                fills = _read_jsonl(self._paths.fills)
                denylist_raw = _read_json(self._paths.denylist)
                if isinstance(denylist_raw, list):
                    denylist: list[str] | None = [
                        str(x) for x in denylist_raw if isinstance(x, str)
                    ]
                elif self._paths.denylist.exists():
                    denylist = None  # present but unreadable: skip the diff
                    report["source_errors"].append("strategy_denylist unreadable")
                else:
                    denylist = []
                heartbeat_raw = _read_json(self._paths.heartbeat)
                heartbeat = heartbeat_raw if isinstance(heartbeat_raw, dict) else None
                alerts_raw = _read_json(self._paths.alerts)
                alerts: dict[str, Any] | None = None
                if isinstance(alerts_raw, dict):
                    alerts = {}
                    for kind, info in (alerts_raw.get("alerts") or {}).items():
                        if isinstance(info, dict) and info.get("active"):
                            alerts[str(kind)] = info
                elif not self._paths.alerts.exists():
                    alerts = {}
                else:
                    report["source_errors"].append("measurement_alerts unreadable")
                if tags is None:
                    report["source_errors"].append("position_tags unreadable")
                    tags = []
                if fills is None:
                    report["source_errors"].append("fill_ledger unreadable")

                if not state["baseline_done"]:
                    # Silent baseline: record the world as seen; announce nothing.
                    state["seen_tag_keys"] = sorted({_tag_key(r) for r in tags})[-MAX_SEEN_KEYS:]
                    state["tag_count"] = len(tags)
                    state["seen_fill_keys"] = sorted(
                        {_fill_key(r) for r in (fills or [])}
                    )[-MAX_SEEN_KEYS:]
                    state["fill_count"] = len(fills or [])
                    if denylist is not None:
                        state["denylist"] = list(denylist)
                    state["breaker_hit"] = bool(
                        heartbeat and heartbeat.get("daily_loss_limit_hit")
                    )
                    if alerts is not None:
                        state["measurement_alerts"] = {
                            k: str((v or {}).get("detail") or "")
                            for k, v in alerts.items()
                        }
                    state["baseline_done"] = True
                    report["baseline"] = True
                    logger.info(
                        "proactive watch: baseline established "
                        f"({len(tags)} tags, {len(fills or [])} fills, "
                        f"denylist={denylist})"
                    )
                elif fills is None:
                    # Ledger unreadable this cycle: detect nothing, retry
                    # next cycle (the error is already in the report).
                    pass
                else:
                    # A shrinking ledger means the state dir was reset:
                    # re-baseline silently instead of re-announcing history.
                    if len(tags) < state["tag_count"] or len(fills) < state["fill_count"]:
                        report["source_errors"].append("ledger shrank; re-baselined")
                        state["seen_tag_keys"] = sorted({_tag_key(r) for r in tags})[-MAX_SEEN_KEYS:]
                        state["tag_count"] = len(tags)
                        state["seen_fill_keys"] = sorted(
                            {_fill_key(r) for r in fills}
                        )[-MAX_SEEN_KEYS:]
                        state["fill_count"] = len(fills)
                        if denylist is not None:
                            state["denylist"] = list(denylist)
                        state["breaker_hit"] = bool(
                            heartbeat and heartbeat.get("daily_loss_limit_hit")
                        )
                        if alerts is not None:
                            state["measurement_alerts"] = {
                                k: str((v or {}).get("detail") or "")
                                for k, v in alerts.items()
                            }
                        report["baseline"] = True
                    else:
                        events = self._detect_events(
                            state,
                            tags=tags,
                            fills=fills,
                            denylist=denylist,
                            heartbeat=heartbeat,
                            alerts=alerts,
                        )
                        report["events_detected"] = len(events)
                        self._flush_held(notifications, state, now=moment, report=report)
                        for event in events:
                            self._deliver(notifications, state, event, now=moment, report=report)

                self._maybe_morning_summary(
                    notifications,
                    state,
                    fills=fills,
                    heartbeat=heartbeat,
                    denylist=denylist or [],
                    alerts=alerts or {},
                    now=moment,
                    report=report,
                )
                self._persist_state()
            except Exception as exc:  # a watch failure must never take FRIDAY down
                logger.exception(f"proactive watch cycle failed: {exc}")
                report["source_errors"].append(f"cycle error: {type(exc).__name__}")
            return report


# ---------------------------------------------------------------------------
# server entry point (process-global watcher)
# ---------------------------------------------------------------------------

_GLOBAL_WATCHER: StratexWatcher | None = None
_GLOBAL_LOCK = threading.Lock()


def run_watch_cycle(notifications: Any, *, now: datetime | None = None) -> dict[str, Any]:
    """Run one cycle on the process-global watcher (server loop entry)."""
    global _GLOBAL_WATCHER
    with _GLOBAL_LOCK:
        if _GLOBAL_WATCHER is None:
            _GLOBAL_WATCHER = StratexWatcher()
        watcher = _GLOBAL_WATCHER
    return watcher.run_cycle(notifications, now=now)
