"""Phone Control Tools for Surendra's FRIDAY (TASK-PHONE-001).

These tools drive the owner's Android phone through the reverse tunnel in
:mod:`friday.remote.phone_bridge`: the phone agent (Termux script or the
companion app) dials out to FRIDAY, and every tool here dispatches one
allowlisted command down that tunnel and reports the evidence record it got
back — including "the phone is not connected" when that is the truth.

They are deliberately separate from ``android_control.py``: those tools speak
ADB to a phone plugged into the machine FRIDAY runs on, which on the cloud
server is never the owner's phone.

Safety: placing a call and sending messages are SENSITIVE — they act in the
owner's name, on his accounts, and cannot be unsent — so the agent's
confirmation flow applies before they run. Everything else here is SAFE:
worst case it opens an app or makes the phone ring.
"""

from __future__ import annotations

import base64
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from friday.core.logging import get_logger
from friday.core.types import SafetyLevel, ToolResult
from friday.remote.phone_bridge import (
    PhoneBridgeTimeout,
    PhoneDisconnected,
    PhoneNotConnected,
    PhoneUnsupportedCommand,
    phone_bridge,
)
from friday.tools.base import BaseTool

logger = get_logger("tools.phone_control")

_DEVICE_ARG = {
    "device_id": {
        "type": "string",
        "description": "Optional phone device id; omit to use the paired phone.",
    }
}


def _resolve_device_id(device_id: str | None) -> str | None:
    if device_id and str(device_id).strip():
        return str(device_id).strip()
    return phone_bridge.default_device_id()


def _dispatch(
    tool_name: str,
    command: str,
    args: dict[str, Any],
    *,
    device_id: str | None = None,
    timeout: float = 30.0,
    success: str,
) -> ToolResult:
    """Run one bridge command and render its evidence as a ToolResult."""
    target = _resolve_device_id(device_id)
    if target is None:
        return ToolResult(
            name=tool_name,
            content=(
                "No phone is paired with FRIDAY yet. Pairing takes one minute: "
                "install the phone agent (see docs/PHONE_CONTROL.md), ask FRIDAY "
                "to pair your phone, and type the 6-digit code it gives you."
            ),
            is_error=True,
            refused=True,
        )
    try:
        evidence = phone_bridge.execute_sync(target, command, timeout=timeout, args=args)
    except PhoneNotConnected:
        return ToolResult(
            name=tool_name,
            content=(
                f"Your phone '{target}' is paired but not connected right now — "
                "the phone agent is not running or the phone has no network. "
                "Nothing was sent to it."
            ),
            is_error=True,
            refused=True,
        )
    except PhoneUnsupportedCommand as exc:
        return ToolResult(name=tool_name, content=str(exc), is_error=True, refused=True)
    except PhoneBridgeTimeout as exc:
        return ToolResult(
            name=tool_name,
            content=(
                f"The phone did not answer '{command}' in time ({exc}). "
                "The command may or may not have happened; check the phone before retrying."
            ),
            is_error=True,
            metadata={"evidence": exc.evidence},
        )
    except PhoneDisconnected as exc:
        return ToolResult(
            name=tool_name,
            content=f"The phone disconnected during '{command}': {exc}",
            is_error=True,
            metadata={"evidence": exc.evidence},
        )
    except ValueError as exc:
        return ToolResult(name=tool_name, content=str(exc), is_error=True, refused=True)

    if evidence.get("ok"):
        output = str(evidence.get("output") or "").strip()
        content = success if not output else f"{success} Phone reported: {output}"
        return ToolResult(name=tool_name, content=content, metadata={"evidence": evidence})
    error = str(evidence.get("error") or "the phone reported failure").strip()
    output = str(evidence.get("output") or "").strip()
    content = f"The phone could not complete '{command}': {error}"
    if output:
        content += f" Detail: {output}"
    return ToolResult(name=tool_name, content=content, is_error=True, metadata={"evidence": evidence})


def _clean_number(value: str) -> str:
    return re.sub(r"[^\d+]", "", str(value or ""))


