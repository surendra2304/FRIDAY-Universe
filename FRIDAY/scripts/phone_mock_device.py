#!/usr/bin/env python3
"""Mock phone executor for TASK-PHONE-001 — a fake Android phone for tests.

Implements the phone-bridge protocol from the executor side against an
in-memory fake device, so the full round trip

    FRIDAY tool -> PhoneBridge -> WebSocket frames -> executor -> result

can be proven with zero hardware (FRIDAY/tests/test_phone_bridge.py drives
:class:`MockPhoneExecutor` through a fake socket). It can also run live
against a deployed FRIDAY to smoke-test the real routes:

    python phone_mock_device.py --pair 123456            # exchange a code
    python phone_mock_device.py                          # connect + serve

Requires the ``websockets`` package for live mode only; importing the
executor class (what the tests do) needs nothing beyond the stdlib.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://friday-universe.duckdns.org/friday"
CONFIG_PATH = Path.home() / ".friday_mock_phone.json"

ALL_CAPABILITIES = [
    "device_status",
    "open_app",
    "close_app",
    "open_url",
    "make_call",
    "send_sms",
    "send_whatsapp",
    "read_notifications",
    "set_alarm",
    "media_control",
    "set_volume",
    "find_phone",
    "tap",
    "swipe",
    "type_text",
    "press_key",
    "screenshot",
]

# 1x1 transparent PNG — the mock's "screen".
_FAKE_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class MockPhoneExecutor:
    """A fake phone: every command mutates inspectable fake state."""

    executor_name = "mock"
    capabilities = ALL_CAPABILITIES

    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "battery_percent": 87,
            "model": "MockPhone 12",
            "android_version": "15",
            "screen_on": True,
            "foreground_app": None,
            "calls": [],
            "sms": [],
            "whatsapp": [],
            "alarms": [],
            "notifications": [
                {"app": "com.whatsapp", "title": "WhatsApp", "text": "2 new messages"},
                {"app": "com.google.android.gm", "title": "Gmail", "text": "Your receipt is ready"},
            ],
            "media": {"playing": False, "track": None},
            "volume": {"music": 40, "ring": 60, "call": 50},
            "taps": [],
            "typed": "",
            "keys": [],
            "ringing": False,
        }

    def handle(self, command: str, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        """Execute one command; returns (ok, output, error)."""
        s = self.state
        if command == "device_status":
            return True, {
                "model": s["model"],
                "android_version": s["android_version"],
                "battery_percent": s["battery_percent"],
                "screen_on": s["screen_on"],
                "foreground_app": s["foreground_app"],
            }, None
        if command == "open_app":
            s["foreground_app"] = args.get("app")
            return True, f"opened {args.get('app')}", None
        if command == "close_app":
            if s["foreground_app"] == args.get("app"):
                s["foreground_app"] = None
            return True, f"closed {args.get('app')}", None
        if command == "open_url":
            s["foreground_app"] = "browser"
            return True, f"opened {args.get('url')}", None
        if command == "make_call":
            s["calls"].append({"number": args.get("number"), "at": _now_iso()})
            return True, f"calling {args.get('number')}", None
        if command == "send_sms":
            s["sms"].append({"number": args.get("number"), "message": args.get("message")})
            return True, "sms sent", None
        if command == "send_whatsapp":
            s["whatsapp"].append({"number": args.get("number"), "message": args.get("message")})
            return True, "whatsapp sent", None
        if command == "read_notifications":
            limit = int(args.get("limit") or 20)
            return True, s["notifications"][:limit], None
        if command == "set_alarm":
            s["alarms"].append({"hour": args.get("hour"), "minute": args.get("minute"), "label": args.get("label", "")})
            return True, f"alarm set for {args.get('hour'):02d}:{args.get('minute'):02d}", None
        if command == "media_control":
            action = str(args.get("action") or "")
            s["media"]["playing"] = action == "play"
            return True, f"media {action}", None
        if command == "set_volume":
            stream = str(args.get("stream") or "music")
            s["volume"][stream] = int(args.get("percent") or 0)
            return True, f"{stream} volume {args.get('percent')}%", None
        if command == "find_phone":
            s["ringing"] = True
            return True, f"ringing for {args.get('seconds')}s", None
        if command == "tap":
            s["taps"].append((args.get("x"), args.get("y")))
            return True, "tapped", None
        if command == "swipe":
            s["taps"].append(("swipe", args.get("x1"), args.get("y1"), args.get("x2"), args.get("y2")))
            return True, "swiped", None
        if command == "type_text":
            s["typed"] += str(args.get("text") or "")
            return True, "typed", None
        if command == "press_key":
            s["keys"].append(args.get("key"))
            return True, f"pressed {args.get('key')}", None
        if command == "screenshot":
            return True, _FAKE_PNG_B64, None
        return False, "", f"mock executor does not know command '{command}'"


async def _serve(base_url: str, device_id: str, token: str) -> None:
    import urllib.parse

    import websockets  # live mode only

    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    uri = f"{ws_base}/api/phone/connect/{device_id}?token={urllib.parse.quote(token)}"
    executor = MockPhoneExecutor()
    backoff = 5.0
    while True:
        try:
            async with websockets.connect(uri) as ws:
                await ws.send(json.dumps({
                    "type": "hello",
                    "executor": executor.executor_name,
                    "capabilities": executor.capabilities,
                }))
                backoff = 5.0
                heartbeat = asyncio.create_task(_heartbeat(ws))
                try:
                    async for raw in ws:
                        frame = json.loads(raw)
                        if frame.get("type") == "command":
                            started = _now_iso()
                            ok, output, error = executor.handle(
                                str(frame.get("command") or ""), dict(frame.get("args") or {})
                            )
                            await ws.send(json.dumps({
                                "type": "result",
                                "request_id": frame.get("request_id"),
                                "started_at": started,
                                "finished_at": _now_iso(),
                                "ok": ok,
                                "output": output,
                                "error": error,
                            }))
                finally:
                    heartbeat.cancel()
        except Exception as exc:  # reconnect forever, like the real agents
            print(f"[mock-phone] tunnel lost ({type(exc).__name__}); retry in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


async def _heartbeat(ws: Any) -> None:
    while True:
        await asyncio.sleep(25.0)
        await ws.send(json.dumps({"type": "ping", "at": time.time()}))


def _pair(base_url: str, code: str) -> dict[str, Any]:
    import urllib.request

    body = json.dumps({"pairing_code": code, "device_name": "Mock phone", "executor": "mock"}).encode()
    req = urllib.request.Request(
        f"{base_url}/api/phone/pair", data=body, headers={"Content-Type": "application/json"}, method="POST"
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FRIDAY mock phone executor")
    parser.add_argument("--base-url", default=os.getenv("FRIDAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--pair", metavar="CODE", help="exchange a pairing code, save credentials, exit")
    args = parser.parse_args(argv)

    if args.pair:
        issued = _pair(args.base_url, args.pair)
        CONFIG_PATH.write_text(json.dumps(issued), encoding="utf-8")
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass
        print(f"Paired as {issued['device_id']}; credentials saved to {CONFIG_PATH}")
        return 0

    if not CONFIG_PATH.exists():
        print("Not paired. Run with --pair <code> first.", file=sys.stderr)
        return 2
    creds = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    asyncio.run(_serve(args.base_url, creds["device_id"], creds["device_token"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
