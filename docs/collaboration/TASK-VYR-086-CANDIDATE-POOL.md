# TASK-VYR-086: Candidate pool — supervised cycle run 6 — 8 fresh candidates — Muse 14

- Task: TASK-VYR-086 (P1, VyralX: supervised cycle run-6 candidate pool — most-popular discovery + machine QA gates). Claimed 2026-11-27 ~13:02 IST per WATCH210 §3 (hub #2045 comment 7212577169); claim confirmed by WATCH210-CORR2 (hub #2045 comment 7212599352, 13:07 IST) — "Muse 14 KEEPS TASK-VYR-086". Branch `muse14/task-vyr-086` (base main `25ce04a3`). Board AVAILABLE → CLAIMED flip rides in the coordinator board PR (standing orders — no board hunk in the work PR).
- Machine-readable pool: `docs/collaboration/TASK-VYR-086-POOL.json` — **candidates: 8, all fresh, all passing the exercisable gates**. Nothing is invented; every candidate was read first-hand from the S2 flat-playlist output.
- Discovery run: 2026-11-27 ~13:12–13:15 IST, S2 flat-playlist via bridge `run_shell` (standing clearance 7200564540; no safety flag fired), 6 NEW queries, `ytsearch10`, 10 results per query, read-only, no sign-in, no download. 60 results read. Raw yt-dlp invoked directly (same command the VYR-055 script wraps) because the script takes only `--query-index` into its hardcoded 6-query list and the run-6 queries are new. Same channel, same read-only operation class. No S2 change made (only `/tmp` scratch files).

## Safety-flag check (done first, before the live leg)

M9's VYR-086 live-discovery hold (hub #1483 comment 7201405786, ~00:45 IST) was session-specific: a git fetch in M9's own main session failed an execution-risk safety check, and M9 held its own run from that flagged fetch. It was not a task-wide ban. Cleared for Muse 14's run by:

1. Coordinator standing live-verification clearance 7200564540 (hub #1483, ~00:05 IST) — "the live-verification run of YOUR OWN task … including a supervised cycle where the task calls for one" is pre-approved.
2. WATCH210 §3 assigning VYR-086 to Muse 14 as head, confirmed by WATCH210-CORR2 (hub #2045 comment 7212599352) — "Muse 14 KEEPS TASK-VYR-086".
3. Burn Enforcer 13:00 §F (hub #2045 comment 7212471432) — run_shell is NOT down fleet-wide; M9 run_shell exit 0 on S2 12:39:53 IST.
4. No safety flag fired during this run (all 6 queries exit 0).

The BE 13:00 §G / WATCH210-CORR §5 applications of the same clearance to M1 VOI-030, TP12 STR-078 and TP4 STR-099 own-task live legs are the same reading.

## Result: 8 fresh candidates from 60 results

| Query | Returned | Shorts-length (15–60s) | Fresh |
|---|---|---|---|
| "satisfying cake decorating short" | 10 | 0 | 0 |
| "incredible contact juggling short" | 10 | 2 | 2 |
| "satisfying pottery wheel throwing short" | 10 | 1 | 0 |
| "amazing kendama trick short" | 10 | 1 | 1 |
| "satisfying glass blowing art short" | 10 | 0 | 0 |
| "amazing diabolo juggling trick short" | 10 | 5 | 5 |

New queries: the VYR-089 cycle-7 set and the old script set are both exhausted for fresh Shorts at this depth, so 6 new niches were picked and guard-checked before issuing (all 6 queries ALLOW under the VYR-065 guard, run first-hand locally — see below).

## The 8 candidates — all exercisable gates PASS

| # | Candidate | Source | Duration | Views | Verdict |
|---|---|---|---|---|---|
| 1 | "45 seconds of Contact Juggling (by Joseph Viatte)" (id `bRfoNfGBL1o`) | Contact-juggling query, rank 4; https://youtube.com/shorts/bRfoNfGBL1o | 47s — PASS | 12,556 (exact); uploader Joseph Viatte | CANDIDATE, clean — duration PASS, niche guard PASS (single performance by the named creator). |
| 2 | "Woman Shows off Amazing Juggling Skills - 1118283" (id `tBM92m6IZf4`) | Contact-juggling query, rank 7; https://youtube.com/shorts/tBM92m6IZf4 | 21s — PASS | 4,641 (exact); uploader RM Videos | CANDIDATE, CAUTION — duration PASS, guard rule layer ALLOWs it, but aggregator-style channel + numeric-suffixed title suggests a re-uploaded clip; licence/origin re-check owed at QA. |
| 3 | "10 INTERMEDIATE Kendama Tricks (Challenge)" (id `7eA8EF12iSw`) | Kendama query, rank 3; https://youtube.com/shorts/7eA8EF12iSw | 46s — PASS | null (flat row carried no view_count); uploader KIN KENDAMA | CANDIDATE, CAUTION — duration PASS, guard ALLOWs it, but multi-trick list format by a single creator; single-trick fit re-check owed at QA (VYR-087 `SnVtdyiFjFM` precedent). |
| 4 | "Awesome Diabolo Tricks Performance \|\| Best Viral Videos" (id `D0vaOZho524`) | Diabolo query, rank 3; https://youtube.com/shorts/D0vaOZho524 | 27s — PASS | 76 (exact); uploader WooGlobe | CANDIDATE, CAUTION — duration PASS, guard ALLOWs it ("best viral videos" is not the banned phrase "best viral clips"), but WooGlobe is a viral-video aggregator; licence/origin re-check owed at QA. Low-view flag: 76 views, recorded honestly; no view gate in the acceptance. |
| 5 | "Awesome Diabolo Tricks Performance by Girl \|\| WooGlobe" (id `hBRaW8m_eD4`) | Diabolo query, rank 4; https://youtube.com/shorts/hBRaW8m_eD4 | 27s — PASS | 314 (exact); uploader WooGlobe | CANDIDATE, CAUTION — same WooGlobe aggregator note as #4; licence/origin re-check owed at QA. |
| 6 | "MOST AMAZING DIABOLO TRICKS" (id `iAhJZTBfDqs`) | Diabolo query, rank 6; https://youtube.com/shorts/iAhJZTBfDqs | 58s — PASS | 478 (exact); uploader CHOLLET camille | CANDIDATE, clean — duration PASS, niche guard PASS (single video by a single creator). |
| 7 | "Juggling with diabolo" (id `73eQBzC2bpo`) | Diabolo query, rank 8; https://youtube.com/shorts/73eQBzC2bpo | 40s — PASS | 1,721 (exact); uploader facefocus | CANDIDATE, clean — duration PASS, niche guard PASS. |
| 8 | "Awesome diabolo tricks" (id `oZLo2Pmx-mQ`) | Diabolo query, rank 10; https://youtube.com/shorts/oZLo2Pmx-mQ | 47s — PASS | 345 (exact); uploader TheKumba | CANDIDATE, clean — duration PASS, niche guard PASS. |

## Next-cycle shortlist (named)

The 4 clean-PASS candidates are the next-cycle shortlist: `bRfoNfGBL1o` (contact juggling, 47s), `iAhJZTBfDqs` (diabolo, 58s), `73eQBzC2bpo` (diabolo, 40s), `oZLo2Pmx-mQ` (diabolo, 47s). The other 4 stay in the pool with CAUTION flags; each needs its named licence/origin or format re-check at QA before the cycle uses it.

## Near-misses — duration fails / excluded

| Candidate | Duration | Verdict |
|---|---|---|
| "Contact Juggling short" (`PI66lh92GZ0`, Cory J Oliver) | 64s | FAILS 15–60s by 4s |
| "Glassblower Makes Intricate Horse Effortlessly" (`6xf1Qwj7X_w`, Storyful Viral) | 97s | FAILS (shortest glass-blowing result) |
| "Satisfying Pottery Spiral Designs #Shorts" (`OfEaVD7TtXM`) | 41s | In range but EXCLUDED — known ID (VYR-055-REFRESH-3 candidate), caught by the 46-ID set |

## Exclusion sets — verified first-hand

- Applied: 46 known IDs read first-hand from the repo pool JSONs on main (VYR-051: 12, VYR-053: 6, VYR-054: 2, VYR-055: 7, VYR-055-REFRESH-3: 5, VYR-057: 4, VYR-087: 4, VYR-089: 5) + `CpQGaTtppnU` (VYR-037 pool candidate 2). Zero overlap with the 8 candidates. Full list in `TASK-VYR-086-POOL.json` (`excluded_ids`).
- CORRECTION to VYR-089's 40-ID list: it omitted `An4zMciturw` (VYR-055-REFRESH-3 candidate); the union here is 46, and the one shorts-length result that hit the set (`OfEaVD7TtXM`) was excluded on it.
- NOT applied (gap, carried from VYR-087): the S2 exclusion files that held 84 known IDs at VYR-055 time (`rejected_sources.json` 51, `published_shorts_manifest.json` 11, `viral_loop_manifest.jsonl` 11) are unretrievable — absent from the repo on main and from S2 (verified in VYR-087 checkpoint 2). Mitigation applied: every result screened against the VYR-065 banned niches with the repo guard run first-hand locally this run — all 8 candidates + all 6 queries ALLOW; the 4 CAUTION flags above are operator judgment on top of the rule layer (the guard is a rule layer, not a classifier). The gap is carried as a decision owed, not hidden.

## Data-quality notes (S2 flat-playlist output, 13:12–13:15 IST)

- `ytsearch10` returns relevance order, NOT view-count sorted: views are non-monotonic in every query that carried views (e.g. query 2: 153, 12.5M, 5.3K, 12.5K, 341, 27.8K, 4.6K, 371K, 26.6K, 117). Same as the VYR-055/VYR-089 method (ytsearch10, no sort param); the "most-popular" label is the lane's name, not a verified sort. Ranks are the order returned.
- Flat-playlist rows this run were metadata-thin on queries 3–4: all 10 rows of query 3 and 9 of 10 rows of query 4 carried `view_count` null and uploader/channel null (only `7eA8EF12iSw` carried an uploader). Durations were present on every row. Views are recorded null where the row carried none — nothing was filled in from another source.
- No cookie jar on S2 (`VyralX/data/youtube_cookies.txt` absent, `ls` exit 2, verified this run ~13:15 IST); all 6 queries returned 10 results each, exit 0, no bot-block.
- One query (contact juggling) hit a quoting/pipe artifact on the first attempt (empty extraction, exit 0) — re-run with the file-based extractor (`/tmp/vyr086_extract.py` on S2, raw `.jsonl` per query) returned all 10 rows; the artifact was in my extraction pipe, not in yt-dlp. Raw dumps kept on S2 at `/tmp/vyr086_q1.jsonl` … `/tmp/vyr086_q6.jsonl`.
- Bridge transport flaked 3 times during this leg (initialize / notifications-initialized drops) and recovered on retry each time; no data lost, no query re-run needed beyond the retries. Same flakiness class as WATCH210 §6 (a dropped bridge call is transport — retry first).
- Bridge health first-hand this run: `get_system_info` — Oracle Server 1 ONLINE, Oracle Server 2 ONLINE, S2 git `83d53187`; tools list includes `run_shell` (bridge v1.30.0).

## Machine QA gates — recorded BLOCKED, per standing ruling

- Per candidate: duration (15–60s) PASS; licence PENDING; caption-track count, BGM presence, watermark, loudness BLOCKED. The media gates still need a download: yt-dlp download broken on S2 since 2026-11-24 (YouTube n-challenge unsolvable, SABR-only streaming experiment, zero formats); VYR-056 leg CLOSED as unachievable (coordinator ruling 4). WATCH151 ruling 1 (gates PENDING/BLOCKED acceptable, proceed) stands.
- "Passing all gates" in this lane means passing all exercisable gates (duration + VYR-065 niche guard), with media gates recorded BLOCKED — the same reading as the VYR-089 cycle-7 pool (work PR #2067 merged) and the VYR-087 run-6 pool (PR #2020 merged). No download was attempted this run; the broken-download state is inherited from the standing record, not re-proven.

## Overlap note — VYR-088 (Muse 3) / VYR-089

- TASK-VYR-088 ("run 7 + machine-QA dry-run over the run-6 pool") is assigned to Muse 3 (WATCH200 §2; M3 currently on INT-056). The machine-QA dry-run over the run-6 pool belongs to VYR-088, not this task — this task files the run-6 pool itself (the pool VYR-088's dry-run will run over). VYR-089 (cycle 7, PR #2067 merged 11:43 IST) is a separate, later pool; no candidate overlaps it (all 5 of its IDs are in the 46-ID exclusion set).
- Loop stays OFF, uploader stays paused, renders held unlisted — candidates only, no publish step.

## Decisions owed to Muse

1. **Exclusion-set gap:** the 84-ID S2 sets are gone from both the repo and S2. Rebuild from hub/board records, accept the 46-ID repo set, or treat the gap as acceptable for run 6 given the niche-guard screen + 4 CAUTION flags?
2. **CAUTION candidates:** 4 of the 8 carry licence/origin or format CAUTIONs (2 WooGlobe aggregator, 1 RM Videos aggregator-style, 1 multi-trick kendama list). Keep them in the run-6 pool pending QA re-check, or drop them and require a deeper round for replacements?
3. **Thin flat-playlist metadata:** queries 3–4 returned null views/uploaders on most rows. Accept nulls in the pool (done here), or treat view-less rows as unverifiable and exclude them from future pools?

## States

- Implemented YES (pool of 8 filed; S2 discovery leg run first-hand) / tested NO (no download, no render) / merged NO (work PR follows) / deployed N/A / production-verified NO (discovery only; loop OFF, uploader paused, renders held unlisted, no renders in this task).
- No repo code executed (no script changes); no S2 change made (read-only flat-playlist queries only, `/tmp` scratch files); no fleet action taken.

## Next

- Work PR with this doc + `TASK-VYR-086-POOL.json` (no board hunk); paired verification owed; board flip AVAILABLE → CLAIMED rides in the coordinator board PR.

— Muse 14
