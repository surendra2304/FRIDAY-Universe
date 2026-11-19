"""TASK-FRD-030: live activity frames must carry `recorded_at` first-class.

TASK-FRD-029 gave AutonomousActionLog a full ISO-8601 `recorded_at` and
shipped it in the get_status() seed payload (recent_actions), but the LIVE
path never got the field:

- the broadcast frame built in AutonomousController._log_action sends the
  instant only under the key `timestamp`;
- the /api/ws/activity connect backlog built in server.py collapses the
  instant into `timestamp` as `entry.recorded_at or entry.timestamp`, so
  for any entry whose recorded_at is empty (every entry persisted before
  FRD-029 — the whole production history when the fix deployed) the frame
  carries the bare "%H:%M:%S" time-of-day string, which the dashboard's
  clock renderer cannot parse;
- the dashboard's live-append handler reads only `frame.timestamp` (the
  ActivityFrame type did not even declare `recorded_at`).

Net effect, seen on the rendered page 2026-11-19 ~18:06 IST: activity rows
that arrive over the socket render no time at all, while the same history
seeded through get_status() carries a usable recorded_at. These tests pin
the frame shapes — the actual payloads the browser receives — so the live
path cannot silently lose the field again.
"""

import asyncio
from datetime import datetime

import pytest
from starlette.websockets import WebSocketDisconnect

from friday.api import activity_stream
from friday.autonomous import controller as controller_module


@pytest.fixture()
def fresh_controller(tmp_path):
    controller = controller_module.AutonomousController()
    saved_history = controller.action_history
    saved_activity = controller._agent_activity
    saved_path = controller._history_path
    controller.action_history = []
    controller._agent_activity = {}
    controller._history_path = tmp_path / "autonomous_action_history.json"
    try:
        yield controller
    finally:
        controller.action_history = saved_history
        controller._agent_activity = saved_activity
        controller._history_path = saved_path


class _FakeWebSocket:
    """Minimal socket double: records what the server pushes to it."""

    def __init__(self) -> None:
        self.headers: dict[str, str] = {}
        self.sent: list[dict] = []
        self.accepted = False

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)

    async def receive_json(self) -> dict:
        raise WebSocketDisconnect(code=1000)

    async def close(self, code: int = 1000, reason: str = "") -> None:
        pass


def _parseable_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    assert parsed.tzinfo is not None, "recorded_at must carry a timezone"
    return parsed


def test_live_broadcast_frame_carries_recorded_at(fresh_controller):
    """The fire-and-forget broadcast for a freshly recorded action must
    carry the entry's recorded_at as its own field — the same instant the
    entry itself recorded (one captured instant, not a second clock read
    that can drift from the persisted entry)."""
    ws = _FakeWebSocket()

    async def scenario() -> None:
        activity_stream.register(ws)
        try:
            fresh_controller.record_agent_action(
                "INFERENCE", "Execute planned actions", "done", True
            )
            # emit() is fire-and-forget: let the scheduled broadcast run.
            await asyncio.sleep(0.2)
        finally:
            activity_stream.unregister(ws)

    asyncio.run(scenario())

    assert len(ws.sent) == 1
    frame = ws.sent[0]
    entry = fresh_controller.action_history[-1]
    assert frame["type"] == "activity"
    assert frame["agent"] == "INFERENCE"
    assert "recorded_at" in frame, "live frame must carry recorded_at first-class"
    assert frame["recorded_at"] == entry.recorded_at
    _parseable_iso(frame["recorded_at"])


def test_backlog_frame_carries_recorded_at(fresh_controller):
    """The /api/ws/activity connect backlog — the frames that populate the
    dashboard log on page load, appended through the live handler — must
    ship each entry's recorded_at as its own field, exactly like the
    get_status() seed payload does."""
    from friday.api import server as server_module

    fresh_controller.record_agent_action(
        "INFERENCE", "Analyze goal and gather context", "ok", True
    )
    entry = fresh_controller.action_history[-1]

    ws = _FakeWebSocket()
    asyncio.run(server_module.activity_ws_endpoint(ws))

    assert ws.accepted
    frames = [f for f in ws.sent if f.get("type") == "activity"]
    assert len(frames) == 1
    frame = frames[0]
    assert frame["directive"] == "Analyze goal and gather context"
    assert "recorded_at" in frame, "backlog frame must carry recorded_at first-class"
    assert frame["recorded_at"] == entry.recorded_at
    _parseable_iso(frame["recorded_at"])


def test_backlog_frame_for_legacy_entry_carries_blank_recorded_at(fresh_controller):
    """A pre-FRD-029 entry has no recorded instant: the backlog frame must
    still carry the field (honestly empty — no invented time), so the
    dashboard's live handler prefers it and renders no time, exactly as
    the seed path does for the same entry."""
    from friday.api import server as server_module

    legacy = controller_module.AutonomousActionLog(
        timestamp="18:02:11",
        action_type="AGENT_CONTROL",
        target="INFERENCE",
        directive="Plan execution approach",
        result="ok",
        success=True,
    )
    assert legacy.recorded_at == ""
    fresh_controller.action_history.append(legacy)

    ws = _FakeWebSocket()
    asyncio.run(server_module.activity_ws_endpoint(ws))

    frames = [f for f in ws.sent if f.get("type") == "activity"]
    assert len(frames) == 1
    frame = frames[0]
    assert "recorded_at" in frame, "even a legacy entry's frame must carry the field"
    assert frame["recorded_at"] == ""
    # The legacy `timestamp` fallback is unchanged for other consumers.
    assert frame["timestamp"] == "18:02:11"


def test_live_and_seed_payloads_agree_on_recorded_at(fresh_controller):
    """The same entry must present the same recorded_at on both payload
    paths — live backlog frame and get_status() recent_actions — so the
    dashboard renders the same time no matter which path delivered it."""
    from friday.api import server as server_module

    fresh_controller.record_agent_action(
        "INFERENCE", "Execute planned actions", "done", True
    )
    entry = fresh_controller.action_history[-1]

    ws = _FakeWebSocket()
    asyncio.run(server_module.activity_ws_endpoint(ws))
    frame = [f for f in ws.sent if f.get("type") == "activity"][0]

    seed_row = fresh_controller.get_status()["recent_actions"][0]
    assert seed_row["recorded_at"] == entry.recorded_at
    assert frame["recorded_at"] == seed_row["recorded_at"]
