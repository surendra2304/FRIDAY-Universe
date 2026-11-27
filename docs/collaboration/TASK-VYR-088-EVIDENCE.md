# TASK-VYR-088 — Checkpoint 1: scoping — supervised-cycle candidate pool run 7 + machine-QA dry-run over the run-6 pool

- Task: TASK-VYR-088 (P1, VyralX). Claimed 2026-11-27 ~15:01 IST per Burn Enforcer 14:44 §D (hub #2045 comment 7214462343) — head task, answers M3's free/requesting post 14:31 IST (hub 7214192517). Branch `muse3/task-vyr-088-candidate-pool-prep-run-7` @ `b74efa00` (adopted per board watch200 note; claim-only, zero work commits). Board record on main `eb7f81d0`: AVAILABLE / owner muse_3; flip to CLAIMED rides the next coordinator board PR (Burn Enforcer 14:44 §H).
- Prior state: drafted by coordinator watch177 (2026-11-26) as M3 double-scope; released by M3 (hub 7202036053); pool/HOLD by coordinator watch182 follow-up pending a coordinator ruling. The Burn Enforcer 14:44 §D assignment IS that ruling — the HOLD is lifted by explicit assignment. TP14's claim (hub 7198307780) never started the task.
- Paired duty held alongside: PR #2103 verdict VERIFIED filed (review 6086088105, ~15:03 IST, due ~15:45) — CI 9/9 on head `17368e04`, mergeable True, 1-file evidence-only diff read in full, substance verified on main.

## Acceptance (board, main `eb7f81d0`)

1. Prepare the run-7 supervised-cycle candidate pool from most-popular-video discovery + machine QA gates (caption-track count, BGM presence, watermark, loudness), following the VYR-053/054/055 pattern; file the pool (POOL.json + evidence doc) with per-candidate QA results.
2. Machine-QA dry-run over the run-6 pool (VYR-086/087) to shake out the gates before the next supervised cycle; file the dry-run results.
3. Loop stays OFF, uploader stays paused, renders held unlisted — candidates only, no publish step.

## Scoping findings (verified first-hand on main `eb7f81d0`, 2026-11-27 ~15:05 IST)

- `docs/collaboration/TASK-VYR-088-EVIDENCE.md` does NOT exist on main (contents API 404) — this doc creates it. No prior VYR-088 execution exists.
- Run-6 pools read first-hand: `TASK-VYR-086-POOL.json` (8 candidates, Muse 14, discovery 2026-11-27 ~13:12 IST) and `TASK-VYR-087-POOL.json` (4 candidates) — 12 candidates total for the dry-run. Every candidate: duration gate 15–60s PASS, niche guard PASS (4 of the 8 VYR-086 carry CAUTION flags: licence/origin or format re-check owed at QA); licence PENDING; caption-track count, BGM presence, loudness BLOCKED; watermark BLOCKED (VYR-089 pool shows the same pattern).
- Run-7 precedent: `TASK-VYR-089-POOL.json` (5 candidates, Muse 14, PR #2067 merged 11:43 IST) is a separate cycle-7 pool. VYR-088's pool must be a FRESH set: new queries, screened against the union exclusion set (46 repo IDs per VYR-086 + VYR-086's 8 + VYR-087's 4 + VYR-089's 5 = 63 IDs, all verified in the pool JSONs on main). [CORRECTED in checkpoint 3: the true union is 54 unique IDs — VYR-087's 4 and VYR-089's 5 are already inside the 46; 46+8+4+5 double-counts them.] Overlap question flagged for the coordinator: two cycle-7 pools exist by design (VYR-088 drafted first, VYR-089 executed first); VYR-088 files the second, distinct set.
- Discovery route (established VYR-055/086/087/089 pattern): S2 flat-playlist via bridge `run_shell` under standing clearance 7200564540, `ytsearch10`, 10 results per query, read-only, no sign-in, no download; raw `.jsonl` kept in S2 `/tmp`. VYR-065 guard run first-hand locally on queries + candidates before issuing.
- Machine-QA gates — standing record: media gates need a download; yt-dlp download broken on S2 since 2026-11-24 (YouTube n-challenge unsolvable, SABR-only streaming, zero formats); VYR-056 leg CLOSED as unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates PENDING/BLOCKED acceptable, proceed) stands. Dry-run plan: (a) re-attempt caption-track count WITHOUT download — subtitle-list metadata via `yt-dlp -j` is metadata-only and may unblock that one gate; (b) re-probe the download path once to confirm the broken state is unchanged (record, do not re-prove at length); (c) record BGM presence / watermark / loudness as BLOCKED with the standing reason if the download path is still down. No render, no publish.
- Exclusion-set gap (carried from VYR-086): the 84-ID S2 sets (`rejected_sources.json`, `published_shorts_manifest.json`, `viral_loop_manifest.jsonl`) are unretrievable from repo and S2. Mitigation: repo-union exclusion set + VYR-065 guard screen + CAUTION flags. Decision owed to Muse (VYR-086 decisions §1).
- Safety: read-only S2 probes only, `/tmp` scratch; no server moves (owner stop order 7130069033); no deploys/restarts; loop OFF, uploader paused, renders unlisted.

## Next

- Checkpoint 3 DONE this run (see below) — uniformity sample 3/3 bot-blocked, run-7 pool of 11 filed (`TASK-VYR-088-POOL.json`), dry-run over the run-6 pool complete.
- Work PR with evidence doc + POOL.json (no board hunk); paired verification owed; board flip rides the coordinator board PR.

## Checkpoint 3: uniformity sample + run-7 discovery + pool filing (2026-11-27 ~15:16–15:25 IST, hourly self-check)

- Uniformity sample — video-page block is UNIFORM across both run-6 pools (3/3): `bRfoNfGBL1o` (checkpoint 2) + `tBM92m6IZf4` (VYR-086) + `ETHAGKZlbcY` (VYR-087) all fail caption-track extraction with `ERROR: [youtube] <id>: Sign in to confirm you're not a bot` (cookies required). True exit code re-probed on `tBM92m6IZf4`: yt-dlp exit=1, empty stdout. (The `[exit 0]` printed after the sample probes is a pipe artifact — PIPESTATUS read after an intervening `echo` — not yt-dlp's status; the checkpoint-2 probe command had the same shape, and its evidence is likewise the ERROR text, now corroborated by the exit=1 re-probe.) No download attempted on the sample candidates; download stays down at extraction.
- Machine-QA dry-run over the run-6 pool (12 candidates) — per-candidate results, sample evidence (not 12 identical failing probes):

| Candidate | Pool | Duration | Licence | Caption-track count | BGM | Watermark | Loudness |
|---|---|---|---|---|---|---|---|
| `bRfoNfGBL1o` | VYR-086 | 47s PASS | PENDING | BLOCKED (probed) | BLOCKED | BLOCKED | BLOCKED |
| `tBM92m6IZf4` | VYR-086 | 21s PASS | PENDING | BLOCKED (probed) | BLOCKED | BLOCKED | BLOCKED |
| `7eA8EF12iSw` | VYR-086 | 46s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `D0vaOZho524` | VYR-086 | 27s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `hBRaW8m_eD4` | VYR-086 | 27s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `iAhJZTBfDqs` | VYR-086 | 58s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `73eQBzC2bpo` | VYR-086 | 40s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `oZLo2Pmx-mQ` | VYR-086 | 47s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `ETHAGKZlbcY` | VYR-087 | 52s PASS | PENDING | BLOCKED (probed) | BLOCKED | BLOCKED | BLOCKED |
| `o8NRDVVO0Lo` | VYR-087 | 16s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `SnVtdyiFjFM` | VYR-087 | 56s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |
| `TLRhJ2zlhx8` | VYR-087 | 52s PASS | PENDING | BLOCKED (sample) | BLOCKED | BLOCKED | BLOCKED |

  Dry-run verdict: the machine-QA gates cannot run without a download, and the download path is now blocked at extraction (bot-check), not at format selection — a NEW failure mode since VYR-086's 13:12 IST discovery (search still works, video-page extraction does not). BGM presence, watermark and loudness stay BLOCKED for all 12. The 4 VYR-086 CAUTION flags (2 WooGlobe aggregator, 1 RM Videos aggregator-style, 1 multi-trick kendama list) still stand — licence/origin or format re-check owed at QA. Cookie jar still absent on S2 — owner sign-in step is a decision owed to Muse, not attempted.
- Run-7 discovery — 6 NEW queries, all ALLOW under the VYR-065 guard (run first-hand locally, guard `VyralX/app/services/niche_guard.py` @ `dada67315911` on main; all 6 fresh, none in the 18 used queries): mesmerizing calligraphy writing short; incredible poi spinning trick short; satisfying candle making short; amazing rubiks cube speed solve short; oddly satisfying paper cutting art short; amazing beatbox performance short. S2 flat-playlist `ytsearch10`, 10 results per query, all exit 0, 60 results read. Raw dumps on S2 `/tmp/vyr088_q1.json` … `/tmp/vyr088_q6.json`; extraction via `/tmp/vyr088_extract.py`.
- Run-7 pool: 11 fresh candidates (filed in `TASK-VYR-088-POOL.json`), 9 clean-PASS + 2 CAUTION. Shortlist (clean): `uj57NSz8Yqw` (calligraphy 36s), `KlbEGXkxPhY` (calligraphy 20s), `qV28oUrzJFY` (fire poi 53s), `i-clg1-5sYE` (poi tutorial 38s), `5btlHEYHGqY` (LED poi 56s), `kEAOZpyGi5U` (candle pour 35s, 10 views), `S8g8inWXJDk` (Rubik's world record 18s), `QfVXh_wCvlY` (paper-cut shadow box 31s), `F68Kkr0nkAo` (paper ASMR 35s, 1 view). CAUTION: `5hx28CmXe0Q` (4-year-old in video — age/consent re-check owed at QA), `BAxlCllYoAI` (kids-named channel + 9 views — licence/origin re-check owed). Per-query yield: calligraphy 2, poi 3, candle 1, Rubik's 2, paper 3, beatbox 0 (all 10 beatbox results 128–273s; lane exhausted at top-10 depth). Near-misses: `xqnJEwcNDuM` 64s, `7xGY6vThfgc` 11s, `Ir5vsqMiD7k` 11s.
- Exclusion-set correction (verified first-hand): the checkpoint-1 "63-ID union" double-counts — VYR-087's 4 and VYR-089's 5 are already inside the 46-ID set from `TASK-VYR-086-POOL.json` (both subsets verified against the pool JSONs). True union = 54 unique IDs (46 + VYR-086's 8). Zero shorts-length results hit the set this run. The 84-ID S2 exclusion gap stands (carried decision owed to Muse).
- Data quality: all 60 flat-playlist rows carried full metadata (no null views/uploaders, unlike VYR-086 queries 3–4); ytsearch10 relevance order, not view-sorted (same standing note). Bridge transport flaked zero times this leg (4 bridge calls, all exit 0 first try). No S2 change made (only `/tmp` scratch files); no server moves; loop OFF, uploader paused, renders unlisted.

## Checkpoint 2: dry-run probes — bridge alive, discovery alive, video-page extraction bot-blocked (2026-11-27 ~15:10–15:25 IST)

- Bridge health first-hand: `get_system_info` exit 0 — Oracle Server 1 ONLINE, Oracle Server 2 ONLINE; `run_shell` on Server 2 exit 0 (`hostname` → `friday-universe-vnic-2`). Transport flaked zero times this run (contrast VYR-086's 3 flakes).
- Discovery path ALIVE: flat-playlist `ytsearch5:amazing diabolo juggling trick short` on S2 returned 5 results with full metadata (titles, durations, view counts, channels), exit 0, no bot-block. Run-7 pool leg viable via the established route.
- Caption-track count via video-page metadata: BLOCKED — `yt-dlp --print "%(subtitles)j"` on run-6 candidate `bRfoNfGBL1o` fails at extraction: "Sign in to confirm you're not a bot" (cookies required). This is NEW since VYR-086's 13:12 IST discovery: search still works, but video-page extraction is now bot-gated.
- Download re-probe (once, per checkpoint-1 plan): `yt-dlp -f worst -o /tmp/vyr088_dltest.mp4` on the same candidate fails at the same bot-check; no file created. Download still down — now blocked at extraction, not at format selection (supersedes the standing n-challenge / SABR-only / zero-formats failure mode). BGM presence, watermark, loudness stay BLOCKED (need a download).
- Cookie jar still absent on S2 (verified by VYR-086 ~13:15 IST; no change attempted). Supplying cookies needs an owner sign-in step — decision owed to Muse, not attempted here.
- yt-dlp prints a Python 3.10 deprecation warning on S2 — cosmetic, no effect.
- Dry-run method (recorded, not yet executed in full): probe a 3-candidate sample across both run-6 pools to confirm the block is uniform; record all 12 candidates BLOCKED with the sample evidence rather than burning 12 identical failing probes. Per-candidate table rides checkpoint 3.

## States

- Implemented YES (run-7 pool of 11 filed + dry-run over the run-6 pool complete; evidence doc + POOL.json) / tested NO (no download, no render) / merged NO (work PR follows) / deployed N/A / production-verified NO (discovery + dry-run only; loop OFF, uploader paused, renders held unlisted, no renders in this task).

— Muse 3
