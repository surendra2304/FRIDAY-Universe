# TASK-VYR-101: Supervised cycle 9 candidate pool — discovery + machine QA gates — Muse 14

- Task: TASK-VYR-101 (VyralX supervised cycle 9 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-090 cycle 8). Branch `muse14/task-vyr-101`
  (claim 2026-11-28 ~09:35 IST, hub #2045 comment 7233663119; pool
  pull per the coordinator's WATCH253 correction, hub 7233584307,
  directing M14 to claim a queue head now (SEN-042 MERGED 93ccfd72);
  board on main `767d5a1d` read AVAILABLE / owner null / branch null /
  pr null, no blockers; no competing claim on the hub through comment
  7233636483). Board flips are coordinator-only (ruling 7200564540
  §3) — no board hunk in this PR.
- Discovery run: 2026-11-28 ~09:44–09:50 IST, on S2 via bridge
  `run_shell` (host friday-universe-vnic-2). Caption-track gates:
  2026-11-28 ~09:52–09:56 IST on VyralX-Server (server 5) via bridge
  `run_shell` server=5. Loop stays OFF, uploader paused, renders held
  unlisted; no renders in this task — pool refresh only.
- Pattern: TASK-VYR-097 cycle 11 (Muse 9, PR #2232, M14 VERIFIED
  review 6094780025) — same flat-search method and gates. Predecessor
  VYR-090 cycle 8 MERGED (PR #2251, merge d94fc4b2, ~09:19 IST);
  its 8 candidates are in this cycle's exclusion set.
- Cycle-number note, stated plainly: this task is titled "cycle 9"
  but TASK-VYR-095 already holds cycle 9 (MERGED); VYR-102/103
  likewise duplicate cycles 10/11 (VYR-096/097). No renumbering done
  here; the numbering ruling is owed by the coordinator (same class
  as the SEN run-numbering collision). This run proceeds on the
  TASK-VYR-101 evidence file as assigned.

## Method note

No repo script was shipped or run. Discovery is `yt-dlp
"ytsearch10:<query>" --flat-playlist --dump-json` on S2 — the same
flat search, duration gate (15–60s), exclusion set and niche guard
as the script path. The niche guard was executed on S2 against S2's
own `VyralX/app/services/niche_guard.py` (9061 bytes, same size as
main): `check_query` for all 9 queries before issuing,
`check_candidate` for all 90 returned entries after (title /
description / channel / uploader fields from the flat rows). Raw
per-query output saved at `/tmp/vyr101_q{0..8}.jsonl` on S2; nothing
was written to the S2 checkout (tracked tree clean before and after,
verified this run).

Nine queries ran (not six): the first six yielded 9 shorts-length
fresh candidates but 4 of the 6 queries yielded zero (chalk art,
topiary, macrame, watercolor all returned only long-form rows), so
three more fresh-topic queries ran in the same session to widen the
pool before ranking. All nine are disclosed below; freshness is
verified against the 60 candidate queries recorded in the 19 pool
JSONs on main plus the zero-yield topics from the cycle 10/11/12
evidence tables (needle felting, terrarium, origami, crochet
amigurumi, rug tufting, kite flying, paper marbling, ice-cream
rolling, shadow puppetry, bubble tea, wire sculpture, stone
carving) — chalk art, tie dye, topiary, wax seal, macrame,
watercolor, sourdough scoring, lichtenberg wood burning and bento
box are all new topics.

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `69ff042b1b5963b5d0216348f11d737d2a67a9e2`
  (checkout on another worker's branch
  `musetp4/task-frg-036-rerun3-evidence`; tracked tree clean before
  and after this run, pre-existing untracked scratch only — left as
  found). `VyralX.service`: failed (masked sleeping copy by fleet
  design; the live VyralX is on VyralX-Server); `/health` on 8010
  returns 000. `VyralX-Daemon.service`: inactive (loop OFF, as
  ordered). `yt-dlp` `/usr/local/bin/yt-dlp` 2026.10.21 used for
  search (venv312 python used for guard checks); niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094/095/096/097):
  no cookie jar, no published/rejected manifests. Exclusion set loaded
  this run: the 133-id repo union (see below) — no S2 manifests back
  it. Flat search still runs rc 0 without the cookie jar.
- **VyralX-Server (server 5) is LIVE** (verified this run): host
  `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes, 2026-11-28) EXISTS
  there — existence checked only, contents never read. `yt-dlp`
  `/opt/friday_universe/venv/bin/yt-dlp` 2026.10.21 (Python 3.10.22).
  `VyralX-Daemon.service` inactive (loop OFF, as ordered). The live
  VyralX service was not touched on either host.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-101-POOL.json`.
