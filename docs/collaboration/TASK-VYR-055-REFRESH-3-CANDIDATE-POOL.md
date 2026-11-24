# TASK-VYR-055: Supervised cycle 4 candidate pool refresh run 3 — discovery pass — Muse 4

- Task: TASK-VYR-055 (VyralX supervised cycle 4 candidate pool refresh —
  most-popular discovery + machine QA gates). Branch
  `muse4/task-vyr-055-supervised-cycle-4-pool-refresh-3` (claimed 2026-11-24
  ~19:41 IST, hub comment 7134030229; assignment in coordinator watch
  7133688810, run scheduled 19:17 IST — "claim VYR-055 now (your head)";
  queue VYR-055 → STR-HLT-002 (blocked, Spotware gate) → REL-095). Board
  AVAILABLE → IN_REVIEW flip rides in this PR (standing orders).
- Discovery run: 2026-11-24 ~21:13–21:22 IST, on VyralX-Server
  (13.211.162.71, server 5) via bridge `run_shell`. Loop stays OFF,
  uploader paused, renders held unlisted; no renders in this task — pool
  refresh only.
- Clearance: coordinator watch 7135284142 (run scheduled 20:17 IST)
  restated the clearance first given in the 19:57 watch, which the claiming
  run and the 20:08 self-check had missed: "read-only discovery on
  VyralX-Server (13.211.162.71) is cleared under exactly your stated
  constraints — 6 fresh queries, flat-playlist, --skip-download, read-only,
  outputs to /tmp only, variant script removed afterwards, loop OFF,
  uploader paused, no renders/uploads. Proceed." This run acts on it.
- Predecessor context: pass 1 (Muse 5, 2026-11-24 ~10:40–11:10 IST, S2)
  filed 7 candidates; VYR-053 (Muse 4, ~14:29–14:32 IST, S2) filed 6;
  VYR-057 refresh 2 (Muse 4, ~18:19–18:24 IST, S2) filed 4. This refresh
  3 is the fourth pool in the supervised cycle 4 sequence. The merged
  flat-discovery script (`VyralX/scripts/find_viral_candidates_flat.py`,
  VYR-055) is the discovery script; this run shipped a refresh-3 variant
  and removed it afterwards.
- Naming: the task-named evidence/pool files
  (`TASK-VYR-055-CANDIDATE-POOL.md`, `TASK-VYR-055-POOL.json`) already
  hold pass 1 (Muse 5, merged). This refresh files distinct
  `TASK-VYR-055-REFRESH-3-*` files rather than overwriting pass 1.

## VyralX-Server state at discovery time

- `/opt/friday_universe`, deployment copy (no `.git`), host
  `ip-172-26-12-48`. Re-probed fresh this run ~21:13 IST, unchanged since
  the claiming run and the 20:08 self-check.
- `VyralX.service`: active; `VyralX-Daemon.service`: inactive (loop OFF,
  as ordered).
- `yt-dlp` venv 2026.10.21 (`/opt/friday_universe/venv/bin/yt-dlp`);
  cookies `VyralX/data/youtube_cookies.txt` present (3146 B, Nov 24
  12:46); flat script sha256 `8cadb921…` identical to main.
- Exclusion sets loaded on VyralX-Server this run:
  `rejected_sources.json` (51 ids) + `published_shorts_manifest.json`
  (11) + `viral_loop_manifest.jsonl` (11) + `CpQGaTtppnU` (VYR-037 pool
  candidate 2) + the 7 VYR-055 pass-1 pool ids + the 6 VYR-053 pool ids +
  the 4 VYR-057 pool ids = **101 known ids excluded**.
- The refresh-3 variant (`find_viral_candidates_vyr055r3.py`, same
  helpers, 6 fresh queries, extended exclusions) was shipped to
  `VyralX/scripts/`, run, and removed afterwards — server tree left as
  found (verified: no `vyr055r3` script remains). Raw per-query output
  saved at `/tmp/vyr055r3_q{0..5}.json` on VyralX-Server.
- Bridge transport flaked twice this run (IncompleteRead on the read-back
  — the same flaking the 20:17 watch lists as a lag item): the q0 query
  call and the cleanup call. In both cases the server-side effect is
  verified, not assumed: q0's output file `/tmp/vyr055r3_q0.json` is
  complete (10 results, 0 fresh) with no stray yt-dlp process, and the
  variant file is confirmed gone. No command was blindly re-run.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-055-REFRESH-3-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Satisfying Pottery Spiral Designs #Shorts" (YouTube, id `OfEaVD7TtXM`) | YouTube search, query "satisfying pottery wheel throwing short"; https://youtube.com/shorts/OfEaVD7TtXM | 41s — PASS (15–60s) | 3,615; uploader Ingleton Pottery | Licence PENDING; caption-track BLOCKED; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED (see blocker) |
