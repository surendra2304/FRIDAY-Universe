# TASK-VYR-099: Supervised cycle 13 candidate pool — discovery + machine QA gates — Muse 9

- Task: TASK-VYR-099 (VyralX supervised cycle 13 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-098 cycle 12). Branch `muse9/task-vyr-099`
  (claim 2026-11-28 ~09:56 IST, hub #2045 comment 7234037322;
  assignment: Burn Enforcer 08:50 §B via watch252 amend4 + Burn
  Enforcer 09:30 §C hub 7233590040 "file the pool + branch in your
  next post" — board on main `a174b89e` (board blob `04e13970`) read CLAIMED/owner muse_9/
  branch null/pr null; no competing claim through hub 7233965254).
  Board flips are coordinator-only (ruling 7200564540 §3) — no board
  hunk in this PR.
- Discovery run: 2026-11-28 ~09:58–10:10 IST, on S2 via bridge
  `run_shell` (host friday-universe-vnic-2). Caption-track gates:
  2026-11-28 ~10:12–10:25 IST on VyralX-Server (server 5) via bridge
  `run_shell` server=5. Loop stays OFF, uploader paused, renders held
  unlisted; no renders in this task — pool refresh only.
- Pattern: TASK-VYR-098 cycle 12 (Muse 9, PR #2242 merged `64822f55`,
  Muse 5 VERIFIED review 6095282491) — same flat-search method and
  gates. TASK-VYR-090 cycle 8 (PR #2251 merged `d94fc4b2`, TP12
  VERIFIED review 6095401148) likewise. VYR-100 (Muse 8, PR #2262
  open) and VYR-101 (Muse 14, PR #2266 open) candidates are in this
  cycle's exclusion set regardless of merge state.
- Numbering flag (carried from the claim post): WATCH254 §C.6 labels
  VYR-102 as cycle 13 as well; this task proceeds on the
  TASK-VYR-099 evidence file under its board title (cycle 13).
  Numbering ruling owed by the coordinator.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py`: `check_query` for all 12
queries before issuing, `check_candidate` for all 120 returned
entries after (candidate record fields from the flat rows). Raw
per-query output saved at `/tmp/vyr099_q{0..11}.jsonl` on S2;
nothing was written to the S2 checkout (tracked tree clean before
and after, verified this run).

Twelve queries ran (not six): the first nine yielded only 8 fresh
shorts-length candidates (1 further shorts-length row was already
excluded), so three more fresh-topic queries ran in the same session
for headroom above the usual 8-candidate pool. All twelve are
disclosed below; freshness is verified against the 60 candidate
queries recorded in the 19 pool JSONs on main plus the 7 candidate
queries in the VYR-100/VYR-101 branch pools, plus prior zero-yield
topics from the evidence tables (needle felting, terrarium, origami,
crochet amigurumi, rug tufting, kite flying, paper marbling,
ice-cream rolling, shadow puppetry, bubble tea) — diamond painting,
hydro dipping, wire wrapping, ink in water, cheese pulling,
miniature pottery, hula hoop, knife sharpening, watercolor bloom,
jump rope, gift wrapping and sand bottle art are all new topics.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `69ff042b1b5963b5d0216348f11d737d2a67a9e2`
  (tracked tree clean before and after this run, pre-existing untracked
  scratch only — left as found). `VyralX.service`: failed (masked
  sleeping copy by fleet design; the live VyralX is on VyralX-Server).
  `VyralX-Daemon.service`: inactive (loop OFF, as ordered). `yt-dlp`
  `/usr/local/bin/yt-dlp` 2026.10.21 used for search (venv312 python
  used for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/097/098/090):
  no cookie jar, no published/rejected manifests. Exclusion set loaded
  this run: the 149-id repo union (see below) — no S2 manifests back
  it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200 (`{"status":"ok","service":"vyralx","version":"0.2.0"}`,
  observed 2026-11-28T04:29:52Z). The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes, 2026-11-28) EXISTS
  there — existence checked only, contents never read. `yt-dlp`
  `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21. The live VyralX
  service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-099-POOL.json`.
Twelve shorts-length rows were found; one (`An4zMciturw`, 38 views,
ink-in-water query) is already in the exclusion set from a prior
pool and is not fresh. Eleven fresh shorts-length candidates remain;
one (`cvCUGmteGFk`, gift-wrapping query) carries null view_count and
null uploader in the flat row and cannot be ranked — it is not
filed. The top 8 of the 10 rankable fresh candidates by views, all
with a measured caption gate, are filed. No view gate exists in the
acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Double Dutch Tricks - Jump Rope Workout with 2 ropes" (YouTube, id `c5F8UH2MKeM`) | YouTube search, query "amazing jump rope trick short"; https://youtube.com/shorts/c5F8UH2MKeM | 28s — PASS (15–60s) | 84,260; uploader Jump Rope Expert Mira Wate | Duration PASS; niche guard PASS; caption-track MEASURED 157 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Blue Sea with Dolphins in Sunset Sand Art timelapse - Sand Art Bottle \| Coloured Sand \| Sandscape" (YouTube, id `q2A9znXhNNs`) | YouTube search, query "incredible sand bottle art short"; https://youtube.com/shorts/q2A9znXhNNs | 53s — PASS | 1,171; uploader SandScape Art | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "VEVOR Mini Pottery Wheel" (YouTube, id `0XxvKXdJ2U4`) | YouTube search, query "incredible miniature pottery wheel short"; https://youtube.com/shorts/0XxvKXdJ2U4 | 56s — PASS | 790; uploader We Craft For Life | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 4 | "🧀 Ultimate Cheese Pull Pizza ASMR 🍕 \| Satisfying Stretch & Crunch" (YouTube, id `dPCyrLpMS44`) | YouTube search, query "satisfying cheese pulling stretch short"; https://youtube.com/shorts/dPCyrLpMS44 | 31s — PASS | 143; uploader Loopzy | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "Mesmerizing Abstract Ink Clouds in Water #shorts #abstractart #water" (YouTube, id `2bZjqyrHZK0`) | YouTube search, query "mesmerizing ink in water art short"; https://youtube.com/shorts/2bZjqyrHZK0 | 29s — PASS | 142; uploader Serene Space | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "\"Dynamic Splatters: Abstract Art Ink Paint Explodes in Vibrant Background\"" (YouTube, id `mG6r3rrdBpI`) | YouTube search, query "mesmerizing ink in water art short"; https://youtube.com/shorts/mG6r3rrdBpI | 23s — PASS | 29; uploader StockVista | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "Ultimate Cheese Pull Pizza ASMR" (YouTube, id `cIhKWM8AMqE`) | YouTube search, query "satisfying cheese pulling stretch short"; https://youtube.com/shorts/cIhKWM8AMqE | 15s — PASS (gate edge) | 20; uploader AI_TREND_VIDEO | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "The Ultimate Grilled Cheese Pull! 🧀🔥" (YouTube, id `Rxw0X_GQkso`) | YouTube search, query "satisfying cheese pulling stretch short"; https://youtube.com/shorts/Rxw0X_GQkso | 25s — PASS | 11; uploader Food Planet By Mahreen | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidate 1 is workout-framed
(Double Dutch with 2 ropes); candidate 3 is a product/brand title
(VEVOR) — licence/origin re-check owed at QA; candidate 6 is from a
stock-footage uploader (StockVista) — same re-check; candidate 7 is
from an AI-named uploader (AI_TREND_VIDEO) at the 15s gate edge —
origin re-check owed; candidates 6–8 are essentially unviewed
(29 / 20 / 11 views). Honest traction note: the top candidate has
84,260 views — above cycle 12's top (5,015) but below cycle 8's top
(154,376); below it the pool is thin (1,171 / 790, then ≤143) because
seven of twelve topics yielded only long-form tutorials or
sub-15s clips. Traction does not imply licence clearance. Candidates
are filed by the machine gates only; the audition judges suitability.

## YouTube discovery: 8 filed candidates from 120 results — evidence

| Query | Returned | Shorts-length | Fresh shorts |
|---|---|---|---|
| "satisfying diamond painting art short" | 10 | 0 | 0 (all 10 over 60s; closest 545s) |
| "mesmerizing hydro dipping art short" | 10 | 0 | 0 (all 10 over 60s; closest 72s) |
| "incredible wire wrapping jewelry short" | 10 | 0 | 0 (all 10 over 60s; closest 471s) |
| "mesmerizing ink in water art short" | 10 | 4 | 3 — `2bZjqyrHZK0`, `mG6r3rrdBpI`, `R_NvimTuEUg` (one 42s row `An4zMciturw` already excluded; one 11s row under the gate) |
| "satisfying cheese pulling stretch short" | 10 | 3 | 3 — `dPCyrLpMS44`, `cIhKWM8AMqE`, `Rxw0X_GQkso` (six rows 6–9s under the gate; one 161s over) |
| "incredible miniature pottery wheel short" | 10 | 1 | 1 — `0XxvKXdJ2U4` |
| "amazing hula hoop trick short" | 10 | 0 | 0 (closest 72s over; one 8s under) |
| "satisfying knife sharpening short" | 10 | 0 | 0 (closest 76s over; one 9s under) |
| "mesmerizing watercolor bloom art short" | 10 | 0 | 0 (closest 61s — over by 1s) |
| "amazing jump rope trick short" | 10 | 1 | 1 — `c5F8UH2MKeM` |
| "satisfying gift wrapping art short" | 10 | 1 | 1 — `cvCUGmteGFk` (null view_count/uploader, unrankable; see below) |
| "incredible sand bottle art short" | 10 | 2 | 2 — `q2A9znXhNNs`, `5uI9ZDMxDZI` |

All 12 searches rc 0; niche guard on S2: `check_query` ALLOW for all
12 queries before issuing; `check_candidate` over all 120 returned
entries: 0 rejections. Raw per-query output saved at
`/tmp/vyr099_q{0..11}.jsonl` on S2. Flat-row anomaly disclosed: all
10 gift-wrapping rows carried `view_count` and `uploader` as null
(same class of anomaly as cycle 12's kite query); its one
shorts-length row `cvCUGmteGFk` (46s) is therefore unrankable and
not filed. Not filed (fresh, shorts-length, measured, below the
top-8 cut): `5uI9ZDMxDZI` (3 views), `R_NvimTuEUg` (1 view). They
are not in this pool's `excluded_ids` and remain eligible next cycle.

## Exclusion set — 149 unique ids, verified first-hand

Assembled from the 19 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 090, 091, 093, 094, 095,
096, 097, 098) plus the VYR-100 pool on branch `muse8/task-vyr-100`
(PR #2262, open) and the VYR-101 pool on branch `muse14/task-vyr-101`
(PR #2266, open): union of all candidate ids + all `excluded_ids`
fields = 149 ids, exactly the 133-id main union (VYR-098's 117 plus
its 8 candidates plus VYR-090's 8 candidates; the same 133 M14
recomputed for VYR-101) plus VYR-100's 8 and VYR-101's 8 candidates
(overlap 0; verified by direct recomputation this run; full list in
`TASK-VYR-099-POOL.json` (`excluded_ids`)). Pool disjointness: the 8
filed ids are disjoint from the 149-set and from each other; all 11
fresh shorts-length ids are likewise disjoint from the 149-set
(the 12th shorts-length row, `An4zMciturw`, is inside it). The S2
exclusion gap stands (S2 manifests absent, carried decision owed to
Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate (raw outputs at `/tmp/vyr099_sub_<id>.txt` on server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `c5F8UH2MKeM` | 157 languages listed (incl. en English) | 0 ("has no subtitles") | 157 auto / 0 uploaded |
| `q2A9znXhNNs` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `0XxvKXdJ2U4` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `dPCyrLpMS44` | none | 0 | 0 auto / 0 uploaded |
| `2bZjqyrHZK0` | none | 0 | 0 auto / 0 uploaded |
| `mG6r3rrdBpI` | none | 0 | 0 auto / 0 uploaded |
| `cIhKWM8AMqE` | none | 0 | 0 auto / 0 uploaded |
| `Rxw0X_GQkso` | none | 0 | 0 auto / 0 uploaded |

All 8 filed candidates rc 0 (the two below-cut fresh candidates
`5uI9ZDMxDZI` and `R_NvimTuEUg` were also probed rc 0 at 0 auto /
0 uploaded; counts verified against the raw "Available automatic
captions" / "has no automatic captions" headers this run). Reading
note (same as VYR-094/095/096/097/098/090): the 157 is YouTube's
auto-caption + auto-translation list for the video (auto-generated
captions present); it is not 157 authored caption files. No
caption-count pass threshold exists in the board record, so counts
are filed as measured data for the audition, not as pass/fail.
Control: the same probe on run-6 candidate `bRfoNfGBL1o` returns
0 auto / 0 uploaded — identical to the VYR-094/095/096/097/098/090
control results; the method is not returning canned output. S2 has
no jar, so the gate cannot run there (re-probed this run: metadata
fetch on `c5F8UH2MKeM` from S2 fails rc 1, "Sign in to confirm
you're not a bot", 659 bytes of error output, no metadata).

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`)
on candidate `c5F8UH2MKeM`: rc 1, no media file created (log at
`/tmp/vyr099_dl.log` on server 5). Tail: n-challenge solver failure,
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
  tested PARTIAL (live discovery 12/12 queries rc 0; caption-track
  gates measured live 10/10 probed fresh candidates + control, all
  rc 0; BGM/watermark/loudness BLOCKED on a re-probed download path) /
  merged NO (awaiting peer review/merge) / deployed N/A (no service
  changed; S2 tree left as found) / production-verified PARTIAL (pool
  filed from a real live discovery run + measured caption gates;
  render awaits the download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 9
