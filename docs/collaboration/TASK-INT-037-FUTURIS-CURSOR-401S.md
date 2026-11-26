# TASK-INT-037 — Futuris cursor 401s: verification + CI wiring (Muse 1 close-out)

**Task:** TASK-INT-037 — "IntelX: root-cause and fix the Futuris cursor 401s so scheduled research cycles stop failing auth" (P1, queue position 3)
**Claim:** hub #1483 comment 7177626435, 2026-11-26 ~04:59 IST (Muse 1), on coordinator assignment WATCH122 (7176443876) + WATCH123 nudge (7176656559). M3 non-poster re-slot; M3's prior branch carried zero commits, 1088 behind main — filed fresh, not started from it.
**Branch:** `muse1/task-int-037-futuris-cursor-401s` @ `a0a45bdf`
**Board record verified:** CLAIMED / owner muse_3 / branch muse3/task-int-037-futuris-cursor-401s / pr null on main 8600d3e4 (board blob 153ac2fe) and on the branch base a0a45bdf (same blob — the board did not move between the two). The INT-037 → muse_1 flip rides in coordinator board PR #1909 (open at filing; CI 8/9 green + 1 failure on the roster/task-ID check — the coordinator's rebuild, not this PR's).

## 1. The 401 source — named with log evidence (leg 1: DONE, verified first-hand)

The rejecting check is Memora `authenticate_agent` — `hmac.compare_digest` against the registry value for agent `futuris` (`Memora/apps/api/routers/v1_events.py` `GET /cursor` requires `Depends(authenticate_agent)`). The presented value was the **stale `FUTURIS_MEMORA_API_KEY`** from the Futuris `.env` on S2 — a leftover from the pre-TASK-MEM-005-R1 design, matching neither the registry value nor the valid per-agent `FUTURIS_API_KEY`. It shadowed the valid key on both the cursor-poll path and the notice-write path.

Log evidence (filed in repo, re-read first-hand this run):
- Storm leg: 174 cursor 401s in 45 min before 16:07 IST 2026-11-23 (`GET /v1/events/cursor?consumer_id=futuris-cloud-v1` → HTTP 401 from 10.0.0.120 every ~15 s) — `docs/collaboration/TASK-FUT-022-401-STORM.md`.
- Live fix leg: stale line removed from `Futuris/.env` on S2 + `Futuris.service` restarted 2026-11-23 ~16:14 IST (FUT-022); 0 `futuris-cloud-v1` 401s in the 90 s after; first successful poll 16:15:34 IST (`memora_events_consumed count=41`).
- Post-fix leg: M8's S1 journal probe, live run 3 ~13:05 IST 2026-11-24 (grant: watch 7124945395 ruling 5) — 949 `consumer_id=futuris-cloud-v1` requests over 08:41:52 → 12:59:26 IST (~4h17m), **0 true HTTP 401s**; the 5 loose "401" grep hits are all source ports on 200-OK lines, filed verbatim in `docs/collaboration/TASK-INT-037-CHECKPOINT-5.md`.

Cursor path (re-read first-hand on main a0a45bdf): `Futuris/futuris/integrations/memora_event_consumer.py` (`CONSUMER_ID = "futuris-cloud-v1"`, `POLL_INTERVAL_SECONDS = 15`) calls `client.read_event_cursor("futuris", CONSUMER_ID)` via the `memora_client` shim → `memora_cloud_fallback.MemoraClient._request`. Key resolution there: `self.api_key or FUTURIS_MEMORA_API_KEY or FUTURIS_API_KEY`; `MEMORA_API_KEY` never consulted (TASK-MEM-005-R2). The chain order is deliberate and unchanged — checkpoint 1 proved the follow-up "drop the dedicated key from the chain" would be wrong.

## 2. The fix — merged (leg 2: DONE, verified first-hand)

PR #1661 (Muse 3, "Memora 401 guard — retry once with next chain key + loud warning") **merged 2026-11-24 17:26:40 IST, merge 547cbd98**, head 44f845cf. Its diff: `memora_cloud_fallback.py` (+86/−30), the guard test file (+90/−0), 5 checkpoint docs.

Verified first-hand on current main a0a45bdf (blobs API):
- `Futuris/futuris/integrations/memora_cloud_fallback.py` blob `14c06443` — byte-identical to the #1661 head. Guard present and read: `_key_candidates(agent)` returns ordered `(label, key)` candidates (explicit `api_key` → dedicated `{AGENT}_MEMORA_API_KEY` → per-agent `{AGENT}_API_KEY`, deduped by value, `MEMORA_API_KEY` never); `_request` walks at most the first two candidates — on HTTP 401 it logs a loud warning naming the rejected key label (never the value) and retries the same request ONCE with the next key; a second 401 returns the error dict; non-401 errors never retry.
- `Futuris/tests/integrations/test_memora_cloud_fallback_keys_futuris.py` blob `cedbb15c` — byte-identical to the #1661 head. 8 tests: 4 MEM-005-R2 chain-order + 4 INT-037 guard (`test_dedicated_key_401_retries_once_with_peer_key`, `test_401_on_both_keys_returns_error`, `test_401_without_fallback_key_does_not_retry`, `test_non_401_error_does_not_retry`).
- File history (commits API): nothing has touched `memora_cloud_fallback.py` since M3's guard commit `5fa13b4e` (2026-11-24) — the guard is intact on main. PR #1491 (FUT-022) carries no code change (docs + board flip only, verified in checkpoint 3) — the guard in #1661 is the merged fix, not #1491.

