#!/usr/bin/env python3
"""FRIDAY phone UI agent — ADB executor (TASK-IG-LAP-01).

Gives FRIDAY's phone control the one thing TASK-PHONE-001 could not ship:
a working executor for the UI commands already in the phone-bridge
allowlist (``tap``, ``swipe``, ``type_text``, ``press_key``, ``screenshot``)
plus one new observation command, ``ui_dump`` (the on-screen UI hierarchy).

WHY IT RUNS ON THE OWNER'S PC: Android reserves touch injection and screen
capture for on-device accessibility services, an attached debugger (ADB),
or a rooted phone. The Termux agent has none of those, so it honestly does
not advertise the UI commands. This agent runs on the owner's computer —
the same place Google's ARTEMIS framework runs — with the phone attached
over USB or Wi-Fi ADB, and drives it through ``adb``:

    phone <--USB / Wi-Fi ADB--> this agent <--WSS dial-out--> FRIDAY cloud

It speaks the exact phone-bridge protocol from TASK-PHONE-001 (pairing
code -> per-device token, hash-only server side, hello/capabilities,
command/result frames). Nothing about the server protocol changes; this
is a second executor next to the Termux agent and the companion app, and
each advertises only the capabilities it can really serve.

SETUP (once — full walkthrough in docs/PHONE_UI_AUTOMATION.md):
    1. Install Android platform-tools (``adb``) on this computer.
    2. On the phone: enable Developer options + USB debugging (or Wireless
       debugging), attach it, and approve the debugging prompt.
    3. pip install websockets
    4. python phone_ui_agent_adb.py --pair     # type FRIDAY's 6-digit code
       python phone_ui_agent_adb.py            # later runs: just this
    Optional: --mirror also launches scrcpy (if installed) so you can
    watch the phone screen on the PC while FRIDAY drives it.

PATTERN REFERENCES (no code copied): google/artemis (Apache-2.0 — the
observe-hierarchy-then-act pattern; ARTEMIS itself needs Python 3.12 so
it cannot run on the fleet's 3.10 hosts, hence this stdlib executor),
Dinesh210805/aura-android-use (AGPL-3.0 — pattern reference only),
Genymobile/scrcpy (Apache-2.0 — adopted as the external mirror tool).
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_BASE_URL = "https://friday-universe.duckdns.org/friday"
CONFIG_PATH = Path.home() / ".friday_phone_ui_agent.json"
HEARTBEAT_SECONDS = 25.0

EXECUTOR_NAME = "adb-ui"
CAPABILITIES = [
    "device_status",
    "open_app",
    "close_app",
    "open_url",
    "tap",
    "swipe",
    "type_text",
    "press_key",
    "screenshot",
    "ui_dump",
]

# Same friendly aliases as the Termux agent / ADB controller, so "open
# YouTube" means the same thing on every executor.
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

# Android keyevent codes (subset of friday.devices.android_controller's
# KEY_EVENT_MAP, plus the dpad/editing keys a UI driver actually needs).
KEY_EVENT_MAP = {
    "home": 3,
    "back": 4,
    "call": 5,
    "endcall": 6,
    "dpad_up": 19,
    "dpad_down": 20,
    "dpad_left": 21,
    "dpad_right": 22,
    "dpad_center": 23,
    "volume_up": 24,
    "volume_down": 25,
    "power": 26,
    "camera": 27,
    "tab": 61,
    "space": 62,
    "enter": 66,
    "delete": 67,
    "backspace": 67,
    "menu": 82,
    "search": 84,
    "media_play_pause": 85,
    "media_stop": 86,
    "media_next": 87,
    "media_previous": 88,
    "escape": 111,
    "page_up": 92,
    "page_down": 93,
    "move_home": 122,
    "move_end": 123,
    "app_switch": 187,
    "overview": 187,
    "wake": 224,
    "sleep": 223,
}

MAX_UI_NODES = 120
_BOUNDS_RE = re.compile(r"\[(\d+),(\d+)\]\[(\d+),(\d+)\]")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _package_for(app: str) -> str:
    text = (app or "").strip()
    return APP_PACKAGES.get(text.lower(), text)


def escape_input_text(text: str) -> str:
    """Escape text for ``adb shell input text``.

    The device shell re-parses the argument, so shell metacharacters are
    backslash-escaped, literal ``%`` is escaped (``%s`` is the space
    token), and spaces become ``%s``. Non-ASCII characters pass through;
    stock ``input text`` drops some of them on some devices — the caller
    surfaces that honestly instead of claiming every glyph landed.
    """
    out = text.replace("\\", "\\\\").replace("%", "\\%")
    for ch in "\"'`$&|;()<>#":
        out = out.replace(ch, "\\" + ch)
    return out.replace(" ", "%s")


def parse_bounds(raw: str) -> tuple[int, int, int, int] | None:
    match = _BOUNDS_RE.match((raw or "").strip())
    if not match:
        return None
    return tuple(int(g) for g in match.groups())  # type: ignore[return-value]


def prune_ui_xml(xml_text: str, max_nodes: int = MAX_UI_NODES) -> dict[str, Any]:
    """Reduce a uiautomator XML dump to the nodes a planner can act on.

    Keeps nodes that carry text, a content description or a resource id,
    or that are clickable/focusable — the rest is layout scaffolding.
    Password fields are flagged, never given values.
    """
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as exc:
        return {"nodes": [], "count": 0, "parse_error": f"uiautomator XML did not parse: {exc}"}
    nodes: list[dict[str, Any]] = []
    total = 0
    for element in root.iter("node"):
        attrib = element.attrib
        text = (attrib.get("text") or "").strip()
        desc = (attrib.get("content-desc") or "").strip()
        res_id = (attrib.get("resource-id") or "").strip()
        clickable = attrib.get("clickable") == "true"
        focusable = attrib.get("focusable") == "true"
        if not (text or desc or res_id or clickable or focusable):
            continue
        total += 1
        if len(nodes) >= max_nodes:
            continue
        bounds = parse_bounds(attrib.get("bounds") or "")
        node: dict[str, Any] = {
            "text": text,
            "desc": desc,
            "id": res_id,
            "class": (attrib.get("class") or "").rsplit(".", 1)[-1],
            "package": attrib.get("package") or "",
            "clickable": clickable,
            "focused": attrib.get("focused") == "true",
            "password": attrib.get("password") == "true",
        }
        if bounds:
            x1, y1, x2, y2 = bounds
            node["bounds"] = [x1, y1, x2, y2]
            node["center"] = [(x1 + x2) // 2, (y1 + y2) // 2]
        nodes.append(node)
    return {"nodes": nodes, "count": total, "truncated": total > len(nodes)}


# ---------------------------------------------------------------------------
# ADB transport
# ---------------------------------------------------------------------------

Runner = Callable[[list[str], float], tuple[int, bytes, bytes]]


def _subprocess_runner(argv: list[str], timeout: float) -> tuple[int, bytes, bytes]:
    try:
        proc = subprocess.run(argv, capture_output=True, timeout=timeout, check=False)
        return proc.returncode, proc.stdout, proc.stderr
    except FileNotFoundError:
        return -1, b"", f"{argv[0]} not found".encode()
    except subprocess.TimeoutExpired:
        return -2, b"", f"{argv[0]} timed out after {timeout}s".encode()


class AdbError(RuntimeError):
    """ADB is missing or the phone is not reachable over it."""


class AdbClient:
    """Thin, testable wrapper over the ``adb`` CLI."""

    def __init__(
        self,
        serial: str | None = None,
        runner: Runner | None = None,
        adb_path: str | None = None,
    ) -> None:
        self.serial = serial
        self.runner = runner or _subprocess_runner
        self.adb_path = adb_path or shutil.which("adb") or "adb"

    def _argv(self, *parts: str) -> list[str]:
        argv = [self.adb_path]
        if self.serial:
            argv += ["-s", self.serial]
        return argv + list(parts)

    def run(self, parts: list[str], timeout: float = 20.0) -> tuple[int, str, str]:
        rc, out, err = self.runner(self._argv(*parts), timeout)
        return rc, out.decode("utf-8", "replace").strip(), err.decode("utf-8", "replace").strip()

    def run_bytes(self, parts: list[str], timeout: float = 30.0) -> tuple[int, bytes, str]:
        rc, out, err = self.runner(self._argv(*parts), timeout)
        return rc, out, err.decode("utf-8", "replace").strip()

    def connect(self, host_port: str) -> tuple[bool, str]:
        rc, out, err = self.runner([self.adb_path, "connect", host_port], 15.0)
        text = out.decode("utf-8", "replace").strip() or err.decode("utf-8", "replace").strip()
        return rc == 0 and "connected" in text, text

    def attached_serials(self) -> list[str]:
        rc, out, _ = self.runner([self.adb_path, "devices"], 15.0)
        if rc == -1:
            raise AdbError(
                "adb is not installed on this computer. Install Android "
                "platform-tools, then re-run. (docs/PHONE_UI_AUTOMATION.md)"
            )
        if rc != 0:
            raise AdbError(f"'adb devices' failed (rc={rc})")
        serials = []
        for line in out.decode("utf-8", "replace").splitlines():
            fields = line.strip().split()
            if len(fields) >= 2 and fields[1] == "device":
                serials.append(fields[0])
        return serials

    def ensure_device(self) -> str:
        """Resolve which attached phone to drive, or raise AdbError."""
        serials = self.attached_serials()
        if self.serial:
            if self.serial in serials:
                return self.serial
            raise AdbError(
                f"Phone '{self.serial}' is not attached over ADB "
                f"(attached: {serials or 'none'}). Check USB debugging / "
                "Wi-Fi debugging and approve the prompt on the phone."
            )
        if len(serials) == 1:
            self.serial = serials[0]
            return self.serial
        if not serials:
            raise AdbError(
                "No phone is attached over ADB. Connect it by USB (or run "
                "with --adb-connect <phone-ip>:5555) and approve the "
                "debugging prompt on the phone."
            )
        raise AdbError(
            f"More than one ADB device is attached ({', '.join(serials)}); "
            "pass --adb-serial to choose one."
        )

    # -- device primitives -------------------------------------------------

    def shell(self, *parts: str, timeout: float = 20.0) -> tuple[int, str, str]:
        return self.run(["shell", *parts], timeout=timeout)

    def getprop(self, name: str) -> str:
        rc, out, _ = self.shell("getprop", name, timeout=10.0)
        return out if rc == 0 else ""

    def screencap_png(self) -> bytes:
        rc, data, err = self.run_bytes(["exec-out", "screencap", "-p"], timeout=30.0)
        if rc != 0 or not data.startswith(b"\x89PNG"):
            raise AdbError(f"screencap failed: {err or f'rc={rc}'}")
        return data

    def ui_xml(self) -> str:
        rc, _, err = self.shell("uiautomator", "dump", "/sdcard/window_dump.xml", timeout=25.0)
        if rc != 0:
            raise AdbError(f"uiautomator dump failed: {err or f'rc={rc}'}")
        rc, data, err = self.run_bytes(["exec-out", "cat", "/sdcard/window_dump.xml"], timeout=15.0)
        if rc != 0 or not data:
            raise AdbError(f"could not read UI dump: {err or f'rc={rc}'}")
        return data.decode("utf-8", "replace")


# ---------------------------------------------------------------------------
# Executor: phone-bridge commands -> ADB primitives
# ---------------------------------------------------------------------------


class PhoneUiExecutor:
    """Serves the phone-bridge UI commands by driving the phone over ADB."""

    executor_name = EXECUTOR_NAME
    capabilities = CAPABILITIES

    def __init__(self, adb: AdbClient) -> None:
        self.adb = adb

    def handle(self, command: str, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        handler = getattr(self, f"_cmd_{command}", None)
        if handler is None:
            return False, "", f"adb-ui executor does not serve command '{command}'"
        try:
            self.adb.ensure_device()
        except AdbError as exc:
            return False, "", str(exc)
        try:
            return handler(args)
        except AdbError as exc:
            return False, "", str(exc)
        except Exception as exc:  # an executor must answer, never hang the bridge
            return False, "", f"{type(exc).__name__}: {exc}"

    # -- commands ----------------------------------------------------------

    def _cmd_device_status(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        info: dict[str, Any] = {
            "model": self.adb.getprop("ro.product.model"),
            "android_version": self.adb.getprop("ro.build.version.release"),
            "serial": self.adb.serial,
            "executor": EXECUTOR_NAME,
        }
        rc, out, _ = self.adb.shell("dumpsys", "battery", timeout=10.0)
        if rc == 0:
            for line in out.splitlines():
                if "level:" in line:
                    try:
                        info["battery_percent"] = int(line.rsplit(":", 1)[1].strip())
                    except ValueError:
                        pass
        rc, out, _ = self.adb.shell("wm", "size", timeout=10.0)
        if rc == 0 and ":" in out:
            info["screen_size"] = out.rsplit(":", 1)[1].strip()
        rc, out, _ = self.adb.shell("dumpsys", "window", "windows", timeout=10.0)
        if rc == 0:
            for line in out.splitlines():
                if "mCurrentFocus" in line and "/" in line:
                    info["foreground"] = line.split("=", 1)[-1].strip().strip("}")
                    break
        return True, info, None

    def _cmd_open_app(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        app = str(args.get("app") or "").strip()
        if not app:
            return False, "", "open_app requires an 'app' argument"
        package = _package_for(app)
        rc, out, err = self.adb.shell(
            "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1", timeout=20.0
        )
        if rc == 0 and "Events injected" in out + err:
            return True, f"opened {package}", None
        # Fall back to resolving the launcher activity explicitly.
        rc2, resolved, _ = self.adb.shell(
            "cmd", "package", "resolve-activity", "--brief", "-c",
            "android.intent.category.LAUNCHER", package, timeout=15.0,
        )
        activity = resolved.splitlines()[-1].strip() if rc2 == 0 and resolved else ""
        if activity and "/" in activity:
            rc3, _, err3 = self.adb.shell("am", "start", "-n", activity, timeout=15.0)
            if rc3 == 0:
                return True, f"opened {package} ({activity})", None
            return False, "", f"could not start {package}: {err3}"
        return False, "", f"could not open '{app}' ({package}): {err or out or 'no launcher activity'}"

    def _cmd_close_app(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        app = str(args.get("app") or "").strip()
        if not app:
            return False, "", "close_app requires an 'app' argument"
        package = _package_for(app)
        rc, _, err = self.adb.shell("am", "force-stop", package, timeout=15.0)
        if rc == 0:
            return True, f"force-stopped {package}", None
        return False, "", f"force-stop {package} failed: {err}"

    def _cmd_open_url(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        url = str(args.get("url") or "").strip()
        parsed = urllib.parse.urlparse(url)
        if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
            return False, "", "open_url only accepts absolute http(s) URLs"
        rc, _, err = self.adb.shell(
            "am", "start", "-a", "android.intent.action.VIEW", "-d", url, timeout=15.0
        )
        if rc == 0:
            return True, f"opened {url}", None
        return False, "", f"open_url failed: {err}"

    @staticmethod
    def _coord(args: dict[str, Any], key: str) -> int:
        try:
            value = int(args.get(key))
        except (TypeError, ValueError):
            raise AdbError(f"argument '{key}' must be an integer pixel coordinate")
        if value < 0 or value > 20000:
            raise AdbError(f"argument '{key}' is out of range: {value}")
        return value

    def _cmd_tap(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        x, y = self._coord(args, "x"), self._coord(args, "y")
        rc, _, err = self.adb.shell("input", "tap", str(x), str(y), timeout=10.0)
        return (True, f"tapped ({x}, {y})", None) if rc == 0 else (False, "", f"tap failed: {err}")

    def _cmd_swipe(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        x1, y1 = self._coord(args, "x1"), self._coord(args, "y1")
        x2, y2 = self._coord(args, "x2"), self._coord(args, "y2")
        try:
            duration = int(args.get("duration_ms") or 300)
        except (TypeError, ValueError):
            duration = 300
        duration = max(50, min(3000, duration))
        rc, _, err = self.adb.shell(
            "input", "swipe", str(x1), str(y1), str(x2), str(y2), str(duration), timeout=10.0
        )
        return (True, f"swiped ({x1}, {y1}) -> ({x2}, {y2})", None) if rc == 0 else (
            False, "", f"swipe failed: {err}")

    def _cmd_type_text(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        text = str(args.get("text") or "")
        if not text:
            return False, "", "type_text requires a 'text' argument"
        if len(text) > 4096:
            return False, "", "type_text is limited to 4096 characters per call"
        rc, _, err = self.adb.shell("input", "text", escape_input_text(text), timeout=20.0)
        if rc != 0:
            return False, "", f"type_text failed: {err}"
        note = f"typed {len(text)} characters"
        if any(ord(ch) > 127 for ch in text):
            note += (" (note: stock 'adb input text' drops some non-ASCII "
                     "characters on some devices; check the phone to confirm)")
        return True, note, None

    def _cmd_press_key(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        key = str(args.get("key") or "").strip().lower()
        if not key:
            return False, "", "press_key requires a 'key' argument"
        code = KEY_EVENT_MAP.get(key)
        if code is None:
            try:
                code = int(key)
            except ValueError:
                return False, "", (
                    f"unknown key '{key}'; known keys: {', '.join(sorted(KEY_EVENT_MAP))}"
                )
            if not 0 <= code <= 300:
                return False, "", f"key code out of range: {code}"
        rc, _, err = self.adb.shell("input", "keyevent", str(code), timeout=10.0)
        return (True, f"pressed {key} ({code})", None) if rc == 0 else (
            False, "", f"press_key failed: {err}")

    def _cmd_screenshot(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        png = self.adb.screencap_png()
        return True, base64.b64encode(png).decode("ascii"), None

    def _cmd_ui_dump(self, args: dict[str, Any]) -> tuple[bool, Any, str | None]:
        return True, prune_ui_xml(self.adb.ui_xml()), None


# ---------------------------------------------------------------------------
# Tunnel plumbing (same protocol as scripts/phone_mock_device.py)
# ---------------------------------------------------------------------------


async def _serve(base_url: str, device_id: str, token: str, executor: PhoneUiExecutor) -> None:
    import websockets  # live mode only

    ws_base = base_url.replace("https://", "wss://").replace("http://", "ws://")
    uri = f"{ws_base}/api/phone/connect/{device_id}?token={urllib.parse.quote(token)}"
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
                            ok, output, error = await asyncio.to_thread(
                                executor.handle,
                                str(frame.get("command") or ""),
                                dict(frame.get("args") or {}),
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
        except Exception as exc:  # reconnect forever, like the other agents
            print(f"[phone-ui] tunnel lost ({type(exc).__name__}); retry in {backoff:.0f}s", flush=True)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 60.0)


async def _heartbeat(ws: Any) -> None:
    while True:
        await asyncio.sleep(HEARTBEAT_SECONDS)
        await ws.send(json.dumps({"type": "ping", "at": time.time()}))


def _pair(base_url: str, code: str) -> dict[str, Any]:
    body = json.dumps({
        "pairing_code": code, "device_name": "Phone (ADB UI agent)", "executor": EXECUTOR_NAME,
    }).encode()
    req = urllib.request.Request(
        f"{base_url}/api/phone/pair", data=body,
        headers={"Content-Type": "application/json"}, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="FRIDAY phone UI agent (ADB executor)")
    parser.add_argument("--base-url", default=os.getenv("FRIDAY_BASE_URL", DEFAULT_BASE_URL))
    parser.add_argument("--pair", nargs="?", const="", metavar="CODE",
                        help="exchange a 6-digit pairing code (prompts if omitted), save credentials, exit")
    parser.add_argument("--adb-serial", default=os.getenv("FRIDAY_PHONE_ADB_SERIAL", ""),
                        help="ADB serial of the phone to drive (default: the only attached device)")
    parser.add_argument("--adb-connect", default=os.getenv("FRIDAY_PHONE_ADB_CONNECT", ""),
                        help="host:port for Wi-Fi ADB (adb connect) before serving")
    parser.add_argument("--mirror", action="store_true",
                        help="also launch scrcpy (if installed) so you can watch the phone screen")
    args = parser.parse_args(argv)

    adb = AdbClient(serial=args.adb_serial or None)
    if args.adb_connect:
        ok, text = adb.connect(args.adb_connect)
        print(f"adb connect {args.adb_connect}: {text}")
        if not ok:
            return 2
    try:
        serial = adb.ensure_device()
    except AdbError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"Driving phone {serial} via ADB ({adb.getprop('ro.product.model') or 'unknown model'})")

    if args.mirror:
        scrcpy = shutil.which("scrcpy")
        if scrcpy:
            subprocess.Popen([scrcpy, "-s", serial],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print("scrcpy mirror launched.")
        else:
            print("scrcpy is not installed; continuing without the mirror "
                  "(install scrcpy to watch the phone screen here).")

    if args.pair is not None:
        code = args.pair or input("Enter the 6-digit pairing code from FRIDAY: ").strip()
        issued = _pair(args.base_url, code)
        CONFIG_PATH.write_text(json.dumps(issued), encoding="utf-8")
        try:
            os.chmod(CONFIG_PATH, 0o600)
        except OSError:
            pass
        print(f"Paired as {issued['device_id']}; credentials saved to {CONFIG_PATH}")
        return 0

    if not CONFIG_PATH.exists():
        print("Not paired. Run with --pair first.", file=sys.stderr)
        return 2
    creds = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    asyncio.run(_serve(args.base_url, creds["device_id"], creds["device_token"], PhoneUiExecutor(adb)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
