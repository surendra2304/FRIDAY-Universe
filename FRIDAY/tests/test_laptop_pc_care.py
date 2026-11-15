"""TASK-IG-LAP-03 — PC care cluster tests.

Client handlers (scripts/laptop_bridge_client.py) are driven directly
with monkeypatched platform seams (temp targets, input backend, volume
inventory, subprocess capture); tools are driven with a stubbed
_dispatch. No laptop is connected — the LAP-001 harness pattern.
"""

from __future__ import annotations

import importlib.util
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.core.types import ToolResult  # noqa: E402
from friday.remote.laptop_bridge import ALLOWED_LAPTOP_COMMANDS  # noqa: E402
from friday.tools.builtin.laptop_pc_care import (  # noqa: E402
    NAMED_SHORTCUTS,
    LaptopHotkeyTool,
    LaptopPcCleanupTool,
    LaptopPcHealthTool,
    LaptopStorageCheckTool,
    LaptopStorageRepairTool,
    validate_keys,
)

_CLIENT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "laptop_bridge_client.py"
_spec = importlib.util.spec_from_file_location("laptop_bridge_client_care", _CLIENT_PATH)
_client = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_client)


# ---------------------------------------------------------------------------
# Allowlist parity
# ---------------------------------------------------------------------------


def test_pc_care_commands_allowed_on_both_sides():
    for command in ("pc_health", "pc_cleanup", "hotkey", "storage_check", "storage_repair"):
        assert command in ALLOWED_LAPTOP_COMMANDS
        assert command in _client.ALLOWED_COMMANDS
        assert command in _client._COMMANDS


# ---------------------------------------------------------------------------
# pc_cleanup
# ---------------------------------------------------------------------------


def _aged(path: Path, hours: float, content: bytes = b"x" * 100) -> Path:
    path.write_bytes(content)
    old = time.time() - hours * 3600
    os.utime(path, (old, old))
    return path


def test_cleanup_enumerate_deletes_nothing(tmp_path, monkeypatch):
    monkeypatch.setattr(_client, "_cleanup_targets", lambda: [tmp_path])
    old = _aged(tmp_path / "old.tmp", 48)
    fresh = _aged(tmp_path / "fresh.tmp", 1)
    ok, payload, error = _client._cmd_pc_cleanup({}, 30.0)
    assert ok and error is None
    data = json.loads(payload)
    assert data["mode"] == "enumerate"
    assert data["candidate_count"] == 1
    assert data["candidate_bytes"] == 100
    assert old.exists() and fresh.exists()  # nothing deleted


def test_cleanup_apply_deletes_only_aged_files(tmp_path, monkeypatch):
    monkeypatch.setattr(_client, "_cleanup_targets", lambda: [tmp_path])
    old = _aged(tmp_path / "old.tmp", 72)
    nested = tmp_path / "sub"
    nested.mkdir()
    old_nested = _aged(nested / "old2.tmp", 72)
    fresh = _aged(tmp_path / "fresh.tmp", 2)
    link = tmp_path / "link.tmp"
    link.symlink_to(fresh)
    ok, payload, _ = _client._cmd_pc_cleanup({"apply": True, "min_age_hours": 24}, 30.0)
    assert ok
    data = json.loads(payload)
    assert data["mode"] == "apply"
    assert data["deleted"] == 2 and data["freed_bytes"] == 200
    assert not old.exists() and not old_nested.exists()
    assert fresh.exists() and link.exists()  # fresh + symlink untouched


# ---------------------------------------------------------------------------
# pc_health
# ---------------------------------------------------------------------------


def test_pc_health_returns_measured_report():
    ok, payload, error = _client._cmd_pc_health({}, 30.0)
    assert ok and error is None
    data = json.loads(payload)
    assert data["hostname"]
    assert data["disks"] and "used_percent" in data["disks"][0]
    assert data["checklist"]
    assert data["temp_dir"]["path"]


# ---------------------------------------------------------------------------
# hotkey (client)
# ---------------------------------------------------------------------------


class _FakePyAutoGui:
    def __init__(self) -> None:
        self.calls: list[tuple[str, ...]] = []

    def hotkey(self, *keys: str) -> None:
        self.calls.append(tuple(keys))


def test_client_hotkey_resolves_mod_per_platform(monkeypatch):
    fake = _FakePyAutoGui()
    monkeypatch.setattr(_client, "_input_backend", lambda: (fake, None))
    monkeypatch.setattr(_client.platform, "system", lambda: "Linux")
    ok, _, _ = _client._cmd_hotkey({"keys": ["mod", "c"]}, 10.0)
    assert ok and fake.calls == [("ctrl", "c")]
    monkeypatch.setattr(_client.platform, "system", lambda: "Darwin")
    ok, _, _ = _client._cmd_hotkey({"keys": ["mod", "tab"]}, 10.0)
    assert ok and fake.calls[-1] == ("command", "tab")
    ok, _, _ = _client._cmd_hotkey({"keys": ["win", "l"]}, 10.0)
    assert ok and fake.calls[-1] == ("winleft", "l")


def test_client_hotkey_rejects_off_list_keys(monkeypatch):
    fake = _FakePyAutoGui()
    monkeypatch.setattr(_client, "_input_backend", lambda: (fake, None))
    ok, _, error = _client._cmd_hotkey({"keys": ["ctrl", "launch_missiles"]}, 10.0)
    assert not ok and "allowlist" in (error or "")
    assert fake.calls == []
    ok, _, _ = _client._cmd_hotkey({"keys": []}, 10.0)
    assert not ok


# ---------------------------------------------------------------------------
# storage check / repair (client)
# ---------------------------------------------------------------------------


