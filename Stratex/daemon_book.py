"""
daemon_book.py — the live Stratex book, composed from the daemon's own
state files.

The multi-venue daemon (autonomy/run_daemon.py, Stratex-Daemon.service)
is the only component that trades. It publishes two state files:

* ``state/daemon_heartbeat.json`` — republished every scan cycle: status,
  pid, the combined multi-venue ``total_balance`` / ``total_equity``,
  ``unrealized_pnl`` and the venue-derived ``open_positions`` count.
* ``state/forward_scorecard.json`` — regenerated every 15 min by the
  FWD-013 timer (measurement/forward_scorecard.py): per-entrant
  ``open_positions`` rows composed from position_tags + the fill ledger.

Every surface that answers "what is Stratex holding" composes from these
two files through this module: aggregates from the heartbeat, position
rows from the scorecard. The scorecard carries no per-position marks, so
served rows OMIT ``unrealized_pnl`` — a row's PnL is never synthesised;
the headline unrealized always comes from the heartbeat.

History: these surfaces used to compose from
``state/cloud_portfolio_state.json``, written only by the retired MT5
cTrader engine (frozen 2026-11-08 at balance 10792.8 with zero
positions), so supervision and the dashboard reported an empty book
while the daemon held live positions. The readers were re-based here;
that file is left in place as a record and is read by nothing live.
"""

import datetime
import json
import os
import time
from typing import Any

HEARTBEAT_MAX_AGE_SECONDS = 600
SCORECARD_MAX_AGE_SECONDS = 1800  # 30 min: two scorecard cycles


def pid_alive(pid: Any) -> bool:
    """Best-effort liveness check for a recorded pid (no signal side effects)."""
    if not pid:
        return False
    try:
        if os.name == "nt":
            import ctypes

            PROCESS_QUERY_INFORMATION = 0x0400
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_INFORMATION, False, pid
            )
            if handle:
                ctypes.windll.kernel32.CloseHandle(handle)
                return True
            return False
        os.kill(pid, 0)
        return True
    except Exception:
        return False


def _state_candidates(filename: str, env_var: str) -> list[str]:
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = []
    env_path = os.getenv(env_var)
    if env_path:
        candidates.append(env_path)
    candidates += [
        os.path.join(os.getcwd(), "state", filename),
        os.path.join(here, "state", filename),
    ]
    return candidates


def daemon_heartbeat_candidates() -> list[str]:
    """Candidate paths for state/daemon_heartbeat.json, in priority order.

    TASK-REL-071: the dashboard and the detailed-health feed pillar both
    resolve the daemon heartbeat through this one convention (env
    STRATEX_DAEMON_HEARTBEAT_FILE, then cwd/state, then this module's
    state/), so the writer in autonomy/run_daemon.py and every reader
    always agree on where the live heartbeat lives. The retired
    testnet_heartbeat.json is not a candidate here.
    """
    return _state_candidates("daemon_heartbeat.json", "STRATEX_DAEMON_HEARTBEAT_FILE")


def read_daemon_heartbeat(
    max_age_seconds: int = HEARTBEAT_MAX_AGE_SECONDS,
) -> tuple[dict[str, Any], float] | None:
    """The daemon's raw heartbeat payload + its file age, or None.

    The gate is the one the dashboard has always applied
    (TASK-REL-003): file age <= max_age_seconds, ``status == "RUNNING"``,
    and the recorded pid alive when one is recorded. A heartbeat that
    fails the gate is not evidence of a live daemon, and last figures
    are never served as live.
    """
    for path in _state_candidates("daemon_heartbeat.json", "STRATEX_DAEMON_HEARTBEAT_FILE"):
        if not os.path.exists(path):
            continue
        try:
            age = time.time() - os.path.getmtime(path)
            if age > max_age_seconds:
                continue
            with open(path, "r", encoding="utf-8") as fh:
                hb = json.load(fh)
        except Exception:
            continue
        if not isinstance(hb, dict):
            continue
        if hb.get("status") != "RUNNING":
            continue
        pid = hb.get("pid")
        if pid is not None and not pid_alive(pid):
            continue
        return hb, age
    return None


