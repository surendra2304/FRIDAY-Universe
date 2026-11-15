"""PC care tools for the owner's laptop (TASK-IG-LAP-03).

Three corpus idea groups, one cluster over the LAP-001 laptop bridge:

* **PC health / tune-up / cleanup** (DVQMe9GAE3b, DVhR_XQk6Ml,
  DemQIPwyiyJ, Dee-1i7hsRy, DefKD7YKzol) — ``laptop_pc_health`` (SAFE,
  read-only report with a tune-up checklist) and ``laptop_pc_cleanup``
  (SENSITIVE; enumerate-first: with ``apply`` unset/false it lists what
  WOULD be deleted and deletes nothing).
* **Productivity shortcuts** (DVekxHGCFWT) — ``laptop_hotkey``
  (SENSITIVE): named shortcuts ("copy", "new tab", "show desktop", …)
  or an explicit key combo, validated against a key-name allowlist here
  AND on the laptop client. The ``mod`` key is resolved on the laptop
  (ctrl vs command) because only the laptop knows its OS.
* **Storage repair** (DVlGJaNEal2) — ``laptop_storage_check`` (SAFE,
  read-only scans) and ``laptop_storage_repair`` (DANGEROUS: explicit
  volume + ``confirm=true`` required in the same call; the client
  additionally refuses the system volume and, outside Windows, any
  mounted volume).

All real work happens in the laptop client handlers
(``scripts/laptop_bridge_client.py``); these tools validate, dispatch
and report evidence honestly — including partial results.
"""

from __future__ import annotations

from typing import Any

from friday.core.types import SafetyLevel, ToolResult
from friday.tools.builtin.laptop_control import _LaptopTool

# Canonical shortcut map. "mod" = ctrl (Windows/Linux) / command (macOS),
# resolved by the laptop client. A few are Windows-flavoured (win+d,
# win+l); macOS owners can pass explicit keys instead — the descriptions
# say so rather than pretending one map fits every OS.
NAMED_SHORTCUTS: dict[str, list[str]] = {
    "copy": ["mod", "c"],
    "paste": ["mod", "v"],
    "cut": ["mod", "x"],
    "undo": ["mod", "z"],
    "redo": ["mod", "shift", "z"],
    "save": ["mod", "s"],
    "select_all": ["mod", "a"],
    "find": ["mod", "f"],
    "replace": ["mod", "h"],
    "print": ["mod", "p"],
    "new_window": ["mod", "n"],
    "new_tab": ["mod", "t"],
    "close_tab": ["mod", "w"],
    "reopen_tab": ["mod", "shift", "t"],
    "address_bar": ["mod", "l"],
    "refresh": ["mod", "r"],
    "switch_window": ["alt", "tab"],
    "show_desktop": ["win", "d"],
    "lock": ["win", "l"],
    "back": ["alt", "left"],
    "forward": ["alt", "right"],
    "minimize": ["win", "down"],
    "maximize": ["win", "up"],
    "close_window": ["alt", "f4"],
    "task_view": ["win", "tab"],
}

# Key names accepted for explicit combos (mirrors the client allowlist;
# both sides validate so a bad combo is refused before it travels).
ALLOWED_KEY_NAMES = frozenset(
    set("abcdefghijklmnopqrstuvwxyz0123456789")
    | {f"f{i}" for i in range(1, 13)}
    | {
        "ctrl", "control", "alt", "shift", "win", "windows", "command",
        "cmd", "meta", "mod", "enter", "return", "esc", "escape", "tab",
        "space", "backspace", "delete", "del", "insert", "home", "end",
        "pageup", "pagedown", "pgup", "pgdn", "up", "down", "left", "right",
        "-", "=", "[", "]", ";", "'", ",", ".", "/", "\\", "`",
    }
)


