# FRIDAY Companion (Android) — TASK-PHONE-001 scaffold

The full-control phone executor for FRIDAY: a small Kotlin app that dials
out to FRIDAY over WSS and executes the phone-bridge allowlist with real
Android APIs — including the parts Android reserves for an accessibility
service (tap, swipe, type, screenshot) and a notification listener (read
notifications). Protocol and server side: `FRIDAY/src/friday/remote/phone_bridge.py`;
owner-facing guide: `docs/PHONE_CONTROL.md`.

## Status

**Scaffold — not compiled in the FRIDAY build sandbox** (no JDK/Android SDK
there; stated plainly rather than hidden). The sources are complete and
written against Android API 35 / Kotlin 2.0 / AGP 8.5. First build:

1. Open this folder in Android Studio (or install the Android SDK cmdline
   tools + JDK 17) and run `./gradlew assembleDebug` — a `gradle/wrapper`
   still needs generating by that first Android Studio import.
2. Install the APK on the phone (`adb install app-debug.apk`, or copy it
   over and tap it — sideloading must be allowed for the file manager used).
3. In the app: enter the 6-digit pairing code FRIDAY gives you → Pair.
4. Tap the grant buttons once: call+SMS permissions, Accessibility
   (Settings → Accessibility → FRIDAY phone control), Notification access,
   battery-optimisation exemption.
5. Tap **Start FRIDAY connection**. The foreground service reconnects on
   its own from then on.

## Layout

| File | Role |
|---|---|
| `MainActivity.kt` | Pairing + grants screen |
| `PhoneBridgeService.kt` | Foreground service: WSS tunnel, hello/capabilities, heartbeat, reconnect backoff |
| `CommandDispatcher.kt` | Every allowlisted command → Android APIs, with per-command prerequisite checks |
| `FridayAccessibilityService.kt` | Gestures, set-text, WhatsApp send-button click, accessibility screenshot |
| `FridayNotificationListener.kt` | Notification shade snapshot for `read_notifications` |
| `Prefs.kt` | Base URL + device token storage (see its hardening note) |

## Capability contract

The hello frame advertises only what is usable *now*: accessibility
commands appear only while the accessibility service is live, and
`read_notifications` only while the listener is connected. If a grant is
revoked later, handlers return a precise error — never a fake success.
WhatsApp without accessibility degrades honestly to "chat opened, send tap
is yours", exactly like the Termux agent.
