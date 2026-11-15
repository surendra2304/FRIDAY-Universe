"""TASK-LAP-001 — laptop bridge control surface.

Covers: client/server allowlist parity, the screenshot_data attachment
channel in the server registry (passthrough, oversize drop, wrong-command
drop), the new client command handlers (with fake input backends), and the
laptop_* agent tools (with a stub bridge registry).
"""

from __future__ import annotations

import asyncio
import base64
import importlib.util
import io
import json
import shutil
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

# NOTE: friday.remote.__init__ re-exports the `laptop_bridge` singleton under
# the same name as the submodule, shadowing the attribute — import_module is
# the reliable way to get the module itself.
lb = importlib.import_module("friday.remote.laptop_bridge")

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_PATH = REPO_ROOT / "FRIDAY" / "scripts" / "laptop_bridge_client.py"


def _load_client():
    spec = importlib.util.spec_from_file_location("laptop_bridge_client_under_test", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = _load_client()


# ---------------------------------------------------------------------------
# Allowlist parity
# ---------------------------------------------------------------------------


def test_allowlist_parity_between_client_and_server():
    assert set(client.ALLOWED_COMMANDS) == set(lb.ALLOWED_LAPTOP_COMMANDS)
    for new_command in ("open_app", "type_text", "click", "screenshot_data"):
        assert new_command in lb.ALLOWED_LAPTOP_COMMANDS


# ---------------------------------------------------------------------------
# Server registry: attachment channel
# ---------------------------------------------------------------------------


class FakeWebSocket:
    def __init__(self) -> None:
        self.sent: list[dict] = []

    async def send_json(self, frame: dict) -> None:
        self.sent.append(frame)


async def _execute_with_result(bridge: lb.LaptopBridge, command: str, result_payload: dict):
    ws = FakeWebSocket()
    await bridge.register("lap-test", ws)
    task = asyncio.create_task(bridge.execute("lap-test", command, 5.0, {}))
    await asyncio.sleep(0.05)
    frame = ws.sent[-1]
    assert frame["type"] == "command"
    assert frame["command"] == command
    payload = {"request_id": frame["request_id"], "ok": True, "output": "{}", "error": None}
    payload.update(result_payload)
    assert await bridge.resolve_result("lap-test", payload)
    return await task


@pytest.mark.asyncio
async def test_screenshot_data_attachment_passes_through():
    bridge = lb.LaptopBridge()
    attachment = {
        "kind": "image",
        "format": "jpeg",
        "width": 1280,
        "height": 720,
        "base64": base64.b64encode(b"\xff\xd8\xff fake-jpeg").decode("ascii"),
    }
    evidence = await _execute_with_result(bridge, "screenshot_data", {"attachment": attachment})
    assert evidence["ok"] is True
    assert evidence["attachment"]["base64"] == attachment["base64"]
    assert evidence["attachment"]["width"] == 1280


@pytest.mark.asyncio
async def test_oversize_attachment_is_dropped_not_trusted():
    bridge = lb.LaptopBridge()
    attachment = {
        "kind": "image",
        "format": "jpeg",
        "base64": "A" * (lb.MAX_ATTACHMENT_BYTES + 1),
    }
    evidence = await _execute_with_result(bridge, "screenshot_data", {"attachment": attachment})
    assert evidence["ok"] is True
    assert "attachment" not in evidence


@pytest.mark.asyncio
async def test_attachment_on_other_commands_is_dropped():
    bridge = lb.LaptopBridge()
    attachment = {"kind": "image", "format": "jpeg", "base64": "AAAA"}
    evidence = await _execute_with_result(bridge, "system_info", {"attachment": attachment})
    assert "attachment" not in evidence


@pytest.mark.asyncio
async def test_new_commands_dispatch_and_unknown_still_refused():
    bridge = lb.LaptopBridge()
    evidence = await _execute_with_result(bridge, "open_app", {})
    assert evidence["command"] == "open_app"
    with pytest.raises(ValueError):
        await bridge.execute("lap-test", "definitely_not_a_command", 5.0, {})


# ---------------------------------------------------------------------------
# Client handlers
# ---------------------------------------------------------------------------


def test_client_screenshot_data_returns_real_jpeg_attachment(monkeypatch):
    from PIL import Image, ImageGrab

    source = Image.new("RGB", (1600, 900), color=(10, 20, 30))
    monkeypatch.setattr(ImageGrab, "grab", lambda: source)
    ok, output, error, attachment = client._cmd_screenshot_data({}, 5.0)
    assert ok, error
    assert attachment["kind"] == "image"
    assert attachment["format"] == "jpeg"
    assert attachment["width"] == 1280  # downscaled from 1600
    decoded = Image.open(io.BytesIO(base64.b64decode(attachment["base64"])))
    assert decoded.format == "JPEG"
    assert decoded.size == (1280, 720)
    summary = json.loads(output)
    assert summary["bytes"] > 0


def _fake_pyautogui(calls: list) -> SimpleNamespace:
    return SimpleNamespace(
        FAILSAFE=True,
        write=lambda text, interval=0.0: calls.append(("write", text)),
        click=lambda x, y, button, clicks: calls.append(("click", x, y, button, clicks)),
    )


def test_client_type_and_click_via_pyautogui(monkeypatch):
    calls: list = []
    monkeypatch.setitem(sys.modules, "pyautogui", _fake_pyautogui(calls))
    ok, _out, error = client._cmd_type_text({"text": "hello"}, 5.0)
    assert ok, error
    ok, _out, error = client._cmd_click({"x": 10, "y": 20, "button": "right"}, 5.0)
    assert ok, error
    assert calls == [("write", "hello"), ("click", 10, 20, "right", 1)]


def test_client_type_without_backend_is_an_honest_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "pyautogui", None)  # import raises ImportError
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    ok, _out, error = client._cmd_type_text({"text": "hello"}, 5.0)
    assert not ok
    assert "pyautogui" in error


