# TASK-VYR-106: Supervised cycle 20 candidate pool — discovery + machine QA gates — Muse 8

- Task: TASK-VYR-106 (VyralX supervised cycle 20 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; sequel to VYR-105 cycle 19). Branch `muse8/task-vyr-106`
  (claim 2026-11-28 ~13:41 IST, hub #2045 comment 7236409387;
  assignment: WATCH263 §C hub 7236357595 + BE 13:45 §B hub 7236383505 —
  "M8 → claim TASK-VYR-106 now"; board on main `6b1c91cb` (blob
  `d466a3d8`) read first-hand — TASK-VYR-106 CLAIMED / owner muse_8,
  branch/pr null; no competing claim through hub 7236383505). Board flip
  rides WATCH264's board PR (coordinator-only; board flips are
  coordinator-only per ruling 7200564540 §3 — no board hunk in this PR).
  This PR adds the pool + evidence only, no board hunk.
- Discovery run: 2026-11-28 ~13:47–13:49 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates + download re-probe:
  2026-11-28 ~13:50–13:52 IST on VyralX-Server (server 5) via bridge
  `run_shell` server=5. Loop stays OFF, uploader paused, renders held
  unlisted; no renders in this task — pool refresh only.
- Pattern: TASK-VYR-102 cycle 16 (Muse 8, PR #2290 MERGED 2026-11-28
  13:05 IST, merge `0c288bac`) and TASK-VYR-105 cycle 19 (Muse 7,
  PR #2296 MERGED `afbf6b24`) — same flat-search method and gates.
  VYR-103 (TP3, CLAIMED) pool is still NOT filed — overlap check vs
  VYR-103 owed at merge. VYR-104 (M7, cycle 18) pool is on main now,
  in this cycle's exclusion set.
- Numbering: the board record agrees — "Cycle-20 candidate pool" —
  no numbering flag this cycle (VYR-099 = 13, VYR-100 = 14,
  VYR-101 = 15, VYR-102 = 16, VYR-104 = 18, VYR-105 = 19).

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 12
queries before issuing (ALLOW, all 12), `check_candidate` for all 120
returned entries (3 rejections, all anime — see below). Raw per-query
output saved at `/tmp/vyr106_q{0..11}.jsonl` on S2; nothing was written
to the S2 checkout (tracked tree clean before and after, verified this
run).

Twelve new topics, freshness verified against the 85 unique queries
harvested this run from the 25 pool JSONs on main plus the zero-yield
topics from the VYR-102/104/105 evidence tables (kinetic sand cutting,
resin art pouring, blacksmith forging, slime mixing, magnetic balls
sculpture, candle making, paper quilling, calligraphy writing, ice
carving, embroidery stitching, origami folding, latte art pouring,
soap swirl pouring, agate slicing, whip cracking, cheese carving,
pancake flipping, lock picking, wood joinery, trick archery, caramel
candy pulling, basket weaving, crystal growing, hula hoop, woodturning,
pottery glazing, boomerang, lava lamp making, sandcastle building,
glass engraving, chalk art, topiary, macrame, watercolor, bento box,
needle felting, terrarium, crochet amigurumi, rug tufting, kite flying,
paper marbling, ice-cream rolling, shadow puppetry, bubble tea, wire
sculpture, stone carving) — bonsai pruning, geode cracking, sushi
making, knife sharpening, rope knot tying, coin stacking, card
throwing, honey pouring, string art portrait, miniature house building,
oil painting and dumpling folding repeat none of them. Three queries
yielded zero shorts-length rows (knife sharpening, card throwing, oil
painting) — the pool still reached the usual 8 candidates from the
other nine.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `608fa7e6927675bbbebadba17e824acc6834d510`
  (tracked tree clean before and after this run, pre-existing untracked
  scratch only — left as found). `VyralX.service`: failed (masked
  sleeping copy by fleet design; the live VyralX is on VyralX-Server).
  `VyralX-Daemon.service`: inactive (loop OFF, as ordered). `yt-dlp`
  `/usr/local/bin/yt-dlp` 2026.10.21 used for search; niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/097/
  098/100/102): no cookie jar, no published/rejected manifests. Exclusion
  set loaded this run: the 207-id repo union (see below) — no S2
  manifests back it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200, up 3 days 22:23 at 08:19 UTC, load 0.00. The pipeline
  cookie jar (`VyralX/data/youtube_cookies.txt`, 3146 bytes,
  2026-11-28 06:53) EXISTS there — existence checked only, contents never
  read. `yt-dlp` `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21.
  `VyralX-Daemon.service` inactive (loop OFF, as ordered). The live
  VyralX service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-106-POOL.json`.
