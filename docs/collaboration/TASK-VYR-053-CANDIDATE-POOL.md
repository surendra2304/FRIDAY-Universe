# TASK-VYR-053: Supervised cycle 4 candidate pool — discovery pass — Muse 4

- Task: TASK-VYR-053 (VyralX supervised cycle 4 candidate pool — most-popular
  discovery + machine QA gates). Branch
  `muse4/task-vyr-053-supervised-cycle-4-pool` (claimed 2026-11-24 ~14:26 IST,
  hub comment 7126771362; assignment in coordinator watch 7125702174, run
  scheduled 13:17 IST — "claim VYR-053 now (your head)"; queue STR-HLT-002
  blocked -> VYR-053 -> EARN-005). Board AVAILABLE → CLAIMED flip rides in
  this PR (standing orders).
- Discovery run: 2026-11-24 ~14:29–14:32 IST, on S2 via bridge `run_shell`
  on Server 2 (U2 deleted 2026-11-23; VyralX lives on S2). Loop stays OFF,
  uploader paused, renders held unlisted; no renders in this task — pool
  refresh only.
- Discovery checkpoint posted on hub #1483 as comment 7126771362 (claim;
  this doc + pool filed in the work PR).

## S2 state at discovery time

- `/opt/friday_universe` @ `51084d19`, checked out on
  `muse10/task-rel-088` (tip = main at that commit; main is now `eb69805f` —
  S2 is behind main, parked deliberately; no checkout change made here).
  Working tree: pre-existing untracked scratch only (two more `?? tests/`
  files appeared 14:28–14:35 IST from another worker's activity, not mine).
- `VyralX.service`: active/running, PID 611266 (since 2026-11-23 17:19 IST);
  `/health` 200, `/ready` 200 — on port **8010** (uvicorn
  `--port 8010`), which is why a `:8000` probe returns 000. Not a failure.
- `VyralX-Daemon.service`: inactive (loop OFF, as ordered).
- `yt-dlp` venv 2026.10.21 (`/opt/friday_universe/venv/bin/yt-dlp`; system
  copy same version); cookies `VyralX/data/youtube_cookies.txt` present
  (Nov 24 11:05); ffmpeg/ffprobe 4.4.2 present; deno 2.9.8 system.
- Exclusion sets loaded on S2 this run: `rejected_sources.json` (51 ids) +
  `published_shorts_manifest.json` + `viral_loop_manifest.jsonl` (11) +
  `CpQGaTtppnU` (VYR-037 pool candidate 2) + the 7 VYR-055 pool ids =
  **91 known ids excluded** (VYR-055 counted 84; +7 VYR-055 ids = 91).
- The merged flat-discovery script (`VyralX/scripts/find_viral_candidates_flat.py`,
  VYR-055) is not yet in the S2 checkout, so this run shipped a VYR-053
  variant to that path (same helpers, 6 fresh queries, extended exclusions),
  ran it, and removed it afterwards — S2 tree left as found. Raw per-query
  output saved at `/tmp/vyr053_q{0..5}.json` on S2.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-053-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Ferrofluid skull sculpture test" (YouTube, id `tOlU-Ly1BWk`) | YouTube search, query "mesmerizing ferrofluid art short"; https://youtube.com/shorts/tOlU-Ly1BWk | 34s — PASS (15–60s) | 46,959; uploader Eric Mesple | Licence PENDING; caption-track BLOCKED; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED (see blocker) |
| 2 | "Ferrofluid Art" (YouTube, id `H9IwXr4r3pg`) | Same query | 25s — PASS | 1,208; uploader Frank Marino | Same as #1 |
| 3 | "Ferrofluid Spikes Emerge! 🧲🔄 Liquid Physics Art (4K)" (YouTube, id `8jTv5Mo9vJY`) | Same query | 20s — PASS | 198; uploader DeepSleepVisuAl | Same as #1 |
| 4 | "FerroBeat Turns Sound Into Liquid Art – This Is Unreal" (YouTube, id `vbVT8wfjoWk`) | Same query | 58s — PASS (upper boundary) | 74; uploader Top Crowdfunding Campaigns | Same as #1 |
| 5 | "🧑‍🍳 Tiny Chefs vs. Giant Pizza! 🍕 \| Miniature Cooking in a Big World" (YouTube, id `eQZ-s2JK08I`) | YouTube search, query "epic miniature cooking short"; https://youtube.com/shorts/eQZ-s2JK08I | 46s — PASS | 73; uploader PeppyPods | Same as #1 |
| 6 | "Giant Food Disaster! Miniature Chefs Launch an Epic Rescue Mission!" (YouTube, id `RSu5wD55uag`) | Same query | 58s — PASS (upper boundary) | 22; uploader Tasty Tales | Same as #1 |

Cautions, recorded not recommended: candidates 5–6 look AI-generated
miniature-chef content — audition judges suitability; candidate 4 is 58s
(upper boundary) from a crowdfunding-marketing channel, audition for promo
content; candidate 6 has 22 views (essentially unviewed, last by the
most-popular ranking). Only candidate 1 has real traction (46,959 views).
Candidates are filed by the machine gates only.

## YouTube discovery: 6 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying kinetic sand cutting short" | 10 | 0 | 0 |
| "amazing card trick revealed short" | 10 | 0 | 0 |
| "oddly satisfying slime asmr short" | 10 | 0 | 0 |
| "incredible parkour stunts short" | 10 | 0 | 0 |
| "mesmerizing ferrofluid art short" | 10 | 4 | 4 — `tOlU-Ly1BWk`, `H9IwXr4r3pg`, `8jTv5Mo9vJY`, `vbVT8wfjoWk` |
| "epic miniature cooking short" | 10 | 2 | 2 — `eQZ-s2JK08I`, `RSu5wD55uag` |

All `yt_rc` 0. The four zero-yield queries again surfaced long-form
compilations only (same pattern as VYR-055's three zero-yield queries).
Raw per-query output saved at `/tmp/vyr053_q{0..5}.json` on S2.
Discovery script: the VYR-055 flat-playlist script, VYR-053 variant
(6 fresh queries, +7 VYR-055 ids in `EXTRA_EXCLUDE`); the merged script
itself is unchanged by this task.

## BLOCKER (re-probed this run) — media-level QA gates cannot run: yt-dlp download broken on S2

Re-verified 2026-11-24 ~14:30 IST — same failure VYR-055 documented
~10:40–11:35 IST today, unchanged. This is a pipeline-wide failure, not
a VYR-053 defect.

1. Metadata fetch on a known id (`JxAMNzlUFFE`, VYR-055 pool rank 1) fails
   (rc 1): YouTube's n-challenge cannot be solved — the same deno 2.9.8
   traceback (`a.addOnDisposeCallback is not a function`), followed by
   `n challenge solving failed: Some formats may be missing` and `Some
   web_embedded client https formats have been skipped as they are missing
   a URL. YouTube may have enabled the SABR-only streaming experiment for
   your account` (cf. yt-dlp #12482). End state: `Only images are
   available for download` — zero formats, download impossible.
2. Caption-track via YouTube's timedtext list endpoint: HTTP 200, 0 bytes
   for pool id `tOlU-Ly1BWk` — also blocked, same as VYR-055.
3. No repair attempted this run: VYR-055 already exhausted the repair
   options (node runtime ignored, android/ios/tv/web_safari clients, no
   cookies, deno 2.2.0 side-install — SABR gate, not just the Deno crash;
   in-place downgrade blocked, root-owned binary; yt-dlp already latest
   2026.10.21). Repeating them would not change the outcome.

Consequence for the gates: duration (15–60s) PASS for all 6 candidates;
licence, caption-track count, BGM presence, watermark and loudness are
PENDING/BLOCKED, recorded as such in the pool file — not passed, not
failed. They must run at the supervised cycle once the download path is
repaired. Repair options for the coordinator (no unilateral move made):
fresh YouTube cookie/session, a PO-token provider decision, waiting out
the SABR experiment rollout, or an upstream yt-dlp/Deno fix. VYR-052
(cycle 3) will hit the same wall until one lands.

## What this PR contains

- This doc (`docs/collaboration/TASK-VYR-053-CANDIDATE-POOL.md`).
- `docs/collaboration/TASK-VYR-053-POOL.json`: machine-readable pool.
- `VyralX/tests/test_vyr053_pool.py`: offline pins for the pool file
  (schema, 15–60s gate, most-popular ranking, disjointness from the
  VYR-055 pool and from `CpQGaTtppnU`), wired into the contracts
  workflow list (`owner-workflows.yml`, VyralX step). Stdlib-only, no
  network.
- Board AVAILABLE → IN_REVIEW flip for TASK-VYR-053 (branch + this
  evidence; pr number follows in commit 2).

## Next

1. Repair the S2 YouTube download path (coordinator decision — see
   blocker section).
2. At the supervised cycle: run the four media gates per candidate
   (caption-track count, BGM presence, watermark, loudness) + licence
   check; record pass/fail; render from the top passing candidate, held
   unlisted, loop OFF, uploader paused.
3. Rejections, if any, go in S2 `VyralX/data/rejected_sources.json` as
   before (currently 51 ids).
