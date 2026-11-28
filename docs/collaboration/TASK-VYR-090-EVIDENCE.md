# TASK-VYR-090: Supervised cycle 8 candidate pool — discovery + machine QA gates — Muse 9

- Task: TASK-VYR-090 (VyralX supervised cycle 8 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; filed as follow-up of VYR-089 cycle 7). Branch
  `muse9/task-vyr-090` (claim 2026-11-28 07:58 IST, hub #2045 comment
  7232390826; assignment: Burn Enforcer 07:35 §B, hub 7232141421 —
  Muse 9 → TASK-VYR-090 head; WATCH250 §C decided the re-slot to the
  pool, board flip rides WATCH251 — board on main `b9e3cf77` still
  reads CLAIMED/muse_tp5, verified first-hand at claim; fresh-pool
  claim per the VYR-097 precedent). Board flips are coordinator-only
  (ruling 7200564540 §3) — no board hunk in this PR.
- Cycle-number note, stated plainly: this task is numbered cycle 8
  but cycles 9–12 (VYR-095/096/097/098) already ran while TP5 held
  it (TP5 claim 2026-11-27 23:10 IST, branch
  `musetp5/task-vyr-090-cycle-8-candidate-pool` @ `1a58bb15`, no PR,
  no output — re-slotted per BE 07:35 §C / WATCH250 §C). This run
  executes the cycle-8 task now, with fresh discovery and the full
  exclusion union including cycles 9–12.
- Discovery run: 2026-11-28 ~08:00 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~08:03 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted;
  no renders in this task — pool refresh only.
- Pattern: TASK-VYR-098 cycle 12 (Muse 9, PR #2242 open, head
  `6af7e6f6`, CI 9/9 green first-hand this run — 7 success +
  2 skipped; paired verdict with Muse 5 per WATCH250 §B, due
  ~08:40 IST) — same flat-search method and gates. VYR-098's 8
  candidates are in this cycle's exclusion set regardless.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 9
queries before issuing, `check_candidate` for all 90 returned
entries after (title / description / channel / uploader fields from
the flat rows). Raw per-query output saved at
`/tmp/vyr090_q{0..8}.jsonl` on S2; nothing was written to the S2
checkout (tracked tree clean before and after, verified this run).

Nine queries ran (not six): the first six yielded 12 shorts-length
fresh candidates but 7 were near-zero-view pours from one channel
(Latte Craft, 8–37 views), so three more fresh-topic queries ran in
the same session to widen the pool before ranking. All nine are
disclosed below; freshness is verified against the 54 candidate
queries recorded in the 18 prior pool JSONs (17 on main plus
VYR-098 on its branch) plus the zero-yield topics from the
cycle 10/11/12 evidence tables (needle felting, terrarium, origami,
crochet amigurumi, rug tufting, kite flying, paper marbling,
ice-cream rolling, shadow puppetry, bubble tea) — latte art,
spinning top, noodle pulling, skateboard, fruit carving, marble
run, stone balancing, trick archery and pancake art are all new
topics.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `094dedb20328aec196e85264b5593a005565e6c6`
  (tracked tree clean before and after this run). `VyralX.service`:
  failed (masked sleeping copy by fleet design; the live VyralX is
  on VyralX-Server). `VyralX-Daemon.service`: inactive (loop OFF,
  as ordered). `yt-dlp` `/usr/local/bin/yt-dlp` 2026.10.21 used for
  search (venv312 python used for guard checks); niche guard
  present (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/
  097/098): no cookie jar, no published/rejected manifests.
  Exclusion set loaded this run: the 125-id repo union (see below)
  — no S2 manifests back it. Flat search still runs rc 0 without
  the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200 (`{"status":"ok","service":"vyralx","version":"0.2.0"}`),
  up 3 days 16:36 at 02:32:38 UTC, load 0.00. The pipeline cookie
  jar (`VyralX/data/youtube_cookies.txt`, 3146 bytes, 2026-11-28)
  EXISTS there — existence checked only, contents never read.
  `yt-dlp` `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21. The
  live VyralX service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-090-POOL.json`.
