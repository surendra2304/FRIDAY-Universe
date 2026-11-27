# TASK-FRD-049 — CHECKPOINT 1: repo survey + voice task-board design

- Task: TASK-FRD-049 — "FRIDAY: voice-drawn on-screen task board" (P3)
- Branch: `musetp7/task-frd-049-voice-task-board`, rebased to main `a3c3140e` (2026-11-27 ~08:01 IST)
- Board on main `a3c3140e`: FRD-049 AVAILABLE / muse_tp7 (claim 2026-11-26 03:01 IST on hub #1483;
  board flip rides the work PR per WATCH136)
- Acceptance (board): "A spoken request draws a persistent task board in a screen corner
  (position and items named by voice, e.g. bottom left with three things) and FRIDAY opens
  sites by voice from it."
- Source: CLASSIFICATION-2026-11-24.md §1 item 9 (watch record DgB9CDDlc4b, @jabirbuilds
  talk-to-Mac Jarvis). The classification doc is coordinator-side, not in the repo;
  the board acceptance above is the spec of record.

## 1. Repo survey (read first-hand, main a3c3140e)

### Render surface — desktop overlay already exists
- `FRIDAY/src/friday/desktop/window.py` (428 lines): `DesktopOverlay` (PyQt6) — frameless,
  always-on-top, translucent glassmorphic, draggable, 340x160 default at (100,100),
  9 visual assistant states, Ctrl+Shift+Space hotkey. This is the surface the board
  renders on; no new windowing system is needed.
- `FRIDAY/src/friday/desktop/app.py` (305 lines): bridges the overlay with `FridayAgent`,
  `GeminiLiveVoiceSession`, and the desktop authorizer. The board plugs in here as a
  second widget beside the orb, fed by a Qt signal.
- `FRIDAY/src/friday/desktop/orb.py` (146 lines): orb states/colours — the board reuses
  the same styling language.
- Gap: **no geometry/state persistence** — no `QSettings` / `saveGeometry` anywhere in
  `FRIDAY/src/friday/desktop/*.py`. "Persistent" therefore needs a state file (see §2).

### Open-sites-by-voice half — already built
- `FRIDAY/src/friday/tools/builtin/open_website.py` (119 lines): `OpenWebsiteTool`
  (`open_website`, `SafetyLevel.SAFE`) — popular-site map (youtube, github, gmail, …)
  plus full URLs, launched via `webbrowser`. Registered in
  `FRIDAY/src/friday/tools/builtin/__init__.py` (import line 150, export line 307).
- FRD-049 reuses it unchanged: board items resolve to a site name or URL and open
  through this tool. No new browser-launch code.

### Voice-tool pattern to follow — FRD-050
- `FRIDAY/src/friday/tools/builtin/location_maps.py`: `LocationMapsTool`, registered the
  same way in `tools/builtin/__init__.py`; tests at
  `FRIDAY/tests/test_voice_place_finder.py` (27 tests). FRD-049 follows this shape
  exactly: new tool module + registration + dedicated test file.
- Voice routing is the agent's normal LLM tool-calling (`FridayAgent`); there is no
  separate intent parser. The tool description carries the "draw a board" phrasing,
  so the voice interface is the tool schema + description.

### Other surfaces considered and not used
- `FRIDAY/src/friday/api/dashboard.html` + `companion_ws.py`: a web dashboard exists,
  but the acceptance says "on-screen" in a "screen corner" — the desktop overlay is
  the matching surface, not a browser tab.
- The source demo is a Mac Jarvis; the repo's real surface is the Windows PyQt6
  overlay. Implementation targets the overlay, not macOS.

## 2. Design

### New tool — `TaskBoardTool` (`FRIDAY/src/friday/tools/builtin/task_board.py`)
- Name `task_board`, `SafetyLevel.SAFE` (draw/show/add/remove/clear are display-only;
  opening a site goes through the already-SAFE `open_website`).
- Parses one spoken request into: `position` (top/bottom x left/right; default
  bottom-left — the acceptance example) + `items` (each: label + site name or URL).
  Actions: `draw` (replace board), `add`, `remove`, `clear`, `hide`/`show`.
- State: JSON file under the FRIDAY data dir (position + items + updated_at), written
  on every mutation and read at overlay startup — this is what makes the board
  persistent across restarts. Notifies the overlay via a Qt signal; the overlay also
  re-reads the file on show, so a stale in-memory board cannot survive a restart.
  Note per repo `AGENTS.md`: this file holds local desktop UI state only (board layout),
  not agent data — it is not a database backend; agent data stays on Oracle.

### New widget — `TaskBoardWidget` (in `FRIDAY/src/friday/desktop/`)
- Frameless corner panel inside `DesktopOverlay`: title row + one row per item
  (label; click opens the site via `OpenWebsiteTool`).
- Position: one of four corners, computed from the primary screen geometry at draw
  time; draggable like the overlay (drag updates the stored position corner).
- Voice: "open <item> from the board" / "open YouTube from my board" resolves the
  label against the persisted items, then calls `open_website`. Unknown label ->
  FRIDAY asks which item (no guessing, no opening a wrong site).

### Tests — `FRIDAY/tests/test_voice_task_board.py`
- Parser: "bottom left with YouTube, GitHub and Gmail", top-right variant, missing
  position (defaults bottom-left), one item, empty items (rejected with a clear
  message), unknown corner words (rejected, not silently remapped).
- Persistence round-trip: draw -> reload from file -> identical board.
- Open-item mapping: label -> site name/URL -> `open_website` target; unknown label
  -> no open call.
- Overlay widget tests headless (Qt offscreen) where the harness allows; otherwise
  parser + persistence + mapping carry the gate.

### Acceptance mapping
- Spoken request draws board in named corner -> `task_board` draw + corner panel.
- Persistent -> JSON state file, reloaded at startup.
- FRIDAY opens sites by voice from it -> label resolution + `open_website`.
- Existing pattern kept: FRIDAY still asks before send/pay/delete actions; opening
  a site stays SAFE, same as `open_website` today.

## 3. What is NOT done yet
- Implementation (tool + widget + registration + tests) — checkpoint 2.
- Work PR (board flip rides it per WATCH136) — after checkpoint 2 + local tests green.
- Live leg: voice session on FRIDAY-Server/desktop drawing the board + screenshot
  evidence. HELD — no live move in this run; owner stop order on server moves still
  in force (WATCH173/174 hold) and no Muse clearance for this leg yet.

## 4. State
- Branch `musetp7/task-frd-049-voice-task-board` at main `a3c3140e` + this checkpoint
  (1 commit). Clean tree. No code changes yet — survey + design only.
- FRD-047: fully handed to Muse 10 (board owner muse_10 on main `a3c3140e`; M10 work
  PR #2046 open, live leg released with reasons). TP7 touches that branch no further.
- Queue: FRD-049 (active) -> FRG-026.
