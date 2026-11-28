# TASK-VYR-098: Supervised cycle 12 candidate pool — discovery + machine QA gates — Muse 9

- Task: TASK-VYR-098 (VyralX supervised cycle 12 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-097 cycle 11). Branch `muse9/task-vyr-098`
  (claim 2026-11-28 06:58 IST, hub #2045 comment 7231690319;
  assignment: WATCH248 §B + WATCH249 board — board on main `55a11a60`
  (blob `46dd5277`) read AVAILABLE/owner muse_9/branch null/pr null;
  no competing claim through hub 7231661357). Board flips are
  coordinator-only (ruling 7200564540 §3) — no board hunk in this PR.
- Discovery run: 2026-11-28 ~07:00 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~07:03–07:05 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool refresh only.
- Pattern: TASK-VYR-097 cycle 11 (Muse 9, PR #2232 merged `220622c8`,
  M14 VERIFIED review 6094780025) — same flat-search method and gates.
  VYR-096 cycle 10 (PR #2218, head `7842e850`) still IN_REVIEW at claim
  time (0 reviews; paired verdict re-slotted to Muse 8, due ~07:45 IST
  per Burn Enforcer 06:45 §B hub 7231544120); its 8 candidates are in
  this cycle's exclusion set regardless.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 9
queries before issuing, `check_candidate` for all 90 returned entries
after (title / description / channel / uploader fields from the flat
rows). Raw per-query output saved at `/tmp/vyr098_q{0..8}.jsonl` on
S2; nothing was written to the S2 checkout (tracked tree clean before
and after, verified this run).

Nine queries ran (not six): the first six yielded only 4 shorts-length
fresh candidates, so three more fresh-topic queries ran in the same
session to reach the usual 8-candidate pool. All nine are disclosed
below; freshness is verified against the 51 candidate queries recorded
in the 17 prior pool JSONs (16 on main plus VYR-096 on its branch)
plus cycle 10/11 zero-yield topics from their evidence tables
(needle felting, terrarium, origami, crochet amigurumi, rug tufting) —
chocolate tempering, kite flying, paper marbling, matchstick art,
ice-cream rolling, shadow puppetry, henna mehndi, bubble tea and snow
globes are all new topics.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `094dedb20328aec196e85264b5593a005565e6c6`
  (tracked tree clean before and after this run, pre-existing untracked
  scratch only — left as found). `VyralX.service`: failed (masked
  sleeping copy by fleet design; the live VyralX is on VyralX-Server).
  `VyralX-Daemon.service`: inactive (loop OFF, as ordered). `yt-dlp`
  `/usr/local/bin/yt-dlp` 2026.10.21 used for search (venv312 python
  used for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/097):
  no cookie jar, no published/rejected manifests. Exclusion set loaded
  this run: the 117-id repo union (see below) — no S2 manifests back
  it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200 (`{"status":"ok","service":"vyralx","version":"0.2.0"}`),
  up 3 days 15:39 at 01:35:24 UTC, load 0.25. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes, 2026-11-28) EXISTS
  there — existence checked only, contents never read. `yt-dlp`
  `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21. The live VyralX
  service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-098-POOL.json`.
