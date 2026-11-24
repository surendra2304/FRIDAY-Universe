# TASK-VYR-057: Supervised cycle 4 candidate pool refresh run 2 — discovery pass — Muse 4

- Task: TASK-VYR-057 (VyralX supervised cycle 4 candidate pool refresh run 2 —
  most-popular discovery + machine QA gates). Branch
  `muse4/task-vyr-057-supervised-cycle-4-pool-refresh-2` (claimed 2026-11-24
  ~18:16 IST, hub comment 7131825343; assignment in coordinator watch
  7131647996, run scheduled 17:57 IST — "Claim TASK-VYR-057 NOW as head";
  queue VYR-057 → MEM-028). Board record created in this PR (no TASK-VYR-057
  record on main `ce5c1bd4`, verified first-hand via the git blob API).
- Discovery run: 2026-11-24 ~18:19–18:24 IST, on S2 via bridge `run_shell`
  on Server 2 (U2 deleted 2026-11-23; VyralX lives on S2). Loop stays OFF,
  uploader paused, renders held unlisted; no renders in this task — pool
  refresh only.
- Predecessor context: TASK-STR-063 MERGED this run (#1667, merge `ce5c1bd4`,
  verified first-hand); the 17:57 watch confirms the merge and assigns
  VYR-057 as the new head. TASK-MEM-028 is queue position 2.

## S2 state at discovery time

