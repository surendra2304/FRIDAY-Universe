"""TASK-VOI-014 — production greeting path: D5 + D8.

FRD-005 re-run #3 (run 20261116-120503, deploy blob-proven) failed the
greeting at +33.90 s participant clock despite VOI-013 being live, and
fired the greeting machinery three times. The journal (with
code.line.number) decomposes it:

- D5: the early greeting task launched at room-up correctly, but
  sess.start() executed on the same job loop through a page-fault
  storm (the production worker sits ~87% in swap: VmRSS 25 MB /
  VmSwap 166 MB) and the ready task got no effective loop time for
  ~21 s; the executor warm's discarded sync recall (21.0 s, fired by
  the replacement executor's prewarm AT job launch) competed on top.
  Fix: the ready path awaits the greeting's settlement (bounded,
  non-cancelling) BEFORE starting the session, and the warm loses
  its recall step + never starts while a job is live.
- D8: _greet_when_ready's layer 2 fired generate_reply
  UNCONDITIONALLY — its 30 s shield timed out while the fixed line
  was still playing, and the model spoke a second greeting 39 s
  after the user's first request. Fix: the fixed line is the ONE
  greeting owner; the model greeting survives only as the last
  resort when the line could not be played at all, and no greeting
  stack fires once the user has spoken.
"""

import asyncio
import inspect
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_warm_state():
    w._EXECUTOR_WARM_LAST[0] = 0.0
    w._JOBS_ACTIVE[0] = 0
    yield
    w._EXECUTOR_WARM_LAST[0] = 0.0
    w._JOBS_ACTIVE[0] = 0


# ---------- _await_greeting_settled ----------

def test_settled_wait_none_task_is_settled():
    assert asyncio.run(w._await_greeting_settled(None)) is True


def test_settled_wait_fast_task():
    async def main():
        async def _quick():
            return None

        task = asyncio.ensure_future(_quick())
        return await w._await_greeting_settled(task, timeout_s=5.0)

    assert asyncio.run(main()) is True


def test_settled_wait_timeout_never_cancels_the_line():
    async def main():
        release = asyncio.Event()

        async def _slow_line():
            await release.wait()

        task = asyncio.ensure_future(_slow_line())
        settled = await w._await_greeting_settled(task, timeout_s=0.2)
        # The bound expired, the session would start anyway — and the
        # line task must still be alive (the backstop is concurrency,
        # never cancellation).
        assert settled is False
        assert not task.cancelled() and not task.done()
        release.set()
        await task
        return True

    assert asyncio.run(main()) is True


def test_settled_wait_failed_task_counts_as_settled():
    async def main():
        async def _boom():
            raise RuntimeError("line playback failed")

        task = asyncio.ensure_future(_boom())
        return await w._await_greeting_settled(task, timeout_s=5.0)

    assert asyncio.run(main()) is True


# ---------- entrypoint source shape: settle BEFORE session start ----------

def test_entrypoint_settles_greeting_before_session_start():
    src = inspect.getsource(w.entrypoint)
    settle_at = src.index('await _await_greeting_settled(early_greeting["task"])')
    start_at = src.index("await _start(session, agent)")
    launch_at = src.index('early_greeting["task"] = asyncio.ensure_future(')
    assert launch_at < settle_at < start_at


def test_entrypoint_counts_the_job_active_for_the_warm_guard():
    src = inspect.getsource(w.entrypoint)
    assert "_JOBS_ACTIVE[0] += 1" in src
    assert "ctx.add_shutdown_callback(_voi014_job_finished)" in src


# ---------- D8: _greet_when_ready is fallback-only ----------

def _greet_src() -> str:
    src = inspect.getsource(w.entrypoint)
    greet_at = src.index("async def _greet_when_ready")
    close_at = src.index("async def _close_quietly")
    return src[greet_at:close_at]


def test_greet_when_ready_attempted_line_is_the_only_greeting():
    greet_src = _greet_src()
    attempted_at = greet_src.index('if greeting_state["attempted"]:')
    reply_at = greet_src.index("sess.generate_reply(user_input=_greeting_prompt)")
    # The attempted check returns before the model greeting can fire.
    assert attempted_at < reply_at
    assert "return" in greet_src[attempted_at:reply_at]


def test_greet_when_ready_user_spoke_blocks_every_greeting():
    greet_src = _greet_src()
    # The user-spoke gate is checked before the fallback line play AND
    # before the last-resort model greeting.
    assert greet_src.count('greeting_state.get("user_spoke")') >= 2
    first_gate = greet_src.index('greeting_state.get("user_spoke")')
    assert first_gate < greet_src.index("_play_fixed_line")
    assert first_gate < greet_src.index("sess.generate_reply(user_input=_greeting_prompt)")


def test_model_greeting_only_after_the_line_could_not_play():
    greet_src = _greet_src()
    failed_at = greet_src.index("VOICE fixed-line greeting could not be played")
    reply_at = greet_src.index("sess.generate_reply(user_input=_greeting_prompt)")
    played_return_at = greet_src.index(
        'logger.info("VOICE fixed-line greeting played (recorded line)")'
    )
    # A played line returns; the model greeting sits strictly behind
    # the could-not-play branch.
    assert played_return_at < failed_at < reply_at


def test_handlers_mark_user_spoke():
    src = inspect.getsource(w.entrypoint)
    # Transcription-final handler + user-item handler.
    assert src.count('greeting_state["user_spoke"] = True') == 2


# ---------- the defused warm ----------

def test_warm_steps_never_recall():
    assert "_owner_memory_lines" not in inspect.getsource(w._executor_warm_steps)


def test_warm_never_starts_while_a_job_is_live(monkeypatch):
    ran = []
    monkeypatch.setattr(w, "_executor_warm_steps", lambda: ran.append(1))
    w._JOBS_ACTIVE[0] = 1
    w._prewarm_job_executor(object())
    time.sleep(0.3)
    assert ran == []
    # And it fires again once no job is live.
    w._JOBS_ACTIVE[0] = 0
    w._prewarm_job_executor(object())
    deadline = time.time() + 5.0
    while not ran and time.time() < deadline:
        time.sleep(0.05)
    assert ran == [1]
