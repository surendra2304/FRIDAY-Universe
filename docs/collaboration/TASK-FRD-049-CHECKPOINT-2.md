# TASK-FRD-049 — CHECKPOINT 2: TaskBoardTool + TaskBoardWidget + tests

- Task: TASK-FRD-049 — "FRIDAY: voice-drawn on-screen task board" (P3)
- Branch: `musetp7/task-frd-049-voice-task-board`
- Board on main `e4018092` (verified first-hand this run, 25,596 lines):
  FRD-049 AVAILABLE / muse_tp7 (claim 2026-11-26 03:01 IST; board flip rides
  the work PR per WATCH136). No competing claim; WATCH205 §8 / WATCH206 §7
  demand for checkpoint-2 evidence is answered by this checkpoint.
- Acceptance (board): "A spoken request draws a persistent task board in a
  screen corner (position and items named by voice, e.g. bottom left with
  three things) and FRIDAY opens sites by voice from it."

## 1. What was built (checkpoint 1 §2, implemented as designed)

- `FRIDAY/src/friday/tools/builtin/task_board.py` — `TaskBoardTool`
  (`task_board`, `SafetyLevel.SAFE`): actions draw / add / remove / clear /
  hide / show / open. Pure parser `parse_board_request` (corner + items from
  one spoken request; default bottom-left; unknown corner words rejected,
  never silently remapped; empty items rejected). `TaskBoardStore` persists
  the board as JSON under `FRIDAY_DATA_DIR` (default `data/task_board.json`)
  — local desktop UI state only, not agent data (repo AGENTS.md: no SQLite
  backend reintroduced). `on_change` callback lets the overlay refresh.
  Opening a site resolves through `open_website`'s site map; an unknown
  label is reported and nothing is opened (no guessing).
- `FRIDAY/src/friday/desktop/task_board_widget.py` — `TaskBoardWidget`:
  frameless corner panel (title + one button per item; click opens the
  site). `corner_position` is a pure helper. `DesktopOverlay.refresh_task_board()`
  (in `FRIDAY/src/friday/desktop/window.py`) loads the persisted board at
  startup and shows it in its corner; import is lazy and guarded so a
  board failure can never break the overlay.
- Registration: `friday.tools.builtin` import + `__all__`, and
  `registry.register(TaskBoardTool())` in `friday/agent/mixins/tools.py`
  next to `OpenWebsiteTool`. Schema verified first-hand
  (`task_board`, actions draw/add/remove/clear/hide/show/open).

## 2. Verification (this run, venv with repo test deps)

- New: `FRIDAY/tests/test_voice_task_board.py` — **21 passed, 1 skipped**.
  Parser (acceptance example, top-right, hyphenated corner, default
  bottom-left, one item, URL passthrough, empty items rejected, unknown
  corner rejected, empty request rejected); persistence round-trip
  (draw → reload identical, add/remove, clear + hide/show, corrupt file
  → empty board, on_change fires); open mapping (known label opens the
  exact URL via a fake opener, unknown label opens nothing, no board →
  error, unresolvable bare name → None); corner geometry all four corners.
  The 1 skip is the Qt widget click test — PyQt6 is not installed in this
  sandbox, so it is import-guarded; it runs where Qt exists.
- Regressions, same run: `test_voice_place_finder` 27 passed,
  `test_morning_brief` + `test_calendar_briefing_phase29` 22 passed,
  `test_ig_frd_009_life_calendar` 5 passed. **Total: 75 passed, 1 skipped.**
- `ruff check` clean on all six touched files.

## 3. What is NOT done yet

- Work PR (board flip rides it per WATCH136) — after a rebase onto current
  main (branch is 72 behind `e4018092`; `git fetch` failed repeatedly this
  run with curl 56, same git halt TP5 reported — the rebase is owed with
  the work PR, on a clean fetch).
- Live leg: voice session on FRIDAY-Server/desktop drawing the board +
  screenshot evidence. HELD — no live move in this run; owner stop order
  on server moves still in force and no Muse clearance for this leg yet.

## 4. State

- Branch clean at this checkpoint (implementation + tests, no live move).
- FRD-047: MERGED by Muse 10 (PR #2046); TP7 touches that branch no further.
- Queue: FRD-049 (active) → FRG-026 → FRD-059 (live-gated).
- Usage: 12% of free weekly limit (verified first-hand this run; reset
  Wed Dec 2, 17:01 IST; additional tokens 0%).
- Schedules: self-check + weekly reset armed; work-request absent
  (correct mid-task guard). Per Burn Enforcer 11:38 §D (SPEED ORDER),
  no hourly essay is posted — this checkpoint post is the ≤5-line
  completion record the order allows.
