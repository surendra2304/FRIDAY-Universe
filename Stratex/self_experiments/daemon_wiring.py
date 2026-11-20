"""Daemon wiring for the self-experiment loop (TASK-STR-EXP-004).

TASK-STR-EXP-001 shipped ``run_forever()`` and ``start_if_enabled()``
deliberately NOT hooked into the daemon lifespan; its design doc
names the activation step: "wire the driver with the daemon-activity
probe". This module is that wiring, and ``Stratex/autonomy/
run_daemon.py`` is its only production caller.

Inert-by-default contract (the activation hard requirement):

- Unless the kill switch ``STRATEX_SELF_EXPERIMENTS`` is exactly
  "on" (the same gate expression as
  ``SelfExperimentLoop.experiments_enabled``), :func:`start` returns
  None BEFORE importing the loop package or touching the filesystem:
  no loop object, no thread, no ledger or counter writes, no load.
  The daemon-side hook applies the same check before importing this
  module at all, so with the switch unset or any other value the
  daemon's behaviour is the pre-activation behaviour, unchanged.
- With the switch on, :func:`start` builds the loop through
  EXP-001's own ``start_if_enabled`` (which re-checks the switch),
  passing the daemon-activity probe as the loop's ``work_probe``,
  and drives ``run_forever()`` on a daemon thread with its own
  asyncio loop. A wiring failure raises to the caller — the daemon
  hook catches, logs, and keeps trading; a silently absent loop
  would look exactly like a working one, so nothing is swallowed
  here.

Paths: the loop's data directory and the production stream store
live under ``Stratex/self_experiments_data/`` by default (the store
at ``self_experiments_data/stream_store``, built by the activation
ops step with ``export_stream_store.py --out`` pointing there).
Both are overridable via ``STRATEX_SELF_EXPERIMENTS_DATA_DIR`` /
``STRATEX_SELF_EXPERIMENTS_STORE_DIR`` for testing and staging.
"""

from __future__ import annotations

import asyncio
import os
import threading
from pathlib import Path
from typing import Any, Callable

_STRATEX_ROOT = Path(__file__).resolve().parent.parent

#: Where the loop's ledger / counter / admissions live in production.
DEFAULT_DATA_DIR = _STRATEX_ROOT / "self_experiments_data"
#: Where the activation ops step builds the production stream store.
DEFAULT_STORE_DIR = DEFAULT_DATA_DIR / "stream_store"

ENV_DATA_DIR = "STRATEX_SELF_EXPERIMENTS_DATA_DIR"
ENV_STORE_DIR = "STRATEX_SELF_EXPERIMENTS_STORE_DIR"


def self_experiments_switch_on() -> bool:
    """The kill switch, identical to
    ``SelfExperimentLoop.experiments_enabled``: only the exact value
    "on" (after strip/lower, matching EXP-001's gate) enables the
    loop. Unset, "off", or anything else means disabled."""
    return os.getenv("STRATEX_SELF_EXPERIMENTS", "off").strip().lower() == "on"


def resolve_data_dir(data_dir: Path | None = None) -> Path:
    if data_dir is not None:
        return Path(data_dir)
    env = os.getenv(ENV_DATA_DIR, "").strip()
    return Path(env) if env else DEFAULT_DATA_DIR


def resolve_store_dir(store_dir: Path | None = None) -> Path:
    if store_dir is not None:
        return Path(store_dir)
    env = os.getenv(ENV_STORE_DIR, "").strip()
    return Path(env) if env else DEFAULT_STORE_DIR


class _ThreadControl:
    """Hands the asyncio loop + stop event from the wiring thread
    back to the handle, so stop() can set the event thread-safely."""

    def __init__(self) -> None:
        self.ready = threading.Event()
        self.asyncio_loop: asyncio.AbstractEventLoop | None = None
        self.stop_event: asyncio.Event | None = None


def _thread_main(loop_obj: Any, control: _ThreadControl) -> None:
    async def _amain() -> None:
        control.asyncio_loop = asyncio.get_running_loop()
        control.stop_event = asyncio.Event()
        control.ready.set()
        await loop_obj.run_forever(stop_event=control.stop_event)

    asyncio.run(_amain())


class DaemonWiringHandle:
    """A running self-experiment loop on its daemon thread."""

    def __init__(
        self,
        loop_obj: Any,
        thread: threading.Thread,
        control: _ThreadControl,
    ) -> None:
        self.loop = loop_obj
        self.thread = thread
        self._control = control

    @property
    def is_alive(self) -> bool:
        return self.thread.is_alive()

    def stop(self, timeout: float = 10.0) -> bool:
        """Ask run_forever to stop and join the thread.

        Returns True when the thread has exited. Safe to call more
        than once, and safe when the thread already died."""
        control = self._control
        if control.ready.wait(timeout=2.0):
            asyncio_loop, stop_event = control.asyncio_loop, control.stop_event
            if asyncio_loop is not None and stop_event is not None:
                try:
                    asyncio_loop.call_soon_threadsafe(stop_event.set)
                except RuntimeError:
                    pass  # loop already closed — the thread is ending
        self.thread.join(timeout=timeout)
        return not self.thread.is_alive()


def start(
    work_probe: Callable[[], bool],
    store_dir: Path | None = None,
    data_dir: Path | None = None,
) -> DaemonWiringHandle | None:
    """Start the self-experiment loop for the daemon, or nothing.

    Returns None — having imported nothing and written nothing —
    when the kill switch is not exactly "on". With the switch on,
    builds the loop via EXP-001's ``start_if_enabled`` with the
    daemon-activity ``work_probe`` and starts ``run_forever()`` on a
    daemon thread. Raises whatever loop construction raises (e.g.
    StoreError for a missing/unverified production store): the
    daemon hook is responsible for catching and logging, so a
    failed activation is loud, never silent.
    """
    if not self_experiments_switch_on():
        return None
    from .loop import start_if_enabled

    loop_obj = start_if_enabled(
        store_dir=resolve_store_dir(store_dir),
        data_dir=resolve_data_dir(data_dir),
        work_probe=work_probe,
    )
    if loop_obj is None:
        return None
    control = _ThreadControl()
    thread = threading.Thread(
        target=_thread_main,
        args=(loop_obj, control),
        name="stratex-self-experiments",
        daemon=True,
    )
    thread.start()
    return DaemonWiringHandle(loop_obj=loop_obj, thread=thread, control=control)