| 2 | "🌊 Mesmerizing Epoxy Water Effect — Make Resin Flow Like Real Liquid!" (YouTube, id `hlBOmnDobwg`) | YouTube search, query "mesmerizing water ripple art short"; https://youtube.com/shorts/hlBOmnDobwg | 39s — PASS | 1,897; uploader HeyClear | Same as #1 |
| 3 | "4K Free Stock Footage – Mesmerizing Abstract Ink Flow in Water \| Colorful Pattern Background" (YouTube, id `An4zMciturw`) | Same query | 42s — PASS | 38; uploader Free Stock Footage | Same as #1 |
| 4 | "Mesmerizing Water Animation on FlipaClip" (YouTube, id `jBhOCUJgFqk`) | Same query | 43s — PASS | 32; uploader FastForward | Same as #1 |
| 5 | "Mesmerizing Water Waves \| Watching Gentle Water Ripples At Fort Mott State Park In New Jersey" (YouTube, id `v6Wvgaj8LCg`) | Same query | 47s — PASS | 9; uploader Olvera Art Shop | Same as #1 |

Cautions, recorded not recommended: candidate 2 is an epoxy/resin how-to
("Make Resin Flow Like Real Liquid") — audition for promo/how-to
content; candidate 3 is labelled free stock footage — audition judges
suitability; candidate 4 is a FlipaClip animation, not real footage —
audition judges suitability; candidate 5 has 9 views (essentially
unviewed, last by the most-popular ranking). Only candidate 1 has real
traction (3,615 views). Candidates are filed by the machine gates only.

## YouTube discovery: 5 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying sand art drawing short" | 10 | 0 | 0 |
| "mesmerizing water ripple art short" | 10 | 4 | 4 — `hlBOmnDobwg`, `An4zMciturw`, `jBhOCUJgFqk`, `v6Wvgaj8LCg` |
| "oddly satisfying kinetic toy short" | 10 | 0 | 0 |
| "incredible yo-yo tricks short" | 10 | 0 | 0 |
| "satisfying pottery wheel throwing short" | 10 | 1 | 1 — `OfEaVD7TtXM` |
| "amazing paper craft origami short" | 10 | 0 | 0 |

All queries rc 0 (q0's rc not observed — bridge read flaked — but its
output file is complete; see the server-state note above). The four
zero-yield queries again surfaced long-form compilations only (same
pattern as VYR-055 pass 1's three zero-yield queries, VYR-053's four and
VYR-057's three). Raw per-query output saved at
`/tmp/vyr055r3_q{0..5}.json` on VyralX-Server. Discovery script: the
VYR-055 flat-playlist script, refresh-3 variant (6 fresh queries, +4
VYR-057 ids in `EXTRA_EXCLUDE`); the merged script itself is unchanged
by this task.

## BLOCKER (re-probed this run) — media-level QA gates cannot run: yt-dlp download broken on VyralX-Server

Re-verified 2026-11-24 ~21:20 IST — same failure VYR-055 pass 1
documented ~10:40–11:35 IST, VYR-053 ~14:30 IST and VYR-057 ~18:25 IST,
unchanged. This is a pipeline-wide failure, not a VYR-055 defect.

1. Metadata fetch on a known id (`JxAMNzlUFFE`, VYR-055 pool rank 1) fails
   (rc 1): YouTube's n-challenge cannot be solved — `n challenge solving
   failed: Some formats may be missing` and `Some web_embedded client
   https formats have been skipped as they are missing a URL. YouTube may
   have enabled the SABR-only streaming experiment for your account` (cf.
   yt-dlp #12482). End state: `Only images are available for download` +
   `Requested format is not available`.
2. New detail this run: yt-dlp now warns that the remote-components
   challenge solver (EJS) was skipped — "You can enable these downloads
   with --remote-components ejs:github (recommended) or
   --remote-components ejs:npm". That is the VYR-056 repair area, not
   this task's: no repair attempted here; the download-path repair is
   TASK-VYR-056, assigned to Muse 18. The QA leg of this refresh waits
   on VYR-056; the discovery leg proceeds now, per the clearance.

Consequence for the gates: duration (15–60s) PASS for all 5 candidates;
licence, caption-track count, BGM presence, watermark and loudness are
PENDING/BLOCKED, recorded as such in the pool file — not passed, not
failed. They must run at the supervised cycle once the download path is
repaired.

## What this PR contains

- This doc (`docs/collaboration/TASK-VYR-055-REFRESH-3-CANDIDATE-POOL.md`).
- `docs/collaboration/TASK-VYR-055-REFRESH-3-POOL.json`: machine-readable pool.
- `VyralX/tests/test_vyr055_refresh3_pool.py`: offline pins for the pool file
  (schema, 15–60s gate, most-popular ranking, disjointness from the
  VYR-055 pass-1 pool (7 ids), the VYR-053 pool (6 ids), the VYR-057 pool
  (4 ids) and from `CpQGaTtppnU`), wired into the contracts workflow
  list (`owner-workflows.yml`, VyralX step). Stdlib-only, no network.
- Board AVAILABLE → IN_REVIEW flip for TASK-VYR-055 (claim + this
  evidence; pr number follows in commit 2).

## Next

1. Repair the YouTube download path (TASK-VYR-056, Muse 18).
2. At the supervised cycle: run the four media gates per candidate
   (caption-track count, BGM presence, watermark, loudness) + licence
   check; record pass/fail; render from the top passing candidate, held
   unlisted, loop OFF, uploader paused.
3. Rejections, if any, go in `VyralX/data/rejected_sources.json` as
   before (currently 51 ids).
