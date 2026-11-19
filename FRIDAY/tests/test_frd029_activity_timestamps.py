"""TASK-FRD-029: the autonomous action log must carry a real instant.

The dashboard's Activity Log showed "--:--:--" on every row: the only
timestamp the log recorded was a bare "%H:%M:%S" (no date), which the
UI's clock renderer cannot parse. The fix records a full ISO-8601
`recorded_at` on every entry and ships it in /api/autonomous/status
recent_actions (the /api/ws/activity backlog already preferred a
`recorded_at` attribute — it simply never existed). Entries persisted
before the fix load with recorded_at "" and render no time.
"""

import json
from datetime import datetime, timezone

import pytest

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


def test_log_action_records_full_iso_recorded_at(fresh_controller):
    before = datetime.now(timezone.utc)
    fresh_controller._log_action("AGENT_CONTROL", "STRATEX", "check the book", "ok", True)
    after = datetime.now(timezone.utc)

    entry = fresh_controller.action_history[-1]
    assert entry.recorded_at, "recorded_at must be populated at log time"
    parsed = datetime.fromisoformat(entry.recorded_at)
    assert parsed.tzinfo is not None
    assert before <= parsed <= after
    # The legacy bare time-of-day field stays for its other readers.
    assert entry.timestamp == parsed.strftime("%H:%M:%S")


def test_status_recent_actions_carry_recorded_at(fresh_controller):
    fresh_controller._log_action("SELF_REPAIR", "FRIDAY", "heal thyself", "done", True)

    status = fresh_controller.get_status()
    latest = status["recent_actions"][0]
    assert latest["recorded_at"] == fresh_controller.action_history[-1].recorded_at
    # It must be a string the dashboard's `new Date(...)` can parse —
    # i.e. a full ISO instant, not the bare "HH:MM:SS".
    assert datetime.fromisoformat(latest["recorded_at"]).tzinfo is not None
    assert latest["timestamp"] == fresh_controller.action_history[-1].timestamp


def test_recorded_at_survives_persist_and_reload(fresh_controller):
    fresh_controller._log_action("FAILOVER", "INFERENCE", "reroute", "rerouted", True)
    expected = fresh_controller.action_history[-1].recorded_at
    assert fresh_controller._history_path.is_file()

    fresh_controller.action_history = []
    fresh_controller._load_history()

    assert len(fresh_controller.action_history) == 1
    assert fresh_controller.action_history[0].recorded_at == expected


def test_legacy_history_without_recorded_at_loads_blank(fresh_controller):
    legacy = {
        "actions": [
            {
                "timestamp": "16:43:05",
                "action_type": "AGENT_CONTROL",
                "target": "STRATEX",
                "directive": "old entry",
                "result": "ok",
                "success": True,
                "details": {},
            }
        ],
        "agent_activity": {},
    }
    fresh_controller._history_path.write_text(json.dumps(legacy), encoding="utf-8")

    fresh_controller._load_history()

    assert len(fresh_controller.action_history) == 1
    # No invented instant: the UI renders no time for such an entry.
    assert fresh_controller.action_history[0].recorded_at == ""
