# TASK-FRD-058 — Build & Verify — Muse TP6 — 2026-11-26 ~11:xx IST

## What was built (fresh implementation, branch `musetp6/task-frd-058-rsvp-reader`)

RSVP speed-reading aid: paste text or an article URL → FRIDAY presents
it word by word at an adjustable rate, with pause/resume and rate control
by voice or chat. Nothing is taken from superseded PR #1850's branch;
every file below is written fresh on this branch (same shape as the
FRD-057 precedent: workflow + tools + tests + CI tier-1 line).

| File | Change |
|---|---|
| `FRIDAY/src/friday/workflows/rsvp.py` | New. Sessions, `SESSION_DIR`, `extract_article_text`, `create_session`, `control_session`, `session_progress`, `current_word`, `get_session`. |
| `FRIDAY/src/friday/tools/builtin/rsvp_tools.py` | New. `RsvpStartTool` (`rsvp_start`), `RsvpControlTool` (`rsvp_control`), `RsvpStatusTool` (`rsvp_status`). |
| `FRIDAY/src/friday/api/rsvp.html` | New. Reading surface (served as `/static/rsvp.html`): paste box, URL input, WPM slider 60–1200, ORP-highlighted word, pause/resume, ±50 wpm, restart, progress bar. |
| `FRIDAY/src/friday/api/server.py` | +75 lines. `POST /api/rsvp/start`, `POST /api/rsvp/control`, `GET /api/rsvp/status/{id}`, `GET /api/rsvp/session/{id}` — all origin-gated (same tier as owner preferences; sessions are local JSON, no fleet/system effect). |
| `FRIDAY/src/friday/tools/builtin/__init__.py` | Export the three tools (import + `__all__`). |
| `FRIDAY/src/friday/agent/mixins/tools.py` | Register the three tools in `_create_default_registry` (AUDIT-2 lesson: export-only is not implemented). |
| `FRIDAY/tests/test_ig_frd_058_rsvp.py` | New. 23 hermetic tests  (see below). |
| `.github/workflows/friday-universe-ci.yml` | FRIDAY tier-1: `tests/test_ig_frd_058_rsvp.py` rides in the invocation (REL-068). |
| `docs/collaboration/WORK_BOARD.yaml` | FRD-058 record: branch + pr fields set (follow-up commit after the PR opens). |

## Why PR #1850 failed (isolated first-hand, not guessed)

PR #1850 (Muse TP9, superseded by WATCH129) failed its `test` job:
13 failed, 237 passed (run 45664458992, job 139382705634, step "Run
FRIDAY tier-1 tests"). All 13 failures were in
`tests/test_ig_frd_058_rsvp.py`, all `AttributeError`: the test file
expected `rsvp.SESSION_DIR` (fixture, line 29) and
`rsvp.extract_article_text` (line 111), and the workflow module defined
neither. Everything else in the job passed. This branch's module defines
exactly that API surface, and the tests below pin it — the same failure
cannot recur from a missing attribute.

## Tests (`FRIDAY/tests/test_ig_frd_058_rsvp.py`, 21 tests, all hermetic)

- Sessions: defaults (300 wpm, position 0, file saved), wpm clamped to
  60–1200, empty text honest error, URL fetch failure honest error, URL
  uses the extractor (article only — nav/footer/script excluded), URL
  with no visible text honest error.
- Extraction: prefers `<article>`, falls back to `<main>` then `<body>`,
  drops scripts/styles.
- Control: pause/resume/rate/jump, clamps on rate and position, unknown
  session/action/missing value honest errors.
- Progress/current word: percent math, unknown session honest error,
  end-of-text honest error, `get_session` returns the word list.
- Tools: real workflow path under a tmp `SESSION_DIR` (create + control
  + status), honest errors, package export, live-registry register lines
  pinned (source-level: the full registry build needs the production
  agent import chain, which the tier-1 venv does not guarantee).

## Verify

- **No repo code was executed locally** (execution-risk flag stands).
  New Python files were compile-checked only (`py_compile` — parses,
  never imports or runs). CI is the proof: the work PR's `test` job
  runs this file in the FRIDAY tier-1 invocation.
- Read-back: every file above was read back via the API after pushing
  and matches the prepared content (shas in checkpoint 2).
- Board flip (branch + pr) rides in the work PR; live leg (one real
  article read on production FRIDAY at two rates) is NOT done here —
  gated, clearance owed (see checkpoint 2).

— Muse TP6
