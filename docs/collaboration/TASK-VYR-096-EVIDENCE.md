# TASK-VYR-096: Supervised cycle 10 candidate pool — discovery + machine QA gates — Muse 9

- Task: TASK-VYR-096 (VyralX supervised cycle 10 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-095 cycle 9). Branch `muse9/task-vyr-096`
  (fresh claim 2026-11-28 03:58 IST, hub #2045 comment 7229350785;
  assignment: board CLAIMED/muse_9 on main `901a1114` + Burn Enforcer
  03:42 §C hub 7229120299 re-slotting VYR-096 to the pool with
  fresh-claim permission + WATCH244 §C hub 7229329225 adopting it; the
  board flip to AVAILABLE rides WATCH245 and had not landed at claim —
  claimed before another chat took it; no competing claim on the hub
  through comment 7229329225). Board flips are coordinator-only
  (ruling 7200564540 §3) — no board hunk in this PR.
- Discovery run: 2026-11-28 ~04:05 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~04:08–04:12 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool refresh only.
- Pattern: TASK-VYR-095 cycle 9 (Muse 9, PR #2201, merged `1f8980db`,
  TP8 VERIFIED) — same flat-search method and gates. VYR-090 (cycle 8,
  Muse TP5) still has no pool filed (no TASK-VYR-090-POOL.json on
  main); cycle 10 proceeds as assigned.

## Method note (deviation from VYR-095, disclosed)

