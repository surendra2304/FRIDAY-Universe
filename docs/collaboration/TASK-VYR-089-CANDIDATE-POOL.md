# TASK-VYR-089: Candidate pool — supervised cycle 7 — 5 fresh candidates — Muse 14

- Task: TASK-VYR-089 (P1, VyralX: supervised cycle 7 candidate pool — most-popular discovery + machine QA gates). Claimed 2026-11-27 ~09:45 IST from the central pool (hub #2045 comment 7209646942). Branch `muse14/task-vyr-089` (base main `cb57c8c8`). Board AVAILABLE → CLAIMED flip rides in the coordinator board PR (standing orders — no board hunk in the work PR).
- Machine-readable pool: `docs/collaboration/TASK-VYR-089-POOL.json` — **candidates: 5, all fresh, all passing the exercisable gates**. Nothing is invented; every candidate was read first-hand from the S2 flat-playlist output.
- Discovery run: 2026-11-27 ~09:50–09:51 IST, S2 flat-playlist via bridge `run_shell` (standing clearance 7200564540; no safety flag fired), 6 NEW queries, `ytsearch10`, 10 results per query, read-only, no sign-in, no download. 60 results read. Raw yt-dlp invoked directly (same command the VYR-055 script wraps) because the script takes only `--query-index` into its hardcoded 6-query list and the cycle-7 queries are new. Same channel, same read-only operation class. No S2 change made.

## Result: 5 fresh candidates from 60 results

| Query | Returned | Shorts-length (15–60s) | Fresh |
|---|---|---|---|
| "satisfying kinetic sand cutting short" | 10 | 0 | 0 |
| "amazing cardistry flourish short" | 10 | 0 | 0 |
| "oddly satisfying resin art short" | 10 | 2 | 2 |
| "incredible pen spinning trick short" | 10 | 0 | 0 |
| "satisfying slime swirl ASMR short" | 10 | 0 | 0 |
| "amazing yo-yo trick short" | 10 | 3 | 3 |

New queries per TP6's recommendation (a) from VYR-087 checkpoint 2: the old 6-query set is exhausted at top-30 public depth + S2 ytsearch10. All 6 new queries were guard-checked before issuing (none names a VYR-065 banned niche).

## The 5 candidates — all gates exercisable PASS

| # | Candidate | Source | Duration | Views | Verdict |
|---|---|---|---|---|---|
| 1 | "The Most Satisfying Table Build Ever 🤯 #shorts #oddlysatisfying #resinart #epoxy" (id `Ka_s31jW2mw`) | Resin query, rank 7; https://youtube.com/shorts/Ka_s31jW2mw | 21s — PASS | 119 (exact) ; uploader Melt Fable | CANDIDATE — duration PASS, niche guard PASS (resin art table build; single video, not a compilation). Low-view flag: 119 views, recorded honestly; no view gate in the acceptance. |
| 2 | "DIY Resin Money Tree with Coins 💸 \| Satisfying Resin Art" (id `JBYAB-I3VDE`) | Resin query, rank 10; https://youtube.com/shorts/JBYAB-I3VDE | 21s — PASS | 8 (exact); uploader Elegant_rp | CANDIDATE — duration PASS, niche guard PASS (single DIY resin video). Low-view flag: 8 views, recorded honestly; no view gate in the acceptance. |
| 3 | "a short yoyo combo" (id `bmTtoGBZyDw`) | Yo-yo query, rank 3; https://youtube.com/shorts/bmTtoGBZyDw | 15s — PASS (lower bound, inclusive) | 40,763 (exact); uploader Hyun | CANDIDATE — duration PASS, niche guard PASS (single yoyo combo). |
| 4 | "How To Do The Brain Twister Yoyo Trick" (id `qWLHDsv46ls`) | Yo-yo query, rank 7; https://youtube.com/shorts/qWLHDsv46ls | 36s — PASS | 271,760 (exact); uploader OFFSET yoyo | CANDIDATE — duration PASS, niche guard PASS (single-trick tutorial, not a highlights compilation). |
| 5 | "How To Do Rock The Baby Yoyo Trick" (id `hNCOShf2oeI`) | Yo-yo query, rank 8; https://youtube.com/shorts/hNCOShf2oeI | 27s — PASS | 531,132 (exact); uploader OFFSET yoyo | CANDIDATE — duration PASS, niche guard PASS (single-trick tutorial, not a highlights compilation). |

## Near-misses — duration fails

| Candidate | Duration | Verdict |
|---|---|---|
| "Making a Galaxy in 60 Seconds 🌌 (Satisfying Resin Art)" (`PTrfe9lduwo`, Rainbow Learning & Crafts) | 65s | FAILS 15–60s by 5s |
| "6 easy diy resin coaster for beginners" (`I_uj8Gq_XJ4`, Tuba art and craft) | 61s | FAILS by 1s |
| "How To Spin A Pen - Infinity Tutorial" (`sg25h7O4b74`, Next Level Spins) | 61s | FAILS by 1s |
| "Cool life with cards - Card Flourishes" (`9kcKhvjBCaY`, Sergio Roca) | 80s | FAILS (shortest cardistry result) |

## Exclusion sets — verified first-hand

- Applied: 40 known IDs read first-hand from the repo pool JSONs on main (VYR-051: 12, VYR-053: 6, VYR-054: 2, VYR-055: 7, VYR-055-REFRESH-3: 5, VYR-057: 4, VYR-087: 4) + `CpQGaTtppnU` (VYR-037 pool candidate 2). Zero overlap with the 5 candidates. Full list in `TASK-VYR-089-POOL.json` (`excluded_ids`).
- NOT applied (gap, carried from VYR-087): the S2 exclusion files that held 84 known IDs at VYR-055 time (`rejected_sources.json` 51, `published_shorts_manifest.json` 11, `viral_loop_manifest.jsonl` 11) are unretrievable — absent from the repo on main and from S2 (verified in VYR-087 checkpoint 2). Mitigation applied: every result screened against the VYR-065 banned niches; no banned-niche title appears among the 5 candidates or the 4 near-misses. The gap is carried as a decision owed, not hidden.

## Data-quality notes (S2 flat-playlist output, 09:50–09:51 IST)

- `ytsearch10` returns relevance order, NOT view-count sorted: views are non-monotonic in every query (e.g. query 1: 37K, 5.8M, 108K, 114K, 18.6M). Same as the VYR-055 method (ytsearch10, no sort param); the "most-popular" label is the lane's name, not a verified sort. Ranks are the order returned.
- Durations and views are yt-dlp exact integers (seconds / counts), unlike browser-rounded values.
- No cookie jar on S2 (`VyralX/data/youtube_cookies.txt` absent, bridge `read_text` exit 2, verified this run ~09:52 IST); all 6 queries returned 10 results each, exit 0, no bot-block.
- Bridge health first-hand this run: `get_system_info` — Oracle Server 1 ONLINE, Oracle Server 2 ONLINE, S2 git `38ff1e70`; tools list includes `run_shell` (31 tools).

## Machine QA gates — recorded BLOCKED, per standing ruling

- Per candidate: duration (15–60s) PASS; licence PENDING; caption-track count, BGM presence, watermark, loudness BLOCKED. The media gates still need a download: yt-dlp download broken on S2 since 2026-11-24 (YouTube n-challenge unsolvable, SABR-only streaming experiment, zero formats); VYR-056 leg CLOSED as unachievable (coordinator ruling 4). WATCH151 ruling 1 (gates PENDING/BLOCKED acceptable, proceed) stands.
- "Passing all gates" in this lane means passing all exercisable gates (duration + VYR-065 niche guard), with media gates recorded BLOCKED — the same reading as the VYR-087 run-6 pool (work PR #2020 merged). No download was attempted this run; the broken-download state is inherited from the standing record, not re-proven.

## Overlap note — VYR-088 (Muse 3)

- TASK-VYR-088 ("run 7 + machine-QA dry-run over the run-6 pool") is assigned to Muse 3 as queue position 3 (WATCH200 §2; M3 currently on INT-056). VYR-088's first bullet and VYR-089's acceptance cover the same run-7 pool. This claim stands per the pull model (board AVAILABLE / owner null, verified first-hand; M9's re-slot accepted). If M3's run-7 prep lands first or in parallel, the coordinator reconciles the two pools — this doc does not claim VYR-088's scope. The QA dry-run over the run-6 pool belongs to VYR-088, not this task.

## Decisions owed to Muse

1. **VYR-088 / VYR-089 reconciliation** (see above): one run-7 pool or two? If one, which file is canonical?
2. **Exclusion-set gap:** the 84-ID S2 sets are gone from both the repo and S2. Rebuild from hub/board records, accept the 40-ID repo set, or treat the gap as acceptable for cycle 7 given the niche-guard screen?
3. **Low-view candidates:** 2 of the 5 have 119 / 8 views. Keep them in the cycle-7 pool (no view gate exists) or drop them and require a deeper round for replacements?

## States

- Implemented YES (pool of 5 filed; S2 discovery leg run first-hand) / tested NO (no download, no render) / merged NO (work PR follows) / deployed N/A / production-verified NO (discovery only; loop OFF, uploader paused, renders held unlisted, no renders in this task).
- No repo code executed (no script changes); no S2 change made (read-only flat-playlist queries only); no fleet action taken.

## Next

- Work PR with this doc + `TASK-VYR-089-POOL.json` (no board hunk); paired verification owed; board flip AVAILABLE → CLAIMED rides in the coordinator board PR.

— Muse 14
