"""TASK-VOI-013: the greeting trigger is room-up + verified-key.

FRD-005 re-run #2 (run 20261116-103839) measured the VOI-011 early
greeting firing at worker-connect+12.39 s — 0.5 s before the session
started — on a job where the room and the verified key were both in
hand within ~1 s of the connect. Two stacked causes: the task was
created only after ``_built = await _build_task`` resolved (so it
inherited the whole model + session construction), and created that
late its participant wait ran on the job loop while sess.start()
executed on it.

These tests pin the restructure:

- ``_greet_at_room_up``: plays the line as soon as the KEY leg
  resolves — with no build future anywhere in its contract, an
  artificially slow (here: never-completing) session construction
  cannot delay it. Keyless / disabled / plugin-missing / failed
  resolution all produce ZERO greeting attempts (the VOI-010
  recorded-notice shape is preserved exactly). The key future is
  shielded: cancelling the greeting task never cancels the shared
  key resolution the build also awaits.
- ``_settle_early_greeting``: the unavailable notice never overlaps
  the line and never precedes an attempted one — unattempted tasks
  are cancelled (notice keeps its no-greeting-first shape), attempted
  tasks are awaited (bounded) so the notice plays after the line.
- Entrypoint source shape: the launch sits BEFORE the first
  session is built (since TASK-VOI-017 (F3) the build runs in-job
  through ``_make_session``; it was ``_built = await _build_task``
  before) and therefore before ``sess.start()``, and both
  unavailable branches settle the greeting task before announcing.
"""
import asyncio
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


def _resolved_key_task(value="key"):
    async def _key():
        return value

    return asyncio.ensure_future(_key())


def _failing_key_task():
    async def _key():
        raise RuntimeError("resolution blew up")

    return asyncio.ensure_future(_key())


class _PlayRecorder:
    def __init__(self):
        self.calls = 0

    async def __call__(self):
        self.calls += 1


# ---------- _greet_at_room_up ----------

def test_greet_plays_once_key_resolves():
    async def main():
        play = _PlayRecorder()
        await w._greet_at_room_up(
            _resolved_key_task(),
            greeting_enabled=True, plugin_available=True, play_line=play,
        )
        return play.calls

    assert asyncio.run(main()) == 1


def test_greet_never_waits_for_session_construction():
    """The brief's pin: with construction artificially slow (a build
    future that NEVER completes during the test), the line still
    plays — the trigger's contract contains no build at all."""

    async def main():
        play = _PlayRecorder()
        build = asyncio.ensure_future(asyncio.sleep(3600))  # never lands
        greet = asyncio.ensure_future(
            w._greet_at_room_up(
                _resolved_key_task(),
                greeting_enabled=True, plugin_available=True, play_line=play,
            )
        )
        await asyncio.wait_for(greet, timeout=5.0)
        assert not build.done()  # construction still "in progress"
        build.cancel()
        return play.calls

    assert asyncio.run(main()) == 1


def test_greet_waits_for_a_slow_key_but_nothing_else():
    async def main():
        play = _PlayRecorder()

        async def slow_key():
            await asyncio.sleep(0.4)
            return "key"

        key_task = asyncio.ensure_future(slow_key())
        await w._greet_at_room_up(
            key_task,
            greeting_enabled=True, plugin_available=True, play_line=play,
        )
        return play.calls

    assert asyncio.run(main()) == 1


def test_greet_zero_attempts_when_keyless():
    async def main():
        play = _PlayRecorder()
        await w._greet_at_room_up(
            _resolved_key_task(None),
            greeting_enabled=True, plugin_available=True, play_line=play,
        )
        return play.calls

    assert asyncio.run(main()) == 0


