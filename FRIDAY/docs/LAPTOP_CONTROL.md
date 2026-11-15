# FRIDAY Laptop Control — bridge protocol, pairing, and owner setup

TASK-LAP-001. This document describes the laptop reverse tunnel as it
actually works today: what was already built, what LAP-001 added, how
pairing/auth works, and the exact steps to connect a real computer.

## How it works

The laptop has no public address, so **the laptop dials out** to the cloud
FRIDAY and holds a WebSocket open:

```
laptop_bridge_client.py  --wss-->  FRIDAY /api/laptop/connect/{laptop_id}
FRIDAY tools / HTTP API  --command frames-->  tunnel  --result frames-->  laptop
```

* Server registry: `FRIDAY/src/friday/remote/laptop_bridge.py`
  (`LaptopBridge` — register/unregister, request/response correlation,
  timeouts, evidence records).
* Server routes: `FRIDAY/src/friday/api/server.py` —
  `WS /api/laptop/connect/{laptop_id}`, `GET /api/laptop/devices`,
  `POST /api/laptop/{laptop_id}/command` (both HTTP routes require control
  access; loopback callers on the server itself are keyless by design,
  remote callers must present the control key).
* Client: `FRIDAY/scripts/laptop_bridge_client.py` — a single file; it runs
  standalone (stdlib logging fallback when the repo's `friday` package is
  not importable).
* Agent tools: `FRIDAY/src/friday/tools/builtin/laptop_control.py` —
  `laptop_list_devices`, `laptop_open_app`, `laptop_open_url`,
  `laptop_screenshot`, `laptop_type_text`, `laptop_click`,
  `laptop_run_command`.

## Commands

| Command | Args | What the laptop does |
|---|---|---|
| `system_info` | — | hostname, OS, python, user, cwd (+ psutil extras when installed) |
| `screenshot` | — | saves a PNG **on the laptop** and returns its path (evidence only — FRIDAY cannot see it) |
| `screenshot_data` | `max_width` (320–1920, default 1280) | captures the screen, downscales, JPEG-encodes and returns the image as a result-frame **attachment** so FRIDAY actually receives it |
| `open_url` | `url` | opens an absolute http(s) URL in the default browser |
| `open_app` | `app` | launches an application by name (Windows shell / `open -a` / PATH lookup) |
| `type_text` | `text` (≤4096 chars) | types into the focused window (pyautogui, or xdotool on Linux) |
| `click` | `x`, `y`, `button`, `clicks` | clicks at screen coordinates (pyautogui, or xdotool) |
| `list_files` | `path`, `limit` | directory listing (names, sizes, mtimes) |
| `read_file` | `path` | first 16 KB of a file as text |
| `run_shell` | `command` | shell command — **double-gated**, see below |
| `notify` | `title`, `message` | desktop notification (plyer/win10toast; else logged) |

Protocol rules both sides enforce:

* Command frames: `{type: "command", request_id, laptop_id, command, args, timeout}`.
* Result frames: `{type: "result", request_id, laptop_id, command, started_at,
  finished_at, ok, output, error}` plus an optional `attachment`.
* `output`/`error` are bounded to 16 KB / 2 KB — evidence, not file transport.
* Attachments are the single exception: only `screenshot_data` may carry one,
  only `{kind: "image", format: jpeg|png, base64, width, height}`, capped at
  2,500,000 base64 characters server-side; anything else is dropped and logged.
* Heartbeats: client pings every 20 s; the server answers `pong` and refreshes
  `last_seen`. On connect the server sends a `welcome` frame listing the
  commands and whether shell is enabled server-side.
* `run_shell` is refused unless `FRIDAY_LAPTOP_ALLOW_SHELL=true` is set on
  **both** the FRIDAY host and the laptop. The refusal is explicit on either
  side; nothing degrades silently.

## Pairing / authentication

There is no separate pairing code — **pairing is the shared control key**:

