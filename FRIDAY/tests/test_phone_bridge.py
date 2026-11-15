"""TASK-PHONE-001 — phone bridge protocol, pairing and tool tests.

The round-trip tests drive the REAL :class:`PhoneBridge` with a fake socket
whose other end is the mock executor from ``scripts/phone_mock_device.py``:
bridge -> command frame -> (mock) executor -> result frame -> evidence.
That is the full server->protocol->executor->result path, minus hardware.

The sync-topology test reproduces production shape: the bridge lives on an
event loop in one thread (the API server), while FRIDAY's tool layer calls
``execute_sync`` from a worker thread.
"""

import asyncio
import importlib.util
import json
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from friday.remote.phone_bridge import (  # noqa: E402
    ALLOWED_PHONE_COMMANDS,
    PairingStore,
    PhoneBridge,
    PhoneBridgeTimeout,
    PhoneDisconnected,
    PhoneNotConnected,
    PhoneUnsupportedCommand,
)

_MOCK_PATH = Path(__file__).resolve().parents[1] / "scripts" / "phone_mock_device.py"
_spec = importlib.util.spec_from_file_location("phone_mock_device", _MOCK_PATH)
_mock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_mock)
MockPhoneExecutor = _mock.MockPhoneExecutor

TERMUX_LIKE_CAPS = [
    "device_status",
    "open_app",
    "open_url",
    "make_call",
    "send_sms",
    "send_whatsapp",
    "read_notifications",
    "set_alarm",
    "media_control",
    "set_volume",
    "find_phone",
]


def _run(coro):
    return asyncio.new_event_loop().run_until_complete(coro)


@pytest.fixture()
def store(tmp_path):
    return PairingStore(state_file=tmp_path / "bridge_state.json")


@pytest.fixture()
def bridge(store):
    return PhoneBridge(pairing_store=store)


def _pair(bridge: PhoneBridge, name="Owner phone", executor="mock"):
    issued_code = bridge.pairing.create_pairing_code()
    issued = bridge.pairing.consume_pairing_code(
        issued_code["pairing_code"], device_name=name, executor=executor
    )
    assert issued is not None
    return issued["device_id"], issued["device_token"]


class FakeSocket:
    """The executor end of the tunnel: answers command frames via the mock."""

    def __init__(self, bridge, device_id, executor=None, on_command=None):
        self.bridge = bridge
        self.device_id = device_id
        self.executor = executor or MockPhoneExecutor()
        self.on_command = on_command
        self.frames = []

    async def send_json(self, frame):
        self.frames.append(frame)
        if frame.get("type") != "command":
            return
        if self.on_command is not None:
            await self.on_command(frame)
            return
        ok, output, error = self.executor.handle(
            str(frame.get("command") or ""), dict(frame.get("args") or {})
        )
        await self.bridge.resolve_result(
            self.device_id,
            {
                "request_id": frame.get("request_id"),
                "ok": ok,
                "output": output,
                "error": error,
            },
        )


# ---------------------------------------------------------------------------
# Pairing
# ---------------------------------------------------------------------------


def test_pairing_code_is_six_digits_and_single_use(bridge):
    device_id, token = _pair(bridge)
    assert device_id.startswith("phone-")
    assert token
    # The same code cannot be consumed twice.
    code = bridge.pairing.create_pairing_code()["pairing_code"]
    assert len(code) == 6 and code.isdigit()
    assert bridge.pairing.consume_pairing_code(code) is not None
    assert bridge.pairing.consume_pairing_code(code) is None


def test_pairing_wrong_code_and_garbage_rejected(bridge):
    bridge.pairing.create_pairing_code()
    assert bridge.pairing.consume_pairing_code("000000") is None
    assert bridge.pairing.consume_pairing_code("abcdef") is None
    assert bridge.pairing.consume_pairing_code("") is None


def test_token_authentication_and_revoke(bridge):
    device_id, token = _pair(bridge)
    assert bridge.pairing.authenticate(device_id, token) is True
    assert bridge.pairing.authenticate(device_id, token + "x") is False
    assert bridge.pairing.authenticate(device_id, "") is False
    assert bridge.pairing.authenticate("phone-nope", token) is False
    assert bridge.pairing.revoke(device_id) is True
    assert bridge.pairing.authenticate(device_id, token) is False
    assert bridge.pairing.revoke(device_id) is False


def test_pairing_persists_and_state_file_holds_only_the_hash(tmp_path):
    state = tmp_path / "bridge_state.json"
    store1 = PairingStore(state_file=state)
    code = store1.create_pairing_code()["pairing_code"]
    issued = store1.consume_pairing_code(code, device_name="Pixel", executor="termux")
    assert issued is not None
    raw = state.read_text(encoding="utf-8")
    assert issued["device_token"] not in raw  # the plain token is never stored
    store2 = PairingStore(state_file=state)  # a "restarted" store sees the device
    assert store2.authenticate(issued["device_id"], issued["device_token"]) is True
    assert store2.get_device(issued["device_id"])["name"] == "Pixel"


# ---------------------------------------------------------------------------
# Round trip: bridge -> protocol -> mock executor -> evidence
# ---------------------------------------------------------------------------