def test_greet_zero_attempts_when_disabled_or_plugin_missing():
    async def main():
        calls = 0
        for enabled, plugin in ((False, True), (True, False), (False, False)):
            play = _PlayRecorder()
            await w._greet_at_room_up(
                _resolved_key_task(),
                greeting_enabled=enabled, plugin_available=plugin,
                play_line=play,
            )
            calls += play.calls
        return calls

    assert asyncio.run(main()) == 0


def test_greet_zero_attempts_when_key_resolution_fails():
    async def main():
        play = _PlayRecorder()
        await w._greet_at_room_up(
            _failing_key_task(),
            greeting_enabled=True, plugin_available=True, play_line=play,
        )
        return play.calls

    assert asyncio.run(main()) == 0


def test_cancelling_the_greeting_never_cancels_the_shared_key():
    async def main():
        async def slow_key():
            await asyncio.sleep(30)
            return "key"

        key_task = asyncio.ensure_future(slow_key())
        greet = asyncio.ensure_future(
            w._greet_at_room_up(
                key_task,
                greeting_enabled=True, plugin_available=True,
                play_line=_PlayRecorder(),
            )
        )
        await asyncio.sleep(0.1)
        greet.cancel()
        try:
            await greet
        except asyncio.CancelledError:
            pass
        assert not key_task.done()  # the shield held; the build keeps its leg
        key_task.cancel()
        try:
            await key_task
        except asyncio.CancelledError:
            pass

    asyncio.run(main())


# ---------- _settle_early_greeting ----------

def test_settle_with_no_task_is_a_noop():
    asyncio.run(w._settle_early_greeting(None, {"attempted": False}))


def test_settle_cancels_an_unattempted_greeting():
    async def main():
        played = False

        async def play():
            nonlocal played
            await asyncio.sleep(30)
            played = True

        task = asyncio.ensure_future(play())
        await asyncio.sleep(0.05)
        await w._settle_early_greeting(task, {"attempted": False})
        assert task.cancelled() or task.done()
        return played

    assert asyncio.run(main()) is False


def test_settle_waits_for_an_attempted_line_to_finish():
    async def main():
        order = []

        async def play():
            await asyncio.sleep(0.3)
            order.append("line-finished")

        task = asyncio.ensure_future(play())
        await asyncio.sleep(0.05)
        await w._settle_early_greeting(task, {"attempted": True})
        order.append("notice-may-play")
        return order

    assert asyncio.run(main()) == ["line-finished", "notice-may-play"]


def test_settle_returns_promptly_when_attempted_line_already_done():
    async def main():
        async def play():
            return None

        task = asyncio.ensure_future(play())
        await task
        await asyncio.wait_for(
            w._settle_early_greeting(task, {"attempted": True}), timeout=2.0
        )

    asyncio.run(main())


# ---------- entrypoint source shape ----------

def test_entrypoint_launches_greeting_before_the_first_session_build():
    src = inspect.getsource(w.entrypoint)
    launch_at = src.index('early_greeting["task"] = asyncio.ensure_future(')
    # TASK-VOI-028: the build call now carries artifacts={...} on the next
    # line, so match the call head, not the old single-line form.
    built_at = src.index("session, agent = await _make_session(")
    start_at = src.index("await _start(session, agent)")
    assert launch_at < built_at < start_at
    # The handle is adopted into the shared live dict for
    # _greet_when_ready / the close path, exactly once.
    assert src.count('live["early_greeting_task"] = early_greeting["task"]') == 1


def test_entrypoint_settles_the_greeting_before_every_notice():
    src = inspect.getsource(w.entrypoint)
    settle = 'await _settle_early_greeting(early_greeting["task"], greeting_state)'
    announce = "await _announce_unavailable(ctx.room)"
    assert src.count(settle) == 2
    assert src.count(announce) == 2
    # Each settle immediately precedes its branch's announce.
    first_settle = src.index(settle)
    first_announce = src.index(announce)
    second_settle = src.index(settle, first_settle + 1)
    second_announce = src.index(announce, first_announce + 1)
    assert first_settle < first_announce < second_settle < second_announce
