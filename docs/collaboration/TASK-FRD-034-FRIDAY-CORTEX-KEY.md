# TASK-FRD-034 — FRIDAY .env FRIDAY_CORTEX_API_KEY re-sync to fleet FRIDAY_API_KEY

- **Task:** TASK-FRD-034 (P1) — API-005 follow-up F-API-005-1
  (`TASK-API-005-CORTEX-KEY-RESYNC.md` §5/§6).
- **Worker:** Muse 1. **Coordinator:** Muse. **Owner:** Surendra.
- **Claim:** issue #35 comment 7076299903 (~13:32 IST, 2026-11-22); board-only claim PR #1347
  (head `953ab327`, base main `12d7c0cc`); claim PR still open at implementation time, so the
  work below was committed on top of the claim branch (`muse1/task-frd-034-friday-cortex-key`).
- **Work PR:** (number filled on filing; see board record).
- **NAMES-ONLY RULE:** no key value appears anywhere in this document, in any probe output,
  or in any commit. Only key names, MATCH/DIFFER booleans, HTTP statuses, PIDs, and file hashes.

## 1. Finding (F-API-005-1, restated)

After the (correct) Cortex-side fix in TASK-API-005, Cortex's `FRIDAY_API_KEY` is the fleet
`FRIDAY_API_KEY` value, so FRIDAY's mesh client — which presents a different key — gets 403
on every `ask cortex` / task-delegation call. `FRIDAY/src/friday/ecosystem/fleet_client.py:267`
presents `settings cortex_api_key` (`FRIDAY/src/friday/core/config.py:402`,
`FRIDAY_CORTEX_API_KEY`, falling back to `CORTEX_API_KEY` at `config.py:150`) as
`X-Friday-Api-Key` on `ask_cortex` (`:1045`), task delegation (`:1676`), and the
health-summary monitor (`:2064`). FRIDAY's `.env` `FRIDAY_CORTEX_API_KEY` equalled the fleet
`CORTEX_API_KEY` value, not the fleet `FRIDAY_API_KEY` value. Fix: set FRIDAY's `.env`
`FRIDAY_CORTEX_API_KEY` to the fleet `FRIDAY_API_KEY` value and restart FRIDAY.

## 2. Before state (verified 2026-11-22 ~13:39 IST, pre-fix, Server 1 via bridge)

Fleet value established from the live services (not from documentation alone):

- S1 `FRIDAY/.env` `FRIDAY_API_KEY` vs S1 `Inference/.env` `FRIDAY_API_KEY`: **MATCH**
  (the two fleet copies agree; both ≥32 chars).
- FRIDAY `.env` `FRIDAY_CORTEX_API_KEY` vs fleet `FRIDAY_API_KEY`: **DIFFER** (the bug).
- FRIDAY `.env` `FRIDAY_CORTEX_API_KEY` vs fleet `CORTEX_API_KEY` (FRIDAY copy): **MATCH**
  (bug signature); vs Inference copy: **MATCH**.
- Exactly 1 `FRIDAY_CORTEX_API_KEY` line in `FRIDAY/.env`; 79 lines total.
- FRIDAY service before the fix: `FRIDAY.service` active (running) since 11:15:20 IST,
  Main PID **2076194**.

Fresh live proof (this run, one read-only probe through the live FRIDAY service,
`POST http://127.0.0.1:10000/api/chat` from S1 with message
`ask cortex report operational status`, ~13:39 IST):

- FRIDAY's reply: "I could not get a verified receipt from CORTEX, but it answered
  directly: Cortex health summary request failed with HTTP 403."
- Metadata: `success: false`, `http_status: 403`, `task_state: REFUSED`,
  `contract_used: /v1/task/execute`, task `task_4a3033dfc390`.
- This reproduces the API-005 §5 proof (`task_a9dccb5dc54d`, ~12:30 IST) on the current
  live state. The Cortex side is correct and the FRIDAY side is the mismatch.

## 3. Fix (2026-11-22 ~13:39 IST, on disk only — no restart)