## 3. Three clean cycles (leg 3: SATISFIED per the coordinator's ruling)

Ruling (watch 7126818611, 14:17 run 2026-11-24): "cycle" = the IntelX scheduled research cycle (`AutonomousResearcher`, `RESEARCH_CHECK_INTERVAL_SECONDS = 900`, 15 min); observation = the 15 s poll windows aggregated per cycle, 3 consecutive cycles at 0 true 401s.

M8's window (08:41:52 → 12:59:26 IST 2026-11-24, 15,454 s ≈ 17.2 cycles, 949 cursor requests ≈ 55 polls/cycle, 0 true 401s in every cycle) exceeds the bar — 17 consecutive clean cycles, raw counts filed in checkpoint 5. No cycle in the window shows a 401.

## 4. New finding this run — the guard tests never ran in CI (fixed in this PR)

The CI "Run Futuris tier-1 tests" step (`.github/workflows/friday-universe-ci.yml`) listed only 2 files (`tests/test_futuris_health_contract.py`, `tests/api/test_health.py`). The guard test file was collected by no CI job — the FUT-030 lesson. M3's 8/8 was a local run only; #1661's CI 10/10 green did not prove the guard tests ran.

**Fix in this PR (the only code change):** the keys test file now rides in the Futuris tier-1 pytest invocation (8 tests; stdlib-only imports, loads the fallback module by path, runs in this venv). CI on this PR's head is the proof of the run — the test job's log must show the 8 tests collected and passing. The tier-1 collection gate (`scripts/tier1_collection_gate.py`) checks a FIXED list of 21 files; adding a file to an invocation does not break it (the 2 fixed Futuris files remain collected).

## 5. Fresh S2 live state (bridge read-only probes, 2026-11-26 ~05:09–05:11 IST)

- `Futuris.service`: **inactive / dead, MainPID 0, NRestarts 0** — no Futuris process on S2; its journal has no entries.
- `IntelX.service`: **inactive / disabled** (stopped+disabled since 2026-11-24 19:09:21 UTC, as recorded).
- `/opt/friday_universe/Futuris/.env`: **absent** (only `.env.example` remains) — no stale key can shadow anything on S2; the FUT-022 live fix's target file is gone with the service move. Live Futuris runs on bridge server 6 / AWS (not reachable from this bridge, which serves Oracle S1/S2 only).
- `/opt/friday_universe/IntelX/data/`: absent from the S2 checkout (HEAD 2c960cb7); the IntelX outbox/state.json paths from the Nov 24 checkpoints no longer resolve there.
- Bridge flakiness: 4 dropped calls during these probes (RemoteDisconnected / IncompleteRead); each retried, the successful probes are the ones cited above.

Interpretation, stated plainly: **no S2-side cursor-401 source remains** — the S2 cursor poll does not run anymore. A fresh three-cycle live re-probe would need the live Futuris observation path (bridge server 6 / AWS) plus hub clearance; it is NOT attempted here (owner stop order in force, no restarts/deploys without Muse's hub clearance). The filed M8 window (§3) remains the evidence of record for leg 3. No live change was made or attempted.

## 6. Five states

- implemented: YES — guard merged via PR #1661 (2026-11-24); CI wiring for its tests in this PR.
- tested: PENDING CI ON THIS PR — the 8 guard tests ran 8/8 locally for M3; this PR's CI run is the proof they run in CI (verify the test-job log shows them collected and passing before merge).
- merged: NO (Muse merges; this PR is the close-out).
- deployed: NO — the guard ships with the next Futuris deploy; CD broken + owner stop order, no deploy attempted.
- production-verified: NO — fresh three-cycle live re-probe needs the live-Futuris observation path + hub clearance (see §5); the filed M8 window is the evidence of record.

## 7. Board flip

INT-037 CLAIMED/muse_3 → IN_REVIEW/muse_1 (branch `muse1/task-int-037-futuris-cursor-401s`, pr this PR). Coordinator board PR #1909 carries the same owner flip; if it merges first, the flip here is only branch + pr + IN_REVIEW — verified at PR time. After this PR merges, the MERGED flip rides in the coordinator's board PR.

— Muse 1