class PhoneStatusTool(BaseTool):
    """Reports whether the owner's phone is paired/connected and its status."""

    name = "phone_status"
    description = (
        "Checks the owner's Android phone: whether it is paired with FRIDAY, "
        "connected right now, and (when connected) its battery, model and screen state."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {"type": "object", "properties": dict(_DEVICE_ARG)}

    def execute(self, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        target = _resolve_device_id(device_id)
        if target is None:
            return ToolResult(
                name=self.name,
                content="No phone is paired with FRIDAY yet (see docs/PHONE_CONTROL.md for the one-minute pairing).",
            )
        if not phone_bridge.is_connected(target):
            record = phone_bridge.pairing.get_device(target) or {}
            return ToolResult(
                name=self.name,
                content=(
                    f"Phone '{record.get('name') or target}' is paired "
                    f"(via {record.get('executor') or 'unknown'} agent) but NOT connected "
                    "right now. The phone agent may be stopped, or the phone is offline."
                ),
                metadata={"device_id": target, "online": False},
            )
        return _dispatch(
            self.name,
            "device_status",
            {},
            device_id=target,
            timeout=15.0,
            success=f"Phone '{target}' is connected.",
        )


class PhoneOpenAppTool(BaseTool):
    """Opens an app on the owner's phone by name or package id."""

    name = "phone_open_app"
    description = (
        "Opens an app on the owner's Android phone by common name (e.g. 'youtube', "
        "'whatsapp', 'chrome', 'settings', 'camera') or full package identifier."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "App name or package identifier"},
            **_DEVICE_ARG,
        },
        "required": ["app_name"],
    }

    def execute(self, app_name: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "open_app",
            {"app": str(app_name)},
            device_id=device_id,
            success=f"Opened '{app_name}' on your phone.",
        )


class PhoneCloseAppTool(BaseTool):
    """Force-stops an app on the owner's phone."""

    name = "phone_close_app"
    description = "Closes (force-stops) an app on the owner's Android phone by name or package id."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "app_name": {"type": "string", "description": "App name or package identifier"},
            **_DEVICE_ARG,
        },
        "required": ["app_name"],
    }

    def execute(self, app_name: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "close_app",
            {"app": str(app_name)},
            device_id=device_id,
            success=f"Closed '{app_name}' on your phone.",
        )


class PhoneOpenUrlTool(BaseTool):
    """Opens a URL on the owner's phone."""

    name = "phone_open_url"
    description = "Opens a web URL in the browser on the owner's Android phone."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "The URL to open"},
            **_DEVICE_ARG,
        },
        "required": ["url"],
    }

    def execute(self, url: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "open_url",
            {"url": str(url)},
            device_id=device_id,
            success=f"Opened {url} on your phone.",
        )


class PhoneMakeCallTool(BaseTool):
    """Places a real phone call from the owner's phone."""

    name = "phone_make_call"
    description = (
        "Places a REAL call from the owner's Android phone to the given number. "
        "This dials immediately — confirm the number with the owner first."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "phone_number": {"type": "string", "description": "Number to call, e.g. +91 98XXX XXXXX"},
            **_DEVICE_ARG,
        },
        "required": ["phone_number"],
    }

    def execute(self, phone_number: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        number = _clean_number(phone_number)
        if len(number) < 5:
            return ToolResult(
                name=self.name,
                content=f"'{phone_number}' does not look like a dialable phone number.",
                is_error=True,
                refused=True,
            )
        return _dispatch(
            self.name,
            "make_call",
            {"number": number},
            device_id=device_id,
            success=f"Calling {number} from your phone now.",
        )


class PhoneSendSmsTool(BaseTool):
    """Sends an SMS from the owner's phone."""

    name = "phone_send_sms"
    description = (
        "Sends a REAL SMS text message from the owner's Android phone. "
        "The message is sent immediately and cannot be unsent."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "phone_number": {"type": "string", "description": "Recipient number"},
            "message": {"type": "string", "description": "Message text to send"},
            **_DEVICE_ARG,
        },
        "required": ["phone_number", "message"],
    }

    def execute(
        self, phone_number: str, message: str, device_id: str | None = None, **kwargs: Any
    ) -> ToolResult:
        number = _clean_number(phone_number)
        if len(number) < 5:
            return ToolResult(
                name=self.name,
                content=f"'{phone_number}' does not look like a valid phone number.",
                is_error=True,
                refused=True,
            )
        if not str(message or "").strip():
            return ToolResult(name=self.name, content="The SMS text is empty.", is_error=True, refused=True)
        return _dispatch(
            self.name,
            "send_sms",
            {"number": number, "message": str(message)},
            device_id=device_id,
            success=f"SMS sent to {number} from your phone.",
        )