def test_round_trip_commands_reach_the_executor(bridge):
    async def scenario():
        device_id, _ = _pair(bridge)
        executor = MockPhoneExecutor()
        sock = FakeSocket(bridge, device_id, executor)
        await bridge.register(device_id, sock, executor="mock", capabilities=list(ALLOWED_PHONE_COMMANDS))

        ev = await bridge.execute(device_id, "device_status", 5.0, {})
        assert ev["ok"] is True
        assert "MockPhone" in ev["output"]

        ev = await bridge.execute(device_id, "open_app", 5.0, {"app": "whatsapp"})
        assert ev["ok"] is True
        assert executor.state["foreground_app"] == "whatsapp"  # executor side really ran

        ev = await bridge.execute(device_id, "make_call", 5.0, {"number": "+919999999999"})
        assert ev["ok"] is True
        assert executor.state["calls"][0]["number"] == "+919999999999"

        ev = await bridge.execute(device_id, "send_sms", 5.0, {"number": "+919999999999", "message": "hi"})
        assert ev["ok"] is True
        assert executor.state["sms"][0]["message"] == "hi"

        ev = await bridge.execute(device_id, "read_notifications", 5.0, {"limit": 1})
        assert ev["ok"] is True
        assert "WhatsApp" in ev["output"]

        devices = await bridge.list_devices()
        mine = [d for d in devices if d["device_id"] == device_id][0]
        assert mine["online"] is True
        assert "make_call" in mine["capabilities"]
        await bridge.unregister(device_id, sock)

    _run(scenario())


def test_unknown_command_refused_before_dispatch(bridge):
    async def scenario():
        device_id, _ = _pair(bridge)
        sock = FakeSocket(bridge, device_id)
        await bridge.register(device_id, sock, executor="mock", capabilities=list(ALLOWED_PHONE_COMMANDS))
        with pytest.raises(ValueError):
            await bridge.execute(device_id, "wipe_phone", 5.0, {})
        assert sock.frames == []  # nothing was ever sent to the phone

    _run(scenario())


def test_capability_gating_refuses_what_the_executor_cannot_do(bridge):
    async def scenario():
        device_id, _ = _pair(bridge)
        sock = FakeSocket(bridge, device_id)
        await bridge.register(device_id, sock, executor="termux", capabilities=TERMUX_LIKE_CAPS)
        with pytest.raises(PhoneUnsupportedCommand):
            await bridge.execute(device_id, "tap", 5.0, {"x": 1, "y": 2})
        with pytest.raises(PhoneUnsupportedCommand):
            await bridge.execute(device_id, "screenshot", 5.0, {})
        ev = await bridge.execute(device_id, "send_sms", 5.0, {"number": "+91123", "message": "ok"})
        assert ev["ok"] is True

    _run(scenario())


def test_offline_phone_is_an_honest_error(bridge):
    async def scenario():
        device_id, _ = _pair(bridge)  # paired, never connects
        with pytest.raises(PhoneNotConnected):
            await bridge.execute(device_id, "device_status", 5.0, {})
        devices = await bridge.list_devices()
        mine = [d for d in devices if d["device_id"] == device_id][0]
        assert mine["online"] is False

    _run(scenario())


def test_timeout_returns_evidence_not_a_hang(bridge):
    async def scenario():
        device_id, _ = _pair(bridge)

        async def swallow(frame):  # executor that never answers
            return None

        sock = FakeSocket(bridge, device_id, on_command=swallow)
        await bridge.register(device_id, sock, executor="mock", capabilities=list(ALLOWED_PHONE_COMMANDS))
        with pytest.raises(PhoneBridgeTimeout) as info:
            await bridge.execute(device_id, "device_status", 0.3, {})
        assert info.value.evidence["ok"] is False
        assert "timeout" in info.value.evidence["error"]

    _run(scenario())


def test_disconnect_mid_command_fails_the_waiter(bridge):
    async def scenario():
        device_id, _ = _pair(bridge)
        sock = FakeSocket(bridge, device_id)

        async def drop(frame):
            await bridge.unregister(device_id, sock)

        sock.on_command = drop
        await bridge.register(device_id, sock, executor="mock", capabilities=list(ALLOWED_PHONE_COMMANDS))
        with pytest.raises(PhoneDisconnected):
            await bridge.execute(device_id, "open_app", 5.0, {"app": "maps"})

    _run(scenario())


def test_execute_sync_from_a_worker_thread(bridge):
    """Production topology: bridge loop in one thread, tools in another."""
    device_id, _ = _pair(bridge)
    sock = FakeSocket(bridge, device_id)
    loop = asyncio.new_event_loop()
    ready = threading.Event()

    async def serve():
        await bridge.register(device_id, sock, executor="mock", capabilities=list(ALLOWED_PHONE_COMMANDS))
        ready.set()
        await asyncio.sleep(30)

    thread = threading.Thread(target=lambda: loop.run_until_complete(serve()), daemon=True)
    thread.start()
    assert ready.wait(timeout=10)

    evidence = bridge.execute_sync(device_id, "open_app", timeout=5.0, args={"app": "maps"})
    assert evidence["ok"] is True
    assert sock.executor.state["foreground_app"] == "maps"
    loop.call_soon_threadsafe(loop.stop)


