"""TASK-IG-LAP-01 — Android UI automation tests.

Three layers, zero hardware (the LAP-001 harness pattern):

* the ADB executor (``scripts/phone_ui_agent_adb.py``) driven through a
  fake ``adb`` runner — every protocol command is checked against the
  exact argv it should produce;
* the planner loop (``friday.remote.phone_ui_agent``) driven through a
  fake bridge + scripted decider, including the code-level safety gates;
* the two tools, with the bridge singleton and decider factory stubbed.
"""

from __future__ import annotations

import base64
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.remote.phone_bridge import ALLOWED_PHONE_COMMANDS  # noqa: E402
from friday.remote.phone_ui_agent import (  # noqa: E402
    parse_decision,
    run_ui_task,
    validate_action,
)

_SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "phone_ui_agent_adb.py"
_spec = importlib.util.spec_from_file_location("phone_ui_agent_adb", _SCRIPT_PATH)
_adb_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_adb_mod)

AdbClient = _adb_mod.AdbClient
PhoneUiExecutor = _adb_mod.PhoneUiExecutor
escape_input_text = _adb_mod.escape_input_text
prune_ui_xml = _adb_mod.prune_ui_xml

_PNG_BYTES = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)

_SETTINGS_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="" class="android.widget.FrameLayout"
        package="com.android.settings" bounds="[0,0][1080,2400]" clickable="false" focusable="false">
    <node index="0" text="Battery" resource-id="android:id/title"
          class="android.widget.TextView" package="com.android.settings"
          bounds="[100,400][700,500]" clickable="true" focusable="true" focused="false" password="false"/>
    <node index="1" text="Display" resource-id="android:id/title"
          class="android.widget.TextView" package="com.android.settings"
          bounds="[100,520][700,620]" clickable="true" focusable="true" focused="false" password="false"/>
    <node index="2" text="" resource-id="" class="android.widget.LinearLayout"
          package="com.android.settings" bounds="[0,0][10,10]" clickable="false" focusable="false"/>
  </node>
</hierarchy>
"""

_PASSWORD_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="" resource-id="com.example:id/password"
        class="android.widget.EditText" package="com.example.app"
        bounds="[100,400][900,500]" clickable="true" focusable="true" focused="true" password="true"/>
</hierarchy>
"""

_BANK_XML = """<?xml version="1.0" encoding="UTF-8"?>
<hierarchy rotation="0">
  <node index="0" text="Account balance" resource-id="com.hdfcbank.mobilebanking:id/bal"
        class="android.widget.TextView" package="com.hdfcbank.mobilebanking"
        bounds="[100,400][900,500]" clickable="false" focusable="false" focused="false" password="false"/>
</hierarchy>
"""


# ---------------------------------------------------------------------------
# Fake ADB
# ---------------------------------------------------------------------------


class FakeAdbRunner:
    """Records argv and answers like a friendly attached phone."""

    def __init__(self, xml: str = _SETTINGS_XML, devices: bytes | None = None) -> None:
        self.calls: list[list[str]] = []
        self.xml = xml
        self.devices = devices if devices is not None else (
            b"List of devices attached\nemulator-5554\tdevice\n"
        )

    def __call__(self, argv: list[str], timeout: float) -> tuple[int, bytes, bytes]:
        self.calls.append(list(argv))
        joined = " ".join(argv)
        if argv[1:2] == ["devices"] or argv[-1] == "devices":
            return 0, self.devices, b""
        if "getprop" in argv:
            if "ro.product.model" in argv:
                return 0, b"Pixel 8\n", b""
            return 0, b"15\n", b""
        if "screencap" in argv:
            return 0, _PNG_BYTES, b""
        if "uiautomator" in argv:
            return 0, b"UI hierchary dumped to: /sdcard/window_dump.xml\n", b""
        if "window_dump.xml" in joined and "cat" in argv:
            return 0, self.xml.encode(), b""
        if "dumpsys" in argv and "battery" in argv:
            return 0, b"  level: 76\n  status: 2\n", b""
        if "wm" in argv:
            return 0, b"Physical size: 1080x2400\n", b""
        if "dumpsys" in argv and "window" in argv:
            return 0, b"mCurrentFocus=Window{abc u0 com.android.settings/.Settings}\n", b""
        if "monkey" in argv:
            return 0, b"Events injected: 1\n", b""
        return 0, b"", b""

    def argv_with(self, *needles: str) -> list[str] | None:
        for call in self.calls:
            if all(any(n in part for part in call) for n in needles):
                return call
        return None


