"""Laptop control tools: drive the owner's laptop through the reverse tunnel.

TASK-LAP-001. The laptop dials out to FRIDAY (see
``friday.remote.laptop_bridge`` and ``scripts/laptop_bridge_client.py``);
these tools are the agent-facing surface over that tunnel. Each tool picks
the single online laptop when ``laptop_id`` is omitted, and every failure —
no tunnel, timeout, a gate that is off — is reported as-is. Nothing here
pretends a command ran when the laptop never answered.

TASK-FRD-044 adds the media pair: ``laptop_media_key`` /
``laptop_media_status`` and the user-facing ``spotify_control``, which
verifies every playback change against the laptop's media session instead
of trusting a sent key.

The tools call the in-process bridge registry. Tool execution happens off
the event loop in this codebase (see fleet_dispatch), so a blocking
``asyncio.run`` is the established pattern; when a loop *is* running in the
calling thread the coroutine is driven on a helper thread instead.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import threading
import time
from pathlib import Path
from typing import Any

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.remote.laptop_bridge import (
    LaptopBridgeTimeout,
    LaptopDisconnected,
    LaptopNotConnected,
    laptop_bridge,
)
from friday.tools.base import BaseTool

logger = get_logger("tools.laptop_control")

_CONNECT_HINT = (
    "No laptop is connected to FRIDAY right now. To connect one, run "
    "scripts/laptop_bridge_client.py on the laptop with FRIDAY_API_KEY set "
    "to FRIDAY's control key (see FRIDAY/docs/LAPTOP_CONTROL.md)."
)


def _run(coro_factory) -> Any:
    """Drive a bridge coroutine from sync tool code, loop or no loop."""

    def _target(box: dict[str, Any]) -> None:
        try:
            box["value"] = asyncio.run(coro_factory())
        except BaseException as exc:  # surfaced to the caller unchanged
            box["error"] = exc

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro_factory())
    box: dict[str, Any] = {}
    thread = threading.Thread(target=_target, args=(box,), daemon=True)
    thread.start()
    thread.join()
    if "error" in box:
        raise box["error"]
    return box.get("value")


async def _pick_laptop(laptop_id: str | None) -> str:
    devices = await laptop_bridge.list_devices()
    online = [d for d in devices if d.get("online")]
    if laptop_id:
        wanted = laptop_id.strip()
        if any(d.get("laptop_id") == wanted and d.get("online") for d in devices):
            return wanted
        raise LaptopNotConnected(f"Laptop '{wanted}' is not connected. {_CONNECT_HINT}")
    if not online:
        raise LaptopNotConnected(_CONNECT_HINT)
    if len(online) > 1:
        ids = ", ".join(sorted(str(d.get("laptop_id")) for d in online))
        raise LaptopNotConnected(
            f"More than one laptop is connected ({ids}); pass laptop_id to choose one."
        )
    return str(online[0].get("laptop_id"))


async def _execute_on_laptop(
    command: str, args: dict[str, Any], timeout: float, laptop_id: str | None
) -> dict[str, Any]:
    target = await _pick_laptop(laptop_id)
    return await laptop_bridge.execute(target, command, timeout, args)


class _LaptopTool(BaseTool):
    """Shared evidence-to-ToolResult mapping for laptop bridge tools."""

    command: str = ""
    default_timeout: float = 30.0

    def _dispatch(
        self,
        args: dict[str, Any],
        laptop_id: str | None = None,
        timeout: float | None = None,
        command: str | None = None,
    ) -> tuple[dict[str, Any] | None, ToolResult | None]:
        """Return (evidence, None) on a completed round-trip, else (None, error result).

        ``command`` overrides ``self.command`` for tools that dispatch more
        than one bridge command (TASK-FRD-044 spotify_control).
        """
        cmd = command or self.command
        try:
            evidence = _run(
                lambda: _execute_on_laptop(
                    cmd, args, timeout or self.default_timeout, laptop_id
                )
            )
        except LaptopNotConnected as exc:
            return None, self._error(str(exc))
        except LaptopBridgeTimeout as exc:
            return None, self._error(
                f"The laptop did not answer '{cmd}' in time: {exc}"
            )
        except LaptopDisconnected as exc:
            return None, self._error(f"The laptop tunnel dropped mid-command: {exc}")
        except ValueError as exc:
            # Registry-side refusals (unknown command, run_shell gate off, bad args).
            return None, self._error(str(exc))
        except Exception as exc:
            logger.warning("laptop tool %s failed: %s", self.name, exc)
            return None, self._error(f"Laptop command failed: {type(exc).__name__}: {exc}")
        return evidence, None

    def _error(self, message: str) -> ToolResult:
        return ToolResult(
            name=self.name, content=message, is_error=True, safety_level=self.safety_level
        )

    def _evidence_result(self, evidence: dict[str, Any], ok_text: str) -> ToolResult:
        if evidence.get("ok"):
            return ToolResult(
                name=self.name,
                content=ok_text,
                is_error=False,
                safety_level=self.safety_level,
                metadata={"laptop_id": evidence.get("laptop_id"), "command": self.command},
            )
        detail = evidence.get("error") or evidence.get("output") or "unknown laptop-side error"
        return self._error(f"The laptop refused/failed '{self.command}': {detail}")


class LaptopListDevicesTool(_LaptopTool):
    """List laptops known to the bridge and which are online now."""

    name = "laptop_list_devices"
    description = (
        "List the owner's laptops known to FRIDAY's laptop bridge and whether "
        "each is connected right now. Use this before other laptop_* tools if "
        "you are unsure a laptop is connected."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {"type": "object", "properties": {}, "required": []}

    def execute(self, **kwargs: Any) -> ToolResult:
        try:
            devices = _run(lambda: laptop_bridge.list_devices())
        except Exception as exc:
            return self._error(f"Could not list laptops: {type(exc).__name__}: {exc}")
        online = [d for d in devices if d.get("online")]
        content = json.dumps({"devices": devices}, default=str)
        if not online:
            content += f"\n{_CONNECT_HINT}"
        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
            metadata={"online_count": len(online)},
        )


class LaptopOpenAppTool(_LaptopTool):
    """Open an application on the owner's connected laptop."""

    name = "laptop_open_app"
    description = (
        "Open an application on the owner's laptop (e.g. 'notepad', 'chrome', "
        "'calculator') through the laptop bridge. Use this — not "
        "open_application — when the user means an app on their own computer."
    )
    safety_level = SafetyLevel.SAFE
    command = "open_app"
    parameters = {
        "type": "object",
        "properties": {
            "application": {"type": "string", "description": "Application name to launch on the laptop."},
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["application"],
    }

    def execute(self, application: str = "", laptop_id: str = "", **kwargs: Any) -> ToolResult:
        app = (application or "").strip()
        if not app:
            return self._error("No application name provided.")
        evidence, error = self._dispatch({"app": app}, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(evidence, f"Opened {app} on laptop '{evidence.get('laptop_id')}'.")


class LaptopOpenUrlTool(_LaptopTool):
    """Open a URL in the browser on the owner's connected laptop."""

    name = "laptop_open_url"
    description = "Open a web page in the default browser on the owner's laptop."
    safety_level = SafetyLevel.SAFE
    command = "open_url"
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Absolute http(s) URL to open."},
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["url"],
    }

    def execute(self, url: str = "", laptop_id: str = "", **kwargs: Any) -> ToolResult:
        target = (url or "").strip()
        if not target:
            return self._error("No URL provided.")
        evidence, error = self._dispatch({"url": target}, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(evidence, f"Opened {target} on laptop '{evidence.get('laptop_id')}'.")


class LaptopScreenshotTool(_LaptopTool):
    """Capture the laptop's screen and hand the image (plus OCR text) to FRIDAY."""

    name = "laptop_screenshot"
    description = (
        "See the owner's laptop screen: captures it through the laptop bridge, "
        "saves the image on the FRIDAY host, and returns the saved path plus "
        "any text OCR could read from it. Use when the user asks what is on "
        "their screen or to look at their laptop."
    )
    safety_level = SafetyLevel.SAFE
    command = "screenshot_data"
    default_timeout = 45.0
    parameters = {
        "type": "object",
        "properties": {
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": [],
    }

    def _screen_dir(self) -> Path:
        override = os.getenv("FRIDAY_LAPTOP_SCREEN_DIR", "").strip()
        if override:
            return Path(override)
        import tempfile

        return Path(tempfile.gettempdir()) / "friday-laptop-screens"

    def execute(self, laptop_id: str = "", **kwargs: Any) -> ToolResult:
        evidence, error = self._dispatch({}, laptop_id or None)
        if error is not None:
            return error
        if not evidence.get("ok"):
            return self._evidence_result(evidence, "")
        attachment = evidence.get("attachment")
        if not attachment or not attachment.get("base64"):
            return self._error(
                "The laptop reported a successful capture but sent no image data; "
                "nothing was saved. (The laptop client may be an older build "
                "without screenshot_data.)"
            )
        try:
            raw = base64.b64decode(attachment["base64"])
        except Exception as exc:
            return self._error(f"The screenshot image data was undecodable: {exc}")
        directory = self._screen_dir()
        try:
            directory.mkdir(parents=True, exist_ok=True)
            target = directory / f"laptop-{evidence.get('laptop_id')}-{int(time.time() * 1000)}.jpg"
            target.write_bytes(raw)
        except OSError as exc:
            return self._error(f"Could not save the laptop screenshot on this host: {exc}")

        ocr_text = ""
        ocr_note = ""
        try:
            import io

            from PIL import Image

            from friday.tools.builtin.screen_ocr import _run_ocr

            words = _run_ocr(Image.open(io.BytesIO(raw)))
            ocr_text = " ".join(word for word, _box in words)[:4000]
        except Exception as exc:
            ocr_note = f" OCR unavailable on this host ({type(exc).__name__})."
        content = (
            f"Laptop '{evidence.get('laptop_id')}' screen captured: "
            f"{attachment.get('width')}x{attachment.get('height')} JPEG saved at {target}."
        )
        if ocr_text:
            content += f"\nVisible text (OCR): {ocr_text}"
        else:
            content += f"\nNo OCR text extracted.{ocr_note}"
        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
            metadata={
                "laptop_id": evidence.get("laptop_id"),
                "command": self.command,
                "image_path": str(target),
                "width": attachment.get("width"),
                "height": attachment.get("height"),
            },
        )


class LaptopLockTool(_LaptopTool):
    """Lock the owner's connected laptop screen (TASK-IG-FRD-010).

    The safe half of the voice-assistant desktop pattern: FRIDAY can
    lock the laptop on request ("lock my laptop"). There is no unlock
    tool and no unlock bridge command — unlocking means handling the
    owner's OS credentials at the secure-desktop boundary, which an
    agent must never store or type. That refusal is by design.
    """

    name = "laptop_lock_screen"
    description = (
        "Lock the screen of the owner's connected laptop through the "
        "laptop bridge. Use when the user asks to lock their computer. "
        "FRIDAY cannot unlock a laptop — that stays with the owner at "
        "the machine, by design."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    command = "lock_screen"
    parameters = {
        "type": "object",
        "properties": {
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": [],
    }

    def execute(self, laptop_id: str = "", **kwargs: Any) -> ToolResult:
        evidence, error = self._dispatch({}, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"Locked the screen of laptop '{evidence.get('laptop_id')}'."
        )


class LaptopTypeTextTool(_LaptopTool):
    """Type text on the owner's connected laptop."""

    name = "laptop_type_text"
    description = (
        "Type text on the owner's laptop, into whatever window currently has "
        "focus there. Use after laptop_open_app / laptop_screenshot to fill "
        "in fields on the laptop."
    )
    safety_level = SafetyLevel.SENSITIVE
    command = "type_text"
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type on the laptop (max 4096 characters)."},
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["text"],
    }

    def execute(self, text: str = "", laptop_id: str = "", **kwargs: Any) -> ToolResult:
        if not text:
            return self._error("No text provided.")
        evidence, error = self._dispatch({"text": text}, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"Typed {len(text)} characters on laptop '{evidence.get('laptop_id')}'."
        )


class LaptopClickTool(_LaptopTool):
    """Click at screen coordinates on the owner's connected laptop."""

    name = "laptop_click"
    description = (
        "Click at (x, y) screen coordinates on the owner's laptop. Get the "
        "coordinates from a laptop_screenshot first."
    )
    safety_level = SafetyLevel.SENSITIVE
    command = "click"
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "Horizontal pixel coordinate."},
            "y": {"type": "integer", "description": "Vertical pixel coordinate."},
            "button": {"type": "string", "description": "left, right or middle (default left)."},
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["x", "y"],
    }

    def execute(
        self, x: int = -1, y: int = -1, button: str = "left", laptop_id: str = "", **kwargs: Any
    ) -> ToolResult:
        if x is None or y is None or int(x) < 0 or int(y) < 0:
            return self._error("Both x and y coordinates are required.")
        args = {"x": int(x), "y": int(y), "button": (button or "left")}
        evidence, error = self._dispatch(args, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"Clicked at ({int(x)}, {int(y)}) on laptop '{evidence.get('laptop_id')}'."
        )


class LaptopRunCommandTool(_LaptopTool):
    """Run a shell command on the owner's connected laptop (double-gated)."""

    name = "laptop_run_command"
    description = (
        "Run a shell command on the owner's laptop through the bridge. This "
        "only works when FRIDAY_LAPTOP_ALLOW_SHELL=true is set on BOTH the "
        "FRIDAY host and the laptop; otherwise the refusal is reported as-is."
    )
    safety_level = SafetyLevel.DANGEROUS
    risk_level = "DANGEROUS"
    command = "run_shell"
    default_timeout = 60.0
    parameters = {
        "type": "object",
        "properties": {
            "command": {"type": "string", "description": "Shell command to run on the laptop."},
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["command"],
    }

    def execute(self, command: str = "", laptop_id: str = "", **kwargs: Any) -> ToolResult:
        shell_command = (command or "").strip()
        if not shell_command:
            return self._error("No command provided.")
        evidence, error = self._dispatch({"command": shell_command}, laptop_id or None)
        if error is not None:
            return error
        if evidence.get("ok"):
            return ToolResult(
                name=self.name,
                content=str(evidence.get("output") or ""),
                is_error=False,
                safety_level=self.safety_level,
                metadata={"laptop_id": evidence.get("laptop_id"), "command": self.command},
            )
        return self._evidence_result(evidence, "")


def _describe_media_session(evidence: dict[str, Any]) -> str:
    """Render a media_status evidence record as one spoken line.

    The laptop returns JSON {playing, status, title, artist, source};
    anything unparseable is passed through raw rather than invented.
    """
    raw = str(evidence.get("output") or "").strip()
    laptop = evidence.get("laptop_id")
    try:
        session = json.loads(raw)
    except (TypeError, ValueError):
        return f"Media session on laptop '{laptop}': {raw or 'no session data returned'}"
    if not isinstance(session, dict):
        return f"Media session on laptop '{laptop}': {raw}"
    status = str(session.get("status") or "unknown")
    if status == "no_session":
        return f"No media session is active on laptop '{laptop}' right now."
    title = session.get("title")
    artist = session.get("artist")
    source = session.get("source")
    track = f"'{title}'" + (f" by {artist}" if artist else "")
    source_note = f" (source: {source})" if source else ""
    state = "playing" if session.get("playing") else "paused"
    return (
        f"Media session on laptop '{laptop}': {track or 'no track reported'} "
        f"is {state} (session status: {status}){source_note}."
    )


class LaptopMediaKeyTool(_LaptopTool):
    """Send a media key (play/pause, next, previous) to the owner's laptop.

    TASK-FRD-044. The key lands on whichever media session Windows routes
    it to on the laptop — Spotify when it is the active session. A sent
    key is NOT proof playback changed; use laptop_media_status to read
    the session back. This tool says so in its result.
    """

    name = "laptop_media_key"
    description = (
        "Send a media key to the owner's laptop through the laptop bridge: "
        "'play_pause', 'next' or 'previous'. The key is confirmed delivered "
        "to the laptop only — whether playback actually changed is NOT proven "
        "by this step; use laptop_media_status to read the session back."
    )
    safety_level = SafetyLevel.SAFE
    command = "media_key"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play_pause", "play", "pause", "next", "previous"],
                "description": "Media-key action to send.",
            },
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["action"],
    }

    _ACTION_ALIASES = {"play": "play_pause", "pause": "play_pause"}

    def execute(self, action: str = "", laptop_id: str = "", **kwargs: Any) -> ToolResult:
        act = (action or "").strip().lower()
        act = self._ACTION_ALIASES.get(act, act)
        if act not in ("play_pause", "next", "previous"):
            return self._error("Unknown media-key action — use play_pause, next or previous.")
        evidence, error = self._dispatch({"action": act}, laptop_id or None)
        if error is not None:
            return error
        if not evidence.get("ok"):
            return self._evidence_result(evidence, "")
        return ToolResult(
            name=self.name,
            content=(
                f"Media key '{act}' sent to laptop '{evidence.get('laptop_id')}'. "
                "Delivery to the laptop is confirmed; whether playback changed "
                "is not proven by this step — read it back with laptop_media_status."
            ),
            is_error=False,
            safety_level=self.safety_level,
            metadata={"laptop_id": evidence.get("laptop_id"), "command": self.command},
        )


