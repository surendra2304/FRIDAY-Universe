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
- Run-7 precedent: `TASK-VYR-089-POOL.json` (5 candidates, Muse 14, PR #2067 merged 11:43 IST) is a separate cycle-7 pool. VYR-088's pool must be a FRESH set: new queries, screened against the union exclusion set (46 repo IDs per VYR-086 + VYR-086's 8 + VYR-087's 4 + VYR-089's 5 = 63 IDs, all verified in the pool JSONs on main). Overlap question flagged for the coordinator: two cycle-7 pools exist by design (VYR-088 drafted first, VYR-089 executed first); VYR-088 files the second, distinct set.
- Discovery route (established VYR-055/086/087/089 pattern): S2 flat-playlist via bridge `run_shell` under standing clearance 7200564540, `ytsearch10`, 10 results per query, read-only, no sign-in, no download; raw `.jsonl` kept in S2 `/tmp`. VYR-065 guard run first-hand locally on queries + candidates before issuing.
- Machine-QA gates — standing record: media gates need a download; yt-dlp download broken on S2 since 2026-11-24 (YouTube n-challenge unsolvable, SABR-only streaming, zero formats); VYR-056 leg CLOSED as unachievable (coordinator ruling 4); WATCH151 ruling 1 (gates PENDING/BLOCKED acceptable, proceed) stands. Dry-run plan: (a) re-attempt caption-track count WITHOUT download — subtitle-list metadata via `yt-dlp -j` is metadata-only and may unblock that one gate; (b) re-probe the download path once to confirm the broken state is unchanged (record, do not re-prove at length); (c) record BGM presence / watermark / loudness as BLOCKED with the standing reason if the download path is still down. No render, no publish.
- Exclusion-set gap (carried from VYR-086): the 84-ID S2 sets (`rejected_sources.json`, `published_shorts_manifest.json`, `viral_loop_manifest.jsonl`) are unretrievable from repo and S2. Mitigation: repo-union exclusion set + VYR-065 guard screen + CAUTION flags. Decision owed to Muse (VYR-086 decisions §1).
- Safety: read-only S2 probes only, `/tmp` scratch; no server moves (owner stop order 7130069033); no deploys/restarts; loop OFF, uploader paused, renders unlisted.

## Next

- Checkpoint 2: bridge health check (`get_system_info` + one `run_shell` probe), then the dry-run leg over the 12 run-6 candidates (caption metadata first, download re-probe once).
- Checkpoint 3: run-7 discovery (6 new queries) + pool filing (`TASK-VYR-088-POOL.json` + this doc updated with per-candidate QA results).
- Work PR with evidence doc + POOL.json (no board hunk); paired verification owed; board flip rides the coordinator board PR.

## States

- Implemented NO / tested NO / merged NO / deployed N/A / production-verified NO (scoping only; no live leg run yet in this checkpoint).

— Muse 3
