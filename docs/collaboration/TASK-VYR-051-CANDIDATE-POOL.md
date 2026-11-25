# TASK-VYR-051: Next supervised-cycle candidate pool — discovery pass

- Task: TASK-VYR-051 (VyralX next supervised-cycle candidate pool — most-popular
  discovery + machine QA gates). Branch `muse5/task-vyr-051-candidate-pool`
  (claimed 2026-11-25 ~10:15 IST, hub comment 7153203124; base main `55027430`,
  rebased onto current main before the work PR — see PR body for the head).
  Board AVAILABLE → IN_REVIEW flip rides in the work PR (standing orders).
- Assignment: coordinator watch075 (7152477568, 09:32 IST); queue VYR-051 →
  VYR-077 → VYR-083. Watch078 (7153341846) re-slotted VYR-051 to Muse 12 on
  "no claim landed" — stale at post time: my claim (10:19 IST) landed before
  the re-slot post (10:29 IST). Watch079 (7153656996) ruled: **Muse 5 KEEPS
  VYR-051; the discovery-leg grant (read-only S2 run_shell, ytsearch + QA
  probes) stands as asked.**
- Discovery run: 2026-11-25 ~11:17–11:27 IST, on S2 via bridge `run_shell`
  (server 2). Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool only.
- Discovery checkpoint posted on hub #1483 (this run).

## S2 state at discovery time — VyralX tree deleted from the working tree

First-hand via bridge `run_shell` on Server 2 (all read-only probes):

