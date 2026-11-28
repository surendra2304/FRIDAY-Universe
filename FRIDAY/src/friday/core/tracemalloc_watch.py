"""TASK-FRD-064: env-gated tracemalloc observation watch.

FRIDAY.service dies by OOM-kill roughly every 1-2 h (six kills on
2026-11-27 alone) with ~100 MB anonymous-memory spikes in under 20 s and
no chat turn in flight. ``/proc`` attribution proved the floor is ~99 MB
anonymous mmap (67%) vs ~41 MB heap (28%), but it cannot name the
allocating code — a fix PR built on that would be a guess.

WATCH230 §C.2 (hub #2045 comment 7223417776) approved option (a): an
env-gated tracemalloc start plus ONE observation restart under standing
clearance 7200564540; capture the top allocation diffs across the next
OOM window, file the evidence, then revert the gate. Option (b), a
snapshot endpoint, is pre-approved as fallback.

This module is that gate. It is inert unless ``FRIDAY_TRACEMALLOC=1``:
no thread, no tracing, no file writes. When enabled it starts
``tracemalloc`` (25 frames) at boot and a daemon thread snapshots the
heap every ``FRIDAY_TRACEMALLOC_INTERVAL_S`` seconds (default 300),
appending the top-10 allocation diffs plus RSS / traced / peak figures
to ``FRIDAY_TRACEMALLOC_LOG`` (default ``/tmp/friday_tracemalloc.log``)
and one concise INFO line per tick to the service log, so the next OOM
window leaves a per-object trail. A final snapshot is written on
graceful shutdown. Everything here is fail-safe: any error is logged
and swallowed, never raised into startup or shutdown.
"""

from __future__ import annotations

import logging
import os
import threading
import time
import tracemalloc
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

ENV_VAR = "FRIDAY_TRACEMALLOC"
INTERVAL_ENV_VAR = "FRIDAY_TRACEMALLOC_INTERVAL_S"
LOG_ENV_VAR = "FRIDAY_TRACEMALLOC_LOG"
DEFAULT_INTERVAL_S = 300.0
DEFAULT_LOG_PATH = "/tmp/friday_tracemalloc.log"
TOP_N = 10
TRACEBACK_FRAMES = 25
_MAX_LOG_BYTES = 5_000_000

_lock = threading.Lock()
_thread: threading.Thread | None = None
_stop_event: threading.Event | None = None
_log_path: str = DEFAULT_LOG_PATH
_interval_s: float = DEFAULT_INTERVAL_S


def _enabled() -> bool:
    return os.getenv(ENV_VAR, "").strip().lower() in ("1", "true", "yes", "on")


def _parse_interval() -> float:
    try:
        value = float(os.getenv(INTERVAL_ENV_VAR, "") or DEFAULT_INTERVAL_S)
    except ValueError:
        logger.warning("FRD-064 tracemalloc watch: bad %s, using %.0fs",
                       INTERVAL_ENV_VAR, DEFAULT_INTERVAL_S)
        return DEFAULT_INTERVAL_S
    return max(0.1, value)


def _read_rss_mb() -> float:
    """Resident set size in MB from /proc (Linux only); 0.0 elsewhere."""
    try:
        with open("/proc/self/status", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("VmRSS:"):
                    return float(line.split()[1]) / 1024.0
    except (OSError, ValueError, IndexError):
        pass
    return 0.0


def _format_diff_line(stat) -> str:
    """One allocation-diff entry: size delta, block delta, top frames."""
    size_mb = stat.size_diff / (1024.0 * 1024.0)
    frames = " <- ".join(
        f"{frame.filename.rsplit('/', 1)[-1]}:{frame.lineno}"
        for frame in stat.traceback[:3]
    )
    return (f"    {size_mb:+.2f} MB ({stat.count_diff:+d} blocks) {frames}")


def _append_record(kind: str, snapshot, previous) -> None:
    """Append one tick/shutdown record (diffs + totals) to the log file."""
    try:
        current, peak = tracemalloc.get_traced_memory()
        rss_mb = _read_rss_mb()
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        lines = [
            f"[{stamp}] {kind} rss_mb={rss_mb:.1f} "
            f"traced_mb={current / 1048576:.2f} traced_peak_mb={peak / 1048576:.2f}"
        ]
        if previous is not None:
            diffs = snapshot.compare_to(previous, "traceback")[:TOP_N]
            lines.extend(_format_diff_line(s) for s in diffs if s.size_diff != 0)
        if len(lines) == 1:
            lines.append("    (no allocation change since previous snapshot)")
        if os.path.exists(_log_path) and os.path.getsize(_log_path) > _MAX_LOG_BYTES:
            os.replace(_log_path, _log_path + ".1")
        with open(_log_path, "a", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        logger.info(
            "FRD-064 tracemalloc watch %s: rss=%.1fMB traced=%.2fMB peak=%.2fMB",
            kind, rss_mb, current / 1048576, peak / 1048576,
        )
    except Exception:
        logger.exception("FRD-064 tracemalloc watch: failed to write record")


def _watch_loop(stop_event: threading.Event) -> None:
    try:
        previous = tracemalloc.take_snapshot()
        while not stop_event.wait(_interval_s):
            try:
                current_snapshot = tracemalloc.take_snapshot()
                _append_record("tick", current_snapshot, previous)
                previous = current_snapshot
            except Exception:
                logger.exception("FRD-064 tracemalloc watch: tick failed")
    except Exception:
        logger.exception("FRD-064 tracemalloc watch: loop failed")


def maybe_start_tracemalloc_watch() -> bool:
    """Start the observation watch if FRIDAY_TRACEMALLOC=1. Never raises."""
    global _thread, _stop_event, _log_path, _interval_s
    try:
        if not _enabled():
            return False
        with _lock:
            if _thread is not None and _thread.is_alive():
                return True
            _log_path = os.getenv(LOG_ENV_VAR, "") or DEFAULT_LOG_PATH
            _interval_s = _parse_interval()
            if not tracemalloc.is_tracing():
                tracemalloc.start(TRACEBACK_FRAMES)
            _stop_event = threading.Event()
            _thread = threading.Thread(
                target=_watch_loop, args=(_stop_event,),
                name="friday-tracemalloc-watch", daemon=True,
            )
            _thread.start()
        logger.info(
            "FRD-064 tracemalloc watch started (interval=%.0fs log=%s)",
            _interval_s, _log_path,
        )
        return True
    except Exception:
        logger.exception("FRD-064 tracemalloc watch: failed to start")
        return False


def stop_tracemalloc_watch() -> bool:
    """Stop the watch, writing a final snapshot. Never raises."""
    global _thread, _stop_event
    try:
        with _lock:
            thread, stop_event = _thread, _stop_event
            _thread, _stop_event = None, None
        if thread is None or stop_event is None:
            return False
        stop_event.set()
        thread.join(timeout=5.0)
        try:
            final_snapshot = tracemalloc.take_snapshot()
            _append_record("shutdown", final_snapshot, None)
        except Exception:
            logger.exception("FRD-064 tracemalloc watch: final snapshot failed")
        if tracemalloc.is_tracing():
            tracemalloc.stop()
        logger.info("FRD-064 tracemalloc watch stopped")
        return True
    except Exception:
        logger.exception("FRD-064 tracemalloc watch: failed to stop")
        return False


def is_watching() -> bool:
    """True while the watch thread is alive (tests / diagnostics)."""
    with _lock:
        return _thread is not None and _thread.is_alive()
