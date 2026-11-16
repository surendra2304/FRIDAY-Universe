"""TASK-VOI-011: the session-build overlap + early greeting contract.

Production segmentation (2026-11-16) priced the serial pieces of
key-to-session-started at: model + AgentSession construction 1.1–5.1 s
(purely local, needs the key + instructions but NOT the room) plus a
5–19 s tail inside sess.start(). The fixed-line greeting needs only
the room — it publishes the shipped WAV on its own track — never the
session. These tests pin the restructure that exploits both facts:

- ``_early_greeting_warranted``: the early line may start only when
  the greeting is enabled, the Gemini Live plugin exists, and a
  probe-verified key is in hand. Otherwise the job takes the
  recorded-notice path, which must keep its exact pre-VOI-011 shape
  (no greeting before the notice).
- ``_new_greeting_state``: the fixed line is attempted exactly once
  per job, whichever path (early task / post-start fallback) runs.
- ``_wait_for_remote_participant``: bounded, and room-state read
  errors count as 'present' (the greeting path's long-standing
  best-effort semantics).
- Entrypoint source shape: the build task is created BEFORE
  ``ctx.connect()`` is awaited, and the early greeting launches
  BEFORE ``sess.start()`` — a refactor must not silently
  re-serialise the build behind the connect or the greeting behind
  the session start.
"""
import asyncio
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.voice import livekit_worker as w  # noqa: E402


# ---------- _early_greeting_warranted ----------

def test_early_greeting_warranted_only_with_all_three():
    assert w._early_greeting_warranted(True, True, "key") is True
    assert w._early_greeting_warranted(False, True, "key") is False
    assert w._early_greeting_warranted(True, False, "key") is False
    assert w._early_greeting_warranted(True, True, None) is False
    assert w._early_greeting_warranted(True, True, "") is False
    assert w._early_greeting_warranted(False, False, None) is False


# ---------- _new_greeting_state ----------

def test_greeting_state_starts_unattempted_and_is_per_job():
    a = w._new_greeting_state()
    b = w._new_greeting_state()
    assert a == {"attempted": False, "played": False}
    a["attempted"] = True
    assert b["attempted"] is False  # no shared mutable state across jobs


# ---------- _wait_for_remote_participant ----------

class _FakeRoom:
    def __init__(self, participants=None, explode=False):
        self._participants = participants or {}
        self._explode = explode

    @property
    def remote_participants(self):
        if self._explode:
            raise RuntimeError("room state unreadable")
        return self._participants


def test_wait_for_participant_present_immediately():
    room = _FakeRoom({"owner-1": object()})
    assert asyncio.run(w._wait_for_remote_participant(room, timeout_s=1.0)) is True


def test_wait_for_participant_empty_room_times_out_false():
    room = _FakeRoom({})
    assert asyncio.run(
        w._wait_for_remote_participant(room, timeout_s=0.3, poll_s=0.05)
    ) is False


def test_wait_for_participant_read_errors_count_as_present():
    room = _FakeRoom(explode=True)
    assert asyncio.run(w._wait_for_remote_participant(room, timeout_s=1.0)) is True


def test_wait_for_participant_arriving_mid_wait():
    room = _FakeRoom({})

    async def main():
        async def arrive():
            await asyncio.sleep(0.15)
            room._participants["owner-1"] = object()

        task = asyncio.ensure_future(arrive())
        result = await w._wait_for_remote_participant(
            room, timeout_s=2.0, poll_s=0.05
        )
        await task
        return result

    assert asyncio.run(main()) is True


# ---------- entrypoint source shape ----------

def test_entrypoint_build_task_starts_before_the_connect():
    src = inspect.getsource(w.entrypoint)
    build_at = src.index("_build_task = asyncio.ensure_future(_build_first_session())")
    connect_at = src.index("await ctx.connect(")
    assert build_at < connect_at
    # The key + memory legs also start before the connect.
    assert src.index("_key_task = asyncio.ensure_future") < connect_at
    assert src.index("_memory_task = asyncio.ensure_future") < connect_at


def test_entrypoint_early_greeting_launches_before_session_start():
    src = inspect.getsource(w.entrypoint)
    launch_at = src.index('live["early_greeting_task"] = asyncio.create_task(')
    start_at = src.index("await _start(session, agent)")
    assert launch_at < start_at
    # …and only after every unavailable return: the notice path must
    # never be preceded by a greeting.
    assert src.rindex("await _announce_unavailable(ctx.room)") < launch_at


def test_greet_when_ready_respects_the_attempted_flag():
    src = inspect.getsource(w.entrypoint)
    greet_at = src.index("async def _greet_when_ready")
    close_at = src.index("async def _close_quietly")
    greet_src = src[greet_at:close_at]
    assert 'greeting_state["attempted"]' in greet_src
    # The warm realtime greeting still runs after the fixed-line step.
    assert "generate_reply" in greet_src


def test_close_cancels_the_early_greeting_task():
    src = inspect.getsource(w.entrypoint)
    assert '"early_greeting_task"' in src
    close_at = src.index("async def _close_session_when_empty")
    assert "early_greeting_task" in src[close_at:close_at + 1500]