def _executor(xml: str = _SETTINGS_XML) -> tuple[PhoneUiExecutor, FakeAdbRunner]:
    runner = FakeAdbRunner(xml=xml)
    return PhoneUiExecutor(AdbClient(runner=runner)), runner


# ---------------------------------------------------------------------------
# Executor behaviour
# ---------------------------------------------------------------------------


def test_ui_dump_is_an_allowed_bridge_command():
    assert "ui_dump" in ALLOWED_PHONE_COMMANDS


def test_executor_tap_produces_input_tap():
    executor, runner = _executor()
    ok, output, error = executor.handle("tap", {"x": 400, "y": 450})
    assert ok and error is None
    call = runner.argv_with("input", "tap")
    assert call is not None and call[-2:] == ["400", "450"]


def test_executor_swipe_and_press_key():
    executor, runner = _executor()
    ok, _, _ = executor.handle("swipe", {"x1": 500, "y1": 1400, "x2": 500, "y2": 500})
    assert ok
    assert runner.argv_with("input", "swipe") is not None
    ok, output, _ = executor.handle("press_key", {"key": "back"})
    assert ok and "4" in output
    assert runner.argv_with("keyevent", "4") is not None
    ok, _, error = executor.handle("press_key", {"key": "definitely-not-a-key"})
    assert not ok and "unknown key" in (error or "")


def test_executor_type_text_escapes_for_device_shell():
    executor, runner = _executor()
    ok, output, _ = executor.handle("type_text", {"text": "hello world & friends"})
    assert ok and "typed 21 characters" in output
    call = runner.argv_with("input", "text")
    assert call is not None
    typed_arg = call[-1]
    assert " " not in typed_arg and "%s" in typed_arg and "\\&" in typed_arg


def test_executor_screenshot_returns_base64_png():
    executor, _ = _executor()
    ok, output, _ = executor.handle("screenshot", {})
    assert ok
    assert base64.b64decode(output) == _PNG_BYTES


def test_executor_ui_dump_prunes_layout_and_flags_password():
    executor, _ = _executor()
    ok, payload, _ = executor.handle("ui_dump", {})
    assert ok
    labels = [n["text"] for n in payload["nodes"]]
    assert labels == ["Battery", "Display"]  # the empty layout node is pruned
    battery = payload["nodes"][0]
    assert battery["center"] == [400, 450] and battery["clickable"] is True

    executor2, _ = _executor(xml=_PASSWORD_XML)
    ok, payload2, _ = executor2.handle("ui_dump", {})
    assert ok and payload2["nodes"][0]["password"] is True
    assert payload2["nodes"][0]["focused"] is True


def test_executor_open_app_uses_friendly_alias():
    executor, runner = _executor()
    ok, output, _ = executor.handle("open_app", {"app": "YouTube"})
    assert ok and "com.google.android.youtube" in output
    assert runner.argv_with("monkey", "com.google.android.youtube") is not None


def test_executor_rejects_bad_coordinates_and_unknown_command():
    executor, _ = _executor()
    ok, _, error = executor.handle("tap", {"x": -5, "y": 10})
    assert not ok and "out of range" in (error or "")
    ok, _, error = executor.handle("make_call", {"number": "123"})
    assert not ok and "does not serve" in (error or "")


