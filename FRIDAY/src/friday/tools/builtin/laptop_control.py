"""Laptop control tools: drive the owner's laptop through the reverse tunnel.

TASK-LAP-001. The laptop dials out to FRIDAY (see
``friday.remote.laptop_bridge`` and ``scripts/laptop_bridge_client.py``);
these tools are the agent-facing surface over that tunnel. Each tool picks
the single online laptop when ``laptop_id`` is omitted, and every failure —
no tunnel, timeout, a gate that is off — is reported as-is. Nothing here
pretends a command ran when the laptop never answered.

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
    ) -> tuple[dict[str, Any] | None, ToolResult | None]:
        """Return (evidence, None) on a completed round-trip, else (None, error result)."""
        try:
            evidence = _run(
                lambda: _execute_on_laptop(
                    self.command, args, timeout or self.default_timeout, laptop_id
                )
            )
        except LaptopNotConnected as exc:
            return None, self._error(str(exc))
        except LaptopBridgeTimeout as exc:
            return None, self._error(
                f"The laptop did not answer '{self.command}' in time: {exc}"
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


__all__ = [
    "LaptopClickTool",
    "LaptopListDevicesTool",
    "LaptopOpenAppTool",
    "LaptopOpenUrlTool",
    "LaptopRunCommandTool",
    "LaptopScreenshotTool",
    "LaptopTypeTextTool",
]