def _parse_iso_epoch(value: Any) -> float | None:
    if not value:
        return None
    try:
        dt = datetime.datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.timestamp()


def read_forward_scorecard(
    max_age_seconds: int = SCORECARD_MAX_AGE_SECONDS,
) -> dict[str, Any] | None:
    """The forward scorecard + freshness, or None when no file is readable.

    Returns ``{"card", "generated_at", "age_seconds", "fresh"}``. The
    card is returned even when stale (``fresh`` False) so callers can
    withhold the position list while still marking its as-of time;
    freshness is judged by ``generated_at`` when parseable, else by
    file mtime.
    """
    for path in _state_candidates("forward_scorecard.json", "STRATEX_FORWARD_SCORECARD_FILE"):
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as fh:
                card = json.load(fh)
        except Exception:
            continue
        if not isinstance(card, dict):
            continue
        generated_at = card.get("generated_at")
        epoch = _parse_iso_epoch(generated_at)
        if epoch is not None:
            age = max(0.0, time.time() - epoch)
        else:
            try:
                age = max(0.0, time.time() - os.path.getmtime(path))
            except OSError:
                continue
        return {
            "card": card,
            "generated_at": generated_at,
            "age_seconds": age,
            "fresh": age <= max_age_seconds,
        }
    return None


def scorecard_position_rows(card: dict[str, Any]) -> list[dict[str, Any]]:
    """Flatten ``entrants[].open_positions[]`` across ALL entrant cards.

    Cards no entrant claims are surfaced by the scorecard as
    UNREGISTERED entrants — they are part of the book and are flattened
    in like any other card. Translation (SCOPE §5): ``quantity`` <-
    ``qty``; ``position_id`` <- ``"{venue}:{symbol}"`` (scorecard
    semantics: one open slot per (venue, symbol)). Per-row
    ``unrealized_pnl`` / ``stop_loss`` / ``take_profit`` are ABSENT —
    the scorecard has no marks and nothing here invents them.
    """
    rows: list[dict[str, Any]] = []
    if not isinstance(card, dict):
        return rows
    for entrant in card.get("entrants") or []:
        if not isinstance(entrant, dict):
            continue
        for pos in entrant.get("open_positions") or []:
            if not isinstance(pos, dict):
                continue
            venue = str(pos.get("venue") or "")
            symbol = str(pos.get("symbol") or "")
            rows.append(
                {
                    "position_id": f"{venue}:{symbol}",
                    "venue": venue,
                    "symbol": symbol,
                    "side": str(pos.get("side") or ""),
                    "quantity": pos.get("qty"),
                    "entry_price": pos.get("entry_price"),
                    "opened_at": pos.get("opened_at"),
                    "strategy": str(pos.get("strategy") or ""),
                }
            )
    return rows


def live_book() -> dict[str, Any]:
    """Compose the live book once for a surface.

    ``heartbeat``: the gated raw heartbeat payload, or None when the
    daemon is not provably live. ``scorecard``: the read_forward_scorecard
    result, or None. ``rows``: the translated position rows — served
    only from a FRESH scorecard; when the scorecard is missing or stale
    the list is withheld (``rows_withheld`` True) rather than backfilled
    from any legacy store. Divergence rule: the headline count is the
    heartbeat's venue-derived ``open_positions``; the list is served
    as-is and never padded or trimmed to force a match.
    """
    hb_result = read_daemon_heartbeat()
    heartbeat = hb_result[0] if hb_result else None
    scorecard = read_forward_scorecard()
    rows: list[dict[str, Any]] = []
    rows_withheld = True
    if scorecard is not None and scorecard["fresh"]:
        rows = scorecard_position_rows(scorecard["card"])
        rows_withheld = False
    return {
        "heartbeat": heartbeat,
        "scorecard": scorecard,
        "rows": rows,
        "rows_withheld": rows_withheld,
    }