Eighteen fresh shorts-length candidates with measured metadata were
found; the top 8 by views are filed. All 8 filed have non-null views
and uploaders. No view gate exists
in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "How to Make Geode Cookies" (YouTube, id `OkRnqxpMyJk`) | YouTube search, query "mesmerizing geode cracking art short"; https://youtube.com/shorts/OkRnqxpMyJk | 59s — PASS (15–60s) | 217,442; uploader Insider | Duration PASS; niche guard PASS; caption-track MEASURED 157 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Reverse String Art - Horse Head - DIY crafts - Unique Accents - Handmade Canada - wood art - Gift" (YouTube, id `APRRfnfV420`) | YouTube search, query "incredible string art portrait short"; https://youtube.com/shorts/APRRfnfV420 | 39s — PASS | 7,369; uploader Katie McQueen | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "Pouring Honey Stock Video" (YouTube, id `8c9tU5_4Lek`) | YouTube search, query "satisfying honey pouring art short"; https://youtube.com/shorts/8c9tU5_4Lek | 23s — PASS | 1,717; uploader Motion Array | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 4 | "Mini AI Construction Timelapse 🏗️ \| Tiny House Building in Seconds \| Satisfying Miniature DIY Build" (YouTube, id `0TdlWueUKiM`) | YouTube search, query "satisfying miniature house building short"; https://youtube.com/shorts/0TdlWueUKiM | 57s — PASS | 339; uploader Smart Build Studio (trailing space verbatim) | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "Lord Krishna String Art" (YouTube, id `4jLJCrxrPoc`) | YouTube search, query "incredible string art portrait short"; https://youtube.com/shorts/4jLJCrxrPoc | 27s — PASS | 328; uploader GALLIO INTERNATIONAL | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "The Gravity-Defying Art Of Coin Stacking: Triumphal arch  oni a running washing machine" (YouTube, id `AdeHUpyi-aw`) | YouTube search, query "incredible coin stacking art short"; https://youtube.com/shorts/AdeHUpyi-aw | 37s — PASS | 324; uploader Haier Group | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "Satisfying Miniature House Construction 🧱" (YouTube, id `xycDcrWT6c8`) | YouTube search, query "satisfying miniature house building short"; https://youtube.com/shorts/xycDcrWT6c8 | 21s — PASS | 280; uploader PocketWorlds | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "String Art Lion Face" (YouTube, id `Q26GFviHXpc`) | YouTube search, query "incredible string art portrait short"; https://youtube.com/shorts/Q26GFviHXpc | 30s — PASS | 175; uploader GALLIO INTERNATIONAL | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: topic concentration — 3 of the
8 filed candidates are string art and 2 are miniature-house building;
channel concentration — 2 of the 8 are from one channel ("GALLIO
INTERNATIONAL", both string art). Candidate 1 is an Insider
media-publisher clip — licence/origin re-check owed at QA. Candidate 3
is stock footage (Motion Array) — licence/origin re-check owed.
Candidate 6 is a brand channel (Haier Group) — licence/origin re-check
owed. Candidate 4 is titled "Mini AI Construction Timelapse" —
AI-generated-content suitability re-check owed. Candidate 4's flat-row
uploader carries a trailing space ("Smart Build Studio ") — verbatim
from the flat row. Candidate 6's flat-row title carries a double space
and "oni" ("Triumphal arch  oni a running washing machine") — verbatim
from the flat row. Traction note: the top candidate has 217,442 views —
the strongest top since cycle 14's 566,165 (cycle 16's top was 398).
Traction does not imply licence clearance. Candidates are filed by the
machine gates only; the audition judges suitability.

## YouTube discovery: 8 filed candidates from 120 results — evidence

| Query | Returned | Shorts-length | Fresh shorts |
|---|---|---|---|
| "satisfying bonsai pruning art short" | 10 | 1 | 1 — `UAHU-O3rD0c` |
| "mesmerizing geode cracking art short" | 10 | 2 | 2 — `ZzC6ryVCb0M`, `OkRnqxpMyJk` |
| "satisfying sushi making art short" | 10 | 2 (+2 rejected, see note) | 2 — `spuIfDiAee0`, `X0pvtUnbdkw` |
| "satisfying knife sharpening whetstone short" | 10 | 0 | 0 (no shorts-length rows) |
| "satisfying rope knot tying art short" | 10 | 1 | 1 — `Pzt4S-yW03s` |
| "incredible coin stacking art short" | 10 | 2 | 2 — `wFSiTTBkV5s`, `AdeHUpyi-aw` |
| "amazing card throwing trick short" | 10 | 0 | 0 (no shorts-length rows) |
| "satisfying honey pouring art short" | 10 | 2 | 2 — `s1kG6UEiCkY`, `8c9tU5_4Lek` |
| "incredible string art portrait short" | 10 | 5 | 5 — `4jLJCrxrPoc`, `APRRfnfV420`, `Q26GFviHXpc`, `tWb__JLFvBM`, `n__HYvNyZsA` |
| "satisfying miniature house building short" | 10 | 2 | 2 — `xycDcrWT6c8`, `0TdlWueUKiM` |
| "mesmerizing oil painting art short" | 10 | 0 | 0 (no shorts-length rows) |
| "satisfying dumpling folding art short" | 10 | 1 | 1 — `Nk9II04O9B0` |

