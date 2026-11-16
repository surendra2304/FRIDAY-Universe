"""Tools for TASK-IG2-LAP-01 — Escrcpy integration over scrcpy transport.

* ``escrcpy_launch_plan`` (SAFE) — the validated argv + install guidance
  for launching the adopted Escrcpy GUI (or bare scrcpy) on the owner's
  laptop. FRIDAY servers never run the GUI; this is a plan for the
  laptop side, where Escrcpy actually lives.
* ``escrcpy_automation`` (SENSITIVE) — validate a declarative automation
  script (Escrcpy Copilot-pattern) against the phone lane's safety gates
  and render it to adb commands. Rendering is the deliverable; execution
  still goes through the existing phone bridge / ADB agent.
Engine: ``friday.remote.escrcpy_integration``.
"""
from __future__ import annotations

import json
from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.base import BaseTool


class EscrcpyLaunchPlanTool(BaseTool):
    name = "escrcpy_launch_plan"
    description = (
        "Plan launching Escrcpy (the adopted free GUI over scrcpy) on the "
        "owner's laptop to mirror/control his Android phone: returns a "
        "validated, shell-free launch argv plus install guidance. The GUI "
        "runs on the laptop only — never on FRIDAY's servers. The paid "
        "EscrcpyX extension is excluded."
    )
    safety_level = SafetyLevel.SAFE
    parameters = {
        "type": "object",
        "properties": {
            "serial": {"type": "string", "description": "Optional adb device serial."},
            "gui": {"type": "boolean", "description": "True for Escrcpy GUI, false for bare scrcpy."},
            "max_size": {"type": "integer", "description": "0 (native) or 640/800/1024/1280/1600/1920."},
            "platform": {"type": "string", "description": "Laptop OS for install guidance: windows/macos/linux."},
        },
        "required": [],
    }

    def execute(self, serial: str = "", gui: bool = True, max_size: int = 0,
                platform: str = "", **kwargs: Any) -> ToolResult:
        from friday.remote.escrcpy_integration import (
            EscrcpyError, MirrorProfile, build_launch_args, install_guidance)

        try:
            argv = build_launch_args(
                MirrorProfile(serial=serial or "", max_size=int(max_size or 0)), gui=bool(gui))
        except (EscrcpyError, ValueError) as exc:
            return ToolResult(name=self.name, content=f"Launch plan refused: {exc}",
                              is_error=True, refused=True)
        guide = install_guidance(platform)
        content = (f"Launch on the laptop: {' '.join(argv)}\n"
                   f"Install: {guide['steps']}\nSource: {guide['source']}\n{guide['licence']}")
        return ToolResult(name=self.name, content=content,
                          metadata={"argv": argv, "install": guide})


class EscrcpyAutomationTool(BaseTool):
    name = "escrcpy_automation"
    description = (
        "Validate a declarative phone automation script (steps: tap, swipe, "
        "type, wait, find_text, press_key — the Escrcpy Copilot pattern) "
        "against FRIDAY's phone safety gates and render it to adb commands "
        "over the existing scrcpy/ADB transport. Credential typing and "
        "banking/payment/authenticator packages are refused in code."
    )
    safety_level = SafetyLevel.SENSITIVE
    risk_level = "SENSITIVE"
    parameters = {
        "type": "object",
        "properties": {
            "script": {"type": "object", "description": "{name, steps: [{kind, ...}]}"},
            "serial": {"type": "string", "description": "Optional adb device serial."},
        },
        "required": ["script"],
    }

    def execute(self, script: Any = None, serial: str = "", **kwargs: Any) -> ToolResult:
        from friday.remote.escrcpy_integration import (
            AutomationScript, EscrcpyError, render_adb_commands)

        if isinstance(script, str):
            try:
                script = json.loads(script)
            except ValueError:
                return ToolResult(name=self.name, content="script must be a JSON object.",
                                  is_error=True, refused=True)
        if not isinstance(script, dict):
            return ToolResult(name=self.name, content="script must be an object {name, steps}.",
                              is_error=True, refused=True)
        try:
            parsed = AutomationScript.from_dict(script)
            commands = render_adb_commands(parsed, serial=serial or "")
        except EscrcpyError as exc:
            return ToolResult(name=self.name, content=f"Automation refused: {exc}",
                              is_error=True, refused=True)
        lines = [f"Automation '{parsed.name}': {len(commands)} adb commands (validated, not executed):"]
        lines += ["  " + " ".join(cmd) for cmd in commands]
        return ToolResult(name=self.name, content="\n".join(lines),
                          metadata={"commands": commands, "steps": len(commands)})


__all__ = ["EscrcpyAutomationTool", "EscrcpyLaunchPlanTool"]