Ranking note: the top 8 of 16 fresh shorts are filed, by views; the
8 below the cut are listed after the table, not filed (VYR-098
precedent). No view gate exists in the acceptance.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "Vintage sealing wax stamps and 3 colors wax sticks" (YouTube, id `5y3lEUoFHUU`) | YouTube search, query "satisfying wax seal stamping short"; https://youtube.com/shorts/5y3lEUoFHUU | 30s — PASS (15–60s) | 79,244; uploader Elegant Wedding Invites | Duration PASS; niche guard PASS; caption-track MEASURED 0 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Tie Dye Spirit Top" (YouTube, id `_jfTdeHqq3A`) | YouTube search, query "mesmerizing tie dye art short"; https://youtube.com/shorts/_jfTdeHqq3A | 39s — PASS | 17,184; uploader GreaterGood | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 3 | "Tie Dye Block Print Long Sleeve Top" (YouTube, id `dHG6Alw-vJg`) | YouTube search, query "mesmerizing tie dye art short"; https://youtube.com/shorts/dHG6Alw-vJg | 33s — PASS | 10,648; uploader GreaterGood | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 4 | "[AI ASMR] Glass Flower Wax Seal Stamps 🌸 \| Which One Is Your Favorite?" (YouTube, id `8hgWhmK-tTo`) | YouTube search, query "satisfying wax seal stamping short"; https://youtube.com/shorts/8hgWhmK-tTo | 41s — PASS | 1,313; uploader SootheSphere | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 5 | "Mesmerizing Flames: Lichtenberg Artistry Ignites a Stunning Douglas Fir End Grain Table" (YouTube, id `ExrxKlDZEEQ`) | YouTube search, query "mesmerizing lichtenberg wood burning short"; https://youtube.com/shorts/ExrxKlDZEEQ | 29s — PASS | 287; uploader The Raven's Den | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Lichtenberg Wood Burning the Headboard for a School Bus Conversion" (YouTube, id `tTQqWDg91bI`) | YouTube search, query "mesmerizing lichtenberg wood burning short"; https://youtube.com/shorts/tTQqWDg91bI | 30s — PASS | 278; uploader The Bus Experience | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 7 | "How I Score Sourdough Bread" (YouTube, id `4lqRY2PCl8E`) | YouTube search, query "satisfying sourdough bread scoring short"; https://youtube.com/shorts/4lqRY2PCl8E | 47s — PASS | 145; uploader Preserving Today | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "Satisfying Wax Seal Stamp ASMR ✨ Relaxing Wax Melting & Seal Reveal \| No Music" (YouTube, id `20yoPWkauAU`) | YouTube search, query "satisfying wax seal stamping short"; https://youtube.com/shorts/20yoPWkauAU | 58s — PASS | 123; uploader Crystal Bliss | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Below the cut — 8 further fresh shorts, not filed: `i3M5v6iqsvo`
(101 views, bento box), `AmgegxL3Dyc` (53, wax seal), `LltR1fmNB0E`
(46, lichtenberg), `K7tAtrg5eUM` (15, tie dye), `V_I4l7jG-SA` (15,
wax seal), `URoJgsz2_1s` (13, sourdough), `ZRgSWpr07ls` (12,
bento), `BRsrTooafwE` (11, wax seal).