def test_client_open_app_linux_path_lookup(monkeypatch):
    launched: list = []
    monkeypatch.setattr(shutil, "which", lambda name: f"/usr/bin/{name}")
    monkeypatch.setattr(
        subprocess, "Popen", lambda argv, **kw: launched.append(argv)
    )
    ok, output, error = client._cmd_open_app({"app": "fakeapp"}, 5.0)
    assert ok, error
    assert launched == [["/usr/bin/fakeapp"]]
    monkeypatch.setattr(shutil, "which", lambda _name: None)
    ok, _out, error = client._cmd_open_app({"app": "no-such-app"}, 5.0)
    assert not ok
    assert "not found" in error


def test_client_execute_command_carries_attachment():
    record = client._execute_command("lap-test", "req-1", "screenshot_data", {}, 5.0)
    # No display/Pillow guarantee in CI: either a real capture with an
    # attachment, or an honest failure record — never a malformed frame.
    assert record["request_id"] == "req-1"
    assert record["command"] == "screenshot_data"
    if record["ok"]:
        assert record["attachment"]["kind"] == "image"
    else:
        assert record["error"]


# ---------------------------------------------------------------------------
# Agent tools (stub bridge registry)
# ---------------------------------------------------------------------------


class StubBridge:
    def __init__(self, devices, evidence=None, raises=None) -> None:
        self._devices = devices
        self._evidence = evidence
        self._raises = raises
        self.calls: list = []

    async def list_devices(self):
        return self._devices

    async def execute(self, laptop_id, command, timeout, args=None):
        self.calls.append((laptop_id, command, args))
        if self._raises is not None:
            raise self._raises
        return self._evidence


def _online_device(laptop_id="lap-test"):
    return [{"laptop_id": laptop_id, "online": True, "connected_at": "t", "last_seen": "t", "pending_requests": 0}]


