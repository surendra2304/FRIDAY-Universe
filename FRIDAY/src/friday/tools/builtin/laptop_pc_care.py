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
* **Storage-repair sequences** (TASK-FRD-046) — ``laptop_storage_sequences``
  (DANGEROUS on apply): four guided routines — diskpart repartition,
  diskpart write-protection removal, the Linux fsck equivalent, and DISM
  component-store cleanup. Dry-run by default: with ``apply`` unset/false
  the tool returns only the ordered plan (steps + exact commands) and runs
  nothing; ``apply=true`` additionally needs ``confirm=true`` and the
  laptop client re-validates sequence, target and platform before running.

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


# ---------------------------------------------------------------------------
# Storage-repair sequences (TASK-FRD-046)
# ---------------------------------------------------------------------------

# Canonical platform per sequence. The plan builder emits the commands for
# the sequence's home platform; the laptop client routes or refuses per
# the machine it actually runs on (diskpart/DISM are Windows-only,
# fsck -y is the Linux leg — on Windows the same repair is chkdsk /f via
# laptop_storage_repair, on macOS diskutil repairVolume).
STORAGE_SEQUENCES: dict[str, dict[str, Any]] = {
    "diskpart_repartition": {
        "platform": "Windows",
        "destructive": True,
        "summary": (
            "Wipe a non-system disk and create one fresh NTFS partition "
            "(diskpart clean + create partition primary + format quick)."
        ),
        "steps": [
            "List disks and confirm the target disk number",
            "Select the target disk",
            "Clean the disk (removes all partitions and data)",
            "Create one primary partition",
            "Quick-format it NTFS",
            "Assign a drive letter",
        ],
    },
    "diskpart_writeprotect_off": {
        "platform": "Windows",
        "destructive": False,
        "summary": (
            "Clear the read-only attribute on a disk "
            "(diskpart attributes disk clear readonly)."
        ),
        "steps": [
            "List disks and confirm the target disk number",
            "Select the target disk",
            "Clear the read-only attribute",
        ],
    },
    "fsck_equivalent": {
        "platform": "Linux",
        "destructive": False,
        "summary": (
            "Filesystem repair on an unmounted device (fsck -y; "
            "diskutil repairVolume on macOS, chkdsk /f on Windows via "
            "laptop_storage_repair)."
        ),
        "steps": [
            "Confirm the device is unmounted",
            "Run the filesystem check with automatic repair",
        ],
    },
    "dism_cleanup": {
        "platform": "Windows",
        "destructive": False,
        "summary": (
            "Clean the Windows component store "
            "(DISM /Online /Cleanup-Image /StartComponentCleanup), "
            "after a read-only /Analyze."
        ),
        "steps": [
            "Analyse the component store (read-only)",
            "Clean the component store",
        ],
    },
}


def _normalise_target(value: str) -> str:
    """Normalise a repair target for the system-volume check."""
    text = value.strip().rstrip("/\\")
    if len(text) == 2 and text[1] == ":" and text[0].isalpha():
        return text.upper()
    return text


def _disk_number(target: str) -> str | None:
    """Return the diskpart disk number for '1' / 'disk 1', else None."""
    text = target.strip().lower()
    if text.startswith("disk "):
        text = text[5:].strip()
    return text if text.isdigit() else None


def build_storage_sequence_plan(sequence: str, target: str = "") -> dict[str, Any]:
    """Return the ordered plan (steps + exact commands) for a sequence.

    Pure function — no laptop, no subprocess. Raises ValueError for an
    unknown sequence, a missing target, the system volume, or disk 0
    (diskpart targets: disk 0 is the system disk on a normal Windows
    install and is never a repartition/write-protect target).
    """
    name = (sequence or "").strip().lower()
    spec = STORAGE_SEQUENCES.get(name)
    if spec is None:
        raise ValueError(
            f"Unknown storage sequence '{sequence}'. Known: "
            + ", ".join(sorted(STORAGE_SEQUENCES))
            + "."
        )
    cleaned = (target or "").strip()
    if name == "dism_cleanup":
        cleaned = cleaned or "online"
    if not cleaned:
        raise ValueError(f"Sequence '{name}' needs a target (disk, device or volume).")
    if _normalise_target(cleaned) in ("", "/", "C:"):
        raise ValueError(f"Refusing the system volume ({target}) as a repair target.")
    plan: dict[str, Any] = {
        "sequence": name,
        "target": cleaned,
        "platform": spec["platform"],
        "destructive": spec["destructive"],
        "summary": spec["summary"],
        "steps": list(spec["steps"]),
    }
    if name in ("diskpart_repartition", "diskpart_writeprotect_off"):
        disk = _disk_number(cleaned)
        if disk is None:
            raise ValueError(
                f"Sequence '{name}' needs a disk number target "
                f"(e.g. '1' or 'disk 1'), got '{target}'."
            )
        if disk == "0":
            raise ValueError(
                "Refusing disk 0 — on a normal Windows install that is "
                "the system disk."
            )
        script = ["list disk", f"select disk {disk}"]
        if name == "diskpart_repartition":
            script += ["clean", "create partition primary", "format fs=ntfs quick", "assign"]
        else:
            script += ["attributes disk clear readonly"]
        plan["script"] = "\n".join(script)
        plan["commands"] = [["diskpart", "/s", "<script-file>"]]
    elif name == "fsck_equivalent":
        plan["commands"] = [["fsck", "-y", cleaned]]
        plan["platform_note"] = (
            "Linux leg (fsck -y); the laptop client runs diskutil "
            "repairVolume on macOS and refuses on Windows — use "
            "laptop_storage_repair (chkdsk /f) there."
        )
    else:  # dism_cleanup
        plan["commands"] = [
            ["DISM", "/Online", "/Cleanup-Image", "/Analyze"],
            ["DISM", "/Online", "/Cleanup-Image", "/StartComponentCleanup"],
        ]
    return plan