- Source of the fleet value: S1 `FRIDAY/.env` `FRIDAY_API_KEY` itself, read into server
  memory only (never printed, logged, or written to a file); cross-checked in memory
  against S1 `Inference/.env` (MATCH). No cross-server transfer was needed: the fix and
  the fleet value live on the same host.
- Backup: `FRIDAY/.env` copied to `FRIDAY/.env.bak-frd-034-20261122T080936Z` (backup rc 0,
  file exists) before any edit.
- Edit: exactly one `FRIDAY_CORTEX_API_KEY` line in `/opt/friday_universe/FRIDAY/.env`
  replaced with the fleet value (quoting style preserved; line count 79 before and after).
- After-write verification (booleans only, re-read from disk):
  - new FRIDAY copy vs fleet `FRIDAY_API_KEY`: **MATCH**; vs old FRIDAY copy: **DIFFER**;
    vs fleet `CORTEX_API_KEY`: **DIFFER**; own `CORTEX_API_KEY` unchanged: **MATCH**;
    `FRIDAY_API_KEY` itself unchanged: **MATCH**; exactly 1 `FRIDAY_CORTEX_API_KEY` line.
- No code changed. No other agent's `.env` was touched.

## 4. Restart + re-probe — NOT DONE: awaiting Muse's deployment clearance (LIVE-RESTART GATE)

- **FRIDAY was NOT restarted in this run.** The hard gate in the board record stands:
  restart FRIDAY only after Muse explicitly clears deployment on the hub in an issue #35
  comment. No such clearance had arrived as of the last issue #35 read in this run
  (~13:37 IST; latest comment is the claim itself, 7076299903).
- The running process (PID **2076194**, since 11:15:20 IST) still holds the OLD key in
  memory — verified still active after the on-disk edit (`oracle_check_service`, same PID,
  same start time). Until the restart, FRIDAY→Cortex `ask` / delegation calls still fail
  403; the on-disk fix alone does not change live behaviour. That is the expected interim
  state, not a regression.
- **Re-probe NOT done and NOT claimed:** the `ask cortex` + task-delegation 200s in the
  acceptance criteria can only be verified after the restart. The after-fix probe is owed
  in the restart run.
- Batching note: the restart window was to be batched with TASK-FRD-033 (Muse 2) if both
  are ready. FRD-033's claim PR #1342 is still open with the claim commit only
  (head `bf444340`, no work commits as of ~13:42 IST), so it is not ready for a batched
  window yet.

## 5. Acceptance status

- FRIDAY `.env` `FRIDAY_CORTEX_API_KEY` equals the fleet `FRIDAY_API_KEY` value: **MET,
  verified on disk (MATCH, §3)**.
- FRIDAY restarted ONLY after Muse clears deployment: **PENDING — no clearance, no
  restart, stated plainly**.
- FRIDAY `ask cortex` + task-delegation calls succeed (200) with a live probe: **NOT YET
  VERIFIED — owed after the cleared restart**.
- No other agent `.env` touched: **MET** (only `FRIDAY/.env` edited; backup alongside it).

## 6. Method, hygiene, and disclosures

- All key comparisons were equality checks in server memory (MATCH/DIFFER booleans only);
  values were never printed, logged, stored in a file, or posted. The fleet value stayed
  in memory on Server 1 (no transfer file, no cross-server copy).
- This task's live probes: one `ask cortex` message through live FRIDAY `/api/chat` (§2).
  That message left one conversation-history entry and one task record
  (`task_4a3033dfc390`) in FRIDAY's store, and the probe request appears in the FRIDAY
  access log — the same disclosure pattern as TASK-ORCH-010's and TASK-API-005's live
  probes. (The API-005 probe `task_a9dccb5dc54d` is a separate, earlier entry.)
- The local worker clone was blocked by an execution-risk check in this run, so all git
  work (board read, evidence-doc + board commits, PR creation) was done through the
  GitHub API (`custom.github` helpers) instead of local git; no local pytest was run
  (no code changed — `.env` value only).
- `CORTEX_API_KEY` itself was not rotated and no other agent's `.env` was touched.

— Muse 1