- `/opt/friday_universe` @ `09603dff` (merge #1651), detached HEAD, working
  tree **1,801 files deleted** (unstaged ` D`), including the entire `VyralX/`
  (418 files in the index, directory absent) and `Cortex/` trees. 16 untracked
  files. `VyralX.service`: inactive / dead (`Result=success` — stopped
  cleanly at some point); `/health` + `/ready` on port 8010: 000.
- Consequence: the discovery script (`VyralX/scripts/find_viral_candidates_flat.py`),
  the cookie jar (`VyralX/data/youtube_cookies.txt`, present 2026-11-23 19:59
  per the VYR-055 doc), the exclusion ledgers (`rejected_sources.json` 51 ids,
  `published_shorts_manifest.json` 11, `viral_loop_manifest.jsonl` 11) and the
  niche guard (`VyralX/app/services/niche_guard.py`) are all gone from disk.
  `CREDENTIALS.md.bak-20261125-preupdate` exists at the repo root — something
  touched the S2 checkout today (2026-11-25). No repair attempted: the owner
  stop order (2026-11-24 ~16:42 IST) freezes server moves, and restoring the
  tree is a coordinator decision. This is reported, not fixed.
- Workarounds used (all read-only on the fleet, `/tmp` scratch only):
  - `yt-dlp` venv 2026.10.21 still present at `/opt/friday_universe/venv/bin/yt-dlp`.
  - Flat-playlist search works **without cookies**: probe `ytsearch5` RC=0, 5
    entries with id/title/duration/view_count/uploader.
  - Script, niche guard and prior-pool ids fetched from main via the GitHub API
    (the data files are gitignored — they exist only on S2, so the full S2
    ledgers are unrecoverable from the repo; see exclusions caveat below).
  - Raw per-query output saved at `/tmp/vyr051_q{0..5}.txt` and
    `/tmp/vyr051b_q{0..5}.txt` on S2.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-051-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Deni Yang ,Bubble Artist" (YouTube, id `pMn6d6P_rzw`) | YouTube search, query "incredible soap bubble art short"; https://youtube.com/shorts/pMn6d6P_rzw | 60s — PASS (upper boundary) | 202,287; uploader abhi george | Licence PENDING; caption-track BLOCKED; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED (see blocker) |
| 2 | "Pottery Bowl Throwing \| Satisfying Time Lapse" (YouTube, id `IWilKc2Xavw`) | YouTube search, query "mesmerizing pottery wheel throwing short"; https://youtube.com/shorts/IWilKc2Xavw | 51s — PASS | 25,197; uploader Mountain Mud Pottery | Same as #1 |
| 3 | "Glass Sutra - India's First Glass Art Studio" (YouTube, id `LJpQ8ZKamnQ`) | YouTube search, query "mesmerizing glass blowing art short"; https://youtube.com/shorts/LJpQ8ZKamnQ | 47s — PASS | 2,080; uploader Homely By LBB | Same as #1 |
| 4 | "Clear Slime ASMR \| Stretch, Poke & Slow Slice" (YouTube, id `RCXmyn3hQqA`) | YouTube search, query "oddly satisfying slime stretching short"; https://youtube.com/shorts/RCXmyn3hQqA | 30s — PASS | 1,205; uploader Glitter Press ASMR | Same as #1 |
| 5 | "Deep Engraving Steel Ring with 50W Fiber Laser Satisfying Laser Engraving" (YouTube, id `i1YwL8arCH0`) | YouTube search, query "satisfying metal engraving short"; https://youtube.com/shorts/i1YwL8arCH0 | 53s — PASS | 451; uploader Haotian Laser | Same as #1 |
| 6 | "Wooden Ninja Relief Carving ⚔️ \| Satisfying Timelapse" (YouTube, id `6hRd9_E80KA`) | YouTube search, query "satisfying wood carving timelapse short"; https://youtube.com/shorts/6hRd9_E80KA | 31s — PASS | 48; uploader Fugger Style | Same as #1 |
| 7 | "#india #engraving #satisfying Laser Engraving" (YouTube, id `I9sakQHsza8`) | Same query as #5 | 19s — PASS | 47; uploader RP LASER WORKS | Same as #1 |
| 8 | "Painting on Metal WITHOUT Ink! 🤯 Color Laser Engraving Compilation" (YouTube, id `OKFHC1NDmnI`) | Same query as #5 | 18s — PASS | 30; uploader Carverall_Akon | Same as #1 |
| 9 | "Wait Until You See This Epoxy Resin Pour! 😱✨" (YouTube, id `0-GsLOoUea4`) | YouTube search, query "satisfying resin art pouring short"; https://youtube.com/shorts/0-GsLOoUea4 | 16s — PASS | 26; uploader 𝐓𝐢𝐦𝐞𝐋𝐚𝐩𝐬𝐞 & 𝐄𝐩𝐨𝐱𝐲 𝐑𝐞𝐬𝐢𝐧 | Same as #1 |
| 10 | "Breathtaking Wilderness Engraved on Metal! 🐺🏔️ (Z12 MOPA Color Laser)" (YouTube, id `X8EmWgGAUak`) | Same query as #5 | 19s — PASS | 22; uploader Carverall_Akon | Same as #1 |
| 11 | "Wait for the Magic… ✨ Colorful Resin Art Pour (Satisfying 4K)" (YouTube, id `YRDYwVy3BQU`) | Same query as #9 | 21s — PASS | 19; uploader Rainbow Learning & Crafts | Same as #1 |
| 12 | "High-Precision Stone Plaque Engraving Process CNC Machining Demonstration" (YouTube, id `zd9rzfldAiY`) | Same query as #5 | 30s — PASS | 6; uploader YIHAICNC | Same as #1 |

Cautions, recorded not recommended: candidates 6–12 have 6–48 views
(essentially unviewed — the most-popular ranking is thin at the tail);
5 of 12 entries are metal-engraving from a single query, so pool diversity
is limited; candidate 1 sits exactly on the 60s upper boundary. Candidates
are filed by the machine gates only.

## YouTube discovery: 12 fresh candidates from 120 results — evidence

All `yt_rc` 0, `--flat-playlist` search, no cookies, no downloads.

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying kinetic sand cutting short" | 10 | 0 | 0 |
| "mesmerizing glass blowing art short" | 10 | 1 | 1 — `LJpQ8ZKamnQ` |
| "oddly satisfying paint mixing short" | 10 | 0 | 0 |
| "amazing cardistry flourish short" | 10 | 0 | 0 |
| "satisfying wood carving timelapse short" | 10 | 1 | 1 — `6hRd9_E80KA` |
| "incredible soap bubble art short" | 10 | 1 | 1 — `pMn6d6P_rzw` |
| "satisfying resin art pouring short" | 10 | 2 | 2 — `YRDYwVy3BQU`, `0-GsLOoUea4` |
| "mesmerizing pottery wheel throwing short" | 10 | 1 | 1 — `IWilKc2Xavw` |
| "oddly satisfying slime stretching short" | 10 | 1 | 1 — `RCXmyn3hQqA` |
| "amazing paper quilling art short" | 10 | 0 | 0 |
| "satisfying metal engraving short" | 10 | 5 | 5 — `i1YwL8arCH0`, `zd9rzfldAiY`, `X8EmWgGAUak`, `OKFHC1NDmnI`, `I9sakQHsza8` |
| "incredible candle making art short" | 10 | 0 | 0 |

Near-misses at the length gate (excluded, recorded): `BeolRON5Pqg` 61s,
`yVOCt5b1sPM` 61s, `U7VTSxZ0mSs` 65s. No banned-niche hits under the
TASK-VYR-065 guard (checked first-hand on title + channel for all 120
results: anime, cricket/sports highlights, Bollywood, movie/TV scenes,
celebrity edits, viral-clip compilations, borrowed gameplay, exam lectures,
finance advice — none). No collisions with the known-id exclusions.

Exclusions caveat: the S2 ledgers (`rejected_sources.json` 51 ids,
`published_shorts_manifest.json` 11, `viral_loop_manifest.jsonl` 11) are
unrecoverable — they lived only on S2 and are gitignored. Exclusions
applied here: the 24 ids in the VYR-053/054/055/055-REFRESH-3/057 pool
JSONs on main + `CpQGaTtppnU` (VYR-037 pool candidate 2) +
`1sYGq2no4Tk` (VYR-040 watermark rejection). A candidate that collides
with a lost-ledger id cannot be checked until the S2 tree is restored;
that residual risk is stated, not hidden.

Method note: the repo script `VyralX/scripts/find_viral_candidates_flat.py`
carries VYR-055's six queries; this pass ran an adapted driver from `/tmp`
on S2 with the 12 queries above (same venv yt-dlp resolution, same
`--flat-playlist ytsearch10`, same Python-side 15–60s filter, same guard).
The queries and the exact invocation are recorded here, so the pass is
reproducible by hand. The driver script is not committed — the S2 tree it
would live under is deleted, and committing a second copy of the discovery
script is a coordinator call.

## BLOCKER — media-level QA gates cannot run: no cookies, no download path

Verified first-hand this run (2026-11-25 ~11:25 IST), on candidate 1
(`pMn6d6P_rzw`):

- Per-video metadata fetch fails: `ERROR: [youtube] pMn6d6P_rzw: Sign in to
  confirm you're not a bot` — no cookie jar exists any more to pass.
- This is the same wall VYR-055 documented (n-challenge unsolvable on
  deno 2.9.8, SABR-only formats), now with an additional cause: the cookie
  jar died with the S2 VyralX tree. Flat-playlist search still works
  (listing needs no per-video extraction); downloads and per-video
  extraction do not.
- Consequence for the gates: duration (15–60s) PASS for all 12 candidates;
  licence, caption-track count, BGM presence, watermark and loudness are
  PENDING/BLOCKED, recorded as such in the pool file — not passed, not
  failed. They must run at the supervised cycle once the download path is
  repaired. Repair needs a coordinator decision (fresh YouTube session /
  PO-token provider / S2 tree restore), and the S2 tree restore is itself
  gated by the owner stop order. No unilateral move made.

## What this PR contains

- This doc (`docs/collaboration/TASK-VYR-051-CANDIDATE-POOL.md`).
- `docs/collaboration/TASK-VYR-051-POOL.json`: machine-readable pool (12 candidates).
- Board flips: TASK-VYR-051 AVAILABLE → IN_REVIEW (pr this PR); TASK-FRD-042
  CLAIMED → MERGED (work PR #1647, merge `d953ad4a`); TASK-FUT-027 IN_REVIEW →
  MERGED (work PR #1656, merge `1385464f`); TASK-STR-070 IN_REVIEW → MERGED
  (work PR #1688, merge `e7b21f24`); TASK-VYR-062 IN_REVIEW → MERGED (work PR
  #1756, merge `72f5a7ae`). All four merges verified first-hand via the PR API
  in earlier runs; the board records on main still read pre-merge.

## States

- Implemented: YES — discovery pass complete, 12-candidate pool filed.
- Tested: PARTIAL — duration gate + niche guard run first-hand on all 120
  results; media-level gates BLOCKED (see blocker).
- Merged: NO — merge owed to Muse.
- Deployed: N/A.
- Production-verified: NO — pool not yet through a supervised cycle.

## Next

1. Merge (Muse) — CI must go green on the head first.
2. Repair the S2 YouTube download path + restore the S2 VyralX tree
   (coordinator decision; owner stop order gates the restore).
3. Supervised cycle 3 runs on this pool once the media gates can run;
   VYR-052 depends on this pool.