Cautions, recorded not recommended: candidate 1 is a product demo
(Elegant Wedding Invites; the description links to a wax seal stamp
kit product page) — licence/origin re-check owed at QA; candidates
2–3 are product listings (GreaterGood; "Shop Here" links to the
tie-dye tops) — same re-check owed; candidate 4 is labelled AI
content ("[AI ASMR]" in the title; the description says "AI ASMR
video") — licence/origin re-check owed, same class as cycle 11's
#aishorts tag; candidate 6's description notes the wood burner "was
made from a microwave transformer. Definitely dangerous" —
dangerous-DIY framing on a build timelapse; audition judges
suitability; candidate 8 sits at 58s, near the 60s gate edge.
Honest traction note: the top candidate has real traction (79,244
views, vs cycle 11's top 164,282 and cycle 8's 154,376), but it is
a product demo, and the rest of the pool is low-traction (17,184
down to 123) — traction here does not imply licence clearance.
Candidates are filed by the machine gates only; the audition judges
suitability.

## YouTube discovery: 8 filed candidates from 90 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying chalk art drawing short" | 10 | 0 | 0 (all 10 over 60s) |
| "mesmerizing tie dye art short" | 10 | 3 | 3 — `K7tAtrg5eUM`, `_jfTdeHqq3A`, `dHG6Alw-vJg` |
| "incredible topiary garden art short" | 10 | 0 | 0 (one row under the gate, rest over 60s) |
| "satisfying wax seal stamping short" | 10 | 6 | 6 — `BRsrTooafwE`, `20yoPWkauAU`, `V_I4l7jG-SA`, `8hgWhmK-tTo`, `5y3lEUoFHUU`, `AmgegxL3Dyc` |
| "satisfying macrame knot art short" | 10 | 0 | 0 (all 10 over 60s) |
| "mesmerizing watercolor painting short" | 10 | 0 | 0 (one row under the gate, rest over 60s) |
| "satisfying sourdough bread scoring short" | 10 | 2 | 2 — `4lqRY2PCl8E`, `URoJgsz2_1s` |
| "mesmerizing lichtenberg wood burning short" | 10 | 3 | 3 — `ExrxKlDZEEQ`, `tTQqWDg91bI`, `LltR1fmNB0E` |
| "satisfying bento box art short" | 10 | 2 | 2 — `ZRgSWpr07ls`, `i3M5v6iqsvo` |

All 9 searches rc 0; niche guard on S2: `check_query` ALLOW for all
9 queries before issuing; `check_candidate` over all 90 returned
entries: 0 rejections. None of the 9 queries repeats any query in
the 19 prior pool JSONs on main (60 recorded candidate queries)
plus the zero-yield topics from the cycle 10/11/12 evidence tables
— chalk art, tie dye, topiary, wax seal, macrame, watercolor,
sourdough scoring, lichtenberg wood burning and bento box are all
new topics. Raw per-query output saved at `/tmp/vyr101_q{0..8}.jsonl`
on S2. Flat-row check: all 90 rows carried `view_count` and
`uploader` (0 nulls) — no flat-row anomaly this run, unlike cycle
11's LEGO query.

## Exclusion set — 133 unique ids, verified first-hand

Assembled from the 19 pool JSONs on main (VYR-051, 053, 054, 055,
055-REFRESH-3, 057, 067, 086, 087, 088, 089, 090, 091, 093, 094, 095,
096, 097, 098): union of all candidate ids + all `excluded_ids`
fields = 133 ids — exactly the VYR-090 pool's own 133-id set (its
125 `excluded_ids` plus its 8 candidates), verified by direct
recomputation this run; full list in `TASK-VYR-101-POOL.json`
(`excluded_ids`). Pool disjointness: the 8 filed ids are disjoint
from the 133-set and from each other (asserted in the filing
script). The S2 exclusion gap stands (S2 manifests absent, carried
decision owed to Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run,
`yt-dlp --list-subs` with the pipeline cookie jar, one call per
candidate, all rc 0 (raw outputs at `/tmp/vyr101_sub_<id>.txt` on
server 5):

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `5y3lEUoFHUU` | none ("has no automatic captions") | 0 ("has no subtitles") | 0 auto / 0 uploaded |
| `_jfTdeHqq3A` | none | 0 | 0 / 0 |
| `dHG6Alw-vJg` | none | 0 | 0 / 0 |
| `8hgWhmK-tTo` | none | 0 | 0 / 0 |
| `ExrxKlDZEEQ` | none | 0 | 0 / 0 |
| `tTQqWDg91bI` | none | 0 | 0 / 0 |
| `4lqRY2PCl8E` | none | 0 | 0 / 0 |
| `20yoPWkauAU` | none | 0 | 0 / 0 |

No caption-count pass threshold exists in the board record, so
counts are filed as measured data for the audition, not as
pass/fail. Control: the same probe on run-6 candidate `bRfoNfGBL1o`
returns 0 auto / 0 uploaded — identical to the VYR-094/095/096/097
control results; the method is not returning canned output. The
n-challenge solver crashed during these calls (deno
`a.addOnDisposeCallback is not a function`, the VYR-056 crash) but
the subtitle listing still answered rc 0 for every candidate — the
caption leg does not need formats. S2 has no jar, so the gate cannot
run there (re-probed in prior cycles; not re-run here).

BGM presence, watermark and loudness stay BLOCKED — re-probed this
run, not inherited. One download attempt on VyralX-Server with the
VYR-056 proof command (cookies + `--remote-components ejs:github`,
`--no-playlist`, `-f 'bv*[height<=1080]+ba/b[height<=1080]'`,
`--merge-output-format mp4`) on candidate `5y3lEUoFHUU`: rc 1, no
media file created (log at `/tmp/vyr101_dl.log` on server 5). Tail:
n-challenge solver crash (deno `a.addOnDisposeCallback is not a
function`), "n challenge solving failed", "Some web_embedded client
https formats have been skipped as they are missing a URL. YouTube
may have enabled the SABR-only streaming experiment", "Only images
are available for download", "Requested format is not available".
Same standing failure as VYR-056 (Nov 24); VYR-056 leg CLOSED as
unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates
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

— Muse 14
