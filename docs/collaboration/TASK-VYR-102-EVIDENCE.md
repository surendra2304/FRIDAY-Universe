# TASK-VYR-102: Supervised cycle 16 candidate pool — discovery + machine QA gates — Muse 8

- Task: TASK-VYR-102 (VyralX supervised cycle 16 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-101 cycle 15). Branch `muse8/task-vyr-102`
  (claim 2026-11-28 ~11:41 IST, hub #2045 comment 7235139735;
  assignment: BE 11:45 §B hub 7235033944 + WATCH259 correction hub
  7235111247; board on main `42ba9151` (blob `48241373`) read first-hand
  — TASK-VYR-102 AVAILABLE / owner muse_8, branch/pr null; no competing
  claim through hub 7235111247). Claim PR #2286 open (board
  AVAILABLE→CLAIMED, commit `a621aec6`). This PR adds the pool + evidence
  on the same branch.
- Discovery run: 2026-11-28 ~11:47–11:52 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~11:53–11:54 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool refresh only.
- Pattern: TASK-VYR-100 cycle 14 (Muse 8, PR #2262 MERGED 2026-11-28
  10:46 IST, merge `a9a77862`) — same flat-search method and gates.
  VYR-099 cycle 13 (M9, PR #2271 open, M8 VERIFIED review 6095879667)
  and VYR-101 cycle 15 (M14, PR #2266 open) are in this cycle's
  exclusion set. VYR-103 (TP3, claimed) and VYR-104 (M7, claimed) pools
  are NOT yet filed — overlap check vs both owed at merge.
- Numbering flag (board record is stale): the TASK-VYR-102 board record
  says "follow-up of VYR-101 cycle 9" and next_action "cycle 10
  candidate pool". The BE assignment governs: this is cycle 16
  (VYR-099 = 13, VYR-100 = 14, VYR-101 = 15). No board hunk in this PR
  beyond the claim flip.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 12
queries (ALLOW, all 12), `check_candidate` for all 120 returned
entries (title / description / channel / uploader fields from the flat
rows). Raw per-query output saved at `/tmp/vyr102_q{0..11}.jsonl` on
S2; nothing was written to the S2 checkout (tracked tree clean before
and after, verified this run).

Twelve queries ran in two groups: the first nine yielded only 5 fresh
shorts-length candidates, so three further fresh-topic queries ran to
reach the usual 8-candidate pool with measured metadata. All twelve
are disclosed below; freshness is verified against the query lists in
the VYR-098/099/100/101 evidence tables plus VYR-100's note on cycles
7–12 — kinetic sand cutting, resin art pouring, blacksmith forging,
slime mixing, magnetic balls sculpture, candle making, paper quilling,
calligraphy writing, ice carving, embroidery stitching, origami
folding and latte art pouring are all new topics.

Sequence disclosure (two of my own mistakes, neither affecting the
result): (1) the first `check_query` invocation failed with a
SyntaxError (quoting error in my own command) in the same shell call
as the first three searches, so those three searches were issued
before the guard result was known; the guard was then re-run cleanly
and returned ALLOW for all 9 queries, and the remaining nine searches
were issued only after their guard results — no query was issued
against a rejection. (2) One second-batch invocation ran nothing (a
heredoc broken by `;`-joining); it was re-run cleanly with newline
joins. Both are recorded here, not hidden.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `69ff042b1b5963b5d0216348f11d737d2a67a9e2`
  (tracked tree clean before and after this run, pre-existing untracked
  scratch only — left as found). `VyralX.service`: failed (masked
  sleeping copy by fleet design; the live VyralX is on VyralX-Server).
  `VyralX-Daemon.service`: inactive (loop OFF, as ordered). `yt-dlp`
  `/usr/local/bin/yt-dlp` 2026.10.21 used for search (venv312 python
  used for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/097/
  098/100): no cookie jar, no published/rejected manifests. Exclusion
  set loaded this run: the 157-id repo union (see below) — no S2
  manifests back it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200, up 3 days 20:23 at 06:19:52 UTC, load 0.03. The pipeline
  cookie jar (`VyralX/data/youtube_cookies.txt`, 3146 bytes,
  2026-11-28) EXISTS there — existence checked only, contents never
  read. `yt-dlp` `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21.
  The live VyralX service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-102-POOL.json`.
Eleven fresh shorts-length candidates with measured metadata were
found; the top 8 by views are filed. All 8 have non-null views and
uploaders. No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "2022 Winterlude - National Ice Carving Championship" (YouTube, id `fvnhx3gst08`) | YouTube search, query "mesmerizing ice carving short"; https://youtube.com/shorts/fvnhx3gst08 | 45s — PASS (15–60s) | 398; uploader City of Fort St. John | Duration PASS; niche guard PASS; caption-track MEASURED 157 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Kemi: Ice carving" (YouTube, id `FdAmoDQ1eJs`) | YouTube search, query "mesmerizing ice carving short"; https://youtube.com/shorts/FdAmoDQ1eJs | 23s — PASS | 213; uploader Experience365 | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "Ice Sculpting On Display In Center City" (YouTube, id `VIKJYd9XndI`) | YouTube search, query "mesmerizing ice carving short"; https://youtube.com/shorts/VIKJYd9XndI | 20s — PASS | 87; uploader CBS Philadelphia | Caption-track MEASURED 313 auto / 1 uploaded (see note); rest same as #1 |
| 4 | "21-Second Latte Art Tutorial: Watch This Perfect Pour! #latteart #coffeeart #baristaskills" (YouTube, id `CvDedPRKObU`) | YouTube search, query "satisfying latte art pouring short"; https://youtube.com/shorts/CvDedPRKObU | 21s — PASS | 35; uploader Latte Craft | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "Every Barista Tries to Pour Like This : Watch This Perfect Pour! #latteart #coffeeart #baristaskills" (YouTube, id `K37tGPWGHQM`) | YouTube search, query "satisfying latte art pouring short"; https://youtube.com/shorts/K37tGPWGHQM | 32s — PASS | 29; uploader Latte Craft | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Carving an apple in ice timeslapse" (YouTube, id `7_hWsx1y7KI`) | YouTube search, query "mesmerizing ice carving short"; https://youtube.com/shorts/7_hWsx1y7KI | 17s — PASS | 24; uploader PSD Ice | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 7 | "5 Amazing Magnetic Ball Art Secrets You Never Knew" (YouTube, id `27Z2jdrY5wQ`) | YouTube search, query "mesmerizing magnetic balls sculpture short"; https://youtube.com/shorts/27Z2jdrY5wQ | 59s — PASS | 20; uploader Jungle Monkey Shorts | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "The Most Perfect Latte Pour Ever Caught on Camera #latteart #coffeeart #baristaskills" (YouTube, id `h-qJkipt1Uk`) | YouTube search, query "satisfying latte art pouring short"; https://youtube.com/shorts/h-qJkipt1Uk | 38s — PASS | 19; uploader Latte Craft | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: channel concentration — 3 of the
8 filed candidates are from one channel ("Latte Craft", all latte
art) and 4 of 8 are ice carving; the pool is thin on topic diversity.
Candidate 3 is a local-news clip (CBS Philadelphia) — licence/origin
re-check owed at QA. Candidate 1 is a municipal championship
recording (City of Fort St. John) — licence/origin re-check owed.
Candidate 7 is listicle framing ("5 Amazing ... Secrets You Never
Knew") — suitability re-check owed. Candidate 6's flat-row uploader
carries a trailing space ("PSD Ice ") — verbatim from the flat row.
Honest traction note: the top candidate has 398 views — the weakest
top of any recent cycle (cycle 14's top was 566,165; cycle 12's top
5,015; cycle 11's top 164,282). Traction does not imply licence
clearance. Candidates are filed by the machine gates only; the
audition judges suitability.

## YouTube discovery: 8 filed candidates from 120 results — evidence

| Query | Returned | Shorts-length | Fresh shorts |
|---|---|---|---|
| "satisfying kinetic sand cutting short" | 10 | 0 | 0 (no shorts-length rows) |
| "mesmerizing resin art pouring short" | 10 | 1 | 0 — the one shorts-length row (`0-GsLOoUea4`, 16s) is an excluded known id |
| "satisfying blacksmith forging short" | 10 | 1 | 0 — the one shorts-length row (`SFFxtmdc9SE`, 15s, null views) is an excluded known id |
| "satisfying slime mixing art short" | 10 | 0 | 0 (no shorts-length rows) |
| "mesmerizing magnetic balls sculpture short" | 10 | 1 | 1 — `27Z2jdrY5wQ` |
| "satisfying candle making short" | 10 | 1 | 0 — the one shorts-length row (`kEAOZpyGi5U`, 35s) is an excluded known id |
| "incredible paper quilling art short" | 10 | 0 | 0 (no shorts-length rows) |
| "satisfying calligraphy writing short" | 10 | 0 | 0 (no shorts-length rows) |
| "mesmerizing ice carving short" | 10 | 4 | 4 — `7_hWsx1y7KI`, `VIKJYd9XndI`, `FdAmoDQ1eJs`, `fvnhx3gst08` |
| "satisfying embroidery stitching short" | 10 | 0 | 0 (no shorts-length rows) |
| "incredible origami folding art short" | 10 | 0 | 0 (no shorts-length rows) |
| "satisfying latte art pouring short" | 10 | 6 | 6 — `vVGvKPgKLic`, `K37tGPWGHQM`, `CvDedPRKObU`, `RjST3__Wv8k`, `h-qJkipt1Uk`, `nnh7gVBXh_w` |

All 12 searches rc 0; niche guard on S2: `check_query` ALLOW for all
12 queries; `check_candidate` over all 120 returned entries: 0
rejections. Raw per-query output saved at
`/tmp/vyr102_q{0..11}.jsonl` on S2. Not filed (fresh, shorts-length,
below the top-8 measured cut): `RjST3__Wv8k` (10 views),
`vVGvKPgKLic` (8 views), `nnh7gVBXh_w` (6 views). They are not in this
pool's `excluded_ids` and remain eligible next cycle.

## Exclusion set — 157 unique ids, verified first-hand

Assembled from the 22 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 090, 091, 093, 094, 095,
096, 097, 098, 099, 100, 101): union of all candidate ids + all
`excluded_ids` fields = 157 ids, exactly the 133-id base (VYR-100's
recomputation) plus VYR-099's 8 candidates, VYR-100's 8 and VYR-101's
8 (overlap 0; verified by direct recomputation this run; full list in
`TASK-VYR-102-POOL.json` (`excluded_ids`)). Pool disjointness: the 8
filed ids and the 3 below-cut ids are disjoint from the 157-set and
from each other. The S2 exclusion gap stands (S2 manifests absent,
carried decision owed to Muse). VYR-103 (TP3) and VYR-104 (M7) pools
not yet filed — overlap check vs both owed at merge.

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr102_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `fvnhx3gst08` | 157 languages listed (incl. en English) | 0 ("has no subtitles") | 157 auto / 0 uploaded |
| `FdAmoDQ1eJs` | none ("has no automatic captions") | 0 | 0 auto / 0 uploaded |
| `VIKJYd9XndI` | 313 entries listed (see note) | 1 (en, "English - en") | 313 auto / 1 uploaded |
| `CvDedPRKObU` | none | 0 | 0 auto / 0 uploaded |
| `K37tGPWGHQM` | none | 0 | 0 auto / 0 uploaded |
| `7_hWsx1y7KI` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `27Z2jdrY5wQ` | none | 0 | 0 auto / 0 uploaded |
| `h-qJkipt1Uk` | 157 languages listed (incl. en English) | 0 | 0 auto / 0 uploaded |

All 8 filed candidates rc 0. Reading note (same as
VYR-094/095/096/097/098/100): the 157 is YouTube's auto-caption +
auto-translation list for the video (auto-generated captions
present); it is not 157 authored caption files. `VIKJYd9XndI`'s 313
was verified by direct line count: 157 auto-caption languages plus
156 "X from English - en" auto-translations of its 1 uploaded
English subtitle — measured per video, not a threshold. No
caption-count pass threshold exists in the board record, so counts
are filed as measured data for the audition, not as pass/fail.
Control: the same probe on run-6 candidate `bRfoNfGBL1o` returns 0
auto / 0 uploaded — identical to the VYR-094/095/096/097/098/100
control results; the method is not returning canned output.

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`)
on candidate `fvnhx3gst08`: rc 1, no media file created (log at
`/tmp/vyr102_dl.log` on server 5). Tail: n-challenge solver failure
(deno crash), "n challenge solving failed", "Some web_embedded client
https formats have been skipped as they are missing a URL. YouTube may
have enabled the SABR-only streaming experiment", "Only images are
available for download", "Requested format is not available". Same
standing failure as VYR-056 (Nov 24); VYR-056 leg CLOSED as
unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates
PENDING/BLOCKED acceptable, proceed) stands. No download-path repair
was attempted (needs coordinator/owner direction per VYR-056).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 12/12 queries rc 0; caption-track
  gates measured live 8/8 filed + control; BGM/watermark/loudness
  BLOCKED on a re-probed download path) / merged NO (awaiting peer
  review/merge) / deployed N/A (no service changed; S2 tree left as
  found) / production-verified PARTIAL (pool filed from a real live
  discovery run + measured caption gates; render awaits the
  download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 8
