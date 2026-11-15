#!/usr/bin/env python3
"""FRIDAY phone agent for Android — Termux executor (TASK-PHONE-001).

Runs on the owner's phone inside Termux and dials OUT to FRIDAY over WSS,
so it works behind carrier NAT and across Wi-Fi/mobile-data changes with no
inbound ports and no third-party relay. It executes the phone-bridge
command allowlist through Termux:API and Android intents.

SETUP (once, ~2 minutes — full walkthrough in docs/PHONE_CONTROL.md):
    1. Install Termux and Termux:API from F-Droid.
    2. In Termux:  pkg install -y python && pip install websockets
    3. Download this file into Termux and run:
           python phone_agent_termux.py --pair
       It asks for the 6-digit code FRIDAY gives you, exchanges it for a
       device token (saved to ~/.friday_phone_agent.json, mode 0600) and
       connects. Later runs need no code:  python phone_agent_termux.py

CAPABILITY HONESTY: this executor advertises exactly what Termux can do.
Android reserves touch injection (tap/swipe/type), screenshots and
force-stopping other apps for accessibility services / MediaProjection /
system permissions, so those commands are NOT in CAPABILITIES — the server
refuses them with a precise reason instead of pretending. The companion
app (FRIDAY/android-companion/) covers them. WhatsApp here opens the chat
with the message prefilled and reports that the final send tap belongs to
the owner; it never claims a message was sent when it was not.
"""

from __future__ import annotations

import argparse
import asyncio
import glob
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_BASE_URL = "https://friday-universe.duckdns.org/friday"
CONFIG_PATH = Path.home() / ".friday_phone_agent.json"
HEARTBEAT_SECONDS = 25.0

