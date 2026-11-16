# Escrcpy Integration — FRIDAY-side hooks over the scrcpy transport

TASK-IG2-LAP-01, from the owner's Instagram reference corpus
(viarotel-org/escrcpy, reel DYQ2Z2aiaLf). Spec card:
`ig-references/repos/viarotel-org-escrcpy.md` — verdict **adapt**.

## Verdict in one paragraph

Adopt the **released Escrcpy desktop app as-is** on the owner's laptop as
the human-facing GUI over the already-adopted scrcpy transport
(TASK-IG-LAP-01 / `docs/PHONE_UI_AUTOMATION.md`). Adapt, at the automation
layer, its MCP-Copilot + visual-automation pattern as FRIDAY's own
declarative automation scripts over the same ADB/scrcpy channel — instead
of a second, parallel control stack. **Skip the paid private EscrcpyX
extension entirely** (owner's FREE-only rule); the Apache-2.0 core covers
the mirror/control need.

## What shipped

| Piece | Where | What it does |
|---|---|---|
| Integration engine | `FRIDAY/src/friday/remote/escrcpy_integration.py` | Validated shell-free launch argv (`MirrorProfile` → `build_launch_args`), `adb devices` parsing, declarative `AutomationScript` validation + rendering to adb commands, install guidance. Stdlib only, Python 3.10. |
| Tools | `FRIDAY/src/friday/tools/builtin/escrcpy_control.py` | `escrcpy_launch_plan` (SAFE — plan + install guidance for the laptop) and `escrcpy_automation` (SENSITIVE — validate + render a script; rendering is the deliverable, execution still goes through the phone bridge / ADB agent). |
| Tests | `FRIDAY/tests/test_ig2_lap01_escrcpy.py` | Launch-plan validation, device parsing, automation gates and rendering. |

## Owner setup (once, on the laptop)

1. Install Escrcpy from GitHub Releases (Windows/macOS/Linux) — or
   `brew install --cask escrcpy` on macOS. Free core only; do **not**
   purchase/install EscrcpyX.
2. Ensure `adb` (Android platform-tools) is on PATH; enable USB or
   wireless debugging on the phone (realme narzo 30 Pro 5G) and approve
   the debugging prompt.
3. Ask FRIDAY for an `escrcpy_launch_plan`, launch Escrcpy on the laptop,
   pick the phone — mirror, keyboard mapping, multi-device broadcast,
   batch screenshots/APK installs are Escrcpy's own GUI features.
4. For FRIDAY-driven control, use the existing `phone_ui_task` /
   `phone_ui_dump` tools, or a validated `escrcpy_automation` script
   rendered to the same ADB transport.

## Safety model (inherited, not reinvented)

- Automation scripts reuse `BLOCKED_PACKAGE_HINTS` from
  `friday.remote.phone_ui_agent`: banking / payment / authenticator
  packages are refused, credential typing/searching is refused, and
  coordinates / waits / text are bounded in code.
- Launch plans are argv lists, never shell strings; serials are
  regex-validated and every numeric option is range-checked.
- Nothing in this task runs a GUI, scrcpy, or adb on the fleet servers.

## Attribution

viarotel-org/escrcpy (Apache-2.0) and Genymobile/scrcpy (Apache-2.0) are
pattern/transport references and external tools — no code is vendored or
copied into FRIDAY.