def validate_keys(keys: Any) -> list[str] | None:
    """Return the normalised key list, or None if anything is off-list."""
    if not isinstance(keys, list) or not keys or len(keys) > 6:
        return None
    normalised = [str(key).strip().lower() for key in keys]
    if any(not key or key not in ALLOWED_KEY_NAMES for key in normalised):
        return None
    return normalised


class LaptopPcHealthTool(_LaptopTool):
    """Read-only PC health + tune-up report from the owner's laptop."""

    name = "laptop_pc_health"
    description = (
        "Read-only health check of the owner's laptop: disk usage per "
        "volume, CPU and memory pressure, battery and power plan, uptime, "
        "top memory processes, temp-folder size, and a tune-up checklist "
        "derived from the measured values. Nothing is changed."
    )
    safety_level = SafetyLevel.SAFE
    command = "pc_health"
    default_timeout = 120.0
    parameters = {
        "type": "object",
        "properties": {
            "laptop_id": {"type": "string", "description": "Optional laptop id."},
        },
        "required": [],
    }

    def execute(self, laptop_id: str = "", **kwargs: Any) -> ToolResult:
        evidence, error = self._dispatch({}, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"PC health report from laptop '{evidence.get('laptop_id')}':\n{evidence.get('output', '')}"
        )


class LaptopPcCleanupTool(_LaptopTool):
    """Enumerate (default) or apply a temp-files cleanup on the laptop."""

    name = "laptop_pc_cleanup"
    description = (
        "Clean temporary files on the owner's laptop. SAFE DEFAULT: with "
        "apply=false (or omitted) it only enumerates temp files older "
        "than min_age_hours and reports count/bytes/sample — nothing is "
        "deleted. With apply=true it deletes exactly the enumerated "
        "files and reports freed bytes and any locked-file failures."
    )
    safety_level = SafetyLevel.SENSITIVE
    command = "pc_cleanup"
    default_timeout = 240.0
    parameters = {
        "type": "object",
        "properties": {
            "apply": {
                "type": "boolean",
                "description": "false (default): enumerate only. true: delete the enumerated temp files.",
            },
            "min_age_hours": {
                "type": "integer",
                "description": "Only files at least this old are candidates (default 24).",
            },
            "laptop_id": {"type": "string", "description": "Optional laptop id."},
        },
        "required": [],
    }

    def execute(
        self,
        apply: bool = False,
        min_age_hours: int = 24,
        laptop_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        args = {"apply": bool(apply), "min_age_hours": int(min_age_hours)}
        evidence, error = self._dispatch(args, laptop_id or None)
        if error is not None:
            return error
        verb = "Cleanup result" if apply else "Cleanup preview (nothing deleted)"
        return self._evidence_result(
            evidence, f"{verb} from laptop '{evidence.get('laptop_id')}':\n{evidence.get('output', '')}"
        )


class LaptopHotkeyTool(_LaptopTool):
    """Press a named shortcut or an explicit key combo on the laptop."""

    name = "laptop_hotkey"
    description = (
        "Press a keyboard shortcut on the owner's laptop. Pass either "
        "'shortcut' (one of: " + ", ".join(sorted(NAMED_SHORTCUTS)) + ") or "
        "'keys' (an explicit combo like ['ctrl', 'shift', 't']; key names "
        "are allowlist-validated on both sides). 'mod' means ctrl on "
        "Windows/Linux and command on macOS. Some named shortcuts are "
        "Windows-flavoured (show_desktop, lock); on macOS pass explicit keys."
    )
    safety_level = SafetyLevel.SENSITIVE
    command = "hotkey"
    parameters = {
        "type": "object",
        "properties": {
            "shortcut": {"type": "string", "description": "Named shortcut (see description)."},
            "keys": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Explicit key combo, 1-6 allowlisted key names.",
            },
            "laptop_id": {"type": "string", "description": "Optional laptop id."},
        },
        "required": [],
    }

    def execute(
        self,
        shortcut: str = "",
        keys: Any = None,
        laptop_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        name = (shortcut or "").strip().lower()
        if name:
            combo = NAMED_SHORTCUTS.get(name)
            if combo is None:
                return self._error(
                    f"Unknown shortcut '{name}'. Known: {', '.join(sorted(NAMED_SHORTCUTS))}."
                )
            resolved = list(combo)
            label = f"shortcut '{name}'"
        elif keys is not None:
            resolved = validate_keys(keys)
            if resolved is None:
                return self._error(
                    "Invalid 'keys': pass 1-6 key names from the allowlist "
                    "(letters, digits, f1-f12, ctrl/alt/shift/win/command/mod, "
                    "enter, esc, tab, space, arrows, home/end, pageup/pagedown, "
                    "backspace, delete, insert, common punctuation)."
                )
            label = "keys " + "+".join(resolved)
        else:
            return self._error("Pass either 'shortcut' or 'keys'.")
        evidence, error = self._dispatch({"keys": resolved}, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"Pressed {label} on laptop '{evidence.get('laptop_id')}'."
        )


class LaptopStorageCheckTool(_LaptopTool):
    """Read-only filesystem check of laptop volumes."""

    name = "laptop_storage_check"
    description = (
        "Read-only filesystem check of the owner's laptop volumes "
        "(chkdsk scan on Windows, diskutil verify on macOS, fsck -n on "
        "Linux). With no 'volume', all mounted volumes are checked; on "
        "Linux a mounted volume is honestly skipped (fsck needs it "
        "unmounted) — plug in a USB/SD volume, unmount it, then check it."
    )
    safety_level = SafetyLevel.SAFE
    command = "storage_check"
    default_timeout = 280.0
    parameters = {
        "type": "object",
        "properties": {
            "volume": {"type": "string", "description": "Optional single volume (drive letter, device path or mount point)."},
            "laptop_id": {"type": "string", "description": "Optional laptop id."},
        },
        "required": [],
    }

    def execute(self, volume: str = "", laptop_id: str = "", **kwargs: Any) -> ToolResult:
        args = {"volume": volume} if (volume or "").strip() else {}
        evidence, error = self._dispatch(args, laptop_id or None)
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"Storage check from laptop '{evidence.get('laptop_id')}':\n{evidence.get('output', '')}"
        )


