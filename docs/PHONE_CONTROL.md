# FRIDAY Phone Control (TASK-PHONE-001)

FRIDAY can drive the owner's Android phone — open apps, place calls, send
SMS/WhatsApp, read notifications, set alarms, control media, ring the phone
to find it, and (with the companion app) tap, swipe, type and screenshot.

## How it works

The phone dials **out** to FRIDAY over a secure WebSocket
(`friday/remote/phone_bridge.py`, routes in `friday/api/server.py`). That
direction is the whole design: the phone sits behind carrier NAT and home
routers FRIDAY cannot reach into, but an outbound connection works on any
network, survives Wi-Fi↔mobile-data changes (the agent reconnects with
backoff), and needs no inbound port, no exposed ADB, no third-party relay
and no new accounts. The frame protocol (command / result / heartbeat /
evidence record) mirrors the proven laptop bridge
(`friday/remote/laptop_bridge.py`).

The older ADB controller (`devices/android_controller.py`, `android_*`
tools) still exists for a phone plugged into the machine FRIDAY runs on —
on the cloud server that is never the owner's phone, which is why this
bridge exists.

**Security.** The phone never holds FRIDAY's control secret. Pairing: a
control-authenticated request mints a 6-digit code (10-minute TTL,
single-use, attempt-limited); the phone exchanges it for a device id and
its own token. The server stores only the token's SHA-256 hash (state file
`FRIDAY/.data/phone/bridge_state.json`, override `FRIDAY_PHONE_STATE_FILE`)
and any device can be revoked individually
(`DELETE /api/phone/devices/{id}`). Commands are allowlisted, and each
executor advertises a capability map — the server refuses commands the
connected executor cannot honestly perform. Placing calls and sending
messages are SENSITIVE tools (owner confirmation) in FRIDAY's tool layer.
`FRIDAY_PHONE_ENABLED=false` closes pairing and the tunnel.

**Server cost.** Everything rides inside the existing FRIDAY process — no
new service. One socket, bounded queues, one small JSON state file:
< 5 MB RAM.

## Owner setup — Termux agent (works today, ~4 steps)

1. Install **Termux** and **Termux:API** from **F-Droid** (free; the Play
   Store Termux build is outdated).
2. Open Termux and paste:
   ```
   pkg install -y python && pip install websockets && curl -fsSL https://raw.githubusercontent.com/surendra2304/FRIDAY-Universe/main/FRIDAY/scripts/phone_agent_termux.py -o ~/phone_agent_termux.py
   ```
3. Ask FRIDAY **"pair my phone"**, then in Termux run
   `python ~/phone_agent_termux.py --pair` and type the 6-digit code.
   (Later starts: just `python ~/phone_agent_termux.py`.)
4. Tap **Allow** when Android asks for phone / SMS / notification
   permissions for Termux:API, and exempt Termux from battery optimisation
   (Settings → Apps → Termux → Battery → Unrestricted) so Android does not
   put the connection to sleep.

Then just talk to FRIDAY: "open YouTube on my phone", "call …", "text …
saying …", "read my notifications", "set an alarm for 7", "ring my phone".

### What the Termux agent can and cannot do

| Capability | Termux agent | Companion app |
|---|---|---|
| device status, open app, open URL | ✅ | ✅ |
| make call, send SMS | ✅ | ✅ |
| read notifications | ✅ | ✅ |
| set alarm, media play/pause/stop, volume, find-my-phone ring | ✅ | ✅ |
| send WhatsApp | ⚠️ opens chat prefilled — final Send tap is yours | ✅ sends (accessibility clicks Send) |
| tap, swipe, type text, press Home/Back, screenshot | ❌ Android reserves these for accessibility services | ✅ |
| close app (force-stop) | ❌ needs system permission | ⚠️ background processes only |

Every ❌ is refused by the server with that exact reason — FRIDAY will tell
you, not pretend.

## Owner setup — companion app (full control)

Build per `FRIDAY/android-companion/README.md`, install the APK, pair with
the same 6-digit code flow, then grant once: call+SMS permissions,
Accessibility (for tap/type/screenshot), Notification access, battery
exemption. Tap **Start FRIDAY connection** — it reconnects by itself after
that, including after reboots is *not* claimed (Android requires the app to
be opened once after a reboot before foreground services can start; the
Termux agent has the same constraint).

## API surface

| Route | Auth | Purpose |
|---|---|---|
| `POST /api/phone/pairing-code` | control | mint a pairing code |
| `POST /api/phone/pair` | pairing code | exchange code → device id + token (once) |
| `WS /api/phone/connect/{device_id}` | device token | the tunnel (hello → welcome; command/result; ping/pong) |
| `GET /api/phone/devices` | control | paired phones, online state, capabilities |
| `POST /api/phone/{device_id}/command` | control | dispatch one allowlisted command, returns the evidence record |
| `DELETE /api/phone/devices/{device_id}` | control | revoke a pairing |

## DROIDLAB — gesture shortcuts on Android (TASK-LAP-005)

DroidLab: Gesture Toolkit (Light Source Labs, free on the Play Store,
Android 8.0+) turns phone motion and touch zones into shortcuts:
double-tap the back of the phone (Back Tap), Edge Sense, Notch Touch,
Chop Chop, Quick Twist, multi-finger swipes — plus theme changes and
Quick Settings customisation (source item Dc_PBtEq0YM). Typical owner
use: double-tap the back to toggle the flashlight.

Setup: install, run the Calibration Wizard first — it profiles the
phone's sensors so taps do not misfire — then map one gesture to one
action and test it. It needs the Accessibility Service permission;
Android shows a "danger" warning for this, which is the normal system
prompt for the permission — grant it only to the Play Store build.

Caveats: check whether the phone already has the gesture built in
(Motorola's back-tap, for example) before installing another app.
Gestures can misfire while the phone is in a pocket or bag, so never
map a gesture to anything destructive — no calls, no payments, no
deletes.

## Verification state (2026-11-15)

Proven without hardware: the pytest harness
(`FRIDAY/tests/test_phone_bridge.py`) drives the real bridge through a mock
executor — pairing (single-use codes, hashed-token persistence, revoke),
the full command round trip, capability refusals, offline/timeout/
disconnect honesty, and the sync tool layer hopping threads onto the server
loop. **Not yet proven: a real phone round trip.** That is the owner's
4-step setup above; until his phone completes one, phone control is
"built and mock-verified", not "working on his phone".