EXECUTOR_NAME = "termux"
CAPABILITIES = [
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

# Same friendly aliases as the ADB controller, so "open YouTube" means the
# same thing on every executor.
APP_PACKAGES = {
    "youtube": "com.google.android.youtube",
    "chrome": "com.android.chrome",
    "maps": "com.google.android.apps.maps",
    "camera": "com.android.camera",
    "settings": "com.android.settings",
    "messages": "com.google.android.apps.messaging",
    "phone": "com.google.android.dialer",
    "dialer": "com.google.android.dialer",
    "contacts": "com.google.android.contacts",
    "calculator": "com.google.android.calculator",
    "clock": "com.google.android.deskclock",
    "calendar": "com.google.android.calendar",
    "photos": "com.google.android.apps.photos",
    "gmail": "com.google.android.gm",
    "playstore": "com.android.vending",
    "whatsapp": "com.whatsapp",
    "spotify": "com.spotify.music",
    "instagram": "com.instagram.android",
    "telegram": "org.telegram.messenger",
    "netflix": "com.netflix.ninja",
}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _run(cmd: list[str], timeout: float = 20.0) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout.strip(), proc.stderr.strip()
    except FileNotFoundError:
        return -1, "", f"{cmd[0]} not found (is Termux:API installed?)"
    except subprocess.TimeoutExpired:
        return -2, "", f"{cmd[0]} timed out after {timeout}s"


def _package_for(app: str) -> str:
    text = (app or "").strip()
    return APP_PACKAGES.get(text.lower(), text)


# ---------------------------------------------------------------------------
# Command handlers — each returns (ok, output, error)
# ---------------------------------------------------------------------------


def _cmd_device_status(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    info: dict[str, Any] = {}
    rc, out, _ = _run(["termux-battery-status"], timeout=10.0)
    if rc == 0:
        try:
            batt = json.loads(out)
            info["battery_percent"] = batt.get("percentage")
            info["battery_status"] = batt.get("status")
        except Exception:
            pass
    rc, model, _ = _run(["getprop", "ro.product.model"], timeout=5.0)
    if rc == 0 and model:
        info["model"] = model
    rc, rel, _ = _run(["getprop", "ro.build.version.release"], timeout=5.0)
    if rc == 0 and rel:
        info["android_version"] = rel
    if not info:
        return False, "", "no status source answered (termux-battery-status/getprop)"
    return True, info, None


def _cmd_open_app(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    package = _package_for(str(args.get("app") or ""))
    if not package:
        return False, "", "no app given"
    # Resolve the launcher activity, then start it explicitly.
    rc, out, _ = _run(
        ["pm", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN",
         "-c", "android.intent.category.LAUNCHER", package],
        timeout=10.0,
    )
    component = ""
    if rc == 0 and out:
        for line in out.splitlines():
            line = line.strip()
            if "/" in line and " " not in line:
                component = line
    if component:
        rc, _o, err = _run(["am", "start", "-n", component], timeout=10.0)
        if rc == 0:
            return True, f"launched {package}", None
        return False, "", f"am start failed for {component}: {err or 'unknown error'}"
    # Fallback: monkey can still resolve the launcher entry on many builds.
    rc, _o, err = _run(
        ["monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1"], timeout=10.0
    )
    if rc == 0:
        return True, f"launched {package} (monkey)", None
    return False, "", (
        f"could not launch {package}: no launcher activity resolved and monkey failed "
        f"({err or 'unknown error'}). The app may not be installed, or Android blocked a "
        "background start — open Termux once and retry."
    )


def _cmd_open_url(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    url = str(args.get("url") or "")
    if not url:
        return False, "", "no url given"
    rc, _o, err = _run(["termux-open", url], timeout=10.0)
    if rc == 0:
        return True, f"opened {url}", None
    return False, "", f"termux-open failed: {err or 'unknown error'}"


def _cmd_make_call(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    number = str(args.get("number") or "")
    if not number:
        return False, "", "no number given"
    rc, _o, err = _run(["termux-telephony-call", number], timeout=15.0)
    if rc == 0:
        return True, f"calling {number}", None
    return False, "", f"call failed (CALL_PHONE permission granted to Termux:API?): {err or 'unknown error'}"


def _cmd_send_sms(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    number = str(args.get("number") or "")
    message = str(args.get("message") or "")
    if not number or not message:
        return False, "", "number and message are both required"
    rc, _o, err = _run(["termux-sms-send", "-n", number, message], timeout=20.0)
    if rc == 0:
        return True, f"sms sent to {number}", None
    return False, "", f"sms failed (SMS permission granted to Termux:API?): {err or 'unknown error'}"


def _cmd_send_whatsapp(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    number = str(args.get("number") or "").lstrip("+")
    message = str(args.get("message") or "")
    if not number or not message:
        return False, "", "number and message are both required"
    url = f"https://api.whatsapp.com/send?phone={number}&text={urllib.parse.quote(message)}"
    rc, _o, err = _run(
        ["am", "start", "-a", "android.intent.action.VIEW", "-d", url, "com.whatsapp"],
        timeout=10.0,
    )
    if rc != 0:
        return False, "", f"could not open WhatsApp: {err or 'unknown error'}"
    # Honest partial: the chat is open with the text in the box. Termux has
    # no input injection, so the send tap is the owner's — never claim sent.
    return False, (
        "WhatsApp chat opened with the message prefilled. The Termux agent cannot "
        "press Send (Android reserves touch injection for accessibility services), "
        "so the message is NOT sent yet — one tap on the phone sends it. The "
        "companion app completes this fully."
    ), "prefilled_only_manual_send_required"


def _cmd_read_notifications(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    rc, out, err = _run(["termux-notification-list"], timeout=15.0)
    if rc != 0:
        return False, "", (
            f"termux-notification-list failed (notification access granted to "
            f"Termux:API?): {err or 'unknown error'}"
        )
    try:
        items = json.loads(out or "[]")
    except Exception:
        return False, "", "notification list was not valid JSON"
    limit = int(args.get("limit") or 20)
    trimmed = [
        {
            "app": item.get("package") or item.get("app"),
            "title": item.get("title"),
            "text": item.get("content") or item.get("text"),
        }
        for item in items[:limit]
        if isinstance(item, dict)
    ]
    return True, trimmed, None


def _cmd_set_alarm(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    hour = int(args.get("hour") or 0)
    minute = int(args.get("minute") or 0)
    label = str(args.get("label") or "FRIDAY alarm")
    rc, _o, err = _run(
        [
            "am", "start",
            "-a", "android.intent.action.SET_ALARM",
            "--ei", "android.intent.extra.alarm.HOUR", str(hour),
            "--ei", "android.intent.extra.alarm.MINUTES", str(minute),
            "-e", "android.intent.extra.alarm.MESSAGE", label,
            "--ez", "android.intent.extra.alarm.SKIP_UI", "true",
        ],
        timeout=10.0,
    )
    if rc == 0:
        return True, f"alarm set for {hour:02d}:{minute:02d} ({label})", None
    return False, "", f"SET_ALARM intent failed (clock app may need the UI): {err or 'unknown error'}"


def _cmd_media_control(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    action = str(args.get("action") or "").lower()
    if action in {"next", "previous"}:
        return False, "", (
            f"media '{action}' needs a media key event, which the Termux agent "
            "cannot inject; the companion app can."
        )
    if action not in {"play", "pause", "stop"}:
        return False, "", f"unknown media action '{action}'"
    rc, _o, err = _run(["termux-media-player", action], timeout=10.0)
    if rc == 0:
        return True, f"media {action}", None
    return False, "", f"termux-media-player {action} failed: {err or 'unknown error'}"


def _volume_streams() -> dict[str, Any]:
    rc, out, _ = _run(["termux-volume"], timeout=10.0)
    if rc != 0:
        return {}
    try:
        data = json.loads(out or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _cmd_set_volume(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    stream = str(args.get("stream") or "music").lower()
    stream = {"music": "music", "ring": "ring", "call": "call"}.get(stream, "music")
    percent = max(0, min(int(args.get("percent") or 0), 100))
    streams = _volume_streams()
    info = streams.get(stream) or {}
    max_vol = int(info.get("max") or 15)
    index = round(percent / 100.0 * max_vol)
    rc, _o, err = _run(["termux-volume", stream, str(index)], timeout=10.0)
    if rc == 0:
        return True, f"{stream} volume set to {index}/{max_vol} (~{percent}%)", None
    return False, "", f"termux-volume failed: {err or 'unknown error'}"


def _find_ringtone() -> str | None:
    for pattern in ("/system/media/audio/ringtones/*.ogg", "/system/media/audio/ringtones/*.mp3",
                    "/system/media/audio/notifications/*.ogg"):
        hits = sorted(glob.glob(pattern))
        if hits:
            return hits[0]
    return None


def _cmd_find_phone(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    seconds = max(5, min(int(args.get("seconds") or 30), 120))
    ringtone = _find_ringtone()
    if not ringtone:
        return False, "", "no system ringtone file found to play"
    streams = _volume_streams()
    music_max = int((streams.get("music") or {}).get("max") or 15)
    _run(["termux-volume", "music", str(music_max)], timeout=10.0)
    rc, _o, err = _run(["termux-media-player", "play", ringtone], timeout=10.0)
    if rc != 0:
        return False, "", f"could not play the ringtone: {err or 'unknown error'}"
    time.sleep(seconds)
    _run(["termux-media-player", "stop"], timeout=10.0)
    return True, f"rang at full volume for {seconds}s", None


_HANDLERS = {
    "device_status": _cmd_device_status,
    "open_app": _cmd_open_app,
    "open_url": _cmd_open_url,
    "make_call": _cmd_make_call,
    "send_sms": _cmd_send_sms,
    "send_whatsapp": _cmd_send_whatsapp,
    "read_notifications": _cmd_read_notifications,
    "set_alarm": _cmd_set_alarm,
    "media_control": _cmd_media_control,
    "set_volume": _cmd_set_volume,
    "find_phone": _cmd_find_phone,
}


# ---------------------------------------------------------------------------
# Tunnel plumbing (mirrors scripts/laptop_bridge_client.py)
# ---------------------------------------------------------------------------


async def _heartbeat(ws: Any, send_lock: asyncio.Lock) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        async with send_lock:
            await ws.send(json.dumps({"type": "ping", "at": time.time()}))


async def _handle_command(ws: Any, send_lock: asyncio.Lock, frame: dict[str, Any]) -> None:
    request_id = frame.get("request_id")
    command = str(frame.get("command") or "")
    args = dict(frame.get("args") or {})
    timeout = float(frame.get("timeout") or 30.0)
    started = _now_iso()
    handler = _HANDLERS.get(command)
    if handler is None:
        ok, output, error = False, "", f"termux agent does not implement '{command}'"
    else:
        try:
            # Handlers block on subprocesses; keep them off the event loop so
            # heartbeats and further commands are still serviced.
            ok, output, error = await asyncio.to_thread(handler, args, timeout)
        except Exception as exc:  # an executor bug must still produce a result frame
            ok, output, error = False, "", f"executor error: {type(exc).__name__}: {exc}"
    payload = {
        "type": "result",
        "request_id": request_id,
        "started_at": started,
        "finished_at": _now_iso(),
        "ok": ok,
        "output": output,
        "error": error,
    }
    async with send_lock:
        await ws.send(json.dumps(payload))


async def _run_session(base_url: str, device_id: str, token: str) -> None:
    import websockets

    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    uri = f"{ws_base}/api/phone/connect/{device_id}?token={urllib.parse.quote(token)}"
    async with websockets.connect(uri) as ws:
        send_lock = asyncio.Lock()
        async with send_lock:
            await ws.send(json.dumps({
                "type": "hello",
                "executor": EXECUTOR_NAME,
                "capabilities": CAPABILITIES,
                "agent": "phone_agent_termux.py",
            }))
        heartbeat = asyncio.create_task(_heartbeat(ws, send_lock))
        try:
            async for raw in ws:
                try:
                    frame = json.loads(raw)
                except Exception:
                    continue
                if not isinstance(frame, dict):
                    continue
                if frame.get("type") == "command":
                    asyncio.create_task(_handle_command(ws, send_lock, frame))
        finally:
            heartbeat.cancel()


async def _run_forever(base_url: str, device_id: str, token: str) -> None:
    backoff = 5.0
    while True:
        try:
            await _run_session(base_url, device_id, token)
            print("[friday-phone] tunnel closed cleanly; reconnecting", flush=True)
            backoff = 5.0
        except Exception as exc:
            print(f"[friday-phone] tunnel lost ({type(exc).__name__}); retry in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


def _pair(base_url: str, code: str, name: str) -> dict[str, Any]:
    body = json.dumps({
        "pairing_code": code,
        "device_name": name or "Android phone (Termux)",
        "executor": EXECUTOR_NAME,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/phone/pair", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def _save_config(issued: dict[str, Any]) -> None:
    CONFIG_PATH.write_text(json.dumps(issued), encoding="utf-8")
    try:
        os.chmod(CONFIG_PATH, 0o600)
    except OSError:
        pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FRIDAY phone agent (Termux executor)")
    parser.add_argument("--base-url", default=os.getenv("FRIDAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--pair", action="store_true", help="pair with a 6-digit code from FRIDAY, then connect")
    parser.add_argument("--name", default="", help="device name shown to FRIDAY when pairing")
    args = parser.parse_args(argv)

    if args.pair:
        code = input("Enter the 6-digit pairing code FRIDAY gave you: ").strip()
        try:
            issued = _pair(args.base_url, code, args.name)
        except Exception as exc:
            print(f"Pairing failed: {exc}", file=sys.stderr)
            return 1
        _save_config(issued)
        print(f"Paired as {issued['device_id']}. Token saved to {CONFIG_PATH} (0600).")
    elif not CONFIG_PATH.exists():
        print("Not paired yet. Run once with --pair.", file=sys.stderr)
        return 2

    creds = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    _run(["termux-wake-lock"], timeout=5.0)  # best effort; harmless if absent
    print(f"[friday-phone] connecting as {creds['device_id']} …", flush=True)
    try:
        asyncio.run(_run_forever(args.base_url, creds["device_id"], creds["device_token"]))
    except KeyboardInterrupt:
        _run(["termux-wake-unlock"], timeout=5.0)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
