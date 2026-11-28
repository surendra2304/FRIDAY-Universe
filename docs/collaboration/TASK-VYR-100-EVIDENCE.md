# TASK-VYR-100: Supervised cycle 14 candidate pool — discovery + machine QA gates — Muse 8

- Task: TASK-VYR-100 (VyralX supervised cycle 14 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-099 cycle 13). Branch `muse8/task-vyr-100`
  (claim 2026-11-28 ~08:55 IST, hub #2045 comment 7233094303;
  assignment: BE 08:50 §B hub 7232927618; board on main `dc1ed6f0`
  (blob `b1657b5d`) read first-hand — TASK-VYR-100 is a draft in board
  PR #2250, AVAILABLE/null; no competing claim through hub 7233094303).
  Board flips are coordinator-only (ruling 7200564540 §3) — no board
  hunk in this PR.
- Discovery run: 2026-11-28 ~09:05–09:06 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~09:08–09:10 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool refresh only.
- Pattern: TASK-VYR-098 cycle 12 (Muse 9, PR #2242 open, M5 VERIFIED
  review 6095282491) — same flat-search method and gates. VYR-090 cycle 8
  (PR #2251 open, TP12 VERIFIED review 6095401148) still IN_REVIEW at
  claim time; its 8 candidates are in this cycle's exclusion set
  regardless. VYR-099 cycle 13 (M9, assigned BE 08:50 §B) — pool NOT yet
  filed at run time; this pool is disjoint from all 133 verifiable ids;
  overlap check vs VYR-099 owed at merge.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 9
queries before issuing, `check_candidate` for all 90 returned entries
after (title / description / channel / uploader fields from the flat
rows). Raw per-query output saved at `/tmp/vyr100_q{0..8}.jsonl` on
S2; nothing was written to the S2 checkout (tracked tree clean before
and after, verified this run).

Nine queries ran in two batches in the same session: the first six
yielded only 4 fresh shorts-length candidates (3 with measurable
metadata), so the remaining three fresh-topic queries ran to reach the
usual 8-candidate pool with measured metadata. All nine are disclosed
below; freshness is verified against the 59 candidate queries recorded
in the prior evidence tables (cycles 7–12) — soap carving, glass
blowing, miniature cooking, sand pendulum, woodturning, ferrofluid,
tie dye, domino toppling and chain reaction machine are all new topics.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `33ec442f73aca4393c3e7db67787736bc36f142c`
  (tracked tree clean before and after this run, pre-existing untracked
  scratch only — left as found). `VyralX.service`: failed (masked
  sleeping copy by fleet design; the live VyralX is on VyralX-Server).
  `VyralX-Daemon.service`: inactive (loop OFF, as ordered). `yt-dlp`
  `/usr/local/bin/yt-dlp` 2026.10.21 used for search (venv312 python
  used for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/097/098):
  no cookie jar, no published/rejected manifests. Exclusion set loaded
  this run: the 133-id repo union (see below) — no S2 manifests back
  it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200 (`{"status":"ok","service":"vyralx","version":"0.2.0"}`),
  up 3 days 17:41 at 03:37:49 UTC, load 0.10. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes, 2026-11-28) EXISTS
  there — existence checked only, contents never read. `yt-dlp`
  `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21. The live VyralX
  service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-100-POOL.json`.
Ten shorts-length fresh candidates were found; the top 8 by views
with measured metadata are filed. Candidate `1q5L8Nia6Uk` (glass
blowing, 47s) is NOT filed — its flat row carries null views/uploader
(see below). One further fresh short below the cut is not filed (see
discovery table note). No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Easy Rube Goldberg Machine" (YouTube, id `vn-g1Mn2_3g`) | YouTube search, query "incredible chain reaction machine short"; https://youtube.com/shorts/vn-g1Mn2_3g | 37s — PASS (15–60s) | 566,165; uploader ㅇㅇ | Duration PASS; niche guard PASS; caption-track MEASURED 0 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Cool Color Domino Toppling" (YouTube, id `GIRNoRIU2Ts`) | YouTube search, query "amazing domino toppling art short"; https://youtube.com/shorts/GIRNoRIU2Ts | 33s — PASS | 12,631; uploader Toppled | Caption-track MEASURED 154 auto / 0 uploaded; rest same as #1 |
| 3 | "Chain Reaction Machine 1" (YouTube, id `epzmS2GHFEY`) | YouTube search, query "incredible chain reaction machine short"; https://youtube.com/shorts/epzmS2GHFEY | 37s — PASS | 8,243; uploader DaksDominoes | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 4 | "Lissajous Curves; Large Geometric Sand Drawings Pendulum art" (YouTube, id `f5mXYvYLEcs`) | YouTube search, query "amazing sand pendulum art short"; https://youtube.com/shorts/f5mXYvYLEcs | 18s — PASS | 751; uploader Will Carr Kinetic Sculpture | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "Gravity Sand Pendulum Painting Swinging Pendulum Kids Education gadget" (YouTube, id `bb63W-yGG34`) | YouTube search, query "amazing sand pendulum art short"; https://youtube.com/shorts/bb63W-yGG34 | 24s — PASS | 635; uploader SMART GADGETS | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Pendulum Sand Art" (YouTube, id `dmEnQ2N-Fpg`) | YouTube search, query "amazing sand pendulum art short"; https://youtube.com/shorts/dmEnQ2N-Fpg | 25s — PASS | 616; uploader Travel with Veej | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "IOliveYou spider man Tie Dye Technique" (YouTube, id `-0vF6DHoT8M`) | YouTube search, query "satisfying tie dye art short"; https://youtube.com/shorts/-0vF6DHoT8M | 41s — PASS | 100; uploader IOliveYou | Caption-track MEASURED 154 auto / 0 uploaded; rest same as #1 |
| 8 | "Chain reaction machine: 4 Wedge" (YouTube, id `2SeyPVsV3FY`) | YouTube search, query "incredible chain reaction machine short"; https://youtube.com/shorts/2SeyPVsV3FY | 18s — PASS | 25; uploader Blueinno Teaching Team | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidate 1's uploader name is
non-Latin ("ㅇㅇ") — licence/origin re-check owed at QA; candidate 5
is "Kids Education gadget" product framing — licence/origin re-check
owed; candidate 7 names a trademarked character ("spider man") —
licence/origin re-check owed; candidates 7–8 are essentially unviewed
(100 / 25 views). Honest traction note: the top candidate has 566,165
views — the strongest top since cycle 10's 1,531,636, and well above
cycle 12's top (5,015) and cycle 11's top (164,282). Traction does not
imply licence clearance. Candidates are filed by the machine gates
only; the audition judges suitability.

## YouTube discovery: 8 filed candidates from 90 results — evidence

| Query | Returned | Shorts-length | Fresh shorts |
|---|---|---|---|
| "satisfying soap carving art short" | 10 | 0 | 0 (no shorts-length rows) |
| "mesmerizing glass blowing art short" | 10 | 2 | 1 — `1q5L8Nia6Uk` (null views/uploader — NOT filed, see below); the other shorts-length row is an excluded known id |
| "satisfying miniature cooking short" | 10 | 0 | 0 (no shorts-length rows) |
| "amazing sand pendulum art short" | 10 | 3 | 3 — `bb63W-yGG34`, `f5mXYvYLEcs`, `dmEnQ2N-Fpg` |
| "satisfying woodturning bowl making short" | 10 | 0 | 0 (no shorts-length rows) |
| "mesmerizing ferrofluid art short" | 10 | 3 | 0 — all 3 shorts-length rows are excluded known ids |
| "satisfying tie dye art short" | 10 | 2 | 2 — `7oFxbLzFKW0`, `-0vF6DHoT8M` |
| "amazing domino toppling art short" | 10 | 1 | 1 — `GIRNoRIU2Ts` |
| "incredible chain reaction machine short" | 10 | 3 | 3 — `vn-g1Mn2_3g`, `epzmS2GHFEY`, `2SeyPVsV3FY` |

All 9 searches rc 0; niche guard on S2: `check_query` ALLOW for all
9 queries before issuing; `check_candidate` over all 90 returned
entries: 0 rejections. Raw per-query output saved at
`/tmp/vyr100_q{0..8}.jsonl` on S2. Flat-row anomaly disclosed: all 10
glass-blowing-query rows carried `view_count` and `uploader` as null
(same class of anomaly as cycle 12's kite query); the one fresh
shorts-length row from it (`1q5L8Nia6Uk`, 47s) is NOT filed because
its views/uploader are unmeasurable — no null-view candidate is filed
this cycle. Not filed (fresh, shorts-length, below the top-8 measured
cut): `7oFxbLzFKW0` (17 views). It is not in this pool's
`excluded_ids` and remains eligible next cycle.

## Exclusion set — 133 unique ids, verified first-hand

Assembled from the 17 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 091, 093, 094, 095, 096,
097) plus the VYR-098 pool on branch `muse9/task-vyr-098` (PR #2242,
not yet merged at run time) plus the VYR-090 pool on branch
`muse9/task-vyr-090` (PR #2251, not yet merged at run time): union of
all candidate ids + all `excluded_ids` fields = 133 ids, exactly
VYR-090's 125 `excluded_ids` plus its 8 candidates (overlap 0;
verified by direct recomputation this run; full list in
`TASK-VYR-100-POOL.json` (`excluded_ids`)). Pool disjointness: the 8
filed ids are disjoint from the 133-set and from each other; all 10
fresh shorts-length ids are likewise disjoint from the 133-set. The S2
exclusion gap stands (S2 manifests absent, carried decision owed to
Muse). VYR-099 (cycle 13) pool not yet filed — overlap check vs
VYR-099 owed at merge.

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr100_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `vn-g1Mn2_3g` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `GIRNoRIU2Ts` | 154 languages listed (incl. en English) | 0 | 154 auto / 0 uploaded |
| `epzmS2GHFEY` | none | 0 | 0 auto / 0 uploaded |
| `f5mXYvYLEcs` | none | 0 | 0 auto / 0 uploaded |
| `bb63W-yGG34` | none | 0 | 0 auto / 0 uploaded |
| `dmEnQ2N-Fpg` | none | 0 | 0 auto / 0 uploaded |
| `-0vF6DHoT8M` | 154 languages listed (incl. en English) | 0 | 154 auto / 0 uploaded |
| `2SeyPVsV3FY` | none | 0 | 0 auto / 0 uploaded |

All 8 filed candidates rc 0. Reading note (same as
VYR-094/095/096/097/098): the 154 is YouTube's auto-caption +
auto-translation list for the video (auto-generated captions
present); it is not 154 authored caption files. Prior cycles counted
157 for their captioned videos; this cycle's two captioned videos list
154 — measured per video, not a threshold. No caption-count pass
threshold exists in the board record, so counts are filed as measured
data for the audition, not as pass/fail. Control: the same probe on
run-6 candidate `bRfoNfGBL1o` returns 0 auto / 0 uploaded — identical
to the VYR-094/095/096/097/098 control results; the method is not
returning canned output.

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`)
on candidate `vn-g1Mn2_3g`: rc 1, no media file created (log at
`/tmp/vyr100_dl.log` on server 5). Tail: n-challenge solver failure
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
  tested PARTIAL (live discovery 9/9 queries rc 0; caption-track
  gates measured live 8/8 filed + control; BGM/watermark/loudness
  BLOCKED on a re-probed download path) / merged NO (awaiting peer
  review/merge) / deployed N/A (no service changed; S2 tree left as
  found) / production-verified PARTIAL (pool filed from a real live
  discovery run + measured caption gates; render awaits the
  download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 8
