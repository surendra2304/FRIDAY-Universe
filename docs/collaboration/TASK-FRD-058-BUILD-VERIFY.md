# TASK-FRD-058 — BUILD VERIFY: RSVP speed-reading aid

**Task:** FRIDAY: RSVP speed-reading aid — word-by-word reader for pasted text and articles.
**Source:** friday package F-17 (item DcmUG0vNBEK). **Priority:** P3. **Worker:** Muse TP9.
**Claim:** hub #1483 comment 7164541771 (2026-11-25 ~19:52 IST). **Branch:** `musetp9/task-frd-058`.
**Merge-base:** main `3b8c03075464ddfb7fe7478a6d832e4217b7170b`.

## Five states

| State | Value | Evidence |
|---|---|---|
| Implemented | YES | Workflow + reading surface + API routes + tools, all on branch (see below) |
| Tested | PARTIAL | 15 hermetic tests written, collected in FRIDAY tier-1 (REL-068); CI verdict pending on this PR |
| Merged | NO | PR open, awaiting peer merge |
| Deployed | NO | Needs merge + deploy to FRIDAY-Server |
| Production-verified | NO | Done = one real article read through the RSVP surface on production FRIDAY at two different rates |

## Baseline (read first-hand, 2026-11-25)

No RSVP / speed-reading baseline exists in FRIDAY: code search for
`rsvp`, `wpm`, `speed-read` returns ~0 real hits (`FRIDAY/src/friday/core/readings.py`
is about measured-vs-invented numbers, unrelated). FRIDAY's Next.js UI
(`FRIDAY/ui/app/`) is a static export mounted at `/` and cannot be rebuilt
here; the API server mounts **its own directory `FRIDAY/src/friday/api/` as
`/static`** (server.py, `_API_STATIC_DIR = Path(__file__).parent`) and that
directory holds the live HTML/JS surfaces (index.html, dashboard.html,
voice_system.js) — so the RSVP page goes there as `rsvp.html`, served at
`/static/rsvp.html`. API route patterns: FastAPI routes in server.py with
`/api/...` + `/v1/...` dual registration common; `_require_control_access`
gates state-changing routes; read-only GETs are ungated.

## What was built

- **Workflow `FRIDAY/src/friday/workflows/rsvp.py`** — sessions as local
  JSON files under `FRIDAY/.data/rsvp/sessions/<id>.json` (words, wpm,
  paused, position, title, created_at). `create_session` (pasted text or
  article URL — URL fetched, readable text extracted by stripping
  script/style/nav/header/footer/aside + tags, prefers `<article>`/`<main>`;
  honest errors on empty text / fetch failure / empty extraction),
  `control_session` (wpm/paused/position, only given fields change),
  `session_progress`, `current_word`, `tokenize`. WPM default 250, clamped
  50–1000. No send/apply path by design — a reader only.
- **Reading surface `FRIDAY/src/friday/api/rsvp.html`** — served at
  `/static/rsvp.html`. Word-by-word display with ORP pivot-letter
  highlight, progress bar, Pause/Resume, ±50 WPM buttons, WPM slider
  (50–1000), Restart, paste form when no session, keyboard Space/arrows.
  Polls session state every 1s so voice/chat pause/rate changes apply live.
- **API routes in `FRIDAY/src/friday/api/server.py`** — POST
  `/api/rsvp/session` (create, control-gated), GET
  `/api/rsvp/session/{id}` (read-only, returns words + state for the page),
  POST `/api/rsvp/session/{id}/control` (control-gated). Request models
  `RSVPCreateRequest` / `RSVPControlRequest` sit next to
  `VoiceSpeakRequest`.
- **Tools `FRIDAY/src/friday/tools/builtin/rsvp_tools.py`** —
  `create_rsvp_session` (SENSITIVE — fetches URLs; returns the
  reading-surface link, word count and rate), `control_rsvp_session`
  (SAFE — pause/resume, rate, jump). Registered in
  `friday/tools/builtin/__init__.py`.
- **Tests `FRIDAY/tests/test_ig_frd_058_rsvp.py`** — 15 hermetic tests
  (tokenise, extract, create/control/progress, clamping, honest failures,
  both tools; session store pointed at a scratch dir per test, no network).
  Collected in FRIDAY tier-1 in `.github/workflows/friday-universe-ci.yml`
  (REL-068 — the file was previously uncollected by construction).

## What is NOT done (Done blockers)

Done = **one real article read through the RSVP surface on production
FRIDAY at two different rates**. That needs: (1) this PR merged, (2) deploy
to FRIDAY-Server, (3) one real article opened on `/static/rsvp.html` and
read at two rates (e.g. 250 and 400 WPM) with pause/resume exercised live.
No deploy has happened; nothing here claims otherwise.

## Verification notes

- Code diagnosed by READING only (execution-risk restriction on the local
  clone: no git/package commands, no running repo code). PR CI is the test
  runner.
- The roster validator will fail on this PR until roster PR #1843 merges
  (board owner `muse_tp9` not yet a registered collaborator) — expected
  sequencing, same as PRs #1848/#1849.
- Mobile viewport was not tested in this worker (no mobile viewport in
  tooling); the page is a single-column layout with large touch targets,
  but live mobile proof is owed at production verification.
