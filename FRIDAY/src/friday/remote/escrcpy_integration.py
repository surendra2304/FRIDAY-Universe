"""Escrcpy integration for FRIDAY's Laptop-Phone lane (TASK-IG2-LAP-01).

ADAPT of viarotel-org/escrcpy (Apache-2.0): the *released desktop app* is
adopted as-is on the owner's laptop as the human-facing GUI over the
already-adopted scrcpy transport (Genymobile/scrcpy, Apache-2.0 — see
``docs/PHONE_UI_AUTOMATION.md``). Escrcpy is an Electron app: it can never
run on the 956 MB headless fleet servers, and this module never tries to
run it there. What lives here is the FRIDAY-side integration:

* a validated, shell-free launch-plan builder — the exact ``escrcpy`` /
  ``scrcpy`` argv FRIDAY hands to the laptop bridge / owner, with every
  value range-checked so no argument can smuggle a shell or a flag;
* ``adb devices`` parsing so FRIDAY can confirm which phone Escrcpy will
  mirror before anyone launches anything;
* the automation design reference taken from Escrcpy's MCP-Copilot +
  visual-automation pattern, re-implemented FRIDAY-natively: a
  *declarative* automation script (tap / swipe / type / wait / find-text
  steps) that is validated against the SAME code-level safety gates as
  ``friday.remote.phone_ui_agent`` (no credential instructions, no
  banking/payment/authenticator packages, no password-field typing) and
  rendered to plain ``adb`` commands over the existing scrcpy/ADB
  transport — no second, parallel control stack, no EscrcpyX (the paid
  private extension is explicitly out, per the owner's FREE-only rule).

No code is copied from Escrcpy (TypeScript/Electron); this is a pattern
adaptation. Attribution: viarotel-org/escrcpy, Apache-2.0.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

try:  # reuse the planner's gate lists so the lanes can never drift apart
    from friday.remote.phone_ui_agent import BLOCKED_PACKAGE_HINTS
except Exception:  # pragma: no cover - import fallback for isolated tests
    BLOCKED_PACKAGE_HINTS = ("bank", "paytm", "gpay", "paisa", "phonepe",
                              "bhim", "upi", "wallet", "authenticator",
                              "keepass", "bitwarden", "lastpass", "1password")

_SERIAL_RE = re.compile(r"^[A-Za-z0-9._:\-]{1,64}$")
_CREDENTIAL_HINTS = ("password", "otp", "cvv", "authenticator code",
                     "one-time code", "pin code")
MAX_BIT_RATE = 32_000_000
MIN_BIT_RATE = 100_000
MAX_SIZE_CHOICES = (0, 640, 800, 1024, 1280, 1600, 1920)


class EscrcpyError(ValueError):
    """Raised when a launch plan or automation script is refused."""


@dataclass(frozen=True, slots=True)
class MirrorProfile:
    """Validated options for one Escrcpy/scrcpy mirror session."""

    serial: str = ""
    max_size: int = 0
    bit_rate: int = 8_000_000
    max_fps: int = 60
    turn_screen_off: bool = False
    stay_awake: bool = True
    record_file: str = ""

    def validate(self) -> None:
        if self.serial and not _SERIAL_RE.match(self.serial):
            raise EscrcpyError(f"unsafe device serial: {self.serial!r}")
        if self.max_size not in MAX_SIZE_CHOICES:
            raise EscrcpyError(
                f"max_size must be one of {MAX_SIZE_CHOICES}, got {self.max_size}")
        if not (MIN_BIT_RATE <= self.bit_rate <= MAX_BIT_RATE):
            raise EscrcpyError(
                f"bit_rate must be {MIN_BIT_RATE}..{MAX_BIT_RATE}, got {self.bit_rate}")
        if not (1 <= self.max_fps <= 120):
            raise EscrcpyError(f"max_fps must be 1..120, got {self.max_fps}")
        if self.record_file and ("/" in self.record_file.replace("\\", "/")
                                 and ".." in self.record_file):
            raise EscrcpyError("record_file must not contain '..'")


def build_launch_args(profile: MirrorProfile, *, gui: bool = True) -> list[str]:
    """Return the shell-free argv that launches the mirror on the laptop.

    ``gui=True`` launches the adopted Escrcpy app; ``gui=False`` launches
    the underlying scrcpy binary directly (same transport, no GUI).
    The result is an argv list — it is never joined into a shell string.
    """
    profile.validate()
    argv = ["escrcpy"] if gui else ["scrcpy"]
    if profile.serial:
        argv += ["--serial", profile.serial] if not gui else ["-s", profile.serial]
    if not gui:
        if profile.max_size:
            argv += ["--max-size", str(profile.max_size)]
        argv += ["--video-bit-rate", str(profile.bit_rate),
                 "--max-fps", str(profile.max_fps)]
        if profile.turn_screen_off:
            argv.append("--turn-screen-off")
        if profile.stay_awake:
            argv.append("--stay-awake")
        if profile.record_file:
            argv += ["--record", profile.record_file]
    return argv


def parse_adb_devices(text: str) -> list[dict[str, str]]:
    """Parse ``adb devices`` output into [{serial, state}, ...]."""
    devices: list[dict[str, str]] = []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("List of devices"):
            continue
        parts = line.split()
        if len(parts) >= 2:
            devices.append({"serial": parts[0], "state": parts[1]})
    return devices


def usable_devices(text: str) -> list[str]:
    """Serials in the ``device`` (ready) state only."""
    return [d["serial"] for d in parse_adb_devices(text) if d["state"] == "device"]


# --- Declarative automation (Escrcpy Copilot / visual-automation pattern) ---

_STEP_KINDS = frozenset({"tap", "swipe", "type", "wait", "find_text", "press_key"})
_KEYCODES = frozenset({"BACK", "HOME", "ENTER", "TAB", "APP_SWITCH", "POWER"})


@dataclass(slots=True)
class AutomationStep:
    kind: str
    x: int = 0
    y: int = 0
    x2: int = 0
    y2: int = 0
    text: str = ""
    seconds: float = 0.0
    key: str = ""
    package: str = ""

    def validate(self) -> None:
        if self.kind not in _STEP_KINDS:
            raise EscrcpyError(f"unknown automation step kind: {self.kind!r}")
        lowered = f"{self.text} {self.package}".lower()
        for hint in _CREDENTIAL_HINTS:
            if hint in lowered and self.kind in ("type", "find_text"):
                raise EscrcpyError(
                    "automation scripts may not type or search for credentials")
        for hint in BLOCKED_PACKAGE_HINTS:
            if self.package and hint in self.package.lower():
                raise EscrcpyError(
                    f"automation is refused inside blocked package {self.package!r}")
        if self.kind in ("tap", "swipe"):
            for value in (self.x, self.y, self.x2, self.y2):
                if not (0 <= value <= 10000):
                    raise EscrcpyError("coordinates must be 0..10000")
        if self.kind == "type" and not self.text:
            raise EscrcpyError("type step needs text")
        if self.kind == "type" and len(self.text) > 4096:
            raise EscrcpyError("type step text is too long (max 4096)")
        if self.kind == "wait" and not (0 < self.seconds <= 60):
            raise EscrcpyError("wait step must be 0..60 seconds")
        if self.kind == "press_key" and self.key.upper() not in _KEYCODES:
            raise EscrcpyError(f"key must be one of {sorted(_KEYCODES)}")


@dataclass(slots=True)
class AutomationScript:
    """A validated, declarative phone automation (Copilot-pattern)."""

    name: str
    steps: list[AutomationStep] = field(default_factory=list)

    def validate(self) -> None:
        if not self.name.strip():
            raise EscrcpyError("automation script needs a name")
        if not self.steps:
            raise EscrcpyError("automation script needs at least one step")
        if len(self.steps) > 100:
            raise EscrcpyError("automation script is too long (max 100 steps)")
        for step in self.steps:
            step.validate()

    @classmethod
    def from_dict(cls, data: dict) -> "AutomationScript":
        steps = [AutomationStep(**{k: v for k, v in raw.items()
                                   if k in AutomationStep.__dataclass_fields__})
                 for raw in data.get("steps", [])]
        script = cls(name=str(data.get("name", "")), steps=steps)
        script.validate()
        return script


def _escape_adb_text(text: str) -> str:
    return text.replace("%", "%%").replace(" ", "%s")


def render_adb_commands(script: AutomationScript, serial: str = "") -> list[list[str]]:
    """Render a validated script to plain adb argv lists (scrcpy transport).

    ``find_text`` renders to a ``uiautomator dump`` observation command —
    it observes, it does not act — mirroring Escrcpy's image/text-recognition
    step without any new dependency.
    """
    script.validate()
    if serial and not _SERIAL_RE.match(serial):
        raise EscrcpyError(f"unsafe device serial: {serial!r}")
    base = ["adb"] + (["-s", serial] if serial else [])
    commands: list[list[str]] = []
    for step in script.steps:
        if step.kind == "tap":
            commands.append(base + ["shell", "input", "tap", str(step.x), str(step.y)])
        elif step.kind == "swipe":
            commands.append(base + ["shell", "input", "swipe", str(step.x), str(step.y),
                                    str(step.x2), str(step.y2), "300"])
        elif step.kind == "type":
            commands.append(base + ["shell", "input", "text", _escape_adb_text(step.text)])
        elif step.kind == "wait":
            commands.append(["sleep", str(step.seconds)])
        elif step.kind == "press_key":
            commands.append(base + ["shell", "input", "keyevent",
                                    f"KEYCODE_{step.key.upper()}"])
        elif step.kind == "find_text":
            commands.append(base + ["shell", "uiautomator", "dump", "/sdcard/window_dump.xml"])
    return commands


def install_guidance(platform_name: str = "") -> dict[str, str]:
    """How the owner installs the *released* Escrcpy app (free core only)."""
    plat = (platform_name or "").lower()
    common = {
        "source": "https://github.com/viarotel-org/escrcpy/releases",
        "licence": "Apache-2.0 (core app). The paid private EscrcpyX extension is NOT installed — FREE-only rule.",
        "note": "Escrcpy runs on the laptop only; nothing is installed on the fleet servers.",
    }
    if "win" in plat:
        return {**common, "steps": "Download the Windows installer from GitHub Releases, run it, connect the phone by USB or wireless ADB, pick the device in Escrcpy."}
    if "darwin" in plat or "mac" in plat:
        return {**common, "steps": "brew install --cask escrcpy (or download the macOS build from GitHub Releases), connect the phone, pick the device in Escrcpy."}
    return {**common, "steps": "Download the Linux build from GitHub Releases (or your distro package), ensure adb + scrcpy are on PATH, connect the phone, pick the device in Escrcpy."}


__all__ = ["AutomationScript", "AutomationStep", "EscrcpyError", "MirrorProfile",
           "build_launch_args", "install_guidance", "parse_adb_devices",
           "render_adb_commands", "usable_devices"]