class LaptopStorageRepairTool(_LaptopTool):
    """Repair a volume — DANGEROUS, confirm-gated on both sides."""

    name = "laptop_storage_repair"
    description = (
        "Repair a filesystem on the owner's laptop (chkdsk /f, fsck -y, "
        "diskutil repairVolume). DANGEROUS: requires an explicit 'volume' "
        "AND confirm=true in the same call. The laptop refuses the system "
        "volume outright and, outside Windows, any mounted volume — "
        "unmount/eject first. Run laptop_storage_check first and show "
        "the owner the result before repairing."
    )
    safety_level = SafetyLevel.DANGEROUS
    command = "storage_repair"
    default_timeout = 280.0
    parameters = {
        "type": "object",
        "properties": {
            "volume": {"type": "string", "description": "Volume to repair (drive letter, device path or mount point)."},
            "confirm": {"type": "boolean", "description": "Must be true — acknowledges the repair can modify the filesystem."},
            "laptop_id": {"type": "string", "description": "Optional laptop id."},
        },
        "required": ["volume", "confirm"],
    }

    def execute(
        self,
        volume: str = "",
        confirm: bool = False,
        laptop_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        target = (volume or "").strip()
        if not target:
            return self._error("No volume given — repair needs an explicit target.")
        if confirm is not True:
            return self._error(
                "Refused: storage repair can modify a filesystem. Re-run with "
                "confirm=true only after the owner has seen a storage_check "
                "result for this volume."
            )
        evidence, error = self._dispatch(
            {"volume": target, "confirm": True}, laptop_id or None
        )
        if error is not None:
            return error
        return self._evidence_result(
            evidence, f"Storage repair of {target} on laptop '{evidence.get('laptop_id')}':\n{evidence.get('output', '')}"
        )