def test_executor_reports_missing_adb_honestly():
    def dead_runner(argv: list[str], timeout: float) -> tuple[int, bytes, bytes]:
        return -1, b"", b"not found"

    executor = PhoneUiExecutor(AdbClient(runner=dead_runner))
    ok, _, error = executor.handle("device_status", {})
    assert not ok and "platform-tools" in (error or "")


def test_escape_input_text_rules():
    assert escape_input_text("a b") == "a%sb"
    assert escape_input_text("100%") == "100\\%"
    assert escape_input_text('say "hi"') == 'say%s\\"hi\\"'


def test_prune_ui_xml_truncation_flag():
    many = "".join(
        f'<node text="Item {i}" resource-id="id/{i}" class="android.widget.TextView" '
        f'package="com.example" bounds="[0,{i}][10,{i + 5}]" clickable="true" focusable="false"/>'
        for i in range(150)
    )
    payload = prune_ui_xml(f"<hierarchy>{many}</hierarchy>")
    assert payload["count"] == 150 and payload["truncated"] is True
    assert len(payload["nodes"]) == 120


# ---------------------------------------------------------------------------
# Planner loop
# ---------------------------------------------------------------------------


class FakeBridge:
    """execute_sync-shaped fake serving scripted screens."""

    def __init__(self, screens: list[dict[str, Any]]) -> None:
        self.screens = screens
        self.screen_index = 0
        self.executed: list[tuple[str, dict[str, Any]]] = []

    def execute_sync(self, device_id: str, command: str, timeout: float = 30.0,
                     args: dict[str, Any] | None = None) -> dict[str, Any]:
        args = args or {}
        if command == "ui_dump":
            screen = self.screens[min(self.screen_index, len(self.screens) - 1)]
            return {"ok": True, "output": json.dumps(screen), "error": None}
        if command == "screenshot":
            return {"ok": True, "output": base64.b64encode(_PNG_BYTES).decode(), "error": None}
        self.executed.append((command, args))
        if command in {"tap", "open_app"} and self.screen_index < len(self.screens) - 1:
            self.screen_index += 1
        return {"ok": True, "output": f"{command} done", "error": None}


def _settings_screen() -> dict[str, Any]:
    return prune_ui_xml(_SETTINGS_XML)


def _battery_screen() -> dict[str, Any]:
    xml = _SETTINGS_XML.replace("Battery", "Battery level 76 percent")
    return prune_ui_xml(xml)


def test_planner_completes_battery_instruction():
    bridge = FakeBridge([_settings_screen(), _battery_screen()])
    seen_steps = []

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        seen_steps.append(observation["step"])
        labels = [n.get("text", "") for n in observation["nodes"]]
        if any("level" in label for label in labels):
            return {"action": "done", "note": "Battery level is 76 percent."}
        for index, node in enumerate(observation["nodes"]):
            if node.get("text") == "Battery":
                return {"action": "tap", "node": index}
        return {"action": "fail", "note": "no Battery node"}

    result = run_ui_task(bridge, "phone-1", "open Settings and tell me the battery level",
                         decide, ocr_fn=lambda b: "")
    assert result["ok"] and result["stop_reason"] == "done"
    assert result["summary"] == "Battery level is 76 percent."
    tap = [a for a in bridge.executed if a[0] == "tap"]
    assert tap and tap[0][1] == {"x": 400, "y": 450}  # Battery node centre


def test_planner_refuses_password_field_typing():
    bridge = FakeBridge([prune_ui_xml(_PASSWORD_XML)])
    result = run_ui_task(
        bridge, "phone-1", "sign in to the app",
        lambda obs: {"action": "type_text", "text": "hunter2"},
        ocr_fn=lambda b: "",
    )
    assert not result["ok"] and result["stop_reason"] == "refused"
    assert bridge.executed == []  # nothing was typed