class LaptopMediaStatusTool(_LaptopTool):
    """Read back the laptop's current media session (TASK-FRD-044).

    This is the proof leg for Spotify control: it reports what the
    laptop's media session actually says, not what was requested.
    """

    name = "laptop_media_status"
    description = (
        "Read the current media session on the owner's laptop: whether "
        "anything is playing, and the track/artist when there is one. "
        "This is the proof leg for Spotify control — it reports what the "
        "laptop's media session actually says, not what was requested."
    )
    safety_level = SafetyLevel.SAFE
    command = "media_status"
    parameters = {
        "type": "object",
        "properties": {
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": [],
    }

    def execute(self, laptop_id: str = "", **kwargs: Any) -> ToolResult:
        evidence, error = self._dispatch({}, laptop_id or None)
        if error is not None:
            return error
        if not evidence.get("ok"):
            return self._evidence_result(evidence, "")
        return ToolResult(
            name=self.name,
            content=_describe_media_session(evidence),
            is_error=False,
            safety_level=self.safety_level,
            metadata={"laptop_id": evidence.get("laptop_id"), "command": self.command},
        )


class SpotifyControlTool(_LaptopTool):
    """Spotify playback control by voice, over the laptop bridge.

    TASK-FRD-044. Play/pause/next/previous ride the laptop media keys;
    every state-changing action reads the media session back and reports
    the VERIFIED state — a key that was sent but did not change the
    session is reported as such, never as playback. Search opens the
    Spotify search page on the laptop (there is no Spotify API key or
    track-resolution service; track selection stays with the owner).
    """

    name = "spotify_control"
    description = (
        "Control Spotify playback on the owner's laptop by voice: 'play', "
        "'pause', 'toggle', 'next', 'previous', 'search' (open a Spotify "
        "search page for a song) or 'status' (read what is playing now). "
        "Play/pause are verified against the laptop's media session, so "
        "the answer says what is actually playing — not just what was asked."
    )
    safety_level = SafetyLevel.SAFE
    command = "media_key"
    parameters = {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["play", "pause", "toggle", "next", "previous", "search", "status"],
                "description": "Spotify playback action.",
            },
            "query": {
                "type": "string",
                "description": "Song or artist to search for (required for 'search').",
            },
            "laptop_id": {"type": "string", "description": "Optional laptop id when more than one is connected."},
        },
        "required": ["action"],
    }

    def execute(
        self, action: str = "", query: str = "", laptop_id: str = "", **kwargs: Any
    ) -> ToolResult:
        act = (action or "").strip().lower()
        target = laptop_id or None
        if act == "status":
            return self._status_result(target)
        if act == "search":
            return self._search(query, target)
        if act not in ("play", "pause", "toggle", "next", "previous"):
            return self._error(
                "Unknown Spotify action — use play, pause, toggle, next, previous, search or status."
            )
        return self._media_action(act, target)

    # -- helpers -------------------------------------------------------

    def _ok(self, content: str, laptop_id: str | None, command: str) -> ToolResult:
        return ToolResult(
            name=self.name,
            content=content,
            is_error=False,
            safety_level=self.safety_level,
            metadata={"laptop_id": laptop_id, "command": command},
        )

    def _session_or_reason(
        self, laptop_id: str | None
    ) -> tuple[dict[str, Any] | None, str | None, str | None]:
        """Read the media session: (session, laptop_id, reason).

        Returns (None, None, reason) when the session cannot be read. A
        failed read never pretends to be a session: callers send the key
        anyway and report the change as unconfirmed.
        """
        evidence, error = self._dispatch({}, laptop_id, command="media_status")
        if error is not None:
            return None, None, str(error.content)
        if not evidence.get("ok"):
            return None, None, str(
                evidence.get("error") or evidence.get("output") or "laptop refused media_status"
            )
        try:
            session = json.loads(str(evidence.get("output") or ""))
        except (TypeError, ValueError):
            return None, None, "the laptop's media session reply was unreadable"
        if not isinstance(session, dict):
            return None, None, "the laptop's media session reply was unreadable"
        return session, evidence.get("laptop_id"), None

    def _send_key(
        self, key_action: str, laptop_id: str | None
    ) -> tuple[dict[str, Any] | None, ToolResult | None]:
        evidence, error = self._dispatch(
            {"action": key_action}, laptop_id, command="media_key"
        )
        if error is not None:
            return None, error
        if not evidence.get("ok"):
            return None, self._evidence_result(evidence, "")
        return evidence, None

    def _status_result(self, laptop_id: str | None) -> ToolResult:
        session, lap, reason = self._session_or_reason(laptop_id)
        if session is None:
            return self._error(f"Could not read the laptop's media session: {reason}")
        return self._ok(
            _describe_media_session({"output": json.dumps(session), "laptop_id": lap}),
            lap,
            "media_status",
        )

    def _search(self, query: str, laptop_id: str | None) -> ToolResult:
        q = (query or "").strip()
        if not q:
            return self._error("No song or artist to search for — say which song to play.")
        from urllib.parse import quote

        url = f"https://open.spotify.com/search/{quote(q)}"
        evidence, error = self._dispatch({"url": url}, laptop_id, command="open_url")
        if error is not None:
            return error
        if not evidence.get("ok"):
            return self._evidence_result(evidence, "")
        lap = evidence.get("laptop_id")
        content = (
            f"Opened Spotify search for '{q}' on laptop '{lap}'. Pick the track "
            "there, or say 'play' once it loads to start playback."
        )
        session, _lap2, _reason = self._session_or_reason(laptop_id)
        if session is not None:
            content += " " + _describe_media_session(
                {"output": json.dumps(session), "laptop_id": lap}
            )
        return self._ok(content, lap, "open_url")

    def _media_action(self, act: str, laptop_id: str | None) -> ToolResult:
        # 1. Read the current state first: play/pause are idempotent, and
        #    the read-back after the key is what proves the change.
        session, lap, _reason = self._session_or_reason(laptop_id)
        if act == "play" and session is not None and session.get("playing"):
            return self._ok(
                "Already playing. "
                + _describe_media_session({"output": json.dumps(session), "laptop_id": lap}),
                lap,
                "media_status",
            )
        if act == "pause" and session is not None and not session.get("playing"):
            return self._ok(
                "Already paused. "
                + _describe_media_session({"output": json.dumps(session), "laptop_id": lap}),
                lap,
                "media_status",
            )
        key_action = "play_pause" if act in ("play", "pause", "toggle") else act
        evidence, error = self._send_key(key_action, laptop_id)
        if error is not None:
            return error
        lap = evidence.get("laptop_id") or lap
        # 2. Read back to verify the change.
        session2, lap2, reason2 = self._session_or_reason(laptop_id)
        if session2 is None:
            return self._ok(
                f"Media key '{key_action}' sent to laptop '{lap}', but the session "
                f"read-back failed ({reason2}); whether playback changed is unconfirmed.",
                lap,
                "media_key",
            )
        lap = lap2 or lap
        return self._ok(
            _describe_media_session({"output": json.dumps(session2), "laptop_id": lap}),
            lap,
            "media_status",
        )


__all__ = [
    "LaptopClickTool",
    "LaptopListDevicesTool",
    "LaptopMediaKeyTool",
    "LaptopMediaStatusTool",
    "LaptopOpenAppTool",
    "LaptopOpenUrlTool",
    "LaptopRunCommandTool",
    "LaptopScreenshotTool",
    "LaptopTypeTextTool",
    "SpotifyControlTool",
]