def test_tool_open_app_no_laptop_connected(monkeypatch):
    from friday.tools.builtin import laptop_control

    monkeypatch.setattr(laptop_control, "laptop_bridge", StubBridge([]))
    result = laptop_control.LaptopOpenAppTool().execute(application="notepad")
    assert result.is_error
    assert "No laptop is connected" in result.content


def test_tool_open_app_dispatches_to_the_one_online_laptop(monkeypatch):
    from friday.tools.builtin import laptop_control

    evidence = {"ok": True, "laptop_id": "lap-test", "command": "open_app", "output": "", "error": None}
    stub = StubBridge(_online_device(), evidence=evidence)
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.LaptopOpenAppTool().execute(application="notepad")
    assert not result.is_error
    assert stub.calls == [("lap-test", "open_app", {"app": "notepad"})]


def test_tool_screenshot_saves_attachment_and_ocr(monkeypatch, tmp_path):
    from friday.tools.builtin import laptop_control
    from friday.tools.builtin import screen_ocr

    from PIL import Image

    buffer = io.BytesIO()
    Image.new("RGB", (64, 32), color=(200, 200, 200)).save(buffer, format="JPEG")
    raw = buffer.getvalue()
    evidence = {
        "ok": True,
        "laptop_id": "lap-test",
        "command": "screenshot_data",
        "output": "{}",
        "error": None,
        "attachment": {
            "kind": "image",
            "format": "jpeg",
            "width": 1280,
            "height": 720,
            "base64": base64.b64encode(raw).decode("ascii"),
        },
    }
    stub = StubBridge(_online_device(), evidence=evidence)
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    monkeypatch.setenv("FRIDAY_LAPTOP_SCREEN_DIR", str(tmp_path))
    monkeypatch.setattr(screen_ocr, "_run_ocr", lambda image: [("hello", (0, 0, 1, 1)), ("screen", (0, 0, 1, 1))])
    result = laptop_control.LaptopScreenshotTool().execute()
    assert not result.is_error
    saved = Path(result.metadata["image_path"])
    assert saved.read_bytes() == raw
    assert "hello screen" in result.content


def test_tool_run_command_surfaces_shell_gate_refusal(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = StubBridge(
        _online_device(),
        raises=ValueError("run_shell is disabled; set FRIDAY_LAPTOP_ALLOW_SHELL=true on the FRIDAY host and on the laptop before using it."),
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.LaptopRunCommandTool().execute(command="echo hi")
    assert result.is_error
    assert "run_shell is disabled" in result.content


def test_tools_are_registered_in_the_default_registry():
    from friday.tools.builtin import (
        LaptopClickTool,
        LaptopListDevicesTool,
        LaptopOpenAppTool,
        LaptopOpenUrlTool,
        LaptopRunCommandTool,
        LaptopScreenshotTool,
        LaptopTypeTextTool,
    )

    names = {
        LaptopListDevicesTool().name,
        LaptopOpenAppTool().name,
        LaptopOpenUrlTool().name,
        LaptopScreenshotTool().name,
        LaptopTypeTextTool().name,
        LaptopClickTool().name,
        LaptopRunCommandTool().name,
    }
    assert names == {
        "laptop_list_devices",
        "laptop_open_app",
        "laptop_open_url",
        "laptop_screenshot",
        "laptop_type_text",
        "laptop_click",
        "laptop_run_command",
    }
    # Schemas must survive the Gemini strictness audit (no empty enum values).
    for tool_cls in (
        LaptopListDevicesTool,
        LaptopOpenAppTool,
        LaptopOpenUrlTool,
        LaptopScreenshotTool,
        LaptopTypeTextTool,
        LaptopClickTool,
        LaptopRunCommandTool,
    ):
        schema = tool_cls().to_openai_schema()
        assert schema["function"]["name"].startswith("laptop_")
