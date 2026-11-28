# TASK-VYR-105: Supervised cycle 19 candidate pool — discovery + machine QA gates — Muse 7

- Task: TASK-VYR-105 (VyralX supervised cycle 19 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; sequel to VYR-104 cycle 18). Branch
  `muse7/task-vyr-105-cycle-19-candidate-pool` @ `e8dfd88f` (claim
  2026-11-28 ~12:18 IST, hub #2045 comment 7235534372; assignment
  WATCH260 7235389912 §D — Muse 7 → TASK-VYR-105 head; board on main
  `e8dfd88f` read AVAILABLE / owner null / branch null / pr null, blob
  `9b9b9301`; no competing claim on the hub through comment 7235530263,
  re-read immediately before claiming). Board flips ride the
  coordinator's board PR (WATCH261) — no board hunk in this PR.
- Discovery run: 2026-11-28 ~12:50 IST, on S2 via bridge `run_shell`
  server=2 (host friday-universe-vnic-2). Caption-track gates +
  download re-probe: 2026-11-28 ~13:00 IST on VyralX-Server (server 5)
  via bridge `run_shell` server=5. Loop stays OFF, uploader paused,
  renders held unlisted; no renders in this task — pool refresh only.
- Pattern: TASK-VYR-104 (Muse 7) — same flat-search method and gates.
  Usage at run time: 62% of free weekly limit (resets Nov 28 9:25 PM
  IST), verified this run.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 9
queries before issuing (all ALLOW), `check_candidate` for all 90
returned entries after (0 rejections). Raw per-query output saved at
`/tmp/vyr105_q{0..8}.jsonl` on S2; nothing was written to the S2
checkout (tracked tree clean before and after, verified this run).

All nine topics are new: freshness verified against the 103 unique
candidate queries harvested this run from the 22 pool JSONs on main
plus the VYR-102 (PR #2290) and VYR-104 (PR #2285) pools, and against
the zero-yield topics from prior cycle evidence tables (chalk art,
topiary, macrame, watercolor, bento box, needle felting, terrarium,
crochet amigurumi, rug tufting, kite flying, paper marbling,
ice-cream rolling, shadow puppetry, bubble tea, wire sculpture,
stone carving, basket weaving, hula hoop, woodturning) — soap swirl
pouring, agate slicing, whip cracking, cheese carving, pancake
flipping, lock picking, wood joinery, trick archery and caramel
candy pulling repeat none of them.

## S2 + VyralX-Server state at run time

- S2 (server 2) host `friday-universe-vnic-2`; checkout
  `/opt/friday_universe` @ `69ff042b`, tracked tree clean
  (pre-existing untracked scratch only — left as found).
  `VyralX-Daemon.service` inactive (loop OFF, as ordered). `yt-dlp`
  2026.10.21; niche guard present (`VyralX/app/services/niche_guard.py`).
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes) EXISTS there —
  existence checked only, contents never read. `yt-dlp`
  `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21.
  `VyralX-Daemon.service` inactive (loop OFF, as ordered). The live
  VyralX service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-105-POOL.json`.
