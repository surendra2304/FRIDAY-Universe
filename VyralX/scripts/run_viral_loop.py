"""Autonomous VyralX loop driver (TASK-VYR-019).

Runs cycles of :func:`app.services.viral_loop.run_viral_loop_cycle`:
find popular videos across ALL categories, route each by the owner's
audio rule (voiced -> framed, voiceless -> commentary), and hold every
result as an UNLISTED ``pending_approval`` publish job for the owner's
review. The loop never uploads anything and never drains a queue —
that is the deliberate difference from ``run_viral_autopilot.py``,
which it does not replace.

The loop is OFF unless ``viral_loop_enabled`` is set (or ``--force``
for one supervised cycle):

    python scripts/run_viral_loop.py            # one cycle
    python scripts/run_viral_loop.py --loop     # cycles forever
    python scripts/run_viral_loop.py --force    # one cycle, ignoring the off switch

A single-instance lock (127.0.0.1:8766) keeps a timer fire and a
manual run from overlapping; the autopilot's 8765 lock is separate.
"""
from __future__ import annotations

import argparse
import json
import logging
import socket
import time

from app.config import get_settings
from app.database import Base, SessionLocal, engine
from app.migrations import run_additive_migrations
from app.services.viral_loop import run_viral_loop_cycle

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("vyralx.viral_loop_driver")


def _acquire_single_instance_lock() -> socket.socket | None:
    lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        lock.bind(("127.0.0.1", 8766))
        lock.listen(1)
    except OSError:
        lock.close()
        return None
    return lock


def main() -> None:
    parser = argparse.ArgumentParser(description="VyralX autonomous loop driver")
    parser.add_argument("--loop", action="store_true", help="run cycles forever")
    parser.add_argument(
        "--force", action="store_true",
        help="run even when viral_loop_enabled is off (supervised cycles only)",
    )
    parser.add_argument(
        "--interval", type=int, default=3600,
        help="seconds between cycles in --loop mode (default 3600)",
    )
    args = parser.parse_args()

    lock = _acquire_single_instance_lock()
    if lock is None:
        log.warning("Another viral loop instance holds the lock; exiting")
        return
    log.info("Viral loop lock acquired (127.0.0.1:8766)")

    Base.metadata.create_all(bind=engine)
    run_additive_migrations(engine)
    settings = get_settings()
    settings.prepare_directories()

    while True:
        with SessionLocal() as db:
            summary = run_viral_loop_cycle(db, force=args.force)
        print(json.dumps(summary, indent=2, default=str))
        if not args.loop:
            return
        if summary.get("status") == "GUARDED" and summary.get("guard") == "LOOP_DISABLED":
            log.info("Loop is disabled; --loop has nothing to do")
            return
        time.sleep(max(60, int(args.interval)))


if __name__ == "__main__":
    main()