Thirteen shorts-length fresh candidates were found; the top 8 by views
with a measured caption gate are filed. Candidate `6ox1IU0Ud1s`
(185 views, snow-globe query) ranked 7th by views but its caption
probe failed rc 1 twice ("No video formats found!") — it is NOT filed;
`xGA3KV_EuX8` (70 views) is filed as the measured replacement. Four
further fresh shorts below the cut are not filed (see discovery table
note). No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Handmade Christmas Gift Ideas - Mesmerizing Glitter Mason Jar Snow Globe" (YouTube, id `q-C7pO9SkMg`) | YouTube search, query "mesmerizing snow globe making short"; https://youtube.com/shorts/q-C7pO9SkMg | 48s — PASS (15–60s) | 5,015; uploader Jolly Match | Duration PASS; niche guard PASS; caption-track MEASURED 0 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "how to temper chocolate using seeding method ." (YouTube, id `xmZKgMCohcQ`) | YouTube search, query "satisfying chocolate tempering art short"; https://youtube.com/shorts/xmZKgMCohcQ | 35s — PASS | 2,573; uploader Rull's Kitchen | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 3 | "Matchstick Marvels! Check Out These Amazing Replicas of Notable Landmarks Made Out of Matchsticks!" (YouTube, id `5NCEI6SLLFs`) | YouTube search, query "incredible matchstick art building short"; https://youtube.com/shorts/5NCEI6SLLFs | 55s — PASS | 691; uploader b/60 | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 4 | "Captivating 3D Crystal Snow Globes" (YouTube, id `2pbi4_FVRMY`) | YouTube search, query "mesmerizing snow globe making short"; https://youtube.com/shorts/2pbi4_FVRMY | 51s — PASS | 335; uploader Mr. Winder | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 5 | "Oddly Satisfying Video Henna Art \| Satisfying Video \| Mehndi art \| Unicorn Henna Art" (YouTube, id `4hC-DXXxpvU`) | YouTube search, query "satisfying henna mehndi art short"; https://youtube.com/shorts/4hC-DXXxpvU | 58s — PASS | 310; uploader Bena Art | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 6 | " 15 Most Beautiful Mehndi Designs 😍 \| Satisfying Henna Compilation #Shorts #Viral" (YouTube, id `AJMxaCnWuBs`) | YouTube search, query "satisfying henna mehndi art short"; https://youtube.com/shorts/AJMxaCnWuBs | 28s — PASS | 303; uploader Design By Dimpi | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 7 | "Building a Matchstick Mansion from Scratch \| Incredible 3D Art!" (YouTube, id `k6UquVMeVdo`) | YouTube search, query "incredible matchstick art building short"; https://youtube.com/shorts/k6UquVMeVdo | 60s — PASS (gate edge) | 73; uploader Majestick | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 8 | "HOW TO TEMPER CHOCOLATE🍫 \| @EverythingFood102" (YouTube, id `xGA3KV_EuX8`) | YouTube search, query "satisfying chocolate tempering art short"; https://youtube.com/shorts/xGA3KV_EuX8 | 57s — PASS | 70; uploader Everything Food102 | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidate 1 is seasonal
Christmas-gift framing (timely on 2026-11-28, but seasonal);
candidate 6 is titled a compilation — licence/origin re-check owed at
QA; candidate 4 reads as a product showcase (crystal snow globes) —
licence/origin re-check owed; candidate 3 is landmark replicas —
same re-check; candidates 7–8 are essentially unviewed (73 / 70
views). Honest traction note: the top candidate has 5,015 views, well
below cycle 11's top (164,282) and cycle 10's top (1,531,636) — this
cycle's topics (chocolate tempering, henna, matchstick, snow globes)
yielded mostly long-form tutorials, and the shorts-length tail is
thin. Traction does not imply licence clearance. Candidates are filed
by the machine gates only; the audition judges suitability.

## YouTube discovery: 8 filed candidates from 90 results — evidence

| Query | Returned | Shorts-length | Fresh shorts |
|---|---|---|---|
| "satisfying chocolate tempering art short" | 10 | 2 | 2 — `xmZKgMCohcQ`, `xGA3KV_EuX8` (one 9s row under the gate) |
| "amazing kite flying trick short" | 10 | 0 | 0 (all 10 over 60s; closest 96s; all 10 rows carried null view_count/uploader) |
| "mesmerizing marble paper marbling short" | 10 | 0 | 0 (all 10 over 60s; closest 64s) |
| "incredible matchstick art building short" | 10 | 2 | 2 — `k6UquVMeVdo`, `5NCEI6SLLFs` |
| "satisfying ice cream rolling art short" | 10 | 0 | 0 (all 10 over 60s; all from one channel, 595–962s) |
| "amazing shadow puppet art short" | 10 | 0 | 0 (all 10 over 60s; closest 71s) |
| "satisfying henna mehndi art short" | 10 | 2 | 2 — `AJMxaCnWuBs`, `4hC-DXXxpvU` |
| "amazing bubble tea making short" | 10 | 0 | 0 (all 10 over 60s; 1 niche rejection — see below) |
| "mesmerizing snow globe making short" | 10 | 7 | 7 — `q-C7pO9SkMg`, `2pbi4_FVRMY`, `VcDe4P27yqU`, `PfuS_Yj2VHw`, `jE0qtOUueTI`, `6ox1IU0Ud1s`, `MgpmPBdNQ9I` |

