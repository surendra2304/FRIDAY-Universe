"""Regression tests: the app lifespan must not install signal handlers.

Production defect (fleet graceful-shutdown diagnosis, 2026-11-17): lifespan
startup used to call ``loop.add_signal_handler(SIGTERM/SIGINT, ...)`` with a
callback that only logged. uvicorn installs its own handlers *before* the
lifespan runs, so the app's registration replaced uvicorn's disposition —
SIGTERM never set ``should_exit``, the lifespan-exit cleanup never ran, and
systemd SIGKILLed the process at TimeoutStopSec on every stop.

Signal ownership belongs to uvicorn alone. These tests pin that the lifespan
registers no handler — at runtime, and in the module's AST (so the log-only
helpers cannot quietly return either).
"""

import ast
import asyncio
import inspect
import os

# The app lifespan builds an httpx client that reads proxy environment
# variables; some sandboxes export values this httpx version cannot parse.
# These tests are fully in-process, so proxying is never needed here.
for _v in (
    "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy",
    "ALL_PROXY", "all_proxy", "NO_PROXY", "no_proxy",
):
    os.environ.pop(_v, None)

from app import main as main_module


class _RecordingLoop(asyncio.SelectorEventLoop):
    """Event loop that records add_signal_handler calls instead of acting.

    The recorder deliberately does not call through: a test must never touch
    the process signal table.
    """

    def __init__(self):
        super().__init__()
        self.signal_handler_calls = []

    def add_signal_handler(self, sig, callback, *args):
        self.signal_handler_calls.append(sig)


def test_lifespan_startup_installs_no_signal_handlers():
    """Drive the real lifespan on a recording loop: zero registrations."""
    loop = _RecordingLoop()
    asyncio.set_event_loop(loop)
    try:

        async def _boot_and_shutdown():
            async with main_module.lifespan(main_module.app):
                pass

        loop.run_until_complete(_boot_and_shutdown())
    finally:
        asyncio.set_event_loop(None)
        loop.close()

    assert loop.signal_handler_calls == [], (
        "the lifespan must not install signal handlers; uvicorn owns "
        "SIGTERM/SIGINT and an app-level registration replaces its "
        "disposition, so shutdown never begins"
    )


def test_main_module_registers_no_signal_handlers():
    """AST guard: no add_signal_handler call and no log-only helpers remain."""
    tree = ast.parse(inspect.getsource(main_module))
    offenders = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "add_signal_handler":
                offenders.append(f"add_signal_handler call at line {node.lineno}")
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name in {"_on_signal", "_signal_callback"}:
                offenders.append(f"{node.name} defined at line {node.lineno}")
    assert offenders == []
