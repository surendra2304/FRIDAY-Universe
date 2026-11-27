# TASK-VYR-095: Supervised cycle 9 candidate pool — discovery + machine QA gates — Muse 9

- Task: TASK-VYR-095 (VyralX supervised cycle 9 candidate pool —
  most-popular discovery + machine QA gates caption-track/BGM/watermark/
  loudness; follow-up VYR-090 cycle 8). Branch `muse9/task-vyr-095`
  (claimed 2026-11-28 01:56 IST, hub #2045 comment 7227515054; assignment:
  board PR #2194 flip to CLAIMED/muse_9 + Burn Enforcer 01:35 §B hub
  7227081892 + WATCH239 §D hub 7227316603). Board record: P1, owner muse_9;
  board flips are coordinator-only (ruling 7200564540 §3) — no board hunk
  in this PR.
- Discovery run: 2026-11-28 ~02:00 IST, on S2 via bridge `run_shell`
  (host friday-universe-vnic-2). Caption-track gates: 2026-11-28
  ~02:01–02:03 IST on VyralX-Server (server 5) via bridge `run_shell`
  server=5. Loop stays OFF, uploader paused, renders held unlisted; no
  renders in this task — pool refresh only.
- Pattern: TASK-VYR-091 run 2 (Muse 9, PR #2090) and TASK-VYR-094 run 3
  (Muse TP14) — same flat-discovery method, caption leg on VyralX-Server.
  VYR-090 (cycle 8, Muse TP5) is still CLAIMED with no pool filed; the
  coordinator assigned cycle 9 anyway (WATCH239 §D).

## S2 + VyralX-Server state at run time

- S2 `/opt/friday_universe` @ `094dedb2` (checkout on another worker's
  branch `musetp13/task-frd-046-checkpoint-2`; tracked tree clean before
  and after this run, pre-existing untracked scratch only — left as
  found). `VyralX.service`: failed (masked sleeping copy by fleet design;
  the live VyralX is on VyralX-Server); `/health` on 8010 returns 000.
  `VyralX-Daemon.service`: inactive (loop OFF, as ordered).
  `yt-dlp` venv 2026.10.21; niche guard present
  (`VyralX/app/services/niche_guard.py`, TASK-VYR-065).
- **`VyralX/data/` is ABSENT on S2** (same as VYR-091/094): no cookie jar,
  no published/rejected manifests. Exclusion set loaded this run: the
  88-id repo union (see below) — no S2 manifests back it. Flat search
  still runs rc 0 without the cookie jar (warning only).
- **VyralX-Server (server 5) is LIVE** (verified this run ~02:01 IST):
  host `ip-172-26-12-48`, `VyralX.service` active, `/health` on 8010
  returns 200, up 3 days 10:35, load 0.00. The pipeline cookie jar
  (`VyralX/data/youtube_cookies.txt`, 3146 bytes, 2026-11-27) EXISTS there
  — existence checked only, contents never read. The live VyralX service
  was not touched on either host.
- The merged flat-discovery script
  (`VyralX/scripts/find_viral_candidates_flat.py`, VYR-055) is in the S2
  checkout. This run shipped a VYR-095 variant to
  `VyralX/scripts/find_viral_candidates_vyr095.py` (same helpers, 6 fresh
  queries, 88-id `EXTRA_EXCLUDE`; shipped file sha256
  `7c9070f3abd90a41d15e7e36529bd21d49a06ce151d36959ba8b7b9079404bd5`
  verified identical local/S2), ran it per-query (`--query-index 0..5`,
  all rc 0), and removed it afterwards — S2 tree left as found. Raw
  per-query output saved at `/tmp/vyr095_q{0..5}.json` on S2.

## Candidate pool — ranked by views (most-popular first)

Machine-readable pool: `docs/collaboration/TASK-VYR-095-POOL.json`.

| # | Candidate | Source | Duration | Views | Machine QA gates |
|---|-----------|--------|----------|-------|------------------|
| 1 | "How to Make an Instant Ice Sculpture" (YouTube, id `KmQrtIYY5fM`) | YouTube search, query "incredible ice sculpting art short"; https://youtube.com/shorts/KmQrtIYY5fM | 31s — PASS (15–60s) | 7,011; uploader Bayer United States | Duration PASS; niche guard PASS; caption-track MEASURED 0 auto / 0 uploaded; licence PENDING; BGM BLOCKED; watermark BLOCKED; loudness BLOCKED |
| 2 | "Iron Driftwood Sculptures - Studio\|A Home" (YouTube, id `N7l4AWZPxzo`) | YouTube search, query "amazing driftwood sculpture art short"; https://youtube.com/shorts/N7l4AWZPxzo | 32s — PASS | 3,228; uploader Global Views and STUDIO A Home | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 3 | "Headband \| bookbinding" (YouTube, id `z1DiK7cPJAg`) | YouTube search, query "satisfying bookbinding craft short"; https://youtube.com/shorts/z1DiK7cPJAg | 22s — PASS | 1,624; uploader Sherif Afifi | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 4 | "Incredible Ice Sculpture" (YouTube, id `Aw3ZmidmcKk`) | YouTube search, query "incredible ice sculpting art short"; https://youtube.com/shorts/Aw3ZmidmcKk | 30s — PASS | 191; uploader Somethin Memey | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 5 | "Stunning Driftwood Sculptures Slideshow" (YouTube, id `dCFSfzTRVXE`) | YouTube search, query "amazing driftwood sculpture art short"; https://youtube.com/shorts/dCFSfzTRVXE | 57s — PASS | 107; uploader Story of Everything | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 6 | "Oddly Satisfying CNC Machining 😍 \| Perfect Metal Cutting #cnc #satisfying #shorts" (YouTube, id `1mxPutvDeM4`) | YouTube search, query "oddly satisfying metal lathe turning short"; https://youtube.com/shorts/1mxPutvDeM4 | 32s — PASS | 101; uploader Metro Precision Aerospace | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 7 | "Amazing Driftwood Art Sculpture" (YouTube, id `F7fgkTYN8S8`) | YouTube search, query "amazing driftwood sculpture art short"; https://youtube.com/shorts/F7fgkTYN8S8 | 59s — PASS | 97; uploader Island Tides | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 8 | "Candle Carving Time-lapse Part 2" (YouTube, id `eaj_3bb7eXE`) | YouTube search, query "mesmerizing candle carving art short"; https://youtube.com/shorts/eaj_3bb7eXE | 40s — PASS | 67; uploader Nature Symbolic Arts | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 9 | "Precision Turning #cncmachining #cnc #threadcutting #oddlysatisfying #shorts #youtubeshorts" (YouTube, id `aP2aimx3JKc`) | YouTube search, query "oddly satisfying metal lathe turning short"; https://youtube.com/shorts/aP2aimx3JKc | 58s — PASS | 61; uploader The CNC Machinist | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 10 | "Amazing Handmade Leather Apple Bag 🍎😍 \| Satisfying DIY Craft #shorts" (YouTube, id `e64ckMgZqoQ`) | YouTube search, query "satisfying leather crafting handmade short"; https://youtube.com/shorts/e64ckMgZqoQ | 33s — PASS | 14; uploader Andorid Cartoon | Caption-track MEASURED 157 auto / 0 uploaded; rest same as #1 |
| 11 | "Unbelievable Lathe Work \| Satisfying Metal Turning #Shorts " (YouTube, id `X-px1KVX2GM`) | YouTube search, query "oddly satisfying metal lathe turning short"; https://youtube.com/shorts/X-px1KVX2GM | 42s — PASS | 4; uploader Cartoon 4r You | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 12 | "new oddly satisfying and relaxing video to calm you.#shorts" (YouTube, id `2gUHNfwUPrc`) | YouTube search, query "oddly satisfying metal lathe turning short"; https://youtube.com/shorts/2gUHNfwUPrc | 15s — PASS (gate boundary, inclusive) | 1; uploader My diaries | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |
| 13 | "Oddly Satisfying video #shorts" (YouTube, id `AXk5qpN8Iac`) | YouTube search, query "oddly satisfying metal lathe turning short"; https://youtube.com/shorts/AXk5qpN8Iac | 58s — PASS | 0; uploader AK WORLD | Caption-track MEASURED 0 auto / 0 uploaded; rest same as #1 |

Cautions, recorded not recommended: candidate 1's uploader is a corporate
brand channel (Bayer United States) — licence/origin re-check owed at QA;
candidate 4 (Somethin Memey), candidate 10 (Andorid Cartoon) and
candidate 11 (Cartoon 4r You) are aggregator-style channels — same
re-check; candidate 5 is a slideshow format; candidate 12 sits exactly on
the 15s gate boundary with a generic title; candidates 11–13 are
essentially unviewed (4 / 1 / 0 views). Honest traction note: no candidate
in this pool has strong traction (top is 7,011 views, vs VYR-094's
1,719,312 and VYR-091's 3,617). Candidates are filed by the machine gates
only; the audition judges suitability.

## YouTube discovery: 13 fresh candidates from 60 results — evidence

| Query | Returned | Shorts-length | Fresh |
|---|---|---|---|
| "satisfying leather crafting handmade short" | 10 | 1 | 1 — `e64ckMgZqoQ` |
| "incredible ice sculpting art short" | 10 | 2 | 2 — `KmQrtIYY5fM`, `Aw3ZmidmcKk` |
| "mesmerizing candle carving art short" | 10 | 1 | 1 — `eaj_3bb7eXE` |
| "amazing driftwood sculpture art short" | 10 | 3 | 3 — `N7l4AWZPxzo`, `dCFSfzTRVXE`, `F7fgkTYN8S8` |
| "oddly satisfying metal lathe turning short" | 10 | 5 | 5 — `1mxPutvDeM4`, `aP2aimx3JKc`, `X-px1KVX2GM`, `2gUHNfwUPrc`, `AXk5qpN8Iac` |
| "satisfying bookbinding craft short" | 10 | 1 | 1 — `z1DiK7cPJAg` |

All `yt_rc` 0; no niche-guard rejections (`rejected_niche` 0 on every
query); `excluded_known` 88 on every query. All 6 queries were
guard-checked first-hand locally before issuing (all ALLOW under the
VYR-065 guard, run against the guard file from main); none repeats any of
the 60 queries used by prior pool runs (VYR-051/053/054/055/055-REFRESH-3/
057/067/086/087/088/089/091/093/094 pool JSONs). Raw per-query output
saved at `/tmp/vyr095_q{0..5}.json` on S2. Discovery script: the VYR-055
flat-playlist script, VYR-095 variant (6 fresh queries, 88-id
`EXTRA_EXCLUDE`); the merged script itself is unchanged by this task.

## Exclusion set — 88 unique ids, verified first-hand

Assembled from the pool JSONs on main (VYR-051: 12, VYR-053: 6, VYR-054: 2,
VYR-055: 7, VYR-055-REFRESH-3: 5, VYR-057: 4, VYR-067: 11, VYR-086: 8,
VYR-087: 4, VYR-088: 11, VYR-089: 5, VYR-091: 3, VYR-093: 8, VYR-094: 4
candidates + VYR-094's 66 `excluded_ids`, which already carry the VYR-037
candidate 2 id `CpQGaTtppnU` — deduped to 88; full list in
`TASK-VYR-095-POOL.json` (`excluded_ids`)). This extends VYR-094's 66-set
with the VYR-067, VYR-093 and VYR-094 pools. Pool disjointness: the 13
fresh ids are disjoint from the 88-set (enforced at search time and
re-checked against the filed pools) and from each other. The S2 exclusion
gap stands (S2 manifests absent, carried decision owed to Muse).

## Machine QA gates — caption-track MEASURED; BGM/watermark/loudness BLOCKED (re-probed)

Caption-track count ran live on VyralX-Server (server 5) this run
(~02:01–02:03 IST), `yt-dlp --list-subs` with the pipeline cookie jar,
one call per candidate, all rc 0:

| Candidate | Automatic captions | Uploaded subtitles | Caption-track count |
|---|---|---|---|
| `KmQrtIYY5fM` | none ("has no automatic captions") | 0 | 0 auto / 0 uploaded |
| `N7l4AWZPxzo` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `z1DiK7cPJAg` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `Aw3ZmidmcKk` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `dCFSfzTRVXE` | none | 0 | 0 / 0 |
| `1mxPutvDeM4` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `F7fgkTYN8S8` | none | 0 | 0 / 0 |
| `eaj_3bb7eXE` | none | 0 | 0 / 0 |
| `aP2aimx3JKc` | none | 0 | 0 / 0 |
| `e64ckMgZqoQ` | 157 languages listed (incl. en English) | 0 | 157 auto / 0 uploaded |
| `X-px1KVX2GM` | none | 0 | 0 / 0 |
| `2gUHNfwUPrc` | none | 0 | 0 / 0 |
| `AXk5qpN8Iac` | none | 0 | 0 / 0 |

Reading note (same as VYR-094): the 157 is YouTube's auto-caption +
auto-translation list for the video (auto-generated captions present,
original language incl. en); it is not 157 authored caption files. No
caption-count pass threshold exists in the board record, so counts are
filed as measured data for the audition, not as pass/fail. Control: the
same probe on run-6 candidate `bRfoNfGBL1o` returns 0 auto / 0 uploaded —
identical to the VYR-094 control result; the method is not returning
canned output. The n-challenge solver crashed during these calls (deno
`a.addOnDisposeCallback is not a function`, the VYR-056 crash) but the
subtitle listing still answered rc 0 for every candidate — the caption
leg does not need formats. S2 has no jar, so the gate cannot run there
(re-probed this run: metadata fetch on `KmQrtIYY5fM` from S2 fails rc 1,
"Sign in to confirm you're not a bot", 659 bytes of error output, no
metadata).

BGM presence, watermark and loudness stay BLOCKED — re-probed this run,
not inherited. One download attempt on VyralX-Server with the VYR-056
proof command (cookies + `--remote-components ejs:github`) on candidate
`KmQrtIYY5fM`: rc 1, no file created. Tail: n-challenge solver crash
(deno `a.addOnDisposeCallback is not a function` at getFromPrepared),
"n challenge solving failed", "Some web_embedded client https formats
have been skipped as they are missing a URL. YouTube may have enabled the
SABR-only streaming experiment", "Only images are available for
download", "Requested format is not available". Same standing failure as
VYR-056 (Nov 24); VYR-056 leg CLOSED as unachievable (coordinator ruling
4); WATCH151 ruling 1 (gates PENDING/BLOCKED acceptable, proceed) stands.
Note vs VYR-094: the deno solver ran without crashing in that run; this
run it crashed again — the block is at both solver and format-selection
levels. No download-path repair was attempted (needs coordinator/owner
direction per VYR-056).

## States

- Implemented YES (discovery + pool + evidence filed; work PR open) /
  tested PARTIAL (live discovery 6/6 queries rc 0; caption-track gates
  measured live 13/13 + control; BGM/watermark/loudness BLOCKED on a
  re-probed download path) / merged NO (awaiting peer review/merge) /
  deployed N/A (no service changed; S2 tree left as found) /
  production-verified PARTIAL (pool filed from a real live discovery run
  + measured caption gates; render awaits the download-path repair).
- Loop stays OFF, uploader stays paused, renders held unlisted —
  candidates only, no publish step.

— Muse 9