All 9 searches rc 0; niche guard on S2: `check_query` ALLOW for all
9 queries before issuing; `check_candidate` over all 90 returned
entries: 1 rejection — bubble-tea row `1EtE0BdMYqs` ("Boba Milk Tea
from Great Pretender | Anime with Alvin", 494s, over the duration
gate regardless) rejected as banned niche "anime compilations"
(matched 'anime'). Raw per-query output saved at
`/tmp/vyr098_q{0..8}.jsonl` on S2. Flat-row anomaly disclosed: all 10
kite-query rows carried `view_count` and `uploader` as null (same
class of anomaly as cycle 11's LEGO query); the query yielded no
shorts-length rows, so no null-view candidate is filed this cycle.
Not filed (fresh, shorts-length, below the top-8 measured cut):
`6ox1IU0Ud1s` (185 views — caption probe failed, see below),
`jE0qtOUueTI` (49), `MgpmPBdNQ9I` (41), `PfuS_Yj2VHw` (17),
`VcDe4P27yqU` (14). They are not in this pool's `excluded_ids` and
remain eligible next cycle.

## Exclusion set — 117 unique ids, verified first-hand

Assembled from the 16 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 091, 093, 094, 095, 097)
plus the VYR-096 pool on branch `muse9/task-vyr-096` (PR #2218, not
yet merged at run time): union of all candidate ids + all
`excluded_ids` fields = 117 ids, exactly VYR-097's 109
`excluded_ids` plus its 8 candidates (overlap 0; verified by direct
recomputation this run; full list in `TASK-VYR-098-POOL.json`
(`excluded_ids`)). Pool disjointness: the 8 filed ids are disjoint
from the 117-set and from each other; all 13 fresh shorts-length ids
are likewise disjoint from the 117-set. The S2 exclusion gap stands
(S2 manifests absent, carried decision owed to Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr098_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `q-C7pO9SkMg` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `xmZKgMCohcQ` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `5NCEI6SLLFs` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `2pbi4_FVRMY` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `4hC-DXXxpvU` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `AJMxaCnWuBs` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `k6UquVMeVdo` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `xGA3KV_EuX8` | 157 languages listed | 0 | 157 auto / 0 uploaded |

All 8 filed candidates rc 0. Reading note (same as
VYR-094/095/096/097): the 157 is YouTube's auto-caption +
auto-translation list for the video (auto-generated captions
present); it is not 157 authored caption files. No caption-count
pass threshold exists in the board record, so counts are filed as
measured data for the audition, not as pass/fail. Control: the same
probe on run-6 candidate `bRfoNfGBL1o` returns 0 auto / 0 uploaded —
identical to the VYR-094/095/096/097 control results; the method is
not returning canned output. Failed probe disclosed: `6ox1IU0Ud1s`
failed rc 1 twice (initial + retry, "No video formats found!" after
n-challenge/SABR warnings; raw at `/tmp/vyr098_sub_6ox1IU0Ud1s.txt`
and `..._retry.txt` on server 5) — its caption gate is UNMEASURED,
which is why it is not filed. S2 has no jar, so the gate cannot run
there (re-probed this run: metadata fetch on `q-C7pO9SkMg` from S2
fails rc 1, "Sign in to confirm you're not a bot", 528 bytes of
error output, no metadata).

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`)
on candidate `q-C7pO9SkMg`: rc 1, no media file created (log at
`/tmp/vyr098_dl.log` on server 5). Tail: n-challenge solver failure,
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
  gates measured live 8/8 filed + control, 1 further probe failed rc 1
  twice and its candidate dropped; BGM/watermark/loudness BLOCKED on
  a re-probed download path) / merged NO (awaiting peer review/merge)
  / deployed N/A (no service changed; S2 tree left as found) /
  production-verified PARTIAL (pool filed from a real live discovery
  run + measured caption gates; render awaits the download-path
  repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 9
