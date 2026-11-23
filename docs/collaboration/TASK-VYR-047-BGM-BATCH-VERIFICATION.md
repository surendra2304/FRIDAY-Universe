# TASK-VYR-047: BGM batch verification — BLOCKED, U2 unreachable — Muse 4

- Task: TASK-VYR-047 (P2). Assigned by Muse (Head Manager) in coordinator
  watch 7105239911 (2026-11-23 ~20:55 IST), as corrected by 7105311681:
  the FRD-038 re-slot to Muse 4 was WITHDRAWN — Muse 4 does NOT claim
  FRD-038. Queue: STR-HLT-002 (blocked head, Spotware gate) -> VYR-047
  (active now) -> OBS-014 live-leg assist (Muse 4 executes the S1 drill
  steps under Muse 8's direction; Muse 8 keeps ownership).
- Claim: successor hub #1483 comment 7105623718 by Muse 4, 2026-11-23
  ~20:58 IST.
- Branch: `muse4/task-vyr-047-bgm-batch-verification` (base main `cfe211cf`).
  Board record: AVAILABLE, owner null on main `f6f1c21e` (board blob
  `67be384d`, 17,163 lines, verified first-hand this run) and re-verified
  unchanged on new main `cfe211cf` (board blob `3c239170`, 17,167 lines)
  at push time — the coordinator merged #1516/#1509/#1511 in between.
  Board PR #1517
  (open, head `864c03e8`) files `owner: muse_4` for VYR-047 as a queue
  filing; this PR flips the record AVAILABLE -> IN_REVIEW with the same
  owner value. If #1517 lands first, this PR's board hunk needs a rebase
  (same record, same owner line).
- Work PR: #1519 (https://github.com/surendra2304/FRIDAY-Universe/pull/1519) — this doc + board flip only. No code
  change: there is no render to verify yet, so nothing to fix.

## Assignment (verbatim scope)

"VyralX: BGM batch verification — the approved BGM batch is present and
audible in the next supervised render; file per-render BGM evidence
(ducked under voice, full in voiceless stretches)". Acceptance: "BGM
evidence filed for the next supervised render."

## The approved BGM batch (established, not assumed)

- Shelf: `VyralX/data/bgm/` on U2, 25 tracks incl. 5 NO LIMITS PHONK
  (`phonk_no-limits-phonk_{reactor,rush,vantage,fastlane,focus}.mp3`),
  stocked 2026-11-21 in TASK-VYR-030 (Muse 1). Record:
  `VyralX/docs/BGM_SHELF.md`. Free use in the project's own videos with
  the credit `Music: NO LIMITS PHONK — https://www.youtube.com/@nolimits_phonk`
  (source page https://nolimitsphonk.com/journal/free-phonk-for-videos/).
- Selection: `VyralX/app/services/viral_bgm.py` — `prepare_music_bed()`
  renders a bed from the library for the video's category; phonk is a
  first-class source category. The bed is recorded per render as
  `bgm_source` on the produce result.
- Mix (code-read from main `f6f1c21e`, `VyralX/app/services/viral_remix.py`,
  `render_scene_timed`): source audio at `volume=0.20`, bed at
  `volume=0.10`, narration at `volume=1.0`, `amix` then
  `loudnorm=I=-14:LRA=9:TP=-1.5`. So "ducked under voice" is by
  construction (bed 0.10 vs voice 1.0) and "full in voiceless stretches"
  means the bed stays at its full 0.10 level where no voice plays — it is
  a fixed mix, not a sidechain duck. The per-render check must measure
  this, not assume it.

## The next supervised render (planned, not run)

- Candidate: VYR-037 pool candidate 1, NASA "Gradient Sun", record
  `1e06e9e0b37a` — the VYR-039 G1 gap ("After merge: pull to U2 and
  re-run candidate 1"). VYR-039 proved the remix produce died at render
  on the then-current U2 code (`ValueError: BGM bed is mandatory`); the
  fix is merged (work PR #1391, merge `a6bd8ac1`, 2026-11-22 22:34 IST).
- Re-run command (VYR-039, unchanged): on U2,
  `run_remix_flow.py produce --record-id 1e06e9e0b37a --script-file
  scripts/remix_scripts/space_sun_facts.txt --title "The Sun Loses 4
  Million Tonnes Every Second" --lane space_science --with-db`.
  Renders held unlisted, loop OFF, uploader paused (supervised-cycle
  orders, VYR-039). The VYR-039 leftover TTS voiceovers
  (`media/voiceovers/remix-1e06e9e0b37a-62fd1b-*`) are transient work
  product from the aborted attempt; the re-run regenerates its own.
- Per-render BGM verification method (to run on the render, once it
  exists): (1) `ffprobe` the render — audio stream present, duration
  matches the picture; (2) read `bgm_source` off the produce result —
  the bed must name a shelf track (a phonk track for this lane if the
  policy selects one); (3) segment the render audio by the narration
  timeline (caption cues / TTS segments): measure RMS/loudness in voiced
  vs voiceless stretches — bed energy must be present in both, and the
  bed's share of mix energy must be higher where no voice plays
  (voice 1.0 absent there; bed still at 0.10); (4) `ffmpeg loudnorm`
  against the -14 LUFS pipeline target; (5) watermark check on frames.
  The render-861 failure this task answers (a render with no BGM) is
  caught by (1)+(2)+(3): no bed track, no `bgm_source`, no bed energy.

## BLOCKER — U2 unreachable (verified first-hand, three times)

No supervised render can be produced while U2 is unreachable: the
produce path is U2 shell only, the merged VYR-039 fix cannot be pulled
to U2 without SSH, and the HTTP API routes (`POST /api/render`,
`POST /api/orchestrator/produce`) require an API key (not fetched — no
secret in chat, no secret hunt) and would run the pre-fix code on U2
anyway. No local run: this VM's clone failed the execution-risk check
in VYR-039, and the shelf, TTS keys and cookies live on U2.

Evidence (all first-hand this run, 2026-11-23):

- ~21:02 IST, from Server 2 via bridge `run_shell`: `ssh -i
  /home/ubuntu/.ssh/aws_lightsail_ed25519 ubuntu@16.176.9.247` ->
  `ssh: connect to host 16.176.9.247 port 22: Connection timed out`.
  Ping from S2: 100% packet loss.
- ~21:06 IST, from Server 1 via bridge `run_shell`: same SSH ->
  connection timed out (S1 has no Lightsail key at that path, but the
  TCP connect itself timed out before auth, so the key is not the cause).
- ~21:07 IST, from Server 2: TCP `:8000` FAIL, `:22` FAIL;
  `curl http://16.176.9.247:8000/health` -> `000` (10s timeout).
  Same from this VM: `/health` and `/ready` -> `000`.
- ~21:11 IST, from Server 2 (re-probe): SSH still connection timed
  out, TCP `:8000` FAIL, `/health` -> `000`. Still down.
- Bridge itself is healthy (calls return in seconds); the failure is
  the S1/S2 -> U2 path, not the bridge.

Coordinator-known: watch 7104470776 (~20:50 IST) and Muse 15's VYR-043
status 7104150168 (~20:05 IST) both record "U2 SSH down from both
Oracle servers (times out) — blocks all U2-side shell work. Coordinator
to chase separately; not a worker task." One change since Muse 15's
report: he recorded "VyralX HTTP service on U2 is up" at ~20:05 IST;
my probes at ~21:07 and ~21:11 IST find HTTP `:8000` (and `:80`)
unreachable too — the outage has deepened, or his check used a
different route. Diagnosis is tracked separately as TASK-OBS-021 (P1,
AVAILABLE, unassigned; drafted ~20:40 IST in board PR #1517) — NOT
claimed here; it is not Muse 4's assignment and the coordinator said
he chases U2 SSH separately.

## Next step (when U2 is back)

1. OBS-021 (or the coordinator's chase) restores U2 access.
2. Pull main to U2 (must include the VYR-039 fix, merge `a6bd8ac1`);
   verify with `git merge-base --is-ancestor a6bd8ac1 HEAD` and the
   `music_bed_path=bed_path` line in `remix_flow.py`.
3. Re-run candidate 1 with the command above (loop OFF, unlisted).
4. Run the §"per-render BGM verification method" checks on the render
   and update this doc with the per-render evidence (bed track,
   `bgm_source`, voiced/voiceless RMS, loudnorm, watermark).
5. File the render's BGM verdict; then the acceptance is met.

## Verification note (stated plainly)

- Board record, assignment, BGM batch definition, fix merge, mix
  levels, and the U2 outage: all verified first-hand this run (GitHub
  API reads of main `f6f1c21e`; bridge `run_shell` probes on S1/S2;
  direct curl from this VM). No render exists, so no BGM gate passed
  or failed — none is claimed. The OBS-014 live-leg assist (queue
  position 3) still awaits Muse 8's direction; nothing was executed
  for it. Nothing uploaded, nothing set public, no loop cycle started,
  no daemon/timer touched, no env change, no secret touched. Stratex
  demo only (no trading in this task).

## States

- Implemented: PARTIAL — pre-flight + verification method + blocked-state
  filing (this doc + board flip); no render produced (blocked)
- Tested: NO — no render exists to verify
- Merged: NO (this PR awaits Muse's review)
- Deployed: NO (nothing to deploy; U2 untouched — unreachable)
- Production-verified: NO (no render; BGM evidence still owed on unblock)

— Muse 4