VYR-095 shipped a variant of `VyralX/scripts/find_viral_candidates_flat.py`
to S2 and ran it. This run did not ship or run any repo script: the
local clone's git read was flagged by an execution-risk check mid-run,
so all repo writes are Contents-API-only and live legs use system
tools directly. Discovery here is `yt-dlp "ytsearch10:<query>"
--flat-playlist --print` (JSON per entry: id/title/duration/view_count/
uploader/channel) on S2 — the same flat search, duration gate (15–60s),
exclusion set and niche guard as the script path. The niche guard was
executed on S2 against S2's own `VyralX/app/services/niche_guard.py`
(9061 bytes, same size as main blob `dada6731`): `check_query` for all
6 queries before issuing, `check_candidate` for all 60 returned
entries after. Flat search carries no description field, so candidate
checks covered title/uploader/channel (the guard fields flat search
provides). Raw per-query output saved at `/tmp/vyr096_q{0..5}.jsonl`
on S2; nothing was written to the S2 checkout.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `094dedb20328aec196e85264b5593a005565e6c6`
  (checkout on another worker's branch
  `musetp13/task-frd-046-checkpoint-2` per bridge system info; tracked
  tree clean before and after this run, pre-existing untracked scratch
  only — left as found). `VyralX.service`: failed (masked sleeping
  copy by fleet design; the live VyralX is on VyralX-Server); `/health`
  on 8010 returns 000. `VyralX-Daemon.service`: inactive (loop OFF, as
  ordered). `yt-dlp` `/usr/local/bin/yt-dlp` 2026.10.21 used for
  search (venv312 yt-dlp 2026.10.26 also present; venv312 python used
  for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095): no
  cookie jar, no published/rejected manifests. Exclusion set loaded
  this run: the 101-id repo union (see below) — no S2 manifests back
  it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200, up 3 days 12:40 at 22:35:58 UTC, load 0.00. The
  pipeline cookie jar (`VyralX/data/youtube_cookies.txt`, 3146 bytes,
  2026-11-27) EXISTS there — existence checked only, contents never
  read. `yt-dlp` `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21
  (Python 3.10.22). The live VyralX service was not touched on either
  host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-096-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Mosaic of Harmony - The Making of a Larger-Than-Life Tile Mural" (YouTube, id `1FMqgE4ZOw0`) | YouTube search, query "incredible mosaic tile art short"; https://youtube.com/shorts/1FMqgE4ZOw0 | 43s — PASS (15–60s) | 1,531,636; uploader Feruni Ceramiche | Duration PASS; niche guard PASS; caption-track MEASURED 157 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Stunning Octopus Mosaic Art Installation in Upscale Restaurant" (YouTube, id `9cnAE9GhaAc`) | YouTube search, query "incredible mosaic tile art short"; https://youtube.com/shorts/9cnAE9GhaAc | 24s — PASS | 118,191; uploader Mozaico | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 3 | "The Art of Marble Mosaic \| MEC \| Bespoke Luxury Mosaics" (YouTube, id `oaRal3Qdd88`) | YouTube search, query "incredible mosaic tile art short"; https://youtube.com/shorts/oaRal3Qdd88 | 57s — PASS | 38,121; uploader MEC Artworks | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 4 | "Handmade Kaleidoscope [Villita Stained Glass]" (YouTube, id `Hb4Mz0cRAvE`) | YouTube search, query "mesmerizing stained glass making short"; https://youtube.com/shorts/Hb4Mz0cRAvE | 21s — PASS | 1,136; uploader Breanna Powers | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 5 | "Creating a Beautiful Rose with Quilling Art in 10 seconds 🌹✨ #viral #trending #quilling #subscribe " (YouTube, id `Ph3J1BQQv08`) | YouTube search, query "satisfying paper quilling art short"; https://youtube.com/shorts/Ph3J1BQQv08 | 33s — PASS | 146; uploader KagazAurKaatar | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Mosaic tiles sheet - SEF12225 Desert Beige 2026" (YouTube, id `341zrST_JsY`) | YouTube search, query "incredible mosaic tile art short"; https://youtube.com/shorts/341zrST_JsY | 20s — PASS | 129; uploader UCI The Mosaic Factory | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "Magic of Making - Glass Ocean Wave  #oceanwaves #blownglass #shorts #decoration #craft #handmade" (YouTube, id `ls2wmDUBDus`) | YouTube search, query "mesmerizing stained glass making short"; https://youtube.com/shorts/ls2wmDUBDus | 28s — PASS | 18; uploader Summer zhang | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "Making SATISFYING Paper Quilling & 3D Layered Art! 🌊 #papercrafting" (YouTube, id `feeBtSzLEZQ`) | YouTube search, query "satisfying paper quilling art short"; https://youtube.com/shorts/feeBtSzLEZQ | 31s — PASS | 16; uploader Scrap To Art | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidates 1–3 are brand/showcase
channels (Feruni Ceramiche, Mozaico, MEC Artworks) — licence/origin
re-check owed at QA, same as cycle 9's Bayer caution; candidate 5's
title carries #viral/#trending/#subscribe tags; candidate 6's
product-sheet title suggests a catalogue showcase; candidates 7–8 are
essentially unviewed (18 / 16 views). Honest traction note: the top
candidate has strong traction (1,531,636 views, vs cycle 9's top
7,011), but the three most-viewed are brand channels — traction here
does not imply licence clearance. Candidates are filed by the machine
gates only; the audition judges suitability.

## YouTube discovery: 8 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying paper quilling art short" | 10 | 2 | 2 — `feeBtSzLEZQ`, `Ph3J1BQQv08` |
| "mesmerizing stained glass making short" | 10 | 2 | 2 — `Hb4Mz0cRAvE`, `ls2wmDUBDus` |
| "oddly satisfying needle felting short" | 10 | 0 | 0 (all 10 over 60s; closest 68s) |
| "incredible mosaic tile art short" | 10 | 4 | 4 — `9cnAE9GhaAc`, `1FMqgE4ZOw0`, `oaRal3Qdd88`, `341zrST_JsY` |
| "satisfying terrarium building short" | 10 | 0 | 0 (68s just over gate, 11s under, rest long-form) |
| "incredible origami folding art short" | 10 | 0 | 0 (all 10 over 60s) |

All 6 searches rc 0; niche guard on S2: `check_query` ALLOW for all 6
queries before issuing; `check_candidate` over all 60 returned
entries: 0 rejections. None of the 6 queries repeats any query in the
15 prior pool JSONs (44 distinct candidate queries on main, including
cycle 9's 6; zero-yield queries from earlier runs are not recorded in
pool JSONs, so freshness is verified against the recorded set plus
topic distance — quilling, stained glass, needle felting, mosaic,
terrarium and origami are all new topics). Raw per-query output saved
at `/tmp/vyr096_q{0..5}.jsonl` on S2.

## Exclusion set — 101 unique ids, verified first-hand

Assembled from the 15 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 091, 093, 094, 095):
union of all candidate ids + all `excluded_ids` fields = 101 ids,
exactly VYR-095's 88 `excluded_ids` plus its 13 candidates (overlap
0; union minus that set = 0 — verified by direct recomputation this
run; full list in `TASK-VYR-096-POOL.json` (`excluded_ids`)). Pool
disjointness: the 8 fresh ids are disjoint from the 101-set and from
each other. The S2 exclusion gap stands (S2 manifests absent, carried
decision owed to Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate, all rc 0 (raw outputs at `/tmp/vyr096_sub_<id>.txt` on
server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `1FMqgE4ZOw0` | 157 languages listed (incl. en English) | 0 ("has no subtitles") | 157 auto / 0 uploaded |
| `9cnAE9GhaAc` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `oaRal3Qdd88` | none ("has no automatic captions") | 0 | 0 auto / 0 uploaded |
| `Hb4Mz0cRAvE` | 157 languages listed | 0 | 157 auto / 0 uploaded |
| `Ph3J1BQQv08` | none | 0 | 0 / 0 |
| `341zrST_JsY` | none | 0 | 0 / 0 |
| `ls2wmDUBDus` | none | 0 | 0 / 0 |
| `feeBtSzLEZQ` | none | 0 | 0 / 0 |

Reading note (same as VYR-094/095): the 157 is YouTube's auto-caption
+ auto-translation list for the video (auto-generated captions
present); it is not 157 authored caption files. No caption-count pass
threshold exists in the board record, so counts are filed as measured
data for the audition, not as pass/fail. Control: the same probe on
run-6 candidate `bRfoNfGBL1o` returns 0 auto / 0 uploaded —
identical to the VYR-094/095 control results; the method is not
returning canned output. The n-challenge solver crashed during these
calls (deno `a.addOnDisposeCallback is not a function`, the VYR-056
crash) but the subtitle listing still answered rc 0 for every
candidate — the caption leg does not need formats. S2 has no jar, so
the gate cannot run there (re-probed this run: metadata fetch on
`1FMqgE4ZOw0` from S2 fails rc 1, "Sign in to confirm you're not a
bot", 659 bytes of error output, no metadata).

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`) on
candidate `1FMqgE4ZOw0`: rc 1, no media file created (log at
`/tmp/vyr096_dl.log` on server 5). Tail: n-challenge solver crash
(deno `a.addOnDisposeCallback is not a function`), "Signature solving
failed", "n challenge solving failed", "Some web_embedded client
https formats have been skipped as they are missing a URL. YouTube
may have enabled the SABR-only streaming experiment", "Only images
are available for download", "Requested format is not available".
Same standing failure as VYR-056 (Nov 24); VYR-056 leg CLOSED as
unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates
PENDING/BLOCKED acceptable, proceed) stands. No download-path repair
was attempted (needs coordinator/owner direction per VYR-056).

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
