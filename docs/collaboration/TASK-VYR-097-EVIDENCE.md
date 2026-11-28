# TASK-VYR-097: Supervised cycle 11 candidate pool — discovery + machine QA gates — Muse 9

- Task: TASK-VYR-097 (VyralX supervised cycle 11 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-096 cycle 10). Branch `muse9/task-vyr-097`
  (fresh claim 2026-11-28 05:59 IST, hub #2045 comment 7230951393;
  assignment: Burn Enforcer 05:35 §B hub 7230673723 re-slotting
  VYR-097 to the pool with fresh-claim permission + WATCH247 §C hub
  7230716540 adopting it; board on main `fac8c0eb` still read
  CLAIMED/muse_9, branch null, pr null — the AVAILABLE flip rides
  WATCH248 and had not landed at claim; no competing claim on the hub
  through comment 7230841822). Board flips are coordinator-only
  (ruling 7200564540 §3) — no board hunk in this PR.
- Discovery run: 2026-11-28 ~06:01 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~06:05–06:07 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool refresh only.
- Pattern: TASK-VYR-096 cycle 10 (Muse 9, PR #2218, head `7842e850`,
  IN_REVIEW at claim time) — same flat-search method and gates.
  VYR-090 (cycle 8, Muse TP5) still has no pool filed (no
  TASK-VYR-090-POOL.json on main); cycle 11 proceeds as assigned.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py` (9061 bytes, same size as
main): `check_query` for all 6 queries before issuing,
`check_candidate` for all 60 returned entries after (title /
description / channel / uploader fields from the flat rows). Raw
per-query output saved at `/tmp/vyr097_q{0..5}.jsonl` on S2; nothing
was written to the S2 checkout (tracked tree clean before and after,
verified this run).

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `094dedb20328aec196e85264b5593a005565e6c6`
  (checkout on another worker's branch
  `musetp13/task-frd-046-checkpoint-2`; tracked tree clean before and
  after this run, pre-existing untracked scratch only — left as
  found). `VyralX.service`: failed (masked sleeping copy by fleet
  design; the live VyralX is on VyralX-Server); `/health` on 8010
  returns 000. `VyralX-Daemon.service`: inactive (loop OFF, as
  ordered). `yt-dlp` `/usr/local/bin/yt-dlp` 2026.10.21 used for
  search (venv312 python used for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096): no
  cookie jar, no published/rejected manifests. Exclusion set loaded
  this run: the 109-id repo union (see below) — no S2 manifests back
  it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200, up 3 days 14:34 at 00:30:50 UTC, load 0.00. The
  pipeline cookie jar (`VyralX/data/youtube_cookies.txt`, 3146 bytes,
  2026-11-27) EXISTS there — existence checked only, contents never
  read. `yt-dlp` `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21
  (Python 3.10.22). The live VyralX service was not touched on either
  host.

## Candidate pool — ranked by views (most-popular first; unknown views last)