Eighteen shorts-length fresh candidates were found; the top 8 by
views with a measured caption gate are filed. All 8 caption probes
returned rc 0 — no failed probe this cycle, no replacement needed.
Ten further fresh shorts below the cut are not filed (see discovery
table note). No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "How to Creative Fruit Carving. by NRTC. Watermelon old ship" (YouTube, id `xxsi7XQ1GJY`) | YouTube search, query "satisfying fruit carving art short"; https://youtube.com/shorts/xxsi7XQ1GJY | 60s — PASS (gate edge) | 154,376; uploader NRTC GROUP | Duration PASS; niche guard PASS; caption-track MEASURED 0 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Ultimate Wooden Marble Run Race \| Relaxing Marble Track \| Oddly Satisfying ASMR Compilation" (YouTube, id `KsQdewOrs_Y`) | YouTube search, query "mesmerizing marble run art short"; https://youtube.com/shorts/KsQdewOrs_Y | 28s — PASS | 414; uploader BARFI ZONE | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "The Art of Stone Balancing" (YouTube, id `clMKJBcF-Uw`) | YouTube search, query "satisfying stone balancing art short"; https://youtube.com/shorts/clMKJBcF-Uw | 57s — PASS | 254; uploader Dinamalar | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 4 | "M.Y. China - Kids Love Noodle Pulling" (YouTube, id `u8raGx5w2MU`) | YouTube search, query "satisfying noodle pulling art short"; https://youtube.com/shorts/u8raGx5w2MU | 30s — PASS | 230; uploader MY China | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 5 | "Stone balance demonstration" (YouTube, id `NXQIvo_h0QY`) | YouTube search, query "satisfying stone balancing art short"; https://youtube.com/shorts/NXQIvo_h0QY | 29s — PASS | 203; uploader Stone.d Art | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Amazing Stone Balancing Art" (YouTube, id `aquaNB6xtZo`) | YouTube search, query "satisfying stone balancing art short"; https://youtube.com/shorts/aquaNB6xtZo | 57s — PASS | 185; uploader I Wayan Sumiarta | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "Emoji Pancake Art Smiling Face With Smiling Eyes, Mini Pancake Art" (YouTube, id `C0r9KeS2l6g`) | YouTube search, query "satisfying pancake art drawing short"; https://youtube.com/shorts/C0r9KeS2l6g | 60s — PASS (gate edge) | 184; uploader Mini Pancake Art | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 8 | "Mesmerizing Marble Run Track Made in Blender 3D Satisfying Animation Relaxing Marble Race" (YouTube, id `f8Ejl-wvWNA`) | YouTube search, query "mesmerizing marble run art short"; https://youtube.com/shorts/f8Ejl-wvWNA | 39s — PASS | 147; uploader Cartoon TV | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidate 2 is titled an ASMR
compilation — it passed the niche guard by rule (no banned phrase
matched: the guard matches "viral compilation"-class phrases, not
bare "compilation"), licence/origin re-check owed at QA; candidate
8 is a Blender 3D animation per its title, not filmed footage —
passed the guard by rule, audition judges; candidate 4 reads as a
restaurant promo (M.Y. China) — licence/origin re-check owed;
candidate 1 is tutorial-style ("How to...") at the 60s gate edge;
candidates 3 and 5–7 are low-view (184–254). Honest traction note:
the top candidate has 154,376 views — below cycle 11's top
(164,282) and cycle 10's top (1,531,636), above cycle 12's top
(5,015). Traction does not imply licence clearance. Candidates are
filed by the machine gates only; the audition judges suitability.

## YouTube discovery: 8 filed candidates from 90 results — evidence

| Query | Returned | Shorts-length | Fresh shorts |
|---|---|---|---|
| "satisfying latte art pouring short" | 10 | 7 | 7 — `CvDedPRKObU`, `vVGvKPgKLic`, `K37tGPWGHQM`, `RjST3__Wv8k`, `h-qJkipt1Uk`, `1EMMCoSelCY`, `nMCtR5G5f6M` (all one channel, Latte Craft, 8–37 views; one 11s row under the gate) |
| "amazing spinning top trick short" | 10 | 0 | 0 (all 10 over 60s; closest 83s) |
| "satisfying noodle pulling art short" | 10 | 2 | 2 — `u8raGx5w2MU`, `hhONJiMT6H0` (one 9s row under the gate) |
| "amazing skateboard trick short" | 10 | 0 | 0 (all 10 over 60s; closest 311s) |
| "satisfying fruit carving art short" | 10 | 1 | 1 — `xxsi7XQ1GJY` (60s, gate edge) |
| "mesmerizing marble run art short" | 10 | 2 | 2 — `KsQdewOrs_Y`, `f8Ejl-wvWNA` (one 11s row under the gate) |
| "satisfying stone balancing art short" | 10 | 5 | 5 — `B1vFkRaBNws`, `aquaNB6xtZo`, `clMKJBcF-Uw`, `NXQIvo_h0QY`, `jWXvIT015dM` |
| "amazing trick archery shot short" | 10 | 0 | 0 (all 10 over 60s; closest 76s) |
| "satisfying pancake art drawing short" | 10 | 1 | 1 — `C0r9KeS2l6g` (60s, gate edge; one 9s row under the gate) |

