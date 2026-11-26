# TASK-FRD-058 — Checkpoint 2 (implementation) — Muse TP6 — 2026-11-26 ~11:xx IST

## Stall repair

- The branch sat at checkpoint 1 (`b67d2dc6`, filed ~10:15 IST) with no
  new commit for ~1 h. This checkpoint repairs the stall: the full
  implementation is filed below.
- Branch maintenance (EARN-023 precedent): main had moved
  `bf41a6c4` → `4127456c` (board PR #1957) → `250cf2b4` (PR #1950).
  The old branch was deleted (204) and recreated at main `250cf2b4`
  (201); checkpoint 1 was re-filed byte-identical (3751 bytes, blob
  `57cdae57`, new commit `e3686224`). The old commit `b67d2dc6` is
  superseded; its content is preserved verbatim in `e3686224`.

## What was built (fresh — nothing from PR #1850's branch)

- `FRIDAY/src/friday/workflows/rsvp.py` — sessions as local JSON under
  `FRIDAY/.data/rsvp/`; `SESSION_DIR` (monkeypatchable), `DEFAULT_WPM`
  300, clamp 60–1200; `extract_article_text` (stdlib parser: prefers
  `<article>`, falls back to `<main>`/`<body>`, drops scripts/styles);
  `create_session` (text or URL), `control_session` (pause/resume/
  set_rate/jump, clamped), `session_progress`, `current_word`,
  `get_session` (full record with words, for the surface).
- `FRIDAY/src/friday/tools/builtin/rsvp_tools.py` — `rsvp_start`,
  `rsvp_control`, `rsvp_status`; exported from `tools.builtin` and
  registered in the live registry (`agent/mixins/tools.py`,
  AUDIT-2 lesson) so voice/chat can actually call them.
- `FRIDAY/src/friday/api/rsvp.html` — reading surface served as
  `/static/rsvp.html`: paste box, URL input, WPM slider, ORP-highlight
  word, pause/resume, ±50 wpm, restart, progress bar.
- `FRIDAY/src/friday/api/server.py` (+75) — `POST /api/rsvp/start`,
  `POST /api/rsvp/control`, `GET /api/rsvp/status/{id}`,
  `GET /api/rsvp/session/{id}`; origin-gated (same tier as owner
  preferences; sessions are local files, no fleet/system effect).
- `FRIDAY/tests/test_ig_frd_058_rsvp.py` — 23 hermetic tests; added to
  the FRIDAY tier-1 invocation in `.github/workflows/friday-universe-ci.yml`
  (REL-068).
- `docs/collaboration/TASK-FRD-058-BUILD-VERIFY.md` — build + verify
  record, including the PR #1850 failure isolation.

## PR #1850 failure, isolated first-hand

- Run 45664458992, job 139382705634, step "Run FRIDAY tier-1 tests":
  13 failed, 237 passed. All 13 failures were `AttributeError` in
  `tests/test_ig_frd_058_rsvp.py`: the test expected `rsvp.SESSION_DIR`
  and `rsvp.extract_article_text`, which that workflow module never
  defined. This module defines both; the tests pin them.

## Verification

- No repo code executed locally (execution-risk flag stands). New
  Python files compile-checked only (`py_compile`); CI is the proof.
- Every file read back via the API after pushing; content matches the
  prepared files (see build-verify doc).
- Work PR follows this checkpoint; board flip (branch + pr) rides in
  the PR (pr number in a follow-up commit after the PR opens).
- Board on main `250cf2b4`: FRD-058 CLAIMED / muse_tp6 (verified
  first-hand); the WATCH141 `next_action` text fix has landed. The
  FRD-058 evidence still carries one wrongly-pasted FRD-059 bullet
  ("Re-slotted to Muse TP7 … PR #1848"); the work PR's board hunk
  removes it and says so.

## Decisions owed to Muse (unchanged from checkpoint 1)

- Live leg (one real article read through the RSVP surface on
  production FRIDAY at two different rates) needs production access.
  Confirm whether it runs as a gated follow-up (VYR-078 bullet-4
  shape: gated, not waived) or under a clearance. Repo leg proceeds
  now; live leg NOT started.

## Next

- Work PR, then CI green, then merge by the coordinator (never my own
  PR). Queue after FRD-058: VYR-087 (AVAILABLE / muse_tp6, P1).

— Muse TP6
