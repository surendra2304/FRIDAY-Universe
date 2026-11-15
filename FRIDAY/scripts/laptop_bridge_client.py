"""Outbound tunnel client for the owner's laptop.

The laptop has no public address, so it dials the cloud FRIDAY and holds the
WebSocket open. FRIDAY sends allowlisted command frames; this client runs them
locally and returns the evidence record.

Usage (from the FRIDAY repo root)::

    set FRIDAY_API_KEY=<control key>
    set FRIDAY_CONTROL_TOKEN=<control token from /api/control/session>
    python scripts/laptop_bridge_client.py

or::

    python -m scripts.laptop_bridge_client

Environment:

``FRIDAY_BRIDGE_URL``
    Tunnel URL template. ``{laptop_id}`` (or ``<id>``) is substituted; a URL
    without a placeholder is treated as the base and the id is appended.
    Defaults to ``wss://friday-universe.duckdns.org/friday/api/laptop/connect/{laptop_id}``.
``FRIDAY_API_KEY``
    Required. The same control key the cloud FRIDAY was configured with. It is
    sent in the ``X-FRIDAY-Api-Key`` header (or used to validate a control token)
    and is never logged.
``FRIDAY_CONTROL_TOKEN``
    Optional. A short-lived control token from ``/api/control/session``. When
    set, it is sent as a ``token`` query parameter on the WebSocket upgrade,
    which is the preferred authentication method for the laptop bridge.
``FRIDAY_LAPTOP_ID``
    Stable device name; defaults to the hostname.
``FRIDAY_LAPTOP_ALLOW_SHELL``
    ``run_shell`` is refused unless this is ``true`` on the laptop *and* on the
    cloud host.

Commands (TASK-LAP-001 additions marked *): ``screenshot`` (saves a PNG on the
laptop and returns its path), ``screenshot_data`` * (returns the image itself
as a base64 JPEG attachment so FRIDAY can actually see the screen),
``open_url``, ``open_app`` * (launch an application by name), ``type_text`` *
and ``click`` * (keyboard/mouse via pyautogui, or xdotool on Linux),
``list_files``, ``read_file``, ``run_shell``, ``system_info``, ``notify``.

Optional laptop-side dependencies: Pillow (screenshots), pyautogui
(type/click; xdotool is the Linux fallback), plyer or win10toast (notify),
psutil (richer system_info). Every command degrades to an honest error naming
the missing dependency instead of failing silently.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import inspect
import json
import logging
import os
import platform
import random
import re
import socket
import subprocess
import sys
import tempfile
import time
import webbrowser
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

_REPO_SRC = Path(__file__).resolve().parents[1] / "src"
if str(_REPO_SRC) not in sys.path:
    sys.path.insert(0, str(_REPO_SRC))

import websockets  # noqa: E402

try:
    from friday.core.logging import get_logger  # noqa: E402

    logger = get_logger("scripts.laptop_bridge_client")
except Exception:  # standalone copy outside a repo checkout (owner's laptop)
    logging.basicConfig(
        level=os.getenv("FRIDAY_LAPTOP_LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] [%(levelname)s] [laptop-bridge]: %(message)s",
    )
    logger = logging.getLogger("scripts.laptop_bridge_client")

DEFAULT_BRIDGE_URL = (
    "wss://friday-universe.duckdns.org/friday/api/laptop/connect/{laptop_id}"
)
HEARTBEAT_SECONDS = 20.0
DEFAULT_COMMAND_TIMEOUT = 30.0
MAX_OUTPUT_BYTES = 16 * 1024
RECONNECT_BASE_SECONDS = 1.0
RECONNECT_MAX_SECONDS = 60.0
MAX_ARGS_BYTES = 64 * 1024
SHELL_COMMAND = "run_shell"
ALLOWED_COMMANDS = frozenset(
    {
        "screenshot",
        "screenshot_data",
        "open_url",
        "open_app",
        "type_text",
        "click",
        "list_files",
        "read_file",
        SHELL_COMMAND,
        "system_info",
        "notify",
        "lock_screen",
    }
)
_TRUNCATION_MARKER = "\n[truncated]"
_INVALID_ID_CHARS = re.compile(r"[^A-Za-z0-9_.:-]+")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _shell_enabled() -> bool:
    return os.getenv("FRIDAY_LAPTOP_ALLOW_SHELL", "").strip().lower() in {"1", "true", "yes", "on"}


def _bounded(value: Any, limit: int = MAX_OUTPUT_BYTES) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value
    else:
        try:
            text = json.dumps(value, default=str)
        except (TypeError, ValueError):
            text = str(value)
    raw = text.encode("utf-8", errors="replace")
    if len(raw) <= limit:
        return text
    marker = _TRUNCATION_MARKER.encode("utf-8")
    keep = max(0, limit - len(marker))
    return raw[:keep].decode("utf-8", errors="ignore") + _TRUNCATION_MARKER


def _clamp_int(value: Any, default: int, low: int, high: int) -> int:
    try:
        number = int(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _safe_url(uri: str) -> str:
    """A loggable form of the tunnel URL: no query string, no credentials."""
    parsed = urlparse(uri)
    port = f":{parsed.port}" if parsed.port else ""
    return f"{parsed.scheme}://{parsed.hostname or ''}{port}{parsed.path}"


def _laptop_id() -> str:
    raw = (os.getenv("FRIDAY_LAPTOP_ID") or socket.gethostname() or "laptop").strip()
    safe = _INVALID_ID_CHARS.sub("-", raw).strip("-.")
    return (safe or "laptop")[:64]


def _bridge_url(laptop_id: str, override: str | None = None) -> str:
    template = (override or os.getenv("FRIDAY_BRIDGE_URL") or DEFAULT_BRIDGE_URL).strip()
    encoded = quote(laptop_id, safe="")
    if "{laptop_id}" in template:
        return template.replace("{laptop_id}", encoded)
    if "<id>" in template:
        return template.replace("<id>", encoded)
    return template.rstrip("/") + "/" + encoded


def _connect(uri: str, api_key: str, control_token: str | None = None) -> Any:
    """Open a WebSocket across ``websockets`` 11-15 header-kwarg changes.

    If ``control_token`` is provided, it is appended as a ``token`` query
    parameter (preferred by the server for WebSocket upgrades). Otherwise the
    raw ``api_key`` is sent in the ``X-FRIDAY-Api-Key`` header.
    """
    params = inspect.signature(websockets.connect).parameters
    header_kwarg = "additional_headers" if "additional_headers" in params else "extra_headers"

    if control_token:
        # Append token as query param; avoid double-encoding if URI already has query
        sep = "&" if "?" in uri else "?"
        uri = f"{uri}{sep}token={quote(control_token, safe='')}"
        connect_kwargs = {
            "ping_interval": 20,
            "ping_timeout": 20,
            "open_timeout": 20,
            "max_size": 2**22,
        }
    else:
        connect_kwargs = {
            header_kwarg: {"X-FRIDAY-Api-Key": api_key},
            "ping_interval": 20,
            "ping_timeout": 20,
            "open_timeout": 20,
            "max_size": 2**22,
        }
    return websockets.connect(uri, **connect_kwargs)


# ---------------------------------------------------------------------------
# Local command implementations. Each returns (ok, output, error).
# ---------------------------------------------------------------------------


def _cmd_screenshot(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    try:
        from PIL import ImageGrab
    except ImportError:
        return False, "", "Pillow is not installed; screenshot capture is unavailable"
    try:
        image = ImageGrab.grab()
        directory = Path(tempfile.gettempdir()) / "friday-laptop-bridge"
        directory.mkdir(parents=True, exist_ok=True)
        target = directory / f"screenshot-{int(time.time() * 1000)}.png"
        image.save(target)
        return True, str(target), None
    except Exception as exc:
        return False, "", f"screenshot failed: {type(exc).__name__}: {exc}"


def _cmd_screenshot_data(args: dict[str, Any], timeout: float):
    """Capture the screen and return the image itself as an attachment.

    The plain ``screenshot`` command only returns a laptop-local path, which
    the cloud can never see. This variant downscales to at most ``max_width``
    pixels wide, JPEG-encodes, and ships base64 in the result frame's
    ``attachment`` field — the one channel the server registry passes through
    outside the 16 KB evidence bound (see friday.remote.laptop_bridge).
    """
    try:
        from PIL import ImageGrab
    except ImportError:
        return False, "", "Pillow is not installed; screenshot capture is unavailable", None
    try:
        import base64
        import io

        image = ImageGrab.grab().convert("RGB")
        max_width = _clamp_int(args.get("max_width"), default=1280, low=320, high=1920)
        if image.width > max_width:
            height = max(1, round(image.height * max_width / image.width))
            image = image.resize((max_width, height))
        buffer = io.BytesIO()
        image.save(buffer, format="JPEG", quality=72)
        payload = buffer.getvalue()
        attachment = {
            "kind": "image",
            "format": "jpeg",
            "width": image.width,
            "height": image.height,
            "base64": base64.b64encode(payload).decode("ascii"),
        }
        summary = json.dumps(
            {"width": image.width, "height": image.height, "format": "jpeg", "bytes": len(payload)}
        )
        return True, summary, None, attachment
    except Exception as exc:
        return False, "", f"screenshot_data failed: {type(exc).__name__}: {exc}", None


def _cmd_open_app(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    app = str(args.get("app") or args.get("application") or args.get("name") or "").strip()
    if not app:
        return False, "", "open_app requires an 'app' argument"
    import shutil

    try:
        if os.name == "nt":
            # App Paths / protocol URIs (ms-settings:, etc.) resolve via the shell.
            try:
                os.startfile(app)  # type: ignore[attr-defined]
                return True, f"Launch requested for '{app}' via Windows shell.", None
            except OSError:
                resolved = shutil.which(app)
                if resolved:
                    subprocess.Popen([resolved])
                    return True, f"Launched '{app}' ({resolved}).", None
                raise
        if sys.platform == "darwin":
            completed = subprocess.run(
                ["open", "-a", app], capture_output=True, timeout=max(1.0, timeout), check=False
            )
            if completed.returncode == 0:
                return True, f"Launched '{app}' via open -a.", None
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            return False, "", f"open -a {app} failed: {detail or 'application not found'}"
        # Linux / other POSIX: resolve on PATH, or an explicit path.
        resolved = shutil.which(app)
        if resolved:
            subprocess.Popen([resolved], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"Launched '{app}' ({resolved}).", None
        if "/" in app and Path(app).exists():
            subprocess.Popen([app], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            return True, f"Launched '{app}'.", None
        return False, "", f"open_app: '{app}' was not found on PATH on this laptop"
    except Exception as exc:
        return False, "", f"open_app failed: {type(exc).__name__}: {exc}"


def _input_backend() -> tuple[Any | None, str | None]:
    """Return (pyautogui module, xdotool path) — either may be None."""
    try:
        import pyautogui

        pyautogui.FAILSAFE = False
        return pyautogui, None
    except ImportError:
        pass
    import shutil

    return None, shutil.which("xdotool")


_NO_INPUT_BACKEND = (
    "no input backend on this laptop: install pyautogui (pip install pyautogui) "
    "or, on Linux, xdotool"
)


def _cmd_type_text(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    text = str(args.get("text") or "")
    if not text:
        return False, "", "type_text requires a 'text' argument"
    if len(text) > 4096:
        return False, "", "type_text is limited to 4096 characters per call"
    pyautogui, xdotool = _input_backend()
    try:
        if pyautogui is not None:
            pyautogui.write(text, interval=0.01)
            return True, f"Typed {len(text)} characters via pyautogui.", None
        if xdotool:
            completed = subprocess.run(
                [xdotool, "type", "--clearmodifiers", "--", text],
                capture_output=True,
                timeout=max(1.0, timeout),
                check=False,
            )
            if completed.returncode == 0:
                return True, f"Typed {len(text)} characters via xdotool.", None
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            return False, "", f"xdotool type failed: {detail or 'unknown error'}"
    except Exception as exc:
        return False, "", f"type_text failed: {type(exc).__name__}: {exc}"
    return False, "", _NO_INPUT_BACKEND


def _cmd_click(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    if args.get("x") is None or args.get("y") is None:
        return False, "", "click requires 'x' and 'y' arguments"
    x = _clamp_int(args.get("x"), default=-1, low=0, high=20000)
    y = _clamp_int(args.get("y"), default=-1, low=0, high=20000)
    if x < 0 or y < 0:
        return False, "", "click 'x' and 'y' must be non-negative integers"
    button = str(args.get("button") or "left").strip().lower()
    if button not in {"left", "right", "middle"}:
        return False, "", "click 'button' must be left, right or middle"
    clicks = _clamp_int(args.get("clicks"), default=1, low=1, high=3)
    pyautogui, xdotool = _input_backend()
    try:
        if pyautogui is not None:
            pyautogui.click(x=x, y=y, button=button, clicks=clicks)
            return True, f"Clicked {button} x{clicks} at ({x}, {y}) via pyautogui.", None
        if xdotool:
            button_number = {"left": "1", "middle": "2", "right": "3"}[button]
            completed = subprocess.run(
                [xdotool, "mousemove", str(x), str(y), "click", "--repeat", str(clicks), button_number],
                capture_output=True,
                timeout=max(1.0, timeout),
                check=False,
            )
            if completed.returncode == 0:
                return True, f"Clicked {button} x{clicks} at ({x}, {y}) via xdotool.", None
            detail = completed.stderr.decode("utf-8", errors="replace").strip()
            return False, "", f"xdotool click failed: {detail or 'unknown error'}"
    except Exception as exc:
        return False, "", f"click failed: {type(exc).__name__}: {exc}"
    return False, "", _NO_INPUT_BACKEND


def _cmd_open_url(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    url = str(args.get("url") or args.get("href") or "").strip()
    if not url:
        return False, "", "open_url requires a 'url' argument"
    parsed = urlparse(url)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False, "", "open_url only accepts absolute http(s) URLs"
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as exc:
        return False, "", f"open_url failed: {type(exc).__name__}: {exc}"
    if not opened:
        return False, "", "the laptop reported no browser handler for the URL"
    return True, f"Opened {url}", None


def _cmd_list_files(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    raw_path = str(args.get("path") or Path.home())
    root = Path(raw_path).expanduser()
    if not root.exists():
        return False, "", f"Path does not exist: {root}"
    if not root.is_dir():
        return False, "", f"Not a directory: {root}"
    limit = _clamp_int(args.get("limit"), default=200, low=1, high=1000)
    entries: list[dict[str, Any]] = []
    try:
        candidates = sorted(root.iterdir(), key=lambda item: item.name.lower())[:limit]
    except OSError as exc:
        return False, "", f"Could not list {root}: {exc}"
    for entry in candidates:
        try:
            stat = entry.stat()
            entries.append(
                {
                    "name": entry.name,
                    "type": "dir" if entry.is_dir() else "file",
                    "size": stat.st_size,
                    "modified": datetime.fromtimestamp(stat.st_mtime, timezone.utc).isoformat(),
                }
            )
        except OSError:
            entries.append({"name": entry.name, "type": "unknown", "size": None, "modified": None})
    payload = {"path": str(root), "count": len(entries), "entries": entries}
    return True, json.dumps(payload), None


def _cmd_read_file(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    raw_path = str(args.get("path") or "").strip()
    if not raw_path:
        return False, "", "read_file requires a 'path' argument"
    target = Path(raw_path).expanduser()
    if not target.exists():
        return False, "", f"File does not exist: {target}"
    if not target.is_file():
        return False, "", f"Not a file: {target}"
    try:
        with target.open("rb") as handle:
            data = handle.read(MAX_OUTPUT_BYTES + 1)
    except OSError as exc:
        return False, "", f"Could not read {target}: {exc}"
    truncated = len(data) > MAX_OUTPUT_BYTES
    text = data[:MAX_OUTPUT_BYTES].decode("utf-8", errors="replace")
    if truncated:
        text += "\n[truncated at 16384 bytes]"
    return True, text, None


def _cmd_run_shell(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    if not _shell_enabled():
        return (
            False,
            "",
            "run_shell is disabled; set FRIDAY_LAPTOP_ALLOW_SHELL=true on this laptop to enable it",
        )
    command = str(args.get("command") or args.get("cmd") or "").strip()
    if not command:
        return False, "", "run_shell requires a 'command' argument"
    try:
        completed = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            timeout=max(1.0, timeout),
            check=False,
        )
    except subprocess.TimeoutExpired:
        return False, "", f"run_shell exceeded its {timeout:g}s deadline"
    stdout = completed.stdout.decode("utf-8", errors="replace")
    stderr = completed.stderr.decode("utf-8", errors="replace")
    output = stdout
    if stderr:
        output = f"{output}\n[stderr]\n{stderr}" if output else f"[stderr]\n{stderr}"
    if completed.returncode != 0:
        return False, output, f"exit code {completed.returncode}"
    return True, output, None


def _cmd_system_info(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    info: dict[str, Any] = {
        "hostname": socket.gethostname(),
        "platform": platform.platform(),
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "processor": platform.processor(),
        "python": platform.python_version(),
        "user": os.getenv("USERNAME") or os.getenv("USER") or "",
        "cwd": os.getcwd(),
    }
    try:
        import psutil

        memory = psutil.virtual_memory()
        info["cpu_count"] = psutil.cpu_count()
        info["memory_total_mb"] = round(memory.total / (1024 * 1024), 1)
        info["memory_available_mb"] = round(memory.available / (1024 * 1024), 1)
        battery = psutil.sensors_battery()
        if battery is not None:
            info["battery_percent"] = round(battery.percent, 1)
            info["battery_charging"] = bool(battery.power_plugged)
    except Exception as exc:
        info["psutil_error"] = type(exc).__name__
    return True, json.dumps(info), None


def _cmd_notify(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    title = str(args.get("title") or "FRIDAY").strip() or "FRIDAY"
    message = str(args.get("message") or args.get("body") or "").strip()
    if not message:
        return False, "", "notify requires a 'message' argument"
    try:
        from plyer import notification

        notification.notify(title=title, message=message, timeout=10)
        return True, "Notification delivered via plyer.", None
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("plyer notification failed: %s", type(exc).__name__)
    try:
        from win10toast import ToastNotifier

        ToastNotifier().show_toast(title, message, duration=10, threaded=True)
        return True, "Notification delivered via win10toast.", None
    except ImportError:
        pass
    except Exception as exc:
        logger.warning("win10toast notification failed: %s", type(exc).__name__)
    # No desktop notifier installed: leave a durable trace instead of claiming
    # a toast the owner never saw.
    logger.info("FRIDAY notification (no desktop notifier): %s - %s", title, message)
    return True, "Notification written to the laptop bridge log (no desktop notifier installed).", None


def _lock_argv(system: str) -> list[str] | None:
    """The OS lock command for ``system`` (platform.system()), or None.

    TASK-IG-FRD-010. Locking is the safe half of the voice-assistant
    desktop pattern. There is deliberately NO unlock command anywhere
    in this client: unlocking means handling the owner's OS credentials
    at the secure-desktop boundary, which an agent must never do.
    """
    if system == "Windows":
        return ["rundll32.exe", "user32.dll,LockWorkStation"]
    if system == "Darwin":
        # Sleeps the display; with "require password immediately after
        # sleep" (the macOS default for lock) the Mac wakes locked.
        return ["/usr/bin/pmset", "displaysleepnow"]
    if system == "Linux":
        return ["loginctl", "lock-session"]
    return None


def _cmd_lock_screen(args: dict[str, Any], timeout: float) -> tuple[bool, Any, str | None]:
    system = platform.system()
    argv = _lock_argv(system)
    if argv is None:
        return False, "", f"lock_screen is not supported on platform {system!r}"
    candidates = [argv]
    if system == "Linux":
        candidates.append(["xdg-screensaver", "lock"])
    last_error = ""
    for candidate in candidates:
        try:
            completed = subprocess.run(
                candidate, capture_output=True, timeout=max(1.0, timeout), check=False
            )
        except FileNotFoundError:
            last_error = f"{candidate[0]} not found"
            continue
        except Exception as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            continue
        if completed.returncode == 0:
            note = f"Screen locked via {' '.join(candidate)}."
            if system == "Darwin":
                note += " (pmset sleeps the display; the Mac wakes locked when 'require password after sleep' is on.)"
            return True, note, None
        detail = completed.stderr.decode("utf-8", errors="replace").strip()
        last_error = f"{' '.join(candidate)} exited {completed.returncode}: {detail or 'no detail'}"
    return False, "", f"lock_screen failed on {system}: {last_error}"


_COMMANDS = {
    "screenshot": _cmd_screenshot,
    "screenshot_data": _cmd_screenshot_data,
    "open_url": _cmd_open_url,
    "open_app": _cmd_open_app,
    "type_text": _cmd_type_text,
    "click": _cmd_click,
    "list_files": _cmd_list_files,
    "read_file": _cmd_read_file,
    SHELL_COMMAND: _cmd_run_shell,
    "system_info": _cmd_system_info,
    "notify": _cmd_notify,
    "lock_screen": _cmd_lock_screen,
}


def _evidence_record(
    laptop_id: str,
    request_id: str,
    command: str,
    *,
    ok: bool,
    output: Any,
    error: str | None,
    started_at: str | None = None,
    finished_at: str | None = None,
    attachment: dict[str, Any] | None = None,
) -> dict[str, Any]:
    now = _now_iso()
    record = {
        "request_id": request_id,
        "laptop_id": laptop_id,
        "command": command,
        "started_at": started_at or now,
        "finished_at": finished_at or _now_iso(),
        "ok": bool(ok),
        "output": _bounded(output),
        "error": None if error is None else _bounded(error, 2048),
    }
    if attachment is not None:
        # Attachments travel outside the bounded evidence text; the server
        # registry validates and caps them (friday.remote.laptop_bridge).
        record["attachment"] = attachment
    return record


def _execute_command(
    laptop_id: str, request_id: str, command: str, args: dict[str, Any], timeout: float
) -> dict[str, Any]:
    """Run one command and always return a complete evidence record."""
    started_at = _now_iso()
    ok = False
    output: Any = ""
    error: str | None = None
    attachment: dict[str, Any] | None = None
    handler = _COMMANDS.get(command)
    if handler is None:
        error = f"unsupported command: {command}"
    else:
        try:
            outcome = handler(args, timeout)
            if len(outcome) == 4:
                ok, output, error, attachment = outcome
            else:
                ok, output, error = outcome
        except Exception as exc:
            ok, output, error = False, "", f"{type(exc).__name__}: {exc}"
    return _evidence_record(
        laptop_id,
        request_id,
        command,
        ok=ok,
        output=output,
        error=error,
        started_at=started_at,
        attachment=attachment,
    )


async def _heartbeat_loop(websocket: Any, send_lock: asyncio.Lock, interval: float) -> None:
    while True:
        await asyncio.sleep(interval)
        async with send_lock:
            await websocket.send(json.dumps({"type": "ping", "timestamp": _now_iso()}))


async def _send(websocket: Any, send_lock: asyncio.Lock, payload: dict[str, Any]) -> None:
    async with send_lock:
        await websocket.send(json.dumps(payload, default=str))


async def _handle_command(
    websocket: Any,
    send_lock: asyncio.Lock,
    laptop_id: str,
    message: dict[str, Any],
) -> None:
    request_id = str(message.get("request_id") or "").strip()
    if not request_id:
        logger.warning("Ignoring command frame without a request_id")
        return
    command = str(message.get("command") or "").strip()
    raw_args = message.get("args")
    args = raw_args if isinstance(raw_args, dict) else {}
    try:
        timeout = float(message.get("timeout") or DEFAULT_COMMAND_TIMEOUT)
    except (TypeError, ValueError):
        timeout = DEFAULT_COMMAND_TIMEOUT
    timeout = max(1.0, min(300.0, timeout))
    if len(json.dumps(args, default=str).encode("utf-8")) > MAX_ARGS_BYTES:
        result = _evidence_record(
            laptop_id,
            request_id,
            command,
            ok=False,
            output="",
            error="command args are too large",
        )
    elif command not in ALLOWED_COMMANDS:
        result = _evidence_record(
            laptop_id,
            request_id,
            command,
            ok=False,
            output="",
            error=f"unsupported command: {command}",
        )
    else:
        # Screenshots, shell commands and file reads block; keep them off the
        # event loop so heartbeats and new commands are still serviced.
        result = await asyncio.to_thread(
            _execute_command, laptop_id, request_id, command, args, timeout
        )
    try:
        await _send(websocket, send_lock, {"type": "result", **result})
    except Exception as exc:
        logger.warning("Could not return result for %s: %s", request_id, type(exc).__name__)


async def _run_session(uri: str, api_key: str, laptop_id: str, control_token: str | None = None) -> None:
    async with _connect(uri, api_key, control_token) as websocket:
        logger.info("Tunnel open to %s as %s", _safe_url(uri), laptop_id)
        send_lock = asyncio.Lock()
        heartbeat = asyncio.create_task(_heartbeat_loop(websocket, send_lock, HEARTBEAT_SECONDS))
        try:
            async for raw in websocket:
                try:
                    message = json.loads(raw)
                except (TypeError, ValueError):
                    logger.warning("Ignoring non-JSON frame from cloud FRIDAY")
                    continue
                if not isinstance(message, dict):
                    continue
                kind = str(message.get("type") or "").strip().lower()
                if kind == "command":
                    asyncio.create_task(
                        _handle_command(websocket, send_lock, laptop_id, message)
                    )
                elif kind in {"ping", "heartbeat"}:
                    await _send(websocket, send_lock, {"type": "pong", "timestamp": _now_iso()})
                elif kind == "welcome":
                    logger.info(
                        "Cloud accepted the tunnel (shell_enabled=%s)",
                        message.get("shell_enabled"),
                    )
                elif kind == "pong":
                    continue
                else:
                    logger.debug("Ignoring tunnel frame of type %s", kind)
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat


async def _run_forever(uri: str, api_key: str, laptop_id: str, control_token: str | None = None) -> None:
    attempt = 0
    while True:
        try:
            await _run_session(uri, api_key, laptop_id, control_token)
            attempt = 0
            logger.info("Tunnel closed cleanly; reconnecting")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            # Never interpolate the URL or headers here: the URL is safe, but a
            # library exception sometimes embeds handshake details.
            logger.warning(
                "Tunnel lost (%s); will reconnect", type(exc).__name__
            )
        delay = min(RECONNECT_MAX_SECONDS, RECONNECT_BASE_SECONDS * (2 ** min(attempt, 10)))
        delay *= random.uniform(0.5, 1.5)
        attempt += 1
        logger.info("Reconnecting in %.1fs", delay)
        await asyncio.sleep(delay)


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FRIDAY laptop reverse-tunnel client")
    parser.add_argument("--url", help="Bridge URL template (overrides FRIDAY_BRIDGE_URL)")
    parser.add_argument("--laptop-id", help="Stable laptop id (overrides FRIDAY_LAPTOP_ID)")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("FRIDAY_LAPTOP_LOG_LEVEL", "INFO").upper(),
        format="[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
    )
    args = _parse_args(argv)
    api_key = (os.getenv("FRIDAY_API_KEY") or "").strip()
    if not api_key:
        logger.error("FRIDAY_API_KEY is not set; the laptop cannot authenticate to FRIDAY")
        return 2
    control_token = (os.getenv("FRIDAY_CONTROL_TOKEN") or "").strip() or None
    laptop_id = _INVALID_ID_CHARS.sub("-", (args.laptop_id or _laptop_id()).strip()).strip("-.")
    if not laptop_id:
        logger.error("No usable laptop id; set FRIDAY_LAPTOP_ID")
        return 2
    laptop_id = laptop_id[:64]
    uri = _bridge_url(laptop_id, args.url)
    logger.info(
        "Starting laptop bridge for %s (shell_enabled=%s, token_auth=%s)",
        laptop_id,
        _shell_enabled(),
        bool(control_token),
    )
    try:
        asyncio.run(_run_forever(uri, api_key, laptop_id, control_token))
    except KeyboardInterrupt:
        logger.info("Laptop bridge stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
