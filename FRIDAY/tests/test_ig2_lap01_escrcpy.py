"""TASK-IG2-LAP-01 — Escrcpy integration tests (no hardware, no GUI)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.remote.escrcpy_integration import (  # noqa: E402
    AutomationScript, EscrcpyError, MirrorProfile, build_launch_args,
    install_guidance, parse_adb_devices, render_adb_commands, usable_devices)
from friday.tools.builtin.escrcpy_control import (  # noqa: E402
    EscrcpyAutomationTool, EscrcpyLaunchPlanTool)


def test_gui_launch_defaults_to_escrcpy_binary():
    assert build_launch_args(MirrorProfile()) == ["escrcpy"]


def test_scrcpy_launch_carries_validated_options():
    argv = build_launch_args(
        MirrorProfile(serial="emulator-5554", max_size=1024, bit_rate=4_000_000,
                      max_fps=30, turn_screen_off=True), gui=False)
    assert argv[0] == "scrcpy" and "--max-size" in argv and "1024" in argv
    assert "--turn-screen-off" in argv


def test_launch_rejects_unsafe_serial_and_bad_size():
    with pytest.raises(EscrcpyError):
        build_launch_args(MirrorProfile(serial="x; rm -rf /"), gui=False)
    with pytest.raises(EscrcpyError):
        build_launch_args(MirrorProfile(max_size=999), gui=False)


def test_parse_adb_devices_and_usable_filter():
    text = "List of devices attached\nemulator-5554\tdevice\nabc123\tunauthorized\n"
    devices = parse_adb_devices(text)
    assert devices == [{"serial": "emulator-5554", "state": "device"},
                       {"serial": "abc123", "state": "unauthorized"}]
    assert usable_devices(text) == ["emulator-5554"]


def test_automation_renders_tap_type_wait_to_adb():
    script = AutomationScript.from_dict({"name": "demo", "steps": [
        {"kind": "tap", "x": 10, "y": 20},
        {"kind": "type", "text": "hello world"},
        {"kind": "wait", "seconds": 2},
        {"kind": "press_key", "key": "BACK"},
    ]})
    cmds = render_adb_commands(script, serial="emulator-5554")
    assert cmds[0][-4:] == ["input", "tap", "10", "20"]
    assert cmds[1][-1] == "hello%sworld"
    assert cmds[2] == ["sleep", "2.0"] or cmds[2] == ["sleep", "2"]
    assert cmds[3][-1] == "KEYCODE_BACK"


def test_automation_refuses_credentials_and_blocked_packages():
    with pytest.raises(EscrcpyError):
        AutomationScript.from_dict({"name": "bad", "steps": [
            {"kind": "type", "text": "my password is x"}]})
    with pytest.raises(EscrcpyError):
        AutomationScript.from_dict({"name": "bad", "steps": [
            {"kind": "tap", "x": 1, "y": 1, "package": "com.example.bank"}]})


def test_install_guidance_excludes_paid_extension():
    guide = install_guidance("windows")
    assert "EscrcpyX" in guide["licence"] and "NOT installed" in guide["licence"]
    assert "github.com/viarotel-org/escrcpy" in guide["source"]


def test_tools_plan_and_automation_and_refusal():
    plan = EscrcpyLaunchPlanTool().execute(serial="emulator-5554")
    assert not plan.is_error and "escrcpy" in plan.content
    ok = EscrcpyAutomationTool().execute(
        script={"name": "s", "steps": [{"kind": "wait", "seconds": 1}]})
    assert not ok.is_error and ok.metadata["steps"] == 1
    bad = EscrcpyAutomationTool().execute(
        script={"name": "s", "steps": [{"kind": "type", "text": "otp 123456"}]})
    assert bad.is_error and bad.refused