* The tunnel upgrade is authorised by `_laptop_tunnel_authorised`
  (server.py): the laptop presents either
  * the control API key — `X-FRIDAY-Api-Key` header (or `Authorization: Bearer`),
    i.e. the same `FRIDAY_API_KEY` the FRIDAY server is configured with; or
  * a short-lived control token (`fcs1.` HMAC token, 20-minute TTL) minted by
    `GET /api/control/session` — sent as the `token` query parameter
    (`FRIDAY_CONTROL_TOKEN` in the client) because WebSocket clients cannot
    always set headers. This is the client's preferred mode when set.
* If no usable `FRIDAY_API_KEY` is configured server-side, the tunnel is
  rejected (fail-closed, close code 1008). Example/placeholder keys
  (`changeme`, `friday_universe_api`, …) count as unusable.
* Revoking a laptop = rotate `FRIDAY_API_KEY` on the server (all tunnels and
  tokens die with the old key) or simply stop the client on the laptop.

## Owner setup — connect your computer (exact steps)

On the computer you want FRIDAY to control (Windows shown; macOS/Linux
differ only in step 1's installer):

1. **Install Python 3.10+** if it is not already there
   (python.org → check "Add python.exe to PATH"), then in a terminal:
   `pip install websockets pillow pyautogui plyer psutil`
   (websockets + pillow are the minimum; pyautogui enables typing/clicking,
   plyer enables notifications, psutil enriches system info.)
2. **Get the client file**: `FRIDAY/scripts/laptop_bridge_client.py` from
   this repo — one file, copy it anywhere (e.g. `C:\friday\laptop_bridge_client.py`).
   It does not need the rest of the repo.
3. **Set the control key** — the value must match `FRIDAY_API_KEY` in the
   FRIDAY server's environment on Server 1 (it is also recorded in the
   servers' CREDENTIALS.md dossier; do not paste it anywhere else):
   * Windows (Command Prompt, permanent): `setx FRIDAY_API_KEY "<the key>"`
     — then open a **new** terminal so the variable is visible.
   * macOS/Linux: `export FRIDAY_API_KEY="<the key>"`
4. *(Optional)* give the machine a stable name and/or enable shell commands:
   `setx FRIDAY_LAPTOP_ID "my-laptop"` ·
   `setx FRIDAY_LAPTOP_ALLOW_SHELL "true"` (only if you want FRIDAY to run
   shell commands on this machine — it also requires the same flag on the
   server; leave unset otherwise).
5. **Run it**: `python C:\friday\laptop_bridge_client.py`
   You should see `Tunnel open to wss://friday-universe.duckdns.org/friday/api/laptop/connect/<id>`.
   It reconnects automatically if the network drops; leave the window open
   (autostart can be arranged later once the manual run is proven).
6. **Verify**: ask FRIDAY "is my laptop connected?" — or, on the server,
   `GET /api/laptop/devices` will list the laptop as `online: true`. Then
   try "open notepad on my laptop" or "what's on my screen?".

## Status (honest, 2026-11-15)

* The tunnel, registry, HTTP surface and auth above predate LAP-001 and are
  **live in production** — `GET /api/laptop/devices` on Server 1 answers
  `{"devices": []}`: the route works, and **no laptop has ever connected**.
* LAP-001 added `open_app`, `type_text`, `click`, `screenshot_data` (image
  handoff), the seven `laptop_*` agent tools, the standalone-client fallback,
  and this document. The full protocol was proven end-to-end in a sandbox
  (real FRIDAY server app + real client against a virtual display, with
  timings) — see the TASK-LAP-001 board entry for the evidence.
* **Protocol-proven is not owner-computer-connected.** The owner's machine
  connects only after the steps above are run on it; that state will be
  claimed only when `/api/laptop/devices` on the production server shows
  his laptop online.
* Known follow-up (not in LAP-001): the chat "read my screen" fast path in
  server.py still uses the path-only `screenshot` command; it can adopt
  `screenshot_data` now that the handoff exists.