All 12 searches rc 0; niche guard on S2: `check_query` ALLOW for all
12 queries before issuing; `check_candidate` over all 120 returned
entries: 3 rejections, all anime from the sushi query —
`YSn8WPY_Z3s` (28s, "How Does This Anime Chef Make Perfect Salmon
Sushi?"), `iyd8zVub1oI` (38s, "Making Traditional Japanese Sushi |
Cozy Anime Cooking ASMR") and `xeOlAfcQewc` (127s, "ASMR Sushi Roll –
Tuna & Pickle | Relaxing Anime Cooking"). The two shorts-length ones
were rejected by the guard before the duration/freshness gates, so
they are not counted in the shorts column above. Zero shorts-length
rows were already-excluded known ids (verified first-hand on S2).
Raw per-query output saved at `/tmp/vyr106_q{0..11}.jsonl` on S2.
Not filed (fresh, shorts-length, below the top-8 measured cut):
`UAHU-O3rD0c` (120 views), `s1kG6UEiCkY` (105), `wFSiTTBkV5s` (63),
`Nk9II04O9B0` (54), `tWb__JLFvBM` (46), `n__HYvNyZsA` (14),
`ZzC6ryVCb0M` (7), plus 3 null-view fresh ids — `spuIfDiAee0` (60s),
`X0pvtUnbdkw` (59s), `Pzt4S-yW03s` (29s), all with null uploader in
the flat rows. They are not in this pool's `excluded_ids` and remain
eligible next cycle (VYR-102 precedent).

## Exclusion set — 207 unique ids, verified first-hand

Assembled from the 25 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 090, 091, 093, 094, 095,
096, 097, 098, 099, 100, 101, 102, 104, 105): union of all candidate
ids + all `excluded_ids` fields = 207 ids. Recomputed this run by
direct blob fetch of all 25 pools: base 19 pools = 133 ids (matches
VYR-100's recomputation); + VYR-099/100/101 → 157; + VYR-102 → 165;
+ VYR-104 → 173; + VYR-105 → 207. Full list in
`TASK-VYR-106-POOL.json` (`excluded_ids`). Provenance note: 26 of the
207 enter the union only via VYR-105's `excluded_ids` (its harvest of
the VYR-102/VYR-104 PR pools' below-cut fresh ids, per VYR-105
evidence; my #2296 paired verification confirmed that file's
199-count arithmetic, 175+8+8+8). Pool disjointness: the 8 filed ids
and the 10 below-cut ids are disjoint from the 207-set and from each
other. The S2 exclusion gap stands (S2 manifests absent, carried
decision owed to Muse). VYR-103 (TP3) pool not yet filed — overlap
check vs VYR-103 owed at merge.

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr106_sub_<id>.txt` on server 5).
First pass mis-parsed one file (header line carries the `[info] `
prefix and two codes carry suffixes, `en-orig` / `zh-Hans`); the
counts below are from a corrected recount of the saved raw outputs,
not from re-running the probes:

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `OkRnqxpMyJk` | 157 languages listed (incl. en English) | 0 ("has no subtitles") | 157 auto / 0 uploaded |
| `APRRfnfV420` | none ("has no automatic captions") | 0 | 0 auto / 0 uploaded |
| `8c9tU5_4Lek` | none | 0 | 0 auto / 0 uploaded |
| `0TdlWueUKiM` | none | 0 | 0 auto / 0 uploaded |
| `4jLJCrxrPoc` | none | 0 | 0 auto / 0 uploaded |
| `AdeHUpyi-aw` | none | 0 | 0 auto / 0 uploaded |
| `xycDcrWT6c8` | none | 0 | 0 auto / 0 uploaded |
| `Q26GFviHXpc` | none | 0 | 0 auto / 0 uploaded |

All 8 filed candidates rc 0. Reading note (same as
VYR-094/095/096/097/098/100/102): the 157 is YouTube's auto-caption +
auto-translation list for the video (auto-generated captions
present); it is not 157 authored caption files. No caption-count pass
threshold exists in the board record, so counts are filed as measured
data for the audition, not as pass/fail. Control: the same probe on
run-6 candidate `bRfoNfGBL1o` returns 0 auto / 0 uploaded — identical
to the VYR-094/095/096/097/098/100/102 control results; the method is
not returning canned output.

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`,
`--no-playlist`, `-f 'bv*[height<=1080]+ba/b[height<=1080]'`,
`--merge-output-format mp4`) on candidate `OkRnqxpMyJk`: rc 1, no media
file created (log at `/tmp/vyr106_dl.log` on server 5). Tail: n-challenge
solver failure (deno crash), "n challenge solving failed", "Some
web_embedded client https formats have been skipped as they are missing
a URL. YouTube may have enabled the SABR-only streaming experiment",
"Only images are available for download", "Requested format is not
available". Same standing failure as VYR-056 (Nov 24); VYR-056 leg
CLOSED as unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates
stay BLOCKED, not PENDING/BLOCKED acceptable, proceed) stands. No
download-path repair was attempted (needs coordinator/owner direction
per VYR-056).

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
