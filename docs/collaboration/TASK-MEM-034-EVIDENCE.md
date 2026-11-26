# TASK-MEM-034 — Memora auto-promotion proof, run 3

**Worker:** Muse 1 · **Date:** 2026-11-26 · **Branch:** `muse1/task-mem-034-auto-promotion-run-3`
**Board:** TASK-MEM-034 (Memora: auto-promotion proof run 3 — one lesson promoted private -> universal by repeated use)
**Assignment:** queue top-up after STR-090 MERGED, coordinator WATCH143 (hub #1483 comment 7184216469). **Claim:** issue #1483 comment 7184478984 (~11:59 IST, combined with the STR-090 merged completion).

> STATUS: CHECKPOINT — probe + evidence filed, live leg OWED. One real lesson staged for promotion PRIVATE -> SHARED -> UNIVERSAL by repeated need + sweep. The live run needs a coordinator grant for bridge `run_shell` on Server 1 (same precedent as MEM-025, watch 7123074240) — see "Live-leg route — decision owed" below. Board: IN_PROGRESS (this PR) — the proof is not complete, so this is not IN_REVIEW.

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

## Live-leg route — decision owed (coordinator)

The bridge client is read-only by design (no `run_shell`); the probe must run on Server 1 and read keys at runtime there, per the MEM-018/MEM-025 pattern. I am not bypassing the read-only restriction unilaterally, and the owner stop order gates live legs. Coordinator, please rule one:
- (a) grant Muse 1 bridge `run_shell` for this probe, Server 1 only, using the filed probe script (same precedent as the MEM-025 grant, watch 7123074240, and the M12 CTX-007 grant — one-off scope-guarded caller, exact granted command only, no key material), or
- (b) a drill assist to copy + run the probe on Server 1 (script + this doc are the full package; raw responses to `/tmp/muse1_mem034/`).

The hourly self-check firings will pick up from this checkpoint and run the probe as soon as a route exists. Run notes for the runner (from MEM-025 run 2): the bridge `run_shell` path is flaky (~1 in 3 calls drop; client-side timeouts do not stop server-side execution) — launch with `nohup`, poll for `SUMMARY.json`, do not re-fire blind while one may still be running server-side. The filed script is the record; fetch it by raw download and verify sha256 before running.

## States

- **implemented:** PARTIAL (checkpoint) — probe script + evidence doc filed, preconditions verified; the live run is owed, so the proof is not complete.
- **tested:** PENDING — probe script `py_compile` clean; the live legs have not executed. No new repo tests in this PR (the promotion mechanism is already covered by `Memora/tests/test_mem013_memory_promotion.py`, `test_mem015_promotion_revert.py`, `test_mem016_promotion_readability_sweep.py`); the FUT-030 new-tests check does not apply.
- **merged:** NO — work PR open for review (merge by Muse, never my own PR).
- **deployed:** N/A — no service change in this PR.
- **production-verified:** NO — live run owed (see route decision above): the lesson must be observed PRIVATE -> SHARED -> UNIVERSAL on Server 1 with the audit rows to match.

— Muse 1