Machine-readable pool: `docs/collaboration/TASK-VYR-097-POOL.json`.
Ranking note: the 5 LEGO-query rows carried no `view_count` (and no
uploader/channel) in flat search this run — recorded null honestly
(VYR-086 precedent for null views); they are ranked after the 3
candidates with measured views, in search-return order. No view
gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "COL@LAD: Fan hurls paper airplane from the upper deck" (YouTube, id `zLukgJFQNhA`) | YouTube search, query "amazing paper airplane trick short"; https://youtube.com/shorts/zLukgJFQNhA | 40s — PASS (15–60s) | 164,282; uploader MLB | Duration PASS; niche guard PASS; caption-track MEASURED 157 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "cute pink car Embroidery🎀 #cute#cutecar#handembroidery#short#shortvideo#embroidery" (YouTube, id `duXSRG2-lUA`) | YouTube search, query "mesmerizing embroidery hoop art short"; https://youtube.com/shorts/duXSRG2-lUA | 32s — PASS | 328; uploader Sign Of Art | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "I Made the MOST Luxurious Rose Cake Ever🎂 \| Satisfying Cake Decorating #baking #aishorts" (YouTube, id `x1ZeBD2mh84`) | YouTube search, query "satisfying cake decorating piping short"; https://youtube.com/shorts/x1ZeBD2mh84 | 56s — PASS | 22; uploader Sarah's lil world | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 4 | "Stunning Creation of 9 Foot Tall Statue of Liberty - LEGO - Time Lapse" (YouTube, id `LVeHFIgN0Xs`) | YouTube search, query "incredible lego building timelapse short"; https://youtube.com/shorts/LVeHFIgN0Xs | 50s — PASS | null (flat row carried no view_count); uploader null | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "LEGO TARDIS Time-Lapse \| Doctor Who" (YouTube, id `BH_DiPIa32A`) | YouTube search, query "incredible lego building timelapse short"; https://youtube.com/shorts/BH_DiPIa32A | 30s — PASS | null; uploader null | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "LEGO® Time-Lapse: Melbourne Builds a LEGO® Christmas!" (YouTube, id `l-62Mdls5a8`) | YouTube search, query "incredible lego building timelapse short"; https://youtube.com/shorts/l-62Mdls5a8 | 48s — PASS | null; uploader null | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 7 | "LEGO® Time-Lapse: Build Your LEGO® Christmas!" (YouTube, id `MXhIjYA1wKI`) | YouTube search, query "incredible lego building timelapse short"; https://youtube.com/shorts/MXhIjYA1wKI | 53s — PASS | null; uploader null | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 8 | "LEGO House official video – Timelapse: Tree of Creativity" (YouTube, id `II5XTaT3GTQ`) | YouTube search, query "incredible lego building timelapse short"; https://youtube.com/shorts/II5XTaT3GTQ | 55s — PASS | null; uploader null | Caption-track MEASURED 313 auto / 1 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidate 1 is a sports
broadcast channel (MLB) — a fan paper-airplane clip at a stadium
(COL@LAD); licence/origin re-check owed at QA, and sports-adjacent
(the niche guard ALLOWs it — no banned phrase matched — but the
audition judges suitability); candidates 4–8 are brand/official
LEGO® titles (candidate 5 also carries Doctor Who IP, candidate 8
is titled an official LEGO House video) — licence/origin re-check
owed, same as cycle 10's brand-channel cautions; candidate 2's title
is hashtag-heavy; candidate 3's title carries a #aishorts tag and
has 22 views (essentially unviewed). Honest traction note: the top
candidate has real traction (164,282 views, vs cycle 10's top
1,531,636 and cycle 9's 7,011), but it is a sports-broadcast clip,
and the 5 LEGO candidates' traction is unknown (null views) —
traction here does not imply licence clearance. Candidates are filed
by the machine gates only; the audition judges suitability.

## YouTube discovery: 8 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying crochet amigurumi making short" | 10 | 0 | 0 (all 10 over 60s; closest 183s) |
| "mesmerizing embroidery hoop art short" | 10 | 1 | 1 — `duXSRG2-lUA` |
| "incredible lego building timelapse short" | 10 | 5 | 5 — `LVeHFIgN0Xs`, `BH_DiPIa32A`, `l-62Mdls5a8`, `MXhIjYA1wKI`, `II5XTaT3GTQ` |
| "satisfying cake decorating piping short" | 10 | 1 | 1 — `x1ZeBD2mh84` (a 61s row sits just over the gate) |
| "amazing paper airplane trick short" | 10 | 1 | 1 — `zLukgJFQNhA` |
| "satisfying rug tufting art short" | 10 | 0 | 0 (one 9s row under the gate, rest over 60s) |

All 6 searches rc 0; niche guard on S2: `check_query` ALLOW for all
6 queries before issuing; `check_candidate` over all 60 returned
entries: 0 rejections. None of the 6 queries repeats any query in
the 15 prior pool JSONs on main plus cycle 10 (47 recorded candidate
queries, plus cycle 10's 3 zero-yield queries — needle felting,
terrarium, origami — from its evidence table; zero-yield queries
from earlier runs are not recorded in pool JSONs, so freshness is
verified against the recorded set plus topic distance — crochet
amigurumi, embroidery hoop, LEGO building, cake decorating piping,
paper airplane and rug tufting are all new topics). Raw per-query
output saved at `/tmp/vyr097_q{0..5}.jsonl` on S2. Flat-row anomaly
disclosed: all 10 LEGO-query rows carried `view_count`, `uploader`
and `channel` as null (verified in the raw jsonl on S2, including
`uploader_url`/`channel_url`/`creators` null); a full-metadata
re-probe on VyralX-Server (`--dump-json` / `--print` with cookies)
fails at format selection (rc 1, "Requested format is not
available"), so the nulls stand as measured. The other 5 queries'
rows all carried views/uploader.

## Exclusion set — 109 unique ids, verified first-hand

Assembled from the 15 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 091, 093, 094, 095)
plus the VYR-096 pool on branch `muse9/task-vyr-096` (PR #2218, not
yet merged at run time): union of all candidate ids + all
`excluded_ids` fields = 109 ids, exactly VYR-096's 101
`excluded_ids` plus its 8 candidates (overlap 0; the 101-id main
union is a subset — verified by direct recomputation this run; full
list in `TASK-VYR-097-POOL.json` (`excluded_ids`)). Pool
disjointness: the 8 fresh ids are disjoint from the 109-set and from
each other. The S2 exclusion gap stands (S2 manifests absent,
carried decision owed to Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate, all rc 0 (raw outputs at `/tmp/vyr097_sub_<id>.txt` on
server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `zLukgJFQNhA` | 157 languages listed (incl. en English) | 0 ("has no subtitles") | 157 auto / 0 uploaded |
| `duXSRG2-lUA` | none ("has no automatic captions") | 0 | 0 auto / 0 uploaded |
| `x1ZeBD2mh84` | none | 0 | 0 / 0 |
| `LVeHFIgN0Xs` | none | 0 | 0 / 0 |
| `BH_DiPIa32A` | none | 0 | 0 / 0 |
| `l-62Mdls5a8` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `MXhIjYA1wKI` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `II5XTaT3GTQ` | 313 languages listed (incl. en) | 1 (en English) | 313 auto / 1 uploaded |

Reading note (same as VYR-094/095/096): the 157 is YouTube's
auto-caption + auto-translation list for the video (auto-generated
captions present); it is not 157 authored caption files. Candidate
`II5XTaT3GTQ` is the first in these cycles with an uploaded subtitle
track (1, en English) and a doubled auto list (313 = original +
from-English translations, counted from the raw listing this run).
No caption-count pass threshold exists in the board record, so
counts are filed as measured data for the audition, not as
pass/fail. Control: the same probe on run-6 candidate `bRfoNfGBL1o`
returns 0 auto / 0 uploaded — identical to the VYR-094/095/096
control results; the method is not returning canned output. The
n-challenge solver crashed during these calls (deno
`a.addOnDisposeCallback is not a function`, the VYR-056 crash) but
the subtitle listing still answered rc 0 for every candidate — the
caption leg does not need formats. S2 has no jar, so the gate cannot
run there (re-probed this run: metadata fetch on `zLukgJFQNhA` from
S2 fails rc 1, "Sign in to confirm you're not a bot", 659 bytes of
error output, no metadata).

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`)
on candidate `zLukgJFQNhA`: rc 1, no media file created (log at
`/tmp/vyr097_dl.log` on server 5). Tail: n-challenge solver crash
(deno `a.addOnDisposeCallback is not a function`), "n challenge
solving failed", "Some web_embedded client https formats have been
skipped as they are missing a URL. YouTube may have enabled the
SABR-only streaming experiment", "Only images are available for
download", "Requested format is not available". Same standing
failure as VYR-056 (Nov 24); VYR-056 leg CLOSED as unachievable
(coordinator ruling 4); WATCH151 ruling 1 (gates PENDING/BLOCKED
acceptable, proceed) stands. No download-path repair was attempted
(needs coordinator/owner direction per VYR-056).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 6/6 queries rc 0; caption-track
  gates measured live 8/8 + control; BGM/watermark/loudness BLOCKED
  on a re-probed download path) / merged NO (awaiting peer
  review/merge) / deployed N/A (no service changed; S2 tree left as
  found) / production-verified PARTIAL (pool filed from a real live
  discovery run + measured caption gates; render awaits the
  download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 9