Ranking note: the top 8 of 19 fresh shorts are filed, by views; the
11 below the cut are listed after the table, not filed (VYR-098
precedent). No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "How to make perfect, fluffy pancakes" (YouTube, id `ac3kxH-BDJQ`) | YouTube search, query "satisfying pancake flipping trick short"; https://youtube.com/shorts/ac3kxH-BDJQ | 47s — PASS (15–60s) | 3,450; uploader Woolworths | Duration PASS; niche guard PASS; caption-track MEASURED auto captions available / 1 uploaded (en); licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Cheese Carving Techniques" (YouTube, id `rqAQFt-vI_k`) | YouTube search, query "satisfying cheese carving art short"; https://youtube.com/shorts/rqAQFt-vI_k | 56s — PASS | 2,682; uploader UkropsSuperMarkets | Caption-track MEASURED auto captions available / 0 uploaded; rest same as #1 |
| 3 | "Nathan Griggs whip cracking at world record speed" (YouTube, id `gqsoJYyQEGQ`) | YouTube search, query "amazing whip cracking trick short"; https://youtube.com/shorts/gqsoJYyQEGQ | 49s — PASS | 2,008; uploader YouKeepUsTraveling | Caption-track MEASURED auto captions available / 0 uploaded; rest same as #1 |
| 4 | "Raw Fordite, very large piece" (YouTube, id `Mlc-ME6QzwI`) | YouTube search, query "mesmerizing agate slicing art short"; https://youtube.com/shorts/Mlc-ME6QzwI | 20s — PASS | 1,898; uploader Scale Solutions | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "Nathan Griggs - Whip Cracking - Trick Tuesday Volleys" (YouTube, id `rM8rDoF6MKs`) | YouTube search, query "amazing whip cracking trick short"; https://youtube.com/shorts/rM8rDoF6MKs | 27s — PASS | 1,852; uploader Nathan Griggs | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Artist Creates Impressive Sculptures Using Cheese" (YouTube, id `jFoQZNT-2mg`) | YouTube search, query "satisfying cheese carving art short"; https://youtube.com/shorts/jFoQZNT-2mg | 60s — PASS | 1,009; uploader Caters Clips | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "Never Waste Leftover Pancakes Again with This Delicious Recipe!" (YouTube, id `W550R_oHmNs`) | YouTube search, query "satisfying pancake flipping trick short"; https://youtube.com/shorts/W550R_oHmNs | 50s — PASS | 783; uploader EasYummy | Caption-track MEASURED uploaded subtitles available (48 language rows) / no automatic-captions section listed; rest same as #1 |
| 8 | "SA Cheese Festival 2018 Ladismith Cheese Carving Competition" (YouTube, id `mwEKuoo247I`) | YouTube search, query "satisfying cheese carving art short"; https://youtube.com/shorts/mwEKuoo247I | 37s — PASS | 669; uploader Agri-Expo | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Below the cut — 11 further fresh shorts, not filed: `DVdds1L5MGE`
(465 views, whip cracking), `7nL6L_HcMCw` (98, cheese carving),
`BcR9idjhcHU` (81, caramel candy), `YtR7VY_MeiU` (57, cheese
carving), `wKnATh0zHlM` (56, agate), `7wd4SPJ0snw` (41, agate),
`vf0902uEkZE` (39, agate), `nsPCEr3Enuw` (36, soap swirl),
`KqCFLfgrcWY` (26, caramel candy), `9yDfeMyKP-s` (15, soap swirl),
`vJEFS77yi2E` (12, cheese carving).

Cautions, recorded not recommended: candidates 1 and 2 are brand
uploads (Woolworths, UkropsSuperMarkets) — licence/origin re-check
owed at QA for each; candidates 3 and 5 are the same performer
(Nathan Griggs), one via a travel channel; candidate 4's title names
fordite, not agate — topic drift from the query, the audition judges
suitability; candidate 6 sits at 60s, the gate edge, and is an
aggregator upload (Caters Clips); candidate 8 is 2018 festival
competition footage. Honest traction note: this pool's head (3,450
views) is far weaker than cycle 18's (2,008,771) — the nine fresh
topics yielded thin shorts-length supply (3 of 9 queries returned
zero shorts-length results); traction does not imply licence
clearance either way. Candidates are filed by the machine gates
only; the audition judges suitability.

## YouTube discovery: 8 filed candidates from 90 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying soap swirl pouring short" | 10 | 2 | 2 — `nsPCEr3Enuw`, `9yDfeMyKP-s` |
| "mesmerizing agate slicing art short" | 10 | 4 | 4 — `Mlc-ME6QzwI`, `7wd4SPJ0snw`, `vf0902uEkZE`, `wKnATh0zHlM` |
| "amazing whip cracking trick short" | 10 | 3 | 3 — `rM8rDoF6MKs`, `gqsoJYyQEGQ`, `DVdds1L5MGE` |
| "satisfying cheese carving art short" | 10 | 6 | 6 — `jFoQZNT-2mg`, `mwEKuoo247I`, `rqAQFt-vI_k`, `vJEFS77yi2E`, `7nL6L_HcMCw`, `YtR7VY_MeiU` |
| "satisfying pancake flipping trick short" | 10 | 2 | 2 — `ac3kxH-BDJQ`, `W550R_oHmNs` |
| "amazing lock picking trick short" | 10 | 0 | 0 (all 10 over 60s) |
| "satisfying wood joinery craft short" | 10 | 0 | 0 (all 10 over 60s) |
| "incredible trick archery shot short" | 10 | 0 | 0 (all 10 over 60s) |
| "satisfying caramel candy pulling short" | 10 | 2 | 2 — `KqCFLfgrcWY`, `BcR9idjhcHU` |