def _linux(monkeypatch, inventory):
    monkeypatch.setattr(_client.platform, "system", lambda: "Linux")
    monkeypatch.setattr(_client, "_volume_inventory", lambda: inventory)


def test_storage_check_skips_mounted_linux_volume(monkeypatch):
    _linux(monkeypatch, [{"device": "/dev/sda1", "mount": "/", "fstype": "ext4"}])
    ok, payload, _ = _client._cmd_storage_check({}, 30.0)
    assert ok
    volumes = json.loads(payload)["volumes"]
    assert volumes[0]["status"] == "skipped"
    assert "unmounted" in volumes[0]["detail"]


def test_storage_check_unmounted_device_uses_fsck_n(monkeypatch):
    _linux(monkeypatch, [{"device": "/dev/sda1", "mount": "/", "fstype": "ext4"}])
    seen = {}

    def fake_run(argv, timeout):
        seen["argv"] = argv
        return 0, "clean", ""

    monkeypatch.setattr(_client, "_run_capture", fake_run)
    ok, payload, _ = _client._cmd_storage_check({"volume": "/dev/sdb1"}, 30.0)
    assert ok
    assert seen["argv"] == ["fsck", "-n", "/dev/sdb1"]
    assert json.loads(payload)["volumes"][0]["status"] == "ok"


def test_storage_repair_refusals(monkeypatch):
    _linux(monkeypatch, [{"device": "/dev/sdb1", "mount": "/media/usb", "fstype": "vfat"}])
    # no confirm
    ok, _, error = _client._cmd_storage_repair({"volume": "/dev/sdb1"}, 30.0)
    assert not ok and "confirm=true" in (error or "")
    # system volume
    ok, _, error = _client._cmd_storage_repair({"volume": "/", "confirm": True}, 30.0)
    assert not ok and "system volume" in (error or "")
    # mounted volume
    ok, _, error = _client._cmd_storage_repair({"volume": "/dev/sdb1", "confirm": True}, 30.0)
    assert not ok and "mounted" in (error or "")


def test_storage_repair_unmounted_runs_fsck_y(monkeypatch):
    _linux(monkeypatch, [{"device": "/dev/sda1", "mount": "/", "fstype": "ext4"}])
    seen = {}

    def fake_run(argv, timeout):
        seen["argv"] = argv
        return 0, "repaired", ""

    monkeypatch.setattr(_client, "_run_capture", fake_run)
    ok, payload, _ = _client._cmd_storage_repair({"volume": "/dev/sdb1", "confirm": True}, 30.0)
    assert ok and seen["argv"] == ["fsck", "-y", "/dev/sdb1"]


def test_storage_repair_windows_system_drive_refused(monkeypatch):
    monkeypatch.setattr(_client.platform, "system", lambda: "Windows")
    monkeypatch.setenv("SystemDrive", "C:")
    monkeypatch.setattr(_client, "_volume_inventory", lambda: [
        {"device": "C:\\", "mount": "C:\\", "fstype": "NTFS"},
        {"device": "D:\\", "mount": "D:\\", "fstype": "NTFS"},
    ])
    ok, _, error = _client._cmd_storage_repair({"volume": "C:", "confirm": True}, 30.0)
    assert not ok and "system volume" in (error or "")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


class _Recorder:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, args, laptop_id=None, timeout=None):
        self.calls.append(args)
        return {"ok": True, "laptop_id": "lap-1", "output": "{}"}, None


def _with_dispatch(tool, recorder):
    tool._dispatch = recorder  # type: ignore[method-assign]
    return tool


def test_health_and_check_tools_dispatch():
    recorder = _Recorder()
    health = _with_dispatch(LaptopPcHealthTool(), recorder)
    assert not health.execute().is_error
    check = _with_dispatch(LaptopStorageCheckTool(), recorder)
    assert not check.execute(volume="/dev/sdb1").is_error
    assert recorder.calls[-1] == {"volume": "/dev/sdb1"}


def test_cleanup_tool_defaults_to_enumerate():
    recorder = _Recorder()
    tool = _with_dispatch(LaptopPcCleanupTool(), recorder)
    assert not tool.execute().is_error
    assert recorder.calls[0]["apply"] is False


def test_hotkey_tool_named_and_explicit():
    recorder = _Recorder()
    tool = _with_dispatch(LaptopHotkeyTool(), recorder)
    assert not tool.execute(shortcut="copy").is_error
    assert recorder.calls[-1] == {"keys": ["mod", "c"]}
    assert not tool.execute(keys=["ctrl", "shift", "t"]).is_error
    assert tool.execute(shortcut="defrag_the_moon").is_error
    assert tool.execute(keys=["ctrl", "f13"]).is_error
    assert tool.execute().is_error
    assert len(recorder.calls) == 2  # refusals never reached the laptop


def test_repair_tool_confirm_gate_and_class():
    recorder = _Recorder()
    tool = _with_dispatch(LaptopStorageRepairTool(), recorder)
    assert str(tool.safety_level).upper().endswith("DANGEROUS")
    assert tool.execute(volume="/dev/sdb1").is_error
    assert recorder.calls == []  # refused before dispatch
    assert not tool.execute(volume="/dev/sdb1", confirm=True).is_error
    assert recorder.calls[0] == {"volume": "/dev/sdb1", "confirm": True}


def test_validate_keys_and_shortcut_map_integrity():
    assert validate_keys(["CTRL", " c "]) == ["ctrl", "c"]
    assert validate_keys(["ctrl", "f13"]) is None
    assert validate_keys("ctrl+c") is None
    assert validate_keys([]) is None
    for name, combo in NAMED_SHORTCUTS.items():
        assert validate_keys(combo) is not None, name