def test_planner_stops_in_banking_app():
    bridge = FakeBridge([prune_ui_xml(_BANK_XML)])
    result = run_ui_task(
        bridge, "phone-1", "check my balance",
        lambda obs: {"action": "tap", "node": 0},
        ocr_fn=lambda b: "",
    )
    assert not result["ok"] and result["stop_reason"] == "refused"
    assert bridge.executed == []


def test_planner_refuses_credential_instruction_upfront():
    bridge = FakeBridge([_settings_screen()])
    result = run_ui_task(
        bridge, "phone-1", "type my password into the form",
        lambda obs: {"action": "done", "note": "x"},
        ocr_fn=lambda b: "",
    )
    assert not result["ok"] and result["stop_reason"] == "refused"
    assert bridge.executed == []


def test_planner_two_bad_decisions_end_task():
    bridge = FakeBridge([_settings_screen()])
    result = run_ui_task(
        bridge, "phone-1", "do something",
        lambda obs: {"action": "teleport"},
        ocr_fn=lambda b: "",
    )
    assert not result["ok"] and result["stop_reason"] == "fail"
    assert bridge.executed == []


def test_planner_step_budget_is_a_failure_not_success():
    bridge = FakeBridge([_settings_screen()])
    result = run_ui_task(
        bridge, "phone-1", "wait forever",
        lambda obs: {"action": "wait", "seconds": 0},
        max_steps=3, ocr_fn=lambda b: "", sleep_fn=lambda s: None,
    )
    assert not result["ok"] and result["stop_reason"] == "max_steps"
    assert len(result["steps"]) == 3


def test_parse_decision_variants():
    assert parse_decision('{"action": "done", "note": "ok"}')["action"] == "done"
    assert parse_decision('```json\n{"action": "wait", "seconds": 1}\n```')["action"] == "wait"
    assert parse_decision('Sure! {"action": "fail", "note": "no"}')['action'] == "fail"
    with pytest.raises(ValueError):
        parse_decision("no json here")
    with pytest.raises(ValueError):
        parse_decision('{"action": "fly"}')
    with pytest.raises(ValueError):
        parse_decision("")


def test_validate_action_node_resolution_and_ranges():
    observation = _settings_screen()
    plan = validate_action({"action": "tap", "node": 0}, observation)
    assert plan == {"command": "tap", "args": {"x": 400, "y": 450}}
    with pytest.raises(ValueError):
        validate_action({"action": "tap", "node": 99}, observation)
    with pytest.raises(ValueError):
        validate_action({"action": "type_text", "text": ""}, observation)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


def test_phone_ui_dump_tool_renders_nodes(monkeypatch):
    from friday.tools.builtin import phone_ui_control

    bridge = FakeBridge([_settings_screen()])
    monkeypatch.setattr(phone_ui_control, "phone_bridge", bridge)
    tool = phone_ui_control.PhoneUiDumpTool()
    result = tool.execute(device_id="phone-1")
    assert not result.is_error
    assert "Battery" in result.content and "Display" in result.content


def test_phone_ui_task_tool_runs_loop(monkeypatch):
    from friday.tools.builtin import phone_ui_control

    bridge = FakeBridge([_settings_screen(), _battery_screen()])
    monkeypatch.setattr(phone_ui_control, "phone_bridge", bridge)

    def decide(observation: dict[str, Any]) -> dict[str, Any]:
        labels = [n.get("text", "") for n in observation["nodes"]]
        if any("level" in label for label in labels):
            return {"action": "done", "note": "Battery level is 76 percent."}
        return {"action": "tap", "node": 0}

    monkeypatch.setattr(phone_ui_control, "make_llm_decider", lambda: decide)
    tool = phone_ui_control.PhoneUiTaskTool()
    assert tool.safety_level is not None and str(tool.safety_level).upper().endswith("SENSITIVE")
    result = tool.execute(instruction="tell me the battery level", device_id="phone-1")
    assert not result.is_error
    assert "76 percent" in result.content