def test_execute_sync_without_any_tunnel_is_honest(bridge):
    with pytest.raises(PhoneNotConnected):
        bridge.execute_sync("phone-whatever", "device_status", timeout=2.0)


# ---------------------------------------------------------------------------
# Tool layer
# ---------------------------------------------------------------------------


def test_phone_tools_register_with_the_right_safety_levels():
    from friday.core.types import SafetyLevel
    from friday.tools.builtin import phone_control as pc
    from friday.tools.registry import ToolRegistry

    registry = ToolRegistry()
    for cls_name in pc.__all__:
        registry.register(getattr(pc, cls_name)())
    names = {t.name for t in registry.list_tools()} if hasattr(registry, "list_tools") else set()
    if not names:  # registry API variant: fall back to schema listing
        names = {s["function"]["name"] for s in registry.to_openai_schemas()} if hasattr(registry, "to_openai_schemas") else set()
    expected = {
        "phone_status", "phone_open_app", "phone_close_app", "phone_open_url",
        "phone_make_call", "phone_send_sms", "phone_send_whatsapp",
        "phone_read_notifications", "phone_set_alarm", "phone_media_control",
        "phone_set_volume", "phone_find", "phone_tap", "phone_swipe",
        "phone_type_text", "phone_press_key", "phone_screenshot",
    }
    assert expected <= names, f"missing tools: {expected - names}"
    assert pc.PhoneMakeCallTool().safety_level == SafetyLevel.SENSITIVE
    assert pc.PhoneSendSmsTool().safety_level == SafetyLevel.SENSITIVE
    assert pc.PhoneSendWhatsAppTool().safety_level == SafetyLevel.SENSITIVE
    assert pc.PhoneOpenAppTool().safety_level == SafetyLevel.SAFE


def test_tools_are_honest_when_nothing_is_paired(tmp_path, monkeypatch):
    from friday.tools.builtin import phone_control as pc

    fresh = PhoneBridge(pairing_store=PairingStore(state_file=tmp_path / "s.json"))
    monkeypatch.setattr(pc, "phone_bridge", fresh)
    result = pc.PhoneStatusTool().execute()
    assert "No phone is paired" in result.content
    result = pc.PhoneOpenAppTool().execute(app_name="whatsapp")
    assert result.is_error and "No phone is paired" in result.content
    result = pc.PhoneMakeCallTool().execute(phone_number="12")
    assert result.is_error and "does not look like" in result.content


def test_tool_round_trip_through_execute_sync(tmp_path, monkeypatch):
    from friday.tools.builtin import phone_control as pc

    live = PhoneBridge(pairing_store=PairingStore(state_file=tmp_path / "s.json"))
    monkeypatch.setattr(pc, "phone_bridge", live)
    code = live.pairing.create_pairing_code()["pairing_code"]
    issued = live.pairing.consume_pairing_code(code, device_name="Pixel", executor="mock")
    device_id = issued["device_id"]
    sock = FakeSocket(live, device_id)

    loop = asyncio.new_event_loop()
    ready = threading.Event()

    async def serve():
        await live.register(device_id, sock, executor="mock", capabilities=list(ALLOWED_PHONE_COMMANDS))
        ready.set()
        await asyncio.sleep(30)

    thread = threading.Thread(target=lambda: loop.run_until_complete(serve()), daemon=True)
    thread.start()
    assert ready.wait(timeout=10)

    result = pc.PhoneOpenAppTool().execute(app_name="whatsapp")
    assert not result.is_error
    assert sock.executor.state["foreground_app"] == "whatsapp"
    result = pc.PhoneStatusTool().execute()
    assert not result.is_error
    assert "connected" in result.content
    loop.call_soon_threadsafe(loop.stop)


def test_mock_executor_covers_the_whole_allowlist():
    executor = MockPhoneExecutor()
    assert set(executor.capabilities) == set(ALLOWED_PHONE_COMMANDS)
    samples = {
        "device_status": {}, "open_app": {"app": "maps"}, "close_app": {"app": "maps"},
        "open_url": {"url": "https://example.org"}, "make_call": {"number": "+91123"},
        "send_sms": {"number": "+91123", "message": "x"},
        "send_whatsapp": {"number": "+91123", "message": "x"},
        "read_notifications": {"limit": 5}, "set_alarm": {"hour": 7, "minute": 30, "label": "up"},
        "media_control": {"action": "play"}, "set_volume": {"percent": 50, "stream": "music"},
        "find_phone": {"seconds": 5}, "tap": {"x": 1, "y": 2},
        "swipe": {"x1": 0, "y1": 0, "x2": 5, "y2": 5, "duration_ms": 100},
        "type_text": {"text": "hello"}, "press_key": {"key": "home"}, "screenshot": {},
    }
    for command, args in samples.items():
        ok, _output, error = executor.handle(command, args)
        assert ok, f"{command} failed on the mock: {error}"
    state_dump = json.dumps(executor.state)
    assert "hello" in state_dump  # typed text really accumulated


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