class PhoneSendWhatsAppTool(BaseTool):
    """Sends a WhatsApp message from the owner's phone."""

    name = "phone_send_whatsapp"
    description = (
        "Sends a WhatsApp message from the owner's Android phone to the given number. "
        "On the companion app this sends directly; on the Termux agent it opens the "
        "chat with the message prefilled and reports that a tap is still needed."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "phone_number": {"type": "string", "description": "Recipient number with country code"},
            "message": {"type": "string", "description": "Message text to send"},
            **_DEVICE_ARG,
        },
        "required": ["phone_number", "message"],
    }

    def execute(
        self, phone_number: str, message: str, device_id: str | None = None, **kwargs: Any
    ) -> ToolResult:
        number = _clean_number(phone_number)
        if len(number) < 7:
            return ToolResult(
                name=self.name,
                content=f"'{phone_number}' does not look like a valid WhatsApp number (country code needed).",
                is_error=True,
                refused=True,
            )
        if not str(message or "").strip():
            return ToolResult(name=self.name, content="The WhatsApp message is empty.", is_error=True, refused=True)
        return _dispatch(
            self.name,
            "send_whatsapp",
            {"number": number, "message": str(message)},
            device_id=device_id,
            timeout=45.0,
            success=f"WhatsApp message sent to {number} from your phone.",
        )


class PhoneReadNotificationsTool(BaseTool):
    """Reads the phone's current notifications."""

    name = "phone_read_notifications"
    description = (
        "Reads the current notifications on the owner's Android phone "
        "(app, title and text of what is in the notification shade right now)."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "limit": {"type": "integer", "description": "Max notifications to return (default 20)", "default": 20},
            **_DEVICE_ARG,
        },
    }

    def execute(self, limit: int = 20, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "read_notifications",
            {"limit": max(1, min(int(limit or 20), 100))},
            device_id=device_id,
            success="Here is what is on your phone's notification shade:",
        )


