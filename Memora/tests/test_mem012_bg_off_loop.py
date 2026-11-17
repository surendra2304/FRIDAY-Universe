"""TASK-MEM-012: Memora's background consolidation / wiki-compile /
skill-evaluation passes must not block the event loop, and a pass
must never overlap itself.

Production evidence (memora-stall forensics, 2026-11-17): the
lifespan background worker ran compile_wiki + consolidate +
run_evaluation_pass synchronously on the event loop every 300s —
a measured 0-9s of loop block per cycle and a reliable trigger for
the swap major-fault storms behind Memora's 20-190s stalls.

On pristine main these tests fail: the worker was a closure inside
lifespan() running the passes inline, and no module-level
_memora_bg_worker / _run_memora_bg_pass symbols exist.
"""
import asyncio
import threading
import time

from apps.api import main as memora_main
from apps.api.routers import context_db as context_db_router


def test_bg_pass_does_not_block_event_loop(monkeypatch):
    """A 0.4s synchronous pass body must not stall the loop: a 10ms
    ticker keeps ticking (max lag far below the pass duration) while
    the worker runs the pass in a thread."""
    pass_starts = []

    def slow_pass():
        pass_starts.append(time.monotonic())
        time.sleep(0.4)

    monkeypatch.setattr(memora_main, "_run_memora_bg_pass", slow_pass)
    monkeypatch.setenv("MEMORA_CONSOLIDATION_INTERVAL_SEC", "0.05")

    async def scenario():
        lags = []
        stop = asyncio.Event()

        async def ticker():
            last = time.monotonic()
            while not stop.is_set():
                await asyncio.sleep(0.01)
                now = time.monotonic()
                lags.append(now - last)
                last = now

        tick_task = asyncio.create_task(ticker())
        worker = asyncio.create_task(memora_main._memora_bg_worker())
        await asyncio.sleep(1.0)
        worker.cancel()
        try:
            await worker
        except asyncio.CancelledError:
            pass
        stop.set()
        await tick_task
        return max(lags) if lags else 0.0

    max_lag = asyncio.run(scenario())
    assert pass_starts, "background pass never ran"
    assert max_lag < 0.2, (
        f"event loop was blocked for {max_lag:.3f}s by a background pass"
    )


def test_bg_pass_never_overlaps_itself(monkeypatch):
    """While one pass is mid-compile, a second invocation must skip
    (not run a concurrent compile); once released, the first pass
    completes in the original order: compile_wiki then consolidate."""
    calls = []
    compile_entered = threading.Event()
    release_compile = threading.Event()

    class StubService:
        def compile_wiki(self, persist=True):
            calls.append("compile_wiki")
            compile_entered.set()
            release_compile.wait(timeout=10)

        def consolidate(self):
            calls.append("consolidate")

    monkeypatch.setattr(context_db_router, "get_service", lambda: StubService())
    monkeypatch.setenv("MEMORA_SKILL_LEARNING_BG", "0")

    first = threading.Thread(target=memora_main._run_memora_bg_pass)
    first.start()
    try:
        assert compile_entered.wait(timeout=10), (
            "first pass never reached compile_wiki"
        )
        memora_main._run_memora_bg_pass()
        assert calls == ["compile_wiki"], f"pass overlapped itself: {calls}"
    finally:
        release_compile.set()
        first.join(timeout=10)
    assert calls == ["compile_wiki", "consolidate"], (
        f"pass order/completion wrong: {calls}"
    )
