"""Phone UI automation tools (TASK-IG-LAP-01).

Two agent-facing surfaces over the phone bridge's UI commands:

* ``phone_ui_dump`` (SAFE) — read the phone's current screen as a list of
  UI nodes (text, descriptions, tap centres). Read-only observation.
* ``phone_ui_task`` (SENSITIVE) — give the phone a natural-language
  instruction ("open Settings, find Battery, tell me the level") and let
  the planner in :mod:`friday.remote.phone_ui_agent` observe, decide and
  act through the bridge until it is done, impossible, or out of steps.
  SENSITIVE because it taps and types inside the owner's apps, in his
  name; the planner's code-level gates (no password fields, no
  banking/payment/authenticator apps, no credential instructions) apply
  on every step.

Both need an executor that serves UI commands — the ADB UI agent
(``scripts/phone_ui_agent_adb.py``) or the companion app. When the
connected executor is the Termux agent, the bridge answers with its
precise "executor does not serve this command" refusal, and that refusal
is reported as-is.
"""

from __future__ import annotations

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
from friday.remote.phone_ui_agent import make_llm_decider, run_ui_task
from friday.tools.base import BaseTool

logger = get_logger("tools.phone_ui_control")

_DEVICE_ARG = {
    "device_id": {
        "type": "string",
        "description": "Optional phone device id; omit to use the paired phone.",
    }
}

_NO_PHONE = (
    "No phone is paired with FRIDAY yet. Pairing takes one minute: install a "
    "phone agent (see docs/PHONE_CONTROL.md), ask FRIDAY to pair your phone, "
    "and type the 6-digit code it gives you."
)


def _resolve_device_id(device_id: str | None) -> str | None:
    if device_id and str(device_id).strip():
        return str(device_id).strip()
    return phone_bridge.default_device_id()


class PhoneUiDumpTool(BaseTool):
    """Read the phone's current screen structure (observation only)."""

    name = "phone_ui_dump"
    description = (
        "See the owner's phone screen as structured UI nodes (labels, "
        "descriptions, tap coordinates) via the phone bridge's ui_dump "
        "command. Read-only. Requires the ADB UI agent or companion app "
        "executor — the Termux agent cannot serve it."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {**_DEVICE_ARG},
        "required": [],
    }

    def execute(self, device_id: str | None = None, **kwargs: Any) -> ToolResult:
        target = _resolve_device_id(device_id)
        if target is None:
            return ToolResult(name=self.name, content=_NO_PHONE, is_error=True, refused=True)
        try:
            evidence = phone_bridge.execute_sync(target, "ui_dump", timeout=30.0, args={})
        except PhoneNotConnected:
            return ToolResult(
                name=self.name,
                content=f"Your phone '{target}' is paired but not connected right now.",
                is_error=True, refused=True,
            )
        except PhoneUnsupportedCommand as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True, refused=True)
        except (PhoneBridgeTimeout, PhoneDisconnected, ValueError) as exc:
            return ToolResult(
                name=self.name, content=f"Could not read the phone screen: {exc}", is_error=True
            )
        if not evidence.get("ok"):
            return ToolResult(
                name=self.name,
                content=f"The phone could not complete 'ui_dump': {evidence.get('error') or 'unknown error'}",
                is_error=True, metadata={"evidence": evidence},
            )
        import json

        payload = evidence.get("output")
        try:
            data = json.loads(payload) if isinstance(payload, str) else payload
        except (ValueError, TypeError):
            data = None
        if not isinstance(data, dict) or "nodes" not in data:
            return ToolResult(
                name=self.name,
                content=f"Phone screen (raw): {str(payload)[:3000]}",
                is_error=False, metadata={"evidence": evidence},
            )
        lines = [f"Phone screen: {data.get('count', len(data['nodes']))} UI nodes"
                 + (" (list truncated)" if data.get("truncated") else "")]
        for index, node in enumerate(data["nodes"][:60]):
            label = node.get("text") or node.get("desc") or node.get("id") or "(unlabelled)"
            extras = []
            if node.get("clickable"):
                extras.append("clickable")
            if node.get("focused"):
                extras.append("focused")
            if node.get("password"):
                extras.append("PASSWORD FIELD")
            suffix = f" [{', '.join(extras)}]" if extras else ""
            lines.append(f"  {index}: {label!r} centre={node.get('center')}{suffix}")
        return ToolResult(
            name=self.name, content="\n".join(lines), is_error=False,
            metadata={"evidence": evidence},
        )


class PhoneUiTaskTool(BaseTool):
    """Run a natural-language instruction on the owner's phone UI."""

    name = "phone_ui_task"
    description = (
        "Do something on the owner's Android phone from a natural-language "
        "instruction — e.g. 'open Settings and tell me the battery level' "
        "or 'open YouTube and search for lo-fi mixes'. FRIDAY observes the "
        "screen (UI hierarchy + screenshot), plans one action at a time and "
        "taps/types through the real apps via the phone bridge. It refuses "
        "password fields, credential instructions and banking/payment/"
        "authenticator apps. Requires the ADB UI agent or companion app "
        "executor; the Termux agent cannot inject touches."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "instruction": {
                "type": "string",
                "description": "What to do on the phone, in plain language.",
            },
            "max_steps": {
                "type": "integer",
                "description": "Planner step budget (default 12, max 30).",
            },
            **_DEVICE_ARG,
        },
        "required": ["instruction"],
    }

    def execute(
        self,
        instruction: str = "",
        max_steps: int = 12,
        device_id: str | None = None,
        **kwargs: Any,
    ) -> ToolResult:
        instruction = (instruction or "").strip()
        if not instruction:
            return ToolResult(
                name=self.name, content="No instruction provided.", is_error=True, refused=True
            )
        target = _resolve_device_id(device_id)
        if target is None:
            return ToolResult(name=self.name, content=_NO_PHONE, is_error=True, refused=True)
        try:
            decider = make_llm_decider()
        except RuntimeError as exc:
            return ToolResult(name=self.name, content=str(exc), is_error=True)
        result = run_ui_task(phone_bridge, target, instruction, decider, max_steps=max_steps)
        transcript = "; ".join(
            f"step {s['step']} {s['action']}: {'ok' if s['ok'] else 'FAILED'}"
            for s in result["steps"]
        )
        content = result["summary"]
        if transcript:
            content += f"\nSteps: {transcript}"
        return ToolResult(
            name=self.name,
            content=content,
            is_error=not result["ok"],
            metadata={"stop_reason": result["stop_reason"], "steps": result["steps"]},
        )


__all__ = ["PhoneUiDumpTool", "PhoneUiTaskTool"]