class LaptopStorageSequencesTool(_LaptopTool):
    """Run one guided storage-repair sequence — dry-run by default."""

    name = "laptop_storage_sequences"
    description = (
        "Run one guided storage-repair sequence on the owner's laptop: "
        "'diskpart_repartition' (Windows: wipe a non-system disk, one fresh NTFS partition), "
        "'diskpart_writeprotect_off' (Windows: clear a disk's read-only flag), "
        "'fsck_equivalent' (Linux: fsck -y on an unmounted device; macOS diskutil repairVolume; on Windows use laptop_storage_repair), "
        "'dism_cleanup' (Windows: DISM component-store cleanup after a read-only /Analyze). "
        "DRY-RUN BY DEFAULT: with apply=false (or omitted) it only returns the ordered plan — steps plus the exact commands — and runs nothing. "
        "With apply=true it additionally needs confirm=true in the same call, and the laptop re-validates the sequence, the target and the platform before running anything. "
        "Disk 0 and the system volume are always refused."
    )
    safety_level = SafetyLevel.DANGEROUS
    command = "storage_sequences"
    default_timeout = 280.0
    parameters = {
        "type": "object",
        "properties": {
            "sequence": {
                "type": "string",
                "description": "One of: diskpart_repartition, diskpart_writeprotect_off, fsck_equivalent, dism_cleanup.",
            },
            "target": {
                "type": "string",
                "description": "Disk number ('1' / 'disk 1') for diskpart, device path ('/dev/sdb1') for fsck; 'online' (default) for dism_cleanup.",
            },
            "apply": {
                "type": "boolean",
                "description": "false (default): return the plan only, run nothing. true: run the sequence on the laptop (needs confirm=true).",
            },
            "confirm": {
                "type": "boolean",
                "description": "Must be true with apply=true — acknowledges the sequence can modify storage.",
            },
            "laptop_id": {"type": "string", "description": "Optional laptop id."},
        },
        "required": ["sequence"],
    }

    def execute(
        self,
        sequence: str = "",
        target: str = "",
        apply: bool = False,
        confirm: bool = False,
        laptop_id: str = "",
        **kwargs: Any,
    ) -> ToolResult:
        try:
            plan = build_storage_sequence_plan(sequence, target)
        except ValueError as exc:
            return self._error(str(exc))
        if not apply:
            lines = [
                f"Plan for '{plan['sequence']}' on {plan['target']} ({plan['platform']}):",
                plan["summary"],
            ]
            for i, step in enumerate(plan["steps"], 1):
                lines.append(f"{i}. {step}")
            if plan.get("platform_note"):
                lines.append(plan["platform_note"])
            lines.append("Commands that would run:")
            for argv in plan["commands"]:
                lines.append("  " + " ".join(argv))
            if plan.get("script"):
                lines.append("diskpart script:")
                lines.extend("  " + line for line in plan["script"].splitlines())
            lines.append(
                "Nothing was run — re-run with apply=true and confirm=true "
                "to execute on the laptop."
            )
            return ToolResult(
                name=self.name,
                content="\n".join(lines),
                is_error=False,
                safety_level=self.safety_level,
            )
        if confirm is not True:
            return self._error(
                "Refused: this sequence can modify storage. Re-run with "
                "apply=true AND confirm=true in the same call, only after "
                "the owner has seen the plan."
            )
        evidence, error = self._dispatch(
            {"sequence": plan["sequence"], "target": plan["target"], "confirm": True},
            laptop_id or None,
        )
        if error is not None:
            return error
        return self._evidence_result(
            evidence,
            f"Storage sequence '{plan['sequence']}' on {plan['target']} "
            f"({evidence.get('laptop_id')}):\n{evidence.get('output', '')}",
        )
