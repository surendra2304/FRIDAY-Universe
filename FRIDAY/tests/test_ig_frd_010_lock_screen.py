"""TASK-IG-FRD-010 — laptop lock_screen command + tool tests.

The invariant under test is as important as the feature: lock exists,
unlock does not — anywhere.
"""

from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from friday.remote.laptop_bridge import ALLOWED_LAPTOP_COMMANDS
from friday.tools.builtin.laptop_control import LaptopLockTool


def _load_client():
    try:
        import websockets  # noqa: F401
    except ImportError:
        sys.modules.setdefault("websockets", SimpleNamespace())
    path = Path(__file__).resolve().parents[1] / "scripts" / "laptop_bridge_client.py"
    spec = importlib.util.spec_from_file_location("laptop_bridge_client_frd010", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = _load_client()


def test_allowlists_include_lock_and_never_unlock():
    assert "lock_screen" in ALLOWED_LAPTOP_COMMANDS
    assert "lock_screen" in client.ALLOWED_COMMANDS
    assert "lock_screen" in client._COMMANDS
    for name in list(ALLOWED_LAPTOP_COMMANDS) + list(client.ALLOWED_COMMANDS) + list(client._COMMANDS):
        assert "unlock" not in name.lower()


def test_lock_argv_per_platform():
    assert client._lock_argv("Windows") == ["rundll32.exe", "user32.dll,LockWorkStation"]
    assert client._lock_argv("Darwin") == ["/usr/bin/pmset", "displaysleepnow"]
    assert client._lock_argv("Linux") == ["loginctl", "lock-session"]
    assert client._lock_argv("Plan9") is None


def test_cmd_lock_screen_success(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    monkeypatch.setattr(client.subprocess, "run", fake_run)
    ok, output, error = client._cmd_lock_screen({}, timeout=5)
    assert ok is True
    assert "locked" in output.lower()
    assert calls == [["loginctl", "lock-session"]]


def test_cmd_lock_screen_linux_fallback(monkeypatch):
    calls = []

    def fake_run(argv, **kwargs):
        calls.append(argv)
        if argv[0] == "loginctl":
            raise FileNotFoundError("no loginctl")
        return SimpleNamespace(returncode=0, stderr=b"")

    monkeypatch.setattr(client.platform, "system", lambda: "Linux")
    monkeypatch.setattr(client.subprocess, "run", fake_run)
    ok, output, error = client._cmd_lock_screen({}, timeout=5)
    assert ok is True
    assert calls[-1] == ["xdg-screensaver", "lock"]


def test_cmd_lock_screen_failure_is_honest(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Windows")
    monkeypatch.setattr(
        client.subprocess,
        "run",
        lambda argv, **kw: SimpleNamespace(returncode=1, stderr=b"denied"),
    )
    ok, output, error = client._cmd_lock_screen({}, timeout=5)
    assert ok is False
    assert "lock_screen failed" in error


def test_cmd_lock_screen_unsupported_platform(monkeypatch):
    monkeypatch.setattr(client.platform, "system", lambda: "Plan9")
    ok, output, error = client._cmd_lock_screen({}, timeout=5)
    assert ok is False
    assert "not supported" in error


def test_tool_dispatch_and_safety_class():
    tool = LaptopLockTool()
    assert tool.safety_level.value in ("sensitive", "SENSITIVE") or str(tool.safety_level).upper().endswith("SENSITIVE")
    tool._dispatch = lambda args, laptop_id=None: ({"ok": True, "laptop_id": "boss", "output": "Screen locked via loginctl lock-session."}, None)
    result = tool.execute()
    assert result.is_error is False
    assert "Locked the screen" in result.content


def test_no_unlock_tool_exists():
    import friday.tools.builtin as builtin

    names = [n for n in dir(builtin) if "Tool" in n]
    assert not any("unlock" in n.lower() for n in names)
    assert "LaptopLockTool" in names
