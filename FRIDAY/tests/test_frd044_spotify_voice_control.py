"""TASK-FRD-044 — Spotify playback control by voice.

Covers: the laptop client's media_key / media_status handlers (with a
fake Windows key backend and a fake WinRT session manager), the
laptop_media_key / laptop_media_status / spotify_control agent tools
(with a sequenced stub bridge), and tool registration. The live leg —
a spoken request changing real playback on the owner's laptop — is
NOT covered here; it needs the owner's laptop online plus hub clearance.
"""

from __future__ import annotations

import ctypes
import enum
import importlib.util
import json
import platform
import sys
import types
from pathlib import Path
from types import SimpleNamespace

lb = importlib.import_module("friday.remote.laptop_bridge")

REPO_ROOT = Path(__file__).resolve().parents[2]
CLIENT_PATH = REPO_ROOT / "FRIDAY" / "scripts" / "laptop_bridge_client.py"


def _load_client():
    spec = importlib.util.spec_from_file_location("laptop_bridge_client_frd044", CLIENT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


client = _load_client()


def _as_windows(monkeypatch):
    monkeypatch.setattr(platform, "system", lambda: "Windows")


# ---------------------------------------------------------------------------
# Client: media_key
# ---------------------------------------------------------------------------


def _fake_windll(calls: list):
    user32 = SimpleNamespace(
        keybd_event=lambda vk, scan, flags, extra: calls.append((vk, flags))
    )
    return SimpleNamespace(user32=user32)


def test_client_media_key_sends_windows_key(monkeypatch):
    _as_windows(monkeypatch)
    calls: list = []
    monkeypatch.setattr(ctypes, "windll", _fake_windll(calls), raising=False)
    ok, output, error = client._cmd_media_key({"action": "play_pause"}, 5.0)
    assert ok, error
    assert json.loads(output) == {"action": "play_pause", "key": "0xB3", "sent": True}
    assert calls == [(0xB3, 0), (0xB3, 0x0002)]


def test_client_media_key_next_and_previous(monkeypatch):
    _as_windows(monkeypatch)
    calls: list = []
    monkeypatch.setattr(ctypes, "windll", _fake_windll(calls), raising=False)
    assert client._cmd_media_key({"action": "next"}, 5.0)[0]
    assert client._cmd_media_key({"action": "previous"}, 5.0)[0]
    assert calls[0][0] == 0xB0
    assert calls[2][0] == 0xB1


def test_client_media_key_rejects_unknown_action(monkeypatch):
    _as_windows(monkeypatch)
    ok, _out, error = client._cmd_media_key({"action": "rewind"}, 5.0)
    assert not ok
    assert "play_pause" in error


def test_client_media_key_non_windows_is_honest_error():
    # CI runs on Linux: the handler must say so, not pretend a key landed.
    assert platform.system() != "Windows"
    ok, _out, error = client._cmd_media_key({"action": "play_pause"}, 5.0)
    assert not ok
    assert "Windows" in error


# ---------------------------------------------------------------------------
# Client: media_status (fake WinRT session manager)
# ---------------------------------------------------------------------------


class _FakePlaybackStatus(enum.IntEnum):
    CLOSED = 0
    OPENED = 1
    CHANGING = 2
    STOPPED = 3
    PLAYING = 4
    PAUSED = 5


class _FakeMediaProperties:
    title = "Bohemian Rhapsody"
    artist = "Queen"


class _FakeSession:
    source_app_user_model_id = "SpotifyAB.SpotifyMusic_zpdnekdrzrea0"

    def __init__(self, status=_FakePlaybackStatus.PLAYING):
        self._status = status

    def get_playback_info(self):
        return SimpleNamespace(playback_status=self._status)

    async def try_get_media_properties_async(self):
        return _FakeMediaProperties()


class _FakeSessionManager:
    def __init__(self, session):
        self._session = session

    def get_current_session(self):
        return self._session


def _install_fake_winrt(monkeypatch, session):
    control = types.ModuleType("winrt.windows.media.control")

    async def _request_async():
        return _FakeSessionManager(session)

    control.GlobalSystemMediaTransportControlsSessionManager = SimpleNamespace(
        request_async=staticmethod(_request_async)
    )
    control.GlobalSystemMediaTransportControlsSessionPlaybackStatus = _FakePlaybackStatus
    for name in ("winrt", "winrt.windows", "winrt.windows.media"):
        monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
    monkeypatch.setitem(sys.modules, "winrt.windows.media.control", control)


def test_client_media_status_reports_playing_session(monkeypatch):
    _as_windows(monkeypatch)
    _install_fake_winrt(monkeypatch, _FakeSession(_FakePlaybackStatus.PLAYING))
    ok, output, error = client._cmd_media_status({}, 5.0)
    assert ok, error
    assert json.loads(output) == {
        "playing": True,
        "status": "PLAYING",
        "title": "Bohemian Rhapsody",
        "artist": "Queen",
        "source": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0",
    }


def test_client_media_status_paused_session(monkeypatch):
    _as_windows(monkeypatch)
    _install_fake_winrt(monkeypatch, _FakeSession(_FakePlaybackStatus.PAUSED))
    ok, output, error = client._cmd_media_status({}, 5.0)
    assert ok, error
    payload = json.loads(output)
    assert payload["playing"] is False
    assert payload["status"] == "PAUSED"


def test_client_media_status_no_session(monkeypatch):
    _as_windows(monkeypatch)
    _install_fake_winrt(monkeypatch, None)
    ok, output, error = client._cmd_media_status({}, 5.0)
    assert ok, error
    assert json.loads(output)["status"] == "no_session"


def test_client_media_status_missing_winrt_is_honest_error(monkeypatch):
    _as_windows(monkeypatch)
    assert "winrt" not in sys.modules
    ok, _out, error = client._cmd_media_status({}, 5.0)
    assert not ok
    assert "winrt" in error


def test_client_media_status_non_windows_is_honest_error():
    assert platform.system() != "Windows"
    ok, _out, error = client._cmd_media_status({}, 5.0)
    assert not ok
    assert "Windows" in error


def test_client_dispatches_media_commands(monkeypatch):
    _as_windows(monkeypatch)
    calls: list = []
    monkeypatch.setattr(ctypes, "windll", _fake_windll(calls), raising=False)
    record = client._execute_command("lap-test", "req-1", "media_key", {"action": "next"}, 5.0)
    assert record["ok"] is True
    assert record["command"] == "media_key"
    assert calls[0][0] == 0xB0


# ---------------------------------------------------------------------------
# Agent tools (sequenced stub bridge)
# ---------------------------------------------------------------------------


class SequencedBridge:
    """Return one canned evidence record per call, in order."""

    def __init__(self, devices, evidences):
        self._devices = devices
        self._evidences = list(evidences)
        self.calls: list = []

    async def list_devices(self):
        return self._devices

    async def execute(self, laptop_id, command, timeout, args=None):
        self.calls.append((laptop_id, command, args))
        if not self._evidences:
            raise AssertionError(f"unexpected extra bridge call: {command} {args}")
        item = self._evidences.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _online_device(laptop_id="lap-test"):
    return [{"laptop_id": laptop_id, "online": True, "connected_at": "t", "last_seen": "t", "pending_requests": 0}]


def _status_evidence(session, laptop_id="lap-test"):
    return {
        "ok": True,
        "laptop_id": laptop_id,
        "command": "media_status",
        "output": json.dumps(session),
        "error": None,
    }


def _key_evidence(action="play_pause", laptop_id="lap-test"):
    return {
        "ok": True,
        "laptop_id": laptop_id,
        "command": "media_key",
        "output": json.dumps({"action": action, "key": "0xB3", "sent": True}),
        "error": None,
    }


def _url_evidence(url, laptop_id="lap-test"):
    return {
        "ok": True,
        "laptop_id": laptop_id,
        "command": "open_url",
        "output": f"Opened {url}",
        "error": None,
    }


_PAUSED = {
    "playing": False,
    "status": "PAUSED",
    "title": "Bohemian Rhapsody",
    "artist": "Queen",
    "source": "SpotifyAB.SpotifyMusic_zpdnekdrzrea0",
}
_PLAYING = dict(_PAUSED, playing=True, status="PLAYING")
_PLAYING_NEXT = dict(_PLAYING, title="Another One Bites the Dust")


def test_tool_media_key_dispatches(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [_key_evidence("next")])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.LaptopMediaKeyTool().execute(action="next")
    assert not result.is_error
    assert stub.calls == [("lap-test", "media_key", {"action": "next"})]
    # A sent key is never claimed as proof of playback.
    assert "not proven" in result.content


def test_tool_media_key_rejects_unknown_action(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.LaptopMediaKeyTool().execute(action="rewind")
    assert result.is_error
    assert stub.calls == []


def test_tool_media_status_renders_session(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [_status_evidence(_PLAYING)])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.LaptopMediaStatusTool().execute()
    assert not result.is_error
    assert "Bohemian Rhapsody" in result.content
    assert "playing" in result.content
    assert stub.calls == [("lap-test", "media_status", {})]


def test_tool_media_status_no_session(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(
        _online_device(),
        [_status_evidence({"playing": False, "status": "no_session", "title": None, "artist": None, "source": None})],
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.LaptopMediaStatusTool().execute()
    assert not result.is_error
    assert "No media session is active" in result.content


def test_spotify_play_when_paused_verifies_playing(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(
        _online_device(),
        [_status_evidence(_PAUSED), _key_evidence("play_pause"), _status_evidence(_PLAYING)],
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="play")
    assert not result.is_error
    assert "Bohemian Rhapsody" in result.content
    assert "playing" in result.content
    assert stub.calls == [
        ("lap-test", "media_status", {}),
        ("lap-test", "media_key", {"action": "play_pause"}),
        ("lap-test", "media_status", {}),
    ]


def test_spotify_play_when_already_playing_sends_no_key(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [_status_evidence(_PLAYING)])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="play")
    assert not result.is_error
    assert "Already playing" in result.content
    assert stub.calls == [("lap-test", "media_status", {})]


def test_spotify_pause_when_playing_verifies_paused(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(
        _online_device(),
        [_status_evidence(_PLAYING), _key_evidence("play_pause"), _status_evidence(_PAUSED)],
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="pause")
    assert not result.is_error
    assert "paused" in result.content
    assert stub.calls[1] == ("lap-test", "media_key", {"action": "play_pause"})


def test_spotify_pause_when_already_paused_sends_no_key(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [_status_evidence(_PAUSED)])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="pause")
    assert not result.is_error
    assert "Already paused" in result.content
    assert stub.calls == [("lap-test", "media_status", {})]


def test_spotify_next_reports_new_track(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(
        _online_device(),
        [_status_evidence(_PLAYING), _key_evidence("next"), _status_evidence(_PLAYING_NEXT)],
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="next")
    assert not result.is_error
    assert "Another One Bites the Dust" in result.content
    assert stub.calls[1] == ("lap-test", "media_key", {"action": "next"})


def test_spotify_key_sent_but_readback_failed_is_honest(monkeypatch):
    from friday.tools.builtin import laptop_control

    failed_read = {
        "ok": False,
        "laptop_id": "lap-test",
        "command": "media_status",
        "output": "",
        "error": "media_status needs the 'winrt' package",
    }
    stub = SequencedBridge(
        _online_device(), [_status_evidence(_PAUSED), _key_evidence("play_pause"), failed_read]
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="play")
    assert not result.is_error
    assert "unconfirmed" in result.content
    assert "read-back failed" in result.content


def test_spotify_search_opens_url(monkeypatch):
    from friday.tools.builtin import laptop_control

    url = "https://open.spotify.com/search/Bohemian%20Rhapsody"
    stub = SequencedBridge(
        _online_device(), [_url_evidence(url), _status_evidence(_PLAYING)]
    )
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="search", query="Bohemian Rhapsody")
    assert not result.is_error
    assert stub.calls[0] == ("lap-test", "open_url", {"url": url})
    assert "Opened Spotify search for 'Bohemian Rhapsody'" in result.content


def test_spotify_search_requires_query(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="search", query="  ")
    assert result.is_error
    assert stub.calls == []


def test_spotify_status_action(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [_status_evidence(_PAUSED)])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="status")
    assert not result.is_error
    assert "paused" in result.content


def test_spotify_unknown_action_is_error(monkeypatch):
    from friday.tools.builtin import laptop_control

    stub = SequencedBridge(_online_device(), [])
    monkeypatch.setattr(laptop_control, "laptop_bridge", stub)
    result = laptop_control.SpotifyControlTool().execute(action="shuffle")
    assert result.is_error
    assert stub.calls == []


def test_media_tools_are_registered():
    from friday.tools.builtin import (
        LaptopMediaKeyTool,
        LaptopMediaStatusTool,
        SpotifyControlTool,
    )

    names = {
        LaptopMediaKeyTool().name,
        LaptopMediaStatusTool().name,
        SpotifyControlTool().name,
    }
    assert names == {"laptop_media_key", "laptop_media_status", "spotify_control"}
    for tool_cls in (LaptopMediaKeyTool, LaptopMediaStatusTool, SpotifyControlTool):
        schema = tool_cls().to_openai_schema()
        assert schema["function"]["name"] in names
