# TASK-VYR-039: Supervised cycle from the VYR-037 candidate pool — Muse 4

- Task: TASK-VYR-039 (pool 9, P1). Assigned by Muse (Head Manager) in
  coordinator watch comment 7081283011 (2026-11-22 ~20:54 IST), answering
  work requests 7080911507 (20:24 IST) and 7081109115 (20:39 IST).
- Claim: issue #35 comment 7081315028 (2026-11-22 ~20:56 IST).
- Branch: `muse4/task-vyr-039-supervised-cycle` (base main `fc845c54`).
  Board record: not yet on main — rides in tomorrow's first consolidated
  board PR per the assigning watch; no duplicate record filed here.
- Work PR: (to be filled on open) — fix + regression test + this doc.
  No board edit in this PR.

## Assignment (verbatim scope)

Execute one supervised cycle from the VYR-037 candidate pool with machine
QA gates (caption-track count, BGM presence, watermark, loudness); renders
held unlisted, loop OFF, uploader paused. The VYR-037 pool is in Muse 5's
PR #1387 — work from that branch's pool.

## Pre-flight (U2 live, 2026-11-22 ~21:05–21:15 IST)

Host verified as FRIDAY-Universe-2 (`ubuntu@16.176.9.247`, Lightsail key,
via bridge `run_shell` on Server 2 — the same path Muse 5 used for
VYR-037, issue #35 comment 7065339584):

- Host `VyralXServer`, load 0.02; repo `/opt/friday_universe` @ `03378ba4`
  on main (matches the VYR-037 doc).
- `vyralx` / `vyralx-daemon` / `vyralx-autopilot` all inactive;
  `vyralx-autopilot.timer` not found/disabled; only the unrelated
  `vyralx-metrics-sync.timer` fires. Loop OFF as ordered.
- `/health` 200, `/ready` 200 (Oracle DB connected, ffmpeg true).
- Loop state: 11 cycles completed, last cycle 2026-11-21T01:27:06Z,
  held publish job 861 — matches the VYR-037 doc exactly.
- BGM shelf: 25 tracks incl. 5 phonk (`phonk_no-limits-phonk_*`).
  YouTube cookies fresh (`data/youtube_cookies.txt`, Nov 22 13:58).
- `AUTONOMOUS_PUBLISH_PRIVACY=unlisted`. `YOUTUBE_UPLOAD_ENABLED=true`
  (noted by Muse 5; left untouched — nothing in this task uploads).

## The cycle — both pool candidates attempted, no render

### Candidate 1 — NASA "Gradient Sun" (record `1e06e9e0b37a`): BLOCKED by a code defect

- Pool gates resolved live: licence public-domain / CC0 (PASS, on file);
  media reachable; source probed 153.0s 640x360; audition
  `has_speech=False, speech=0.0s` (no source narration — PASS).
- Produce: `run_remix_flow.py produce --record-id 1e06e9e0b37a
  --script-file scripts/remix_scripts/space_sun_facts.txt --title "The Sun
  Loses 4 Million Tonnes Every Second" --lane space_science --with-db`
  (U2 PID 132221, 2026-11-22 ~21:17 IST). TTS narration built (45.48s,
  files `media/voiceovers/remix-1e06e9e0b37a-62fd1b-*`), caption cues
  built — then the render step raised before any encode:
  `ValueError: BGM bed is mandatory: music_bed_path must be a real audio
  file, not None` (`viral_remix.render_scene_timed` ->
  `_require_music_bed`). Log: `/tmp/vyr039_cycle1.log` on U2.
- No queue entry, no render file, no publish job from this attempt.

**Root cause (G1, this PR fixes it):** PR #1186 (TASK-VYR-032) made the
bed mandatory in `render_scene_timed` but never updated its remix
caller. `produce_remix_short` (`VyralX/app/services/remix_flow.py`)
calls `render_scene_timed(...)` with no `music_bed_path`, so EVERY remix
produce on current main dies at render. PR #1186 touched
`viral_remix.py`, `viral_framing.py`, `scene_analysis.py` — not
`remix_flow.py`. The last successful remix renders are Nov 15, pre-fix.
The framed/commentary paths are unaffected (both prepare a bed).

**Fix (in this PR):** `produce_remix_short` now prepares a bed exactly
like `produce_viral_short` — `prepare_music_bed(media/voiceovers/
<project_key>-bed.wav, tracks["total_seconds"], category=category)` when
`viral_music_bed_enabled`, passes `music_bed_path=bed_path` to
`render_scene_timed`, and records `bgm_source` on the result. With the
bed disabled it still fails closed (None reaches the real gate).
Regression test: `VyralX/tests/test_vyr039_remix_music_bed.py` (2 tests;
added to the contracts list in `.github/workflows/owner-workflows.yml`).
**Not deployed:** the fix is unmerged code — it was NOT hotfixed onto
U2 (deploy discipline: U2 runs merged main only). Candidate 1 can be
re-run after this PR merges and the fix is pulled to U2.

### Candidate 2 — YouTube `CpQGaTtppnU` (23s trickshot tutorial): auditioned, gated out

- Metadata verified live via yt-dlp: "Mw2 Newest TrickShot The Barrel
  Roll - Tutorial", channel `Julius "ichHero" K`, 23s, 1,310 views,
  licence null (= YouTube standard licence; no CC claim). Licence gate:
  standard licence — the viral path's operator-attested transformative
  commentary basis applies; no licence block. The pool doc's caution
  (2011 footage, gaming tutorial) stands as recorded.
- Routing audition (loop's own two-pass rule): pass1 no speech
  (0.0s); pass2 speech 2.0s / 2 cues → `disagreement_treated_voiced`
  → framed route.
- Framed path re-auditions with default params and finds no narration:
  `SKIPPED, reason source_has_no_narration` (14.9s wall). The 2s pass2
  blip does not survive the framed path's own detection — the candidate
  is effectively silent, routed voiced on a disagreement, and refused
  by the voiced path. This is the pipeline failing closed as designed
  (cycle 11 skipped one candidate the same way). Log:
  `/tmp/vyr039_cycle2.log` on U2; driver `/tmp/vyr039_candidate2.py`.
- No render, no publish job, no vision spend beyond the two Whisper
  passes (vision budget today: Groq 0 / Gemini 0 at run time; no vision
  call was reached).

## Machine QA gates — not runnable: no render exists

The four assigned gates (caption-track count, BGM presence, watermark,
loudness) are checks on a finished render. Neither candidate produced
one, so no gate passed or failed — the gates are NOT claimed. (For the
record: the intended checks were ffprobe stream/cue count, bed-audio
energy in the render, frame inspection for watermarks, and ffmpeg
loudnorm against the -14 LUFS pipeline target.)

## U2 state after the cycle (verified 2026-11-22 ~22:00 IST)

- Remix queue still 2 lines; no new render files; no new publish job;
  loop state unchanged (11 cycles, last 2026-11-21T01:27:06Z);
  manifest tail unchanged (cycle 11, job 861 HELD); units still
  inactive. Only new files are candidate 1's TTS voiceover wavs
  (`media/voiceovers/remix-1e06e9e0b37a-62fd1b-*`, 15:46 UTC) — transient
  work product from the aborted attempt.
- Nothing uploaded, nothing set public, no loop cycle started, no
  daemon/timer touched, no env change, no secret touched. Stratex demo
  only (no trading in this task).

## Gaps

- **G1 (fixed in this PR, merge + deploy owed):** remix path never
  supplied the mandatory BGM bed — `produce_remix_short` dies at render
  on current main. After merge: pull to U2 and re-run candidate 1.
- **G2:** candidate 2's 2s routing disagreement (pass2-only speech) is a
  known detector-marginal case; no action — the fail-closed routing
  worked. If the pool grows, prefer candidates whose narration verdict
  is unambiguous across both passes.
- **G3:** the VYR-037 pool doc's "record pass/fail here" item is answered
  by this doc, not by editing Muse 5's open PR #1387.

## Verification note (stated plainly)

- Live cycle attempts: verified on U2 (logs + state files above).
- Fix + test: authored this run from the live failure; **local pytest
  was NOT run** — the repo clone on this VM failed an execution-risk
  check, so no repo code was executed locally (no pytest, no git in the
  clone). CI on this PR is the verification owed for the fix and the
  new test; the PR body says so. The test follows the VYR-032 stub
  pattern and fails on pristine base code by construction (renderer
  receives `music_bed_path=None`).

## States

- Implemented: YES (fix + regression test + this evidence doc, in this PR)
- Tested: PARTIAL — live cycle attempts verified on U2; fix/test NOT
  locally run (blocked, see above); CI owed
- Merged: NO (this PR awaits Muse's review)
- Deployed: NO (fix unmerged; U2 untouched)
- Production-verified: NO (no render produced this cycle)

— Muse 4
