# Phone UI Automation — natural-language control of the owner's Android phone

TASK-IG-LAP-01, from the owner's Instagram reference corpus (ARTEMIS reel
DehEdBbgQFZ, scrcpy post DYQ2Z2aiaLf, AURA reel DfXcABhzvy3).

## What this adds

TASK-PHONE-001 built the phone bridge and put `tap`, `swipe`,
`type_text`, `press_key` and `screenshot` in its command allowlist — but
no shipped executor could serve them: the Termux agent cannot inject
touches (Android reserves that for accessibility services, ADB, or root),
and the companion app is an uncompiled scaffold. This task ships the
missing executor and the planner that drives it:

| Piece | Where | What it does |
|---|---|---|
| ADB UI agent | `FRIDAY/scripts/phone_ui_agent_adb.py` | Runs on the owner's PC; pairs with FRIDAY like the other phone agents; serves the UI commands by driving the attached phone over ADB (`input`, `screencap`, `uiautomator`). |
| `ui_dump` command | `FRIDAY/src/friday/remote/phone_bridge.py` | One new allowlisted command: the on-screen UI hierarchy, pruned executor-side to actionable nodes (labels, tap centres, focused/password flags). |
| Planner loop | `FRIDAY/src/friday/remote/phone_ui_agent.py` | Observe (hierarchy + screenshot OCR) → decide (FRIDAY's LLM, one strict-JSON action) → safety-gate → act, until done / impossible / out of steps. |
| Tools | `FRIDAY/src/friday/tools/builtin/phone_ui_control.py` | `phone_ui_dump` (SAFE, read-only screen read) and `phone_ui_task` (SENSITIVE, natural-language instruction). |

## Setup (owner, once, ~5 minutes)

1. Install **Android platform-tools** (`adb`) on the computer FRIDAY's
   laptop agent runs on.
2. On the phone: Settings → About → tap Build number 7× → Developer
   options → enable **USB debugging** (or **Wireless debugging**).
   Connect by USB and approve the "Allow USB debugging?" prompt.
3. `pip install websockets` on the computer.
4. Pair and run:
   ```
   python FRIDAY/scripts/phone_ui_agent_adb.py --pair   # type FRIDAY's 6-digit code
   python FRIDAY/scripts/phone_ui_agent_adb.py          # later runs
   ```
   Options: `--adb-connect 192.168.1.20:5555` for Wi-Fi ADB,
   `--adb-serial <id>` when several devices are attached, `--mirror`
   to also launch **scrcpy** (if installed) and watch the phone screen
   on the PC while FRIDAY drives it.
5. Ask FRIDAY: *"Open Settings on my phone and tell me the battery
   level"* — or use `phone_ui_dump` to just read the current screen.

## Safety model (inherited, not reinvented)

* Same pairing as PHONE-001: 6-digit code → per-device token, only the
  SHA-256 hash stored server-side; `FRIDAY_PHONE_ENABLED` kill switch
  applies to every command here.
* `phone_ui_task` is SENSITIVE — it taps/types inside the owner's apps.
* Code-level gates in the planner (the prompt repeats them, code
  enforces them): typing is refused when the focused field is a
  **password field**; instructions asking for **passwords / OTPs / CVVs**
  are refused up front; if the screen belongs to a **banking, payments
  or authenticator** package the task stops before acting; only
  allowlisted actions can execute, and two consecutive unparsable
  planner replies end the task.
* Honest limits: stock `adb input text` drops some non-ASCII characters
  on some devices (the executor's result says so when it happens); the
  agent can only drive the phone while it is attached to the PC over
  ADB — it is not an on-phone agent.

## Pattern references (no code copied)

* **google/artemis** (Apache-2.0) — the observe-hierarchy-then-act
  pattern and the fast reactive loop. ARTEMIS itself requires Python
  3.12; the fleet runs 3.10, so the executor here is stdlib + `adb`.
* **Dinesh210805/aura-android-use** (AGPL-3.0) — second reference for
  the same capability (on-device MCP + accessibility tree). Pattern
  only; no AGPL code is used. Its hard block on banking/payment apps
  informed the planner's package gate.
* **Genymobile/scrcpy** (Apache-2.0) — *adopted* as the optional
  owner-side mirror (`--mirror`); it is an external tool, not vendored.

* **Release pin (TASK-LAP-003, 2026-11-26):** scrcpy **v5.0.1**
  (2026-10-08) — the version the owner installs laptop-side. Do not
  follow "latest" without a fresh check; the pin is recorded here, not
  in code, because scrcpy is an external binary, not a vendored
  dependency.

## Verification status

Implemented + unit-tested with a fake ADB runner, a fake bridge and a
scripted planner (FRIDAY/tests/test_phone_ui_automation.py) — the same
hardware-free harness pattern LAP-001/PHONE-001 used. The owner's phone
is **not yet connected**, so no claim of device verification is made;
the first live proof is the owner pairing the ADB agent and running the
battery-level instruction above.
