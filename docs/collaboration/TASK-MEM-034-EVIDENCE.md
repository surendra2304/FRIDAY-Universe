# TASK-MEM-034 — Memora auto-promotion proof, run 3

**Worker:** Muse 1 · **Date:** 2026-11-26 · **Branch:** `muse1/task-mem-034-auto-promotion-run-3`
**Board:** TASK-MEM-034 (Memora: auto-promotion proof run 3 — one lesson promoted private -> universal by repeated use)
**Assignment:** queue top-up after STR-090 MERGED, coordinator WATCH143 (hub #1483 comment 7184216469). **Claim:** issue #1483 comment 7184478984 (~11:59 IST, combined with the STR-090 merged completion).

> STATUS: CHECKPOINT 2 — live leg DONE, proof complete. The coordinator drill (WATCH158 follow-up, hub 7191062088, 2026-11-26 17:12 IST) ran the filed probe script on Server 1 at 17:10–17:11 IST: lesson `694a6843` promoted PRIVATE -> SHARED -> UNIVERSAL (dual copy `b2ca708e`), 35 PASS / 2 failed checks (both blast-radius expectations — see checkpoint 2). The open question from the drill — the second promotion `b5bfbf85` in both sweeps — is identified live and ruled below: correct and idempotent, no duplicate copy. Board: IN_REVIEW (this PR) — proof complete, awaiting peer verification + coordinator merge.

## Acceptance (board)

One real lesson promoted private -> universal by repeated use, with evidence at each step.

## Design (run 3 of the MEM-018 family, lesson variant)

One real failed-experiment lesson — the STR-044 income-fetch cap, learned from live FRIDAY Universe work this morning (STR-088 run-6 finding, fixed by STR-090) — written PRIVATE by `sentinel`, promoted by repeated need + sweep through both rungs. Replicates MEM-025 run 2 (Muse 8, live proof verified 2026-11-24 ~13:05 IST) with the new coverage being a **real lesson** (run 2's lesson was synthetic test content) and the **run-3 trace**.

Thresholds, from `Memora/core/memory/promotion.py` on main (verified this run):
- PRIVATE -> SHARED: >= 2 distinct non-owner agents, >= 3 needs total.
- SHARED -> UNIVERSAL: >= 4 distinct non-owner agents, >= 8 needs total, and >= 2 distinct needers NOT already on the SHARED allow-list (the round-1 needers land on the allow-list, so round 2 must come from outside agents).
- Dual-copy rule (`_apply_promotion`): target UNIVERSAL + `is_failed_experiment_lesson` (provenance `failed_experiment: true`, or `experiment_outcome` failed/failure, or `lesson_type: failed_experiment`) -> creates a UNIVERSAL copy, original never moves; audit row carries `failed_experiment_dual: true` + `universal_copy_id`.

Probe legs (script `docs/collaboration/TASK-MEM-034-PROBE.py` in this PR, 338 lines, `py_compile` clean; runs ON Server 1, localhost Memora `http://127.0.0.1:8002`):
- **Write:** lesson PRIVATE as sentinel, namespace `memora://sentinel/private`, content prefixed `MUSE1-TEST-MEM-034`, distinctive phrase `verdant ledger twelvefold meridian`, provenance `failed_experiment: true, experiment_outcome: failed, lesson_type: failed_experiment, test_data: true, task: TASK-MEM-034`. Expect 201; owner read 200 PRIVATE; non-owner read 404.
- **Round 1 needs:** 8 needs, 4 agents (friday x2, intelx x2, futuris x2, cortex x2); owner need expect `owner_need_ignored`. Audit baseline 0 need rows before.
- **Sweep 1:** `POST /v1/promotion/sweep {window_days: 30}` as memora. Expect `count: 1`, promotion PRIVATE -> SHARED, `path: auto_repeated_need`, blast radius exactly 1. Verify: owner read 200 SHARED; needer (friday) 200 SHARED; outsider (inference) 404; search finds the target for friday (keyword 1.0, rank 1). Sweep + visibility latencies filed.
- **Round 2 needs:** 4 needs, 2 outside agents (inference x2, stratex x2).
- **Sweep 2:** expect `count: 1`, promotion SHARED -> UNIVERSAL, `path: auto_repeated_need`, `status: promoted_dual_copy`, `universal_copy_id` present, blast radius exactly 1. Verify: original stays SHARED (owner read 200 SHARED); original as outsider still 404; copy reads 200 UNIVERSAL as inference, stratex, friday, futuris; MEM-021 decisive check (copy `hmac_signature` differs, content SHA identical, `promoted_from_memory_id` == original); search finds the copy for inference.
- **Audit:** both `MEMORY_SCOPE_PROMOTED` rows present with `auto_repeated_need`; second row `failed_experiment_dual: true`.
- **Journal:** runner checks the Memora journal around the probe window — no ERROR, no traceback (runner step; script cannot read server logs from here).

Auth (per `Memora/apps/api/dependencies.py`, verified on main this run): `X-Agent-Name` + per-agent `X-API-Key`, env vars `SENTINEL_API_KEY`, `FRIDAY_API_KEY`, `INTELX_API_KEY`, `FUTURIS_API_KEY`, `CORTEX_API_KEY`, `INFERENCE_API_KEY`, `STRATEX_API_KEY`, `MEMORA_API_KEY`, read from the service's own env file at runtime on the server and never printed or copied. Numbered JSON responses to `/tmp/muse1_mem034/` on Server 1.

## The lesson (real, from STR-088/STR-090 work this morning)

> The STR-044 reconciliation job's income fetch made a single `/fapi/v1/income` call with `limit=1000` and no pagination; once more than 1000 income rows existed since `RESET_MS`, every newer row was silently dropped — reported funding +0.2073 vs true +0.4581, frozen since 2026-11-25T08:00:00Z. The fix was to paginate the fetch (start at the last returned row's time, dedup) and round once in `income_sums` (TASK-STR-090, work PR #1950, merged 2026-11-26 11:17 IST, merge `250cf2b4`; CI 10/10 incl contracts; 4 new tests verified from the contracts job log: 579 passed / 6 skipped / 0 failed).

This is a real failed experiment: the job's reporting was wrong in production (demo) until the fix. It is filed as a probe record (`test_data: true`) so the promotion trace stays identifiable and re-runnable.

## Preconditions verified first-hand, 2026-11-26 ~12:04 IST

- Board on main `b1f24f22` (blob `c7226033`, 3,011,005 bytes): MEM-034 AVAILABLE / owner muse_1 / branch null / pr null; claim evidence 7184478984 present. Branch `muse1/task-mem-034-auto-promotion-run-3` @ `b1f24f22` on remote (claim-time head, no work commits yet). Queue: IG-FRD-010-RETEST-01 (PARKED, no laptop connected) -> MEM-034. (Note: the claim post names TASK-VOICE-E2E-003 as the queue head — that record is owned by muse_10 on main `b1f24f22`; it is not in Muse 1's queue. My queue is RETEST-01 -> MEM-034.)
- STR-090 MERGED on the same board (pr 1950, merge `250cf2b4`); work PR #1950 merged by Surendra 2026-11-26T05:47:04Z, CI 10/10 green incl contracts.
- Code on main: promotion thresholds + dual-copy rule (`Memora/core/memory/promotion.py`: `SHARED_MIN_DISTINCT_AGENTS = 2`, `SHARED_MIN_TOTAL_NEEDS = 3`, `UNIVERSAL_MIN_DISTINCT_AGENTS = 4`, `UNIVERSAL_MIN_TOTAL_NEEDS = 8`, `UNIVERSAL_MIN_OUTSIDE_AGENTS = 2`; `_apply_promotion` dual-copy branch with `failed_experiment_dual: true` + `universal_copy_id`; `is_failed_experiment_lesson` provenance rules), sweep/need endpoints (`Memora/apps/api/routers/v1_promotion.py`: sweep is memora-identity only, returns `{promotions, count}`), key env names (`Memora/apps/api/dependencies.py`: `X-Agent-Name` + `X-API-Key`).
- Probe script adapted from the filed run-2 script (`docs/collaboration/TASK-MEM-025-PROBE.py`, 335 lines): only the header, outdir (`/tmp/muse1_mem034`), phrase, prefix, lesson content, and task references changed (diff reviewed line by line); `py_compile` clean. All run-2 fixes are carried over (port 8002, lowercase `memory_type`, `hmac_signature`, `promoted_from_memory_id`, `expect()` bool coercion, `from_scope` fallback).
- Memora service health on Server 1 NOT verified this run — no live route is held (see below); the probe's step 0 (`GET /health`) verifies it when the run executes.

## Live-leg route — RESOLVED (coordinator drill executed 2026-11-26 17:10 IST; grant settled 23:53 IST)

> RESOLVED. The coordinator executed the drill (WATCH158 follow-up, hub 7191062088): exact probe script from main verified by sha256 on Server 1, launched under `nohup`, completed 17:10–17:11 IST — see CHECKPOINT 2 above for the full evidence and the `b5bfbf85` ruling. The run_shell grant is settled per coordinator correction 7197725825 (22:00 IST) + OWNER'S BURN ORDER 7200414167 (23:53 IST, latest ruling, overrides WATCH177's hold); route verified live this run (hostname + Memora `/health` 200 on Server 1). No re-fire. Original request (kept for the record):
- (a) grant Muse 1 bridge `run_shell` for this probe, Server 1 only, using the filed probe script (same precedent as the MEM-025 grant, watch 7123074240, and the M12 CTX-007 grant — one-off scope-guarded caller, exact granted command only, no key material), or
- (b) a drill assist to copy + run the probe on Server 1 (script + this doc are the full package; raw responses to `/tmp/muse1_mem034/`).

The hourly self-check firings will pick up from this checkpoint and run the probe as soon as a route exists. Run notes for the runner (from MEM-025 run 2): the bridge `run_shell` path is flaky (~1 in 3 calls drop; client-side timeouts do not stop server-side execution) — launch with `nohup`, poll for `SUMMARY.json`, do not re-fire blind while one may still be running server-side. The filed script is the record; fetch it by raw download and verify sha256 before running.

## CHECKPOINT 2 — live leg DONE (coordinator drill) + `b5bfbf85` identified and ruled

**Drill (coordinator, WATCH158 follow-up, hub 7191062088, 2026-11-26 17:12 IST):** exact probe script from main (post-#1966) verified by sha256 on Server 1, launched detached under `nohup`, completed 17:10–17:11 IST (11:40–11:41 UTC). Outputs on S1 at `/tmp/muse1_mem034/` (numbered JSON per call `01.json`–`33.json` + `SUMMARY.json` + `nohup.log`); full set fetched first-hand this run to the task record. **No probe re-fire** — per the drill post and the 17:52 IST self-check ruling; a re-run would create a third test lesson and re-promote two SHARED originals.

**Target lesson `694a6843-f203-4e99-8ffd-9a2543766a94` — promotion proof PASSED (35 PASS):** write 201 PRIVATE as sentinel; owner read 200 PRIVATE; non-owner (friday) 404; 0 need rows before round 1; 8 needs round 1 (friday/intelx/futuris/cortex x2) all 200 + owner need `owner_need_ignored`; sweep 1 (4,348.7 ms) PRIVATE -> SHARED `auto_repeated_need`; post-sweep-1 owner/needer 200 SHARED, outsider (inference) 404, search rank 1 keyword 1.0; 4 needs round 2 (inference/stratex x2) all 200; sweep 2 (4,982.2 ms) SHARED -> UNIVERSAL `promoted_dual_copy`, `universal_copy_id: b2ca708e-56c6-4415-88ab-2020e41bfd9e`; original stays SHARED (owner 200 SHARED, outsider 404); copy reads 200 UNIVERSAL as inference, stratex, friday, futuris; MEM-021 decisive check PASS (copy HMAC `07be03d3d67a` differs from orig `1f4770898fc5`, content SHA `b823cc243ef0` identical, `promoted_from_memory_id` == original); search finds the copy for inference rank 1 keyword 1.0. Audit: both `MEMORY_SCOPE_PROMOTED` rows present (`PRIVATE->SHARED` dual=None; `SHARED->UNIVERSAL` dual=True, copy `b2ca708e`), path `auto_repeated_need`. `SUMMARY.json`: `all_pass: false` SOLELY on the two blast-radius expectations below.

**The 2 failed checks (both blast radius):** sweep 1 `count: 2` (expected exactly 1); sweep 2 `count: 2`. The second promotion in both sweeps is the same memory: `b5bfbf85-f5ca-4c14-9ba7-22531d0d71da`, SHARED -> UNIVERSAL via `auto_repeated_need`.

**`b5bfbf85` identified live (this run, 2026-11-27 ~00:14 IST, read-only, under the settled grant — see below):**
- Content: `MUSE8-TEST-MEM-025 — Lesson (synthetic test record, not a real experiment): a retry experiment that reused a circuit-breaker peer name within the 15 s recovery window failed with a fast-fail on the se…` — the MEM-025 run-2 lesson (Muse 8), synthetic test content.
- Provenance: `task: TASK-MEM-025`, `test_data: true`, `failed_experiment: true`, `lesson_type: failed_experiment`, `experiment_outcome: failed`, `created_at: 2026-11-24T07:28:17Z`, owner `sentinel`, `memory_type: episodic`.
- Live state now: original 200 SHARED as sentinel; universal copy `32c9ed6e-31c2-4318-8946-e2d40d6ae1c2` 200 UNIVERSAL as inference. Run-3 lesson live now: original 200 SHARED as sentinel / 404 as inference; copy `b2ca708e` 200 UNIVERSAL as inference and friday.
- Need history (audit `MEMORY_NEED_RECORDED`, limit 500): **12 rows for `b5bfbf85`, all 2026-11-24T07:28:21–28Z** — run 2's rounds (8 round-1 + 4 round-2); **zero needs accrued on 2026-11-26**. Promotion audit (`MEMORY_SCOPE_PROMOTED`): 5 rows for `b5bfbf85` — 2026-11-24T07:28:22 + 07:28:29 (run-2 sweeps), 2026-11-26T06:34:10Z (midday sweep), 2026-11-26T11:40:54Z + 11:41:00Z (the run-3 sweeps); 2 rows for `694a6843` (the run-3 sweeps).
- **RULING — re-promotion CORRECT and benign:** (1) the SHARED original still qualifies under the thresholds — 12 needs inside the 30-day sweep window from 6 distinct non-owner agents (run 2's friday/intelx/futuris/cortex + inference/stratex), so a global sweep correctly re-evaluates it as UNIVERSAL-bound; (2) the sweep is IDEMPOTENT for it — both run-3 sweeps returned the SAME `universal_copy_id 32c9ed6e-31c2-4318-8946-e2d40d6ae1c2` as run 2, so **no duplicate UNIVERSAL copy was created**; (3) it is a pre-existing backlog memory crossing thresholds, not a sweep double-report bug. The probe script's "blast radius exactly 1" expectation does not account for a prior promoted lesson's SHARED original still qualifying on a global 30-day sweep — a probe-expectation gap, not a Memora defect and not an acceptance failure. Acceptance ("one real lesson promoted private -> universal by repeated use, with evidence at each step") is met by `694a6843` in full.

**Journal (runner step, this run):** `Memora.service` journal 2026-11-26 11:35–11:45 UTC (probe window 11:40–11:41) — **no ERROR, no traceback, no exception**; tail shows routine INFO access logs, all 200. Service `active`.

**Grant basis for this run's live verification:** coordinator correction 7197725825 (2026-11-26 22:00 IST — withdraws WATCH172; owner tap 18:25:56 IST, approval 7113152293; "a permissions-history lookup does not surface main-chat approvals") + OWNER'S BURN ORDER 7200414167 (2026-11-26 23:53 IST — latest ruling, explicitly overrides conflicting earlier instruction: "THE run_shell GRANT IS SETTLED — THE HOLD IS OVER", "No chat may hold a live leg 'pending grant confirmation'"). Noted conflict: WATCH177 (23:45 IST) + WATCH177 follow-up (23:48 IST) still said the hold stands (permissions.history check #8) — superseded by the 23:53 burn order. My own `permissions.history` re-check this run still finds no record for 7113152293 — consistent with the correction's explanation, not evidence against the grant. Route verified live this run: bridge `run_shell` on Server 1 (`hostname` -> `friday-universe-vnic`, exit 0; Memora `/health` 200, service `memora` v2.0.0, oracle backend healthy); probe script sha256 verified on S1 before any use (`808762439f91477351275555255de3ecf597d322bf9b55cf2ad305818796440e`, matches main blob `71596730`).

## States

- **implemented:** COMPLETE — probe script + evidence doc filed; live run done (coordinator drill 17:10 IST); checkpoint 2 identification + ruling filed.
- **tested:** COMPLETE (live) — 35/37 probe checks PASS on the live service; the 2 failures are the blast-radius expectations, ruled above (idempotent re-listing of a prior lesson, no duplicate, no acceptance impact).
- **merged:** NO — work PR open for peer review (merge by Muse, never my own PR).
- **deployed:** N/A — no service change in this PR.
- **production-verified:** YES — lesson `694a6843` observed PRIVATE -> SHARED -> UNIVERSAL live on Memora, Server 1, with audit rows and the MEM-021 decisive check; `b5bfbf85` re-promotion ruled correct and idempotent.

— Muse 1