- `/opt/friday_universe` @ `09603dff` — the VYR-053 merge commit. S2 has moved
  on since VYR-053 (was `51084d19` on `muse10/task-rel-088`); `git branch
  --show-current` prints empty (detached HEAD). Working tree: pre-existing
  untracked scratch only (FRIDAY/.venv-friday-ci/, Memora/.venv-memora-ci/,
  VyralX/light_result_r1.txt, VyralX/light_result_r2.txt, bridge/* from the
  17:47 bridge reliability fix, frd042-out-1214.tgz.b64, opt/,
  pro001_scratch/, tests/test_dispatch_bus_persistence.py,
  tests/test_task_router_persistence.py, tmp/, var/, venv312/) — other
  workers' activity, not mine; left as found.
- `VyralX.service`: active/running; `/health` 200, `/ready` 200 — on port
  **8010** (uvicorn `--port 8010`), which is why a `:8000` probe returns 000.
  Not a failure.
- `VyralX-Daemon.service`: inactive (loop OFF, as ordered).
- `yt-dlp` venv 2026.10.21 (`/opt/friday_universe/venv/bin/yt-dlp`); cookies
  `VyralX/data/youtube_cookies.txt` present (Nov 24 15:10); ffmpeg/ffprobe
  4.4.2 present; deno 2.9.8 system.
- Exclusion sets loaded on S2 this run: `rejected_sources.json` (51 ids) +
  `published_shorts_manifest.json` + `viral_loop_manifest.jsonl` (11) +
  `CpQGaTtppnU` (VYR-037 pool candidate 2) + the 7 VYR-055 pool ids + the 6
  VYR-053 pool ids = **97 known ids excluded**.
- The merged flat-discovery script (`VyralX/scripts/find_viral_candidates_flat.py`,
  VYR-055) IS now in the S2 checkout (arrived with the VYR-053 merge
  `09603dff`). This run shipped a VYR-057 variant to
  `VyralX/scripts/find_viral_candidates_vyr057.py` (same helpers, 6 fresh
  queries, extended exclusions), ran it, and removed it afterwards — S2 tree
  left as found. Raw per-query output saved at `/tmp/vyr057_q{0..5}.json` on S2.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-057-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Ripple - Card Flourish" (YouTube, id `-Cl9AAsXzk8`) | YouTube search, query "incredible cardistry flourishes short"; https://youtube.com/shorts/-Cl9AAsXzk8 | 42s — PASS (15–60s) | 50,114; uploader Kenneth Aidan Foo | Licence PENDING; caption-track BLOCKED; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED (see blocker) |
| 2 | "PAINT MIXING: ODDLY SATISFYING PAINT MIXING COMPILATION" (YouTube, id `-NA0MFteWBE`) | YouTube search, query "oddly satisfying paint mixing short"; https://youtube.com/shorts/-NA0MFteWBE | 57s — PASS (upper boundary) | 7,626; uploader Labedzki-Art | Same as #1 |
| 3 | "Wooden Car Making  \| Satisfying ASMR Wood Carving Transformation #shorts" (YouTube, id `0ZRt4Dw5PAQ`) | YouTube search, query "satisfying wood carving short"; https://youtube.com/shorts/0ZRt4Dw5PAQ | 24s — PASS | 2,953; uploader ai_ki_kavita | Same as #1 |
| 4 | "🪵 From Raw Wood to a Masterpiece! 😍 Satisfying Woodworking ASMR #Shorts" (YouTube, id `f-8OGQHhqq0`) | Same query | 21s — PASS | 27; uploader SatisfyCuts | Same as #1 |

Cautions, recorded not recommended: candidate 2 is 57s (upper boundary) and
its title is an all-caps compilation — audition for promo/compilation
content; candidate 3's uploader handle suggests AI-generated content —
audition judges suitability; candidate 4 has 27 views (essentially
unviewed, last by the most-popular ranking). Only candidate 1 has real
traction (50,114 views). Candidates are filed by the machine gates only.

## YouTube discovery: 4 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "mesmerizing resin art short" | 10 | 0 | 0 |
| "satisfying glass blowing short" | 10 | 0 | 0 |
| "incredible cardistry flourishes short" | 10 | 1 | 1 — `-Cl9AAsXzk8` |
| "oddly satisfying paint mixing short" | 10 | 1 | 1 — `-NA0MFteWBE` |
| "amazing miniature world building short" | 10 | 0 | 0 |
| "satisfying wood carving short" | 10 | 2 | 2 — `0ZRt4Dw5PAQ`, `f-8OGQHhqq0` |

All `yt_rc` 0. The three zero-yield queries again surfaced long-form
compilations only (same pattern as VYR-053's four zero-yield queries and
VYR-055's three). Raw per-query output saved at `/tmp/vyr057_q{0..5}.json`
on S2. Discovery script: the VYR-055 flat-playlist script, VYR-057 variant
(6 fresh queries, +6 VYR-053 ids in `EXTRA_EXCLUDE`); the merged script
itself is unchanged by this task.

## BLOCKER (re-probed this run) — media-level QA gates cannot run: yt-dlp download broken on S2

Re-verified 2026-11-24 ~18:25 IST — same failure VYR-053 documented
~14:30 IST today and VYR-055 documented ~10:40–11:35 IST, unchanged. This
is a pipeline-wide failure, not a VYR-057 defect.

1. Metadata fetch on a known id (`JxAMNzlUFFE`, VYR-055 pool rank 1) fails
   (rc 1): YouTube's n-challenge cannot be solved — the same deno 2.9.8
   traceback (`a.addOnDisposeCallback is not a function`), followed by
   `n challenge solving failed: Some formats may be missing` and `Some
   web_embedded client https formats have been skipped as they are missing
   a URL. YouTube may have enabled the SABR-only streaming experiment for
   your account` (cf. yt-dlp #12482). End state: `Only images are
   available for download` + `Requested format is not available`.
2. No repair attempted by this run: the fix is TASK-VYR-056, assigned to
   Muse 18 in the 17:17 watch and nudged to claim NOW in the 17:57 watch
   (comment 7131647996). The QA leg of VYR-057 waits on VYR-056; the
   discovery leg proceeds now, per the queue note.

## States

- Implemented YES (discovery + pool + evidence + test + board record filed;
  work PR open) / tested YES (offline pool test, 9/9 green locally — see
  below) / merged NO (awaiting Muse's merge) / deployed N/A /
  production-verified PARTIAL (pool filed; media QA gates + render await
  the VYR-056 download-path repair).
- Offline test `VyralX/tests/test_vyr057_pool.py` (9 tests, stdlib + pytest,
  no network): pool schema, 15–60s gate, most-popular ranking, disjointness
  from the VYR-055 pool (7 ids), the VYR-053 pool (6 ids) and the VYR-037
  candidate 2 id. Run locally before filing: 8/8 green.
- Queue after VYR-057: STR-HLT-002 (blocked head) → VYR-057 (working head)
  → MEM-028 (position 2).