All 9 searches rc 0; niche guard on S2: `check_query` ALLOW for all
9 queries before issuing; `check_candidate` over all 90 returned
entries: 0 rejections. Raw per-query output saved at
`/tmp/vyr105_q{0..8}.jsonl` on S2.

## Exclusion set — 199 unique ids, verified first-hand

Assembled this run by direct blob fetch: union of all candidate ids
+ all `excluded_ids` fields across the 22 pool JSONs on main
(VYR-051, 053, 054, 055, 055-REFRESH-3, 057, 067, 086, 087, 088,
089, 090, 091, 093, 094, 095, 096, 097, 098, 099, 100, 101) = 175
ids by this run's harvest (VYR-104 filed 157 under its narrower
harvest; this run also collects nested id fields, so the set is
broader, never narrower), plus the VYR-104 filed 8 and below-cut 8
(PR #2285 branch) and the VYR-102 filed 8 (PR #2290 branch) = 199
ids; full list in `TASK-VYR-105-POOL.json` (`excluded_ids`). Pool
disjointness: the 8 filed ids are disjoint from the 199-set and
from each other (asserted in the filing script). The VYR-103 pool
is not filed yet (branch only, no pool at run time) — fresh topics
avoid collision; the coordinator reconciles at merge.

## Machine QA gates — caption-track MEASURED (8/8); BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr105_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `ac3kxH-BDJQ` | available (313 language rows incl. auto-translations) | 1 (en) | auto available / 1 uploaded |
| `rqAQFt-vI_k` | available (157 language rows) | 0 ("has no subtitles") | auto available / 0 uploaded |
| `gqsoJYyQEGQ` | available (157 language rows) | 0 | auto available / 0 uploaded |
| `Mlc-ME6QzwI` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `rM8rDoF6MKs` | none | 0 | 0 / 0 |
| `jFoQZNT-2mg` | none | 0 | 0 / 0 |
| `W550R_oHmNs` | no automatic-captions section listed | available (48 language rows) | uploaded available / no auto section |
| `mwEKuoo247I` | none | 0 | 0 / 0 |

No caption-count pass threshold exists in the board record, so
counts are filed as measured data for the audition, not as
pass/fail. Control: the same probe on run-6 candidate `bRfoNfGBL1o`
returns 0 auto / 0 uploaded — identical to prior cycles' control
results; the method is not returning canned output.

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`,
`--no-playlist`, `-f 'bv*[height<=1080]+ba/b[height<=1080]'`,
`--merge-output-format mp4`) on candidate `ac3kxH-BDJQ`: failed, no
media file created (log at `/tmp/vyr105_dl.log` on server 5). Tail:
"n challenge solving failed", "Some web_embedded client https
formats have been skipped as they are missing a URL. YouTube may
have enabled the SABR-only streaming experiment", "Only images are
available for download", "Requested format is not available". Same
standing failure as VYR-056; WATCH151 ruling 1 (gates
PENDING/BLOCKED acceptable, proceed) stands. No download-path repair
was attempted (needs coordinator/owner direction per VYR-056).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 9/9 queries rc 0; caption-track
  gates measured live 8/8 + control; BGM/watermark/loudness BLOCKED
  on a re-probed download path) / merged NO (awaiting peer
  review/merge) / deployed N/A (no service changed; S2 tree left as
  found) / production-verified PARTIAL (pool filed from a real live
  discovery run + measured caption gates; render awaits the
  download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 7
