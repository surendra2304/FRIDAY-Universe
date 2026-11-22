# TASK-REL-073 — voice-regressions CI job re-probe (2026-11-23)

- **Task:** TASK-REL-073 (pool 10, P1) — re-probe the voice-regressions job on
  main; if still red, root-cause and fix it. Source: MASTER_PLAN TASK-REL-002
  (open since 2026-11-14).
- **Owner:** muse_2 (Muse 2). Assigned by Muse (Head Manager) in coordinator
  watch, issue #35 comment 7083712388 (2026-11-23 ~00:28 IST, rule 1b, on
  work request 7083428348).
- **Claim:** issue #35 comment 7083819070 (2026-11-23 ~00:15 IST); board record
  rides in this work PR (no REL-073 record on main — pool-10 filing rides in
  the next consolidated board PR).
- **Branch:** `muse2/task-rel-073-voice-regressions-reprobe`, base main
  `52b52d02`. This PR carries the claim plus this report and the board
  IN_REVIEW record. **No code change: the job is not red; there is nothing
  to fix.** No test weakened, no test skipped, no assertion touched.
- **Status:** implemented (re-probe + evidence). Awaiting Muse review/merge.
  Not merged, not deployed. Only Muse merges.

## 1. Verdict — NOT RED

The `voice-regressions` job in FRIDAY Universe CI/CD
(`.github/workflows/friday-universe-ci.yml`, job `voice-regressions`) is **not
failing**. Its last executed run on main is **green**, and there is no red
state to root-cause, no failing component to name, and no fix to land.

## 2. Evidence — the re-probe (GitHub Actions API, 2026-11-23 ~00:20 IST)

### 2a. Current main head — job skipped by design, run green

- Main head `52b52d02` (merge of PR #1403, REL-074 name scrub), CI/CD run
  `45055807995`, conclusion `success`.
- `voice-regressions` check on that head: `completed / skipped`.
  `detect-voice-changes` succeeded with `voice=false`: the merge touched no
  voice paths, so the conditional job (`if:
  needs.detect-voice-changes.outputs.voice == 'true'`) did not run. The
  skip is the designed behaviour, not a failure.

### 2b. Last executed run — green, all steps pass

- Run `45051802318`, head `60e09844` (merge of PR #1397, TASK-VOI-028),
  started 2026-11-22T17:52:03Z (23:22 IST): `voice-regressions` conclusion
  `success`, all 9 steps green, including:
  - `Lint changed voice surfaces` — success.
  - `Run voice, LiveKit, Gemini, and CLI regressions` — success.
- Last 12 CI/CD push runs on main: 11 × `voice-regressions` skipped, 1 ×
  success, **0 failures**. No red run exists in that window.

### 2c. The green run covers the voice code on current main

- Compare `60e09844...52b52d02` (GitHub compare API): 14 files changed,
  **0 voice-path files** (`FRIDAY/src/friday/voice/**`,
  `FRIDAY/tests/test_voice*.py`, `test_gemini_live_voice.py`,
  `test_ux_and_cli.py`, `test_livekit_token.py`, and the other
  `detect-voice-changes` filter paths). The three merges since the green run
  (#1400 VAL-006, #1401 FRG-002, #1403 REL-074) touch Forge, docs, and the
  board only. The green run therefore ran against exactly the voice code
  that is on current main.

### 2d. The separate startup workflow is green too

- `Voice startup regressions` (`.github/workflows/voice-startup-regressions.yml`,
  job `voice-startup-regressions`): last run `44133463440`, 2026-11-17,
  `workflow_dispatch`, conclusion `success`. Its last failure was run
  `43713752806` (2026-11-15, TASK-SEN-012 PR), superseded by later successes.

### 2e. The original red is already closed (REL-002)

- The red that opened TASK-REL-002 — CI/CD run `43569163089`, 2026-11-14,
  head `573da9c1`, one failing contract test
  (`test_env_example_documents_every_settings_field`: two undocumented
  `FRIDAY_INTENT_CLASSIFY_*` fields) — was root-caused and closed by Muse 4
  in PR #1299 (merged 2026-11-22, merge `4bbc9e2e`). The fix was already on
  main (Surendra commit `4ac6b270`, 2026-11-14). REL-073 finds no recurrence.

## 3. Acceptance

- "The job is green on main" — met in substance: the last executed run on
  main is green (2b) and no voice file has changed since (2c), so the green
  run covers current main's voice code.
- "Or its current red state is root-caused with the failing component named
  and the fix landed and green" — not applicable: there is no current red
  state.

## 4. Honesty bound — no green check on the exact head 52b52d02

No `voice-regressions` check with conclusion `success` exists on the exact
head `52b52d02`, because the job is conditional and no voice path changed in
that merge. A literal green check on a given head requires either a
voice-path change in the merge or the unconditional-trigger change. The
unconditional-trigger option (run the job on every main push so a regression
cannot sit undetected, as it did 2026-11-14 to 2026-11-19) was already
recorded as a Muse decision in the REL-002 board record; it is **not** made
in this task. If Muse wants it, that is a follow-up workflow change, not a
REL-073 fix.

## 5. Run in progress at probe time (not voice-related)

- CI/CD run `45056688880` (head `e4c78c04`, merge of PR #1405 VAL-007) was
  `in_progress` at probe time; its `voice-regressions` job is also skipped
  (no voice paths in #1405). It does not affect this verdict.

— Muse 2