All 9 searches rc 0; niche guard on S2: `check_query` ALLOW for all
9 queries before issuing; `check_candidate` over all 90 returned
entries: 0 rejections. Raw per-query output saved at
`/tmp/vyr090_q{0..8}.jsonl` on S2. No flat-row null anomaly this
cycle: every shorts-length row carried a view_count and uploader.
Not filed (fresh, shorts-length, below the top-8 measured cut):
`B1vFkRaBNws` (113 views), `jWXvIT015dM` (90 — "reverse video" per
title), `nMCtR5G5f6M` (37), `CvDedPRKObU` (35), `K37tGPWGHQM` (29),
`h-qJkipt1Uk` (19), `hhONJiMT6H0` (14 — 3D cooking animation per
title), `RjST3__Wv8k` (10), `1EMMCoSelCY` (9), `vVGvKPgKLic` (8).
They are not in this pool's `excluded_ids` and remain eligible next
cycle.

## Exclusion set — 125 unique ids, verified first-hand

Assembled from the 17 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 091, 093, 094, 095,
096, 097) plus the VYR-098 pool on branch `muse9/task-vyr-098`
(PR #2242, not yet merged at run time): union of all candidate ids
+ all `excluded_ids` fields = 125 ids, exactly VYR-098's 117
`excluded_ids` plus its 8 candidates (overlap 0; verified by direct
recomputation this run; full list in `TASK-VYR-090-POOL.json`
(`excluded_ids`)). Pool disjointness: the 8 filed ids are disjoint
from the 125-set and from each other; all 18 fresh shorts-length
ids are likewise disjoint from the 125-set. The S2 exclusion gap
stands (S2 manifests absent, carried decision owed to Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr090_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `xxsi7XQ1GJY` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `KsQdewOrs_Y` | none | 0 | 0 auto / 0 uploaded |
| `clMKJBcF-Uw` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `u8raGx5w2MU` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `NXQIvo_h0QY` | none | 0 | 0 auto / 0 uploaded |
| `aquaNB6xtZo` | none | 0 | 0 auto / 0 uploaded |
| `C0r9KeS2l6g` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `f8Ejl-wvWNA` | none | 0 | 0 auto / 0 uploaded |

All 8 filed candidates rc 0; no failed probe this cycle. Reading
note (same as VYR-094/095/096/097/098): the 157 is YouTube's
auto-caption + auto-translation list for the video (auto-generated
captions present); it is not 157 authored caption files. No
caption-count pass threshold exists in the board record, so counts
are filed as measured data for the audition, not as pass/fail.
Control: the same probe on run-6 candidate `bRfoNfGBL1o` returns
0 auto / 0 uploaded — identical to the VYR-094/095/096/097/098
control results; the method is not returning canned output. S2 has
no jar, so the gate cannot run there (re-probed this run: metadata
fetch on `xxsi7XQ1GJY` from S2 fails rc 1, "Sign in to confirm
you're not a bot", 528 bytes of error output, no metadata).

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`)
on candidate `xxsi7XQ1GJY`: rc 1, no media file created (log at
`/tmp/vyr090_dl.log` on server 5). Tail: n-challenge solver failure,
"n challenge solving failed", "Some web_embedded client https
formats have been skipped as they are missing a URL. YouTube may
have enabled the SABR-only streaming experiment", "Only images are
available for download", "Requested format is not available". Same
standing failure as VYR-056 (Nov 24); VYR-056 leg CLOSED as
unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates
PENDING/BLOCKED acceptable, proceed) stands. No download-path repair
was attempted (needs coordinator/owner direction per VYR-056).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 9/9 queries rc 0; caption-track
  gates measured live 8/8 filed + control, 0 failed probes;
  BGM/watermark/loudness BLOCKED on a re-probed download path) /
  merged NO (awaiting peer review/merge) / deployed N/A (no service
  changed; S2 tree left as found) / production-verified PARTIAL
  (pool filed from a real live discovery run + measured caption
  gates; render awaits the download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 9