class PhoneSetAlarmTool(BaseTool):
    """Sets an alarm on the owner's phone."""

    name = "phone_set_alarm"
    description = "Sets an alarm on the owner's Android phone for the given 24h time (hour, minute) with an optional label."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "hour": {"type": "integer", "description": "Hour 0-23"},
            "minute": {"type": "integer", "description": "Minute 0-59"},
            "label": {"type": "string", "description": "Optional alarm label"},
            **_DEVICE_ARG,
        },
        "required": ["hour", "minute"],
    }

    def execute(
        self,
        hour: int,
        minute: int,
        label: str = "",
        device_id: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        hour_i, minute_i = int(hour), int(minute)
        if not (0 <= hour_i <= 23 and 0 <= minute_i <= 59):
            return ToolResult(
                name=self.name,
                content=f"{hour}:{minute} is not a valid 24h time.",
                is_error=True,
                refused=True,
            )
        return _dispatch(
            self.name,
            "set_alarm",
            {"hour": hour_i, "minute": minute_i, "label": str(label or "")},
            device_id=device_id,
            success=f"Alarm set on your phone for {hour_i:02d}:{minute_i:02d}.",
        )


class PhoneMediaControlTool(BaseTool):
    """Controls media playback on the owner's phone."""

    name = "phone_media_control"
    description = "Controls media on the owner's phone: action is one of play, pause, next, previous, stop."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "description": "play | pause | next | previous | stop"},
            **_DEVICE_ARG,
        },
        "required": ["action"],
    }

    def execute(self, action: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        wanted = str(action or "").strip().lower()
        if wanted not in {"play", "pause", "next", "previous", "stop"}:
            return ToolResult(
                name=self.name,
                content=f"'{action}' is not a media action I can send. Use play, pause, next, previous or stop.",
                is_error=True,
                refused=True,
            )
        return _dispatch(
            self.name,
            "media_control",
            {"action": wanted},
            device_id=device_id,
            success=f"Media '{wanted}' sent to your phone.",
        )


class PhoneSetVolumeTool(BaseTool):
    """Sets the phone's media volume percentage."""

    name = "phone_set_volume"
    description = "Sets the media volume on the owner's phone as a percentage (0-100)."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "percent": {"type": "integer", "description": "Volume percent 0-100"},
            "stream": {"type": "string", "description": "music | ring | call (default music)", "default": "music"},
            **_DEVICE_ARG,
        },
        "required": ["percent"],
    }

    def execute(
        self, percent: int, stream: str = "music", device_id: str | None = None, **kwargs: Any
    ) -> ToolResult:
        pct = max(0, min(int(percent), 100))
        return _dispatch(
            self.name,
            "set_volume",
            {"percent": pct, "stream": str(stream or "music")},
            device_id=device_id,
            success=f"Phone volume set to {pct}%.",
        )


class PhoneFindMyPhoneTool(BaseTool):
    """Rings the owner's phone at full volume so it can be found."""

    name = "phone_find"
    description = (
        "Makes the owner's phone ring loudly at full volume for up to a minute, "
        "even on silent, so he can find it. Use when he says he lost/misplaced his phone."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "seconds": {"type": "integer", "description": "How long to ring (default 30, max 120)", "default": 30},
            **_DEVICE_ARG,
        },
    }

    def execute(self, seconds: int = 30, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        secs = max(5, min(int(seconds or 30), 120))
        return _dispatch(
            self.name,
            "find_phone",
            {"seconds": secs},
            device_id=device_id,
            timeout=float(secs) + 30.0,
            success=f"Your phone is ringing at full volume for {secs} seconds.",
        )


class PhoneTapTool(BaseTool):
    """Taps the phone screen (companion-app executor only)."""

    name = "phone_tap"
    description = (
        "Taps the owner's phone screen at pixel coordinates (x, y). "
        "Requires the companion app executor (the Termux agent cannot inject touches)."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "x": {"type": "integer", "description": "X coordinate"},
            "y": {"type": "integer", "description": "Y coordinate"},
            **_DEVICE_ARG,
        },
        "required": ["x", "y"],
    }

    def execute(self, x: int, y: int, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "tap",
            {"x": int(x), "y": int(y)},
            device_id=device_id,
            success=f"Tapped your phone screen at ({x}, {y}).",
        )


class PhoneSwipeTool(BaseTool):
    """Swipes on the phone screen (companion-app executor only)."""

    name = "phone_swipe"
    description = "Swipes on the owner's phone screen from (x1, y1) to (x2, y2). Requires the companion app executor."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "x1": {"type": "integer", "description": "Start X"},
            "y1": {"type": "integer", "description": "Start Y"},
            "x2": {"type": "integer", "description": "End X"},
            "y2": {"type": "integer", "description": "End Y"},
            "duration_ms": {"type": "integer", "description": "Duration in ms (default 300)", "default": 300},
            **_DEVICE_ARG,
        },
        "required": ["x1", "y1", "x2", "y2"],
    }

    def execute(
        self,
        x1: int,
        y1: int,
        x2: int,
        y2: int,
        duration_ms: int = 300,
        device_id: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        return _dispatch(
            self.name,
            "swipe",
            {"x1": int(x1), "y1": int(y1), "x2": int(x2), "y2": int(y2), "duration_ms": int(duration_ms)},
            device_id=device_id,
            success=f"Swiped your phone screen ({x1}, {y1}) → ({x2}, {y2}).",
        )


class PhoneTypeTextTool(BaseTool):
    """Types text on the phone (companion-app executor only)."""

    name = "phone_type_text"
    description = "Types text into the focused field on the owner's phone. Requires the companion app executor."
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "text": {"type": "string", "description": "Text to type"},
            **_DEVICE_ARG,
        },
        "required": ["text"],
    }

    def execute(self, text: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "type_text",
            {"text": str(text)},
            device_id=device_id,
            success="Typed the text on your phone.",
        )


class PhonePressKeyTool(BaseTool):
    """Presses a navigation/hardware key on the phone."""

    name = "phone_press_key"
    description = (
        "Presses a key on the owner's phone: home, back, app_switch, enter, "
        "volume_up, volume_down, power, media_play_pause, media_next, media_previous."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "key": {"type": "string", "description": "Key name"},
            **_DEVICE_ARG,
        },
        "required": ["key"],
    }

    def execute(self, key: str, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        return _dispatch(
            self.name,
            "press_key",
            {"key": str(key).strip().lower()},
            device_id=device_id,
            success=f"Pressed '{key}' on your phone.",
        )


class PhoneScreenshotTool(BaseTool):
    """Captures the phone screen and saves it server-side (companion app only)."""

    name = "phone_screenshot"
    description = (
        "Captures the owner's phone screen and saves the PNG on the server, "
        "returning its path. Requires the companion app executor."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {"type": "object", "properties": dict(_DEVICE_ARG)}

    def execute(self, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        target = _resolve_device_id(device_id)
        if target is None:
            return ToolResult(
                name=self.name,
                content="No phone is paired with FRIDAY yet (see docs/PHONE_CONTROL.md).",
                is_error=True,
                refused=True,
            )
        try:
            evidence = phone_bridge.execute_sync(target, "screenshot", timeout=45.0, args={})
        except (PhoneNotConnected, PhoneUnsupportedCommand) as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True, refused=True)
        except (PhoneBridgeTimeout, PhoneDisconnected) as exc:
            return ToolResult(
                name=self.name,
                content=f"Screenshot failed: {exc}",
                is_error=True,
                metadata={"evidence": getattr(exc, "evidence", {})},
            )
        if not evidence.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"The phone could not take a screenshot: {evidence.get('error') or 'unknown error'}",
                is_error=True,
                metadata={"evidence": evidence},
            )
        raw = str(evidence.get("output") or "")
        try:
            png = base64.b64decode(raw, validate=True)
        except Exception:
            return ToolResult(
                name=self.name,
                content="The phone returned a screenshot payload that is not valid base64; nothing was saved.",
                is_error=True,
                metadata={"evidence": {**evidence, "output": raw[:64] + "…"}},
            )
        out_dir = Path(__file__).resolve().parents[3] / ".data" / "phone" / "screenshots"
        out_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = out_dir / f"{target}-{stamp}.png"
        path.write_bytes(png)
        logger.info("Phone screenshot saved: %s (%d bytes)", path, len(png))
        return ToolResult(
            name=self.name,
            content=f"Captured your phone screen — saved on the server at {path} ({len(png)} bytes).",
            metadata={"evidence": {**evidence, "output": f"<{len(png)} bytes PNG>"}, "path": str(path)},
        )


__all__ = [
    "PhoneCloseAppTool",
    "PhoneFindMyPhoneTool",
    "PhoneMakeCallTool",
    "PhoneMediaControlTool",
    "PhoneOpenAppTool",
    "PhoneOpenUrlTool",
    "PhonePressKeyTool",
    "PhoneReadNotificationsTool",
    "PhoneScreenshotTool",
    "PhoneSendSmsTool",
    "PhoneSendWhatsAppTool",
    "PhoneSetAlarmTool",
    "PhoneSetVolumeTool",
    "PhoneStatusTool",
    "PhoneSwipeTool",
    "PhoneTapTool",
    "PhoneTypeTextTool",
]
