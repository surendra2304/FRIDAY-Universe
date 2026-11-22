# TASK-API-005 — Cortex FRIDAY_API_KEY re-sync to fleet value + restart + re-probe

- **Task:** TASK-API-005 (P1) — API-003 finding F2 (`TASK-API-003_AUDIT.md` §4).
- **Worker:** Muse 1. **Coordinator:** Muse. **Owner:** Surendra Varma Jalli.
- **Claim:** issue #35 comment 7075346423 (~11:58 IST, 2026-11-22); board-only claim PR #1332
  (head `036cf925`, base main `33dcfef1`); merged 2026-11-22 ~12:06 IST (merge `a81a0dc3`).
- **Work PR:** #1339 (`muse1/task-api-005-cortex-key-resync`, base main `a81a0dc3`).
  Board flip to IN_REVIEW is the second commit on the same branch.
- **NAMES-ONLY RULE:** no key value appears anywhere in this document, in any probe output,
  or in any commit. Only key names, MATCH/DIFFER booleans, HTTP statuses, PIDs, and file hashes.

## 1. Finding (F2, restated)

Cortex's `.env` `FRIDAY_API_KEY` equalled Cortex's own `CORTEX_API_KEY` value, not the fleet
`FRIDAY_API_KEY` value. Auth code is correct (`Cortex/apps/api/src/cortex_api/auth.py`,
`verify_friday_token`: `X-Friday-Api-Key` compared against `FRIDAY_API_KEY`, fallback
`FRIDAY_UNIVERSE_API_KEY`; wrong key → 403, no key → 401, unconfigured in production → 503;
a valid key gets the `FRIDAY_SYSTEM` role, which includes admin in the role hierarchy).
The distribution was broken, not the code. Probe endpoint for all matrix rows below:
`GET /api/v1/cortex/budgets` on Cortex :8009 (gated by `require_cortex_route_access` in
`Cortex/apps/api/src/cortex_api/main.py:244`, which delegates to `verify_friday_token` when
`X-Friday-Api-Key` is present; GET needs `CORTEX_VIEWER`, which `FRIDAY_SYSTEM` satisfies).

## 2. Before state (verified 2026-11-22 ~12:10–12:14 IST, pre-fix)

Fleet value established first, from the live services (not from documentation alone):

- S1 `FRIDAY/.env` `FRIDAY_API_KEY` vs S1 `Inference/.env` `FRIDAY_API_KEY`: **MATCH**
  (the two fleet copies agree; both ≥32 chars).
- S1 `FRIDAY/.env` `CORTEX_API_KEY` vs S1 `Inference/.env` `CORTEX_API_KEY`: **MATCH**.
- `CREDENTIALS.md` §5 "FRIDAY (Core)" row vs S1 fleet `FRIDAY_API_KEY`: **MATCH**
  (checked in server memory during the fix run, §3).
- Cortex `.env` `FRIDAY_API_KEY` vs fleet `FRIDAY_API_KEY`: **DIFFER** (the bug).
- Cortex `.env` `FRIDAY_API_KEY` vs Cortex's own `CORTEX_API_KEY`: **MATCH** (bug signature).
- Cortex's own `CORTEX_API_KEY` vs the fleet peer copies of `CORTEX_API_KEY`: **MATCH**
  (proven live, see matrix — the peer copies are what the audit called "fleet CORTEX_API_KEY").

Live matrix, before fix (Cortex PID 565184, running since 2026-11-21 00:47 IST):

| Probe (key presented as `X-Friday-Api-Key`) | Result |
|---|---|
| Fleet `FRIDAY_API_KEY` (S1 FRIDAY copy) → Cortex :8009 | **403** |
| Fleet `FRIDAY_API_KEY` (CREDENTIALS.md §5 row) → Cortex :8009 | **403** |
| Fleet `CORTEX_API_KEY` (S1 FRIDAY copy) → Cortex :8009 | **200** |
| Fleet `CORTEX_API_KEY` (S1 Inference copy) → Cortex :8009 | **200** |
| `CORTEX_API_KEY` (CREDENTIALS.md §5 "Cortex Operations" row) → Cortex :8009 | **403** |
| No key | **401** |
| Random key | **403** |

The 200s on the `CORTEX_API_KEY` rows reproduce F2 exactly: the Cortex key authenticated as
`FRIDAY_SYSTEM` (incl. admin). The 403 on the CREDENTIALS.md Cortex row is a new discrepancy,
filed as follow-up F-API-005-2 (§6): the documented §5 "Cortex Operations" value is **not**
the live fleet `CORTEX_API_KEY` value.

## 3. Fix (2026-11-22 ~12:16 IST)

- Source of the fleet value: S1 `FRIDAY/.env` `FRIDAY_API_KEY`, fetched over SSH from Server 2
  into server memory only (never printed, logged, or written to a file); cross-checked in
  memory against S1 `Inference/.env` (MATCH) and the CREDENTIALS.md §5 FRIDAY row (MATCH).
- Backup: `Cortex/.env` copied to `Cortex/.env.bak-api-005-20261122T064620Z` (backup rc 0,
  file exists) before any edit.
- Edit: exactly one `FRIDAY_API_KEY` line in `/opt/friday_universe/Cortex/.env` replaced
  with the fleet value (quoting style preserved; line count 50 before and after).
- After-write verification (booleans only, re-read from disk):
  - new Cortex copy vs fleet value: **MATCH**; vs old Cortex copy: **DIFFER**;
    vs Cortex's own `CORTEX_API_KEY`: **DIFFER**; own `CORTEX_API_KEY` unchanged: **MATCH**;
    exactly 1 `FRIDAY_API_KEY` line.
- No code changed. Deployed auth code == current main `a81a0dc3` (sha256):
  `Cortex/apps/api/src/cortex_api/auth.py` and `.../main.py` hashes identical before and
  after the restart and identical to main (verified via the GitHub API + local clone).
- Cortex `APP_ENV` is `production`; `CORTEX_DEV_AUTH_BYPASS` is not set in Cortex's `.env`.

## 4. Restart + after state (verified 2026-11-22 ~12:16–12:24 IST)

- Restart: `Cortex.service` restarted on Server 2 at ~12:16:36 IST via the bridge
  (`oracle_restart_service`). Result: `Active: active`.
- New PID **584499** (was 565184 — restart confirmed). `GET /health`: **200**.
- Service stayed healthy through the re-probe (only `/health` hits from the fleet monitor
  plus this task's probes in the log window).

Live matrix, after fix + restart (same endpoint, same keys):

| Probe (key presented as `X-Friday-Api-Key`) | Result |
|---|---|
| Fleet `FRIDAY_API_KEY` (S1 FRIDAY copy — the real mesh caller key) → Cortex :8009 | **200** |
| Fleet `FRIDAY_API_KEY` (CREDENTIALS.md §5 row) → Cortex :8009 | **200** |
| Fleet `CORTEX_API_KEY` (S1 peer copies) as `X-Friday-Api-Key` → Cortex :8009 | **403** |
| `CORTEX_API_KEY` (CREDENTIALS.md §5 row) as `X-Friday-Api-Key` → Cortex :8009 | **403** |
| No key | **401** |
| Random key | **403** |

On-disk equality after restart (re-read): Cortex copy vs fleet `FRIDAY_API_KEY`: **MATCH**;
vs fleet `CORTEX_API_KEY` (CREDENTIALS.md row): **DIFFER**; vs own `CORTEX_API_KEY`:
**DIFFER**; own `CORTEX_API_KEY` vs fleet (CREDENTIALS.md row): **DIFFER** (the §5 drift,
F-API-005-2 — the row still does not match the live fleet value).

Acceptance, Cortex side: **met and verified** — Cortex's `.env` `FRIDAY_API_KEY` is the fleet
value (MATCH), Cortex was restarted and is healthy, and the matrix shows the fleet key
authenticating (200) while `CORTEX_API_KEY` is no longer accepted as `X-Friday-Api-Key` (403).

## 5. Open item — FRIDAY's own Cortex client still presents the wrong key (F-API-005-1)

This task's re-probe caught a second half of F2 that the audit's follow-up did not name.
FRIDAY's live mesh client presents a different key than the fleet `FRIDAY_API_KEY`:

- `FRIDAY/src/friday/ecosystem/fleet_client.py:267` — `self.cortex_key =
  configured_key("cortex_api_key")`, i.e. settings `cortex_api_key`
  (`FRIDAY/src/friday/core/config.py:402`).
- `FRIDAY/src/friday/core/config.py:150` — `FRIDAY_CORTEX_API_KEY` falls back to
  `CORTEX_API_KEY`. FRIDAY's `.env` **has** `FRIDAY_CORTEX_API_KEY` set, and it equals the
  fleet `CORTEX_API_KEY` value (MATCH) and differs from the fleet `FRIDAY_API_KEY` value
  (DIFFER) — checked server-side on S1, booleans only.
- Every FRIDAY→Cortex call in `fleet_client.py` presents `self.cortex_key` as
  `X-Friday-Api-Key`: health probe (`:532`, `/health`, keyless so unaffected), `ask_cortex`
  (`:1045`, `GET /v1/friday/health_summary`), task delegation (`:1676`,
  `POST /v1/task/execute`), health-summary monitor (`:2064`). `fleet_client` is the live
  path — `FRIDAY/src/friday/api/server.py:56` imports it and dispatches `ask cortex …`
  through it (`:4464–4472`).

Live proof (2026-11-22 ~12:30 IST, one read-only probe through the live FRIDAY service,
`POST http://127.0.0.1:10000/api/chat` from S1 with message `ask cortex report operational
status`):

- FRIDAY's reply: "I could not get a verified receipt from CORTEX, but it answered
  directly: Cortex health summary request failed with HTTP 403."
- Metadata: `success: false`, `http_status: 403`, `task_state: REFUSED`,
  `contract_used: /v1/task/execute`, task `task_a9dccb5dc54d`.
- Before this task's fix the same call succeeded (Cortex accepted the presented key
  because it equalled the old misconfigured value); after the fix it is 403. The Cortex
  side is now correct and the FRIDAY side is now the mismatch.

**Required follow-up (not done here):** set FRIDAY's `.env` `FRIDAY_CORTEX_API_KEY` to the
fleet `FRIDAY_API_KEY` value (the credential Cortex's FRIDAY routes accept) and restart
FRIDAY. The restart needs hub clearance — it was not done in this task, and FRIDAY's
`.env` was deliberately left untouched so no file/process inconsistency is introduced.
Until that follow-up lands, FRIDAY→Cortex `ask` / task-delegation calls fail with 403
(the `/health` fleet probe is unaffected). Filed as follow-up F-API-005-1 for Muse to
schedule; it needs a FRIDAY restart decision, not a Cortex change.

## 6. Follow-ups filed (with file/line; nothing silently fixed)

- **F-API-005-1 — FRIDAY's Cortex client presents `CORTEX_API_KEY`, now 403.**
  `FRIDAY/src/friday/ecosystem/fleet_client.py:267,1045,1676,2064`,
  `FRIDAY/src/friday/core/config.py:150,402`. Fix: FRIDAY `.env` `FRIDAY_CORTEX_API_KEY` →
  fleet `FRIDAY_API_KEY` value + FRIDAY restart (hub clearance required). Live proof: §5
  (task `task_a9dccb5dc54d`, HTTP 403, `REFUSED`). Severity: live mesh break introduced
  by the (correct) Cortex-side fix — schedule before any demo of FRIDAY→Cortex asks.
- **F-API-005-2 — CREDENTIALS.md §5 "Cortex Operations" row ≠ live fleet `CORTEX_API_KEY`.**
  `/opt/friday_universe/CREDENTIALS.md` §5. Proven: the documented row presented as
  `X-Friday-Api-Key` returns 403 while the S1 peer copies return 200 (before fix) and the
  Cortex copy check reads DIFFER. The §5 FRIDAY row is in sync (MATCH, §2); only the
  Cortex row drifts. Fix: reconcile the documented row with the live fleet value (or
  document that §5 holds a different credential set); do not use the §5 Cortex row as a
  source of truth until reconciled.
- **F-API-005-3 — `CORTEX_API_KEY` rotation (decision: deferred, not done here).**
  The audit asked for rotation to be considered because the key served as the FRIDAY
  credential. Decision: **do not rotate in this task.** Reasons: (a) the privilege
  escalation is closed — `CORTEX_API_KEY` as `X-Friday-Api-Key` now returns 403 (verified
  live, §4); (b) no evidence the value ever left the fleet's own files (it lived only in
  `.env` files and CREDENTIALS.md); (c) rotation is a fleet-wide redistribution — the key
  name is present in 9 `.env` files on S1 (FRIDAY, Forge, Futuris, Inference, IntelX,
  Memora, Sentinel, Stratex, VyralX) and 5 on S2 (Cortex, Futuris, IntelX, Sentinel,
  VyralX), plus the stale CREDENTIALS.md §5 row (F-API-005-2) — and needs coordinated
  restarts. File as a dedicated rotation task for Muse to schedule; do F-API-005-1
  first so the rotation does not have to chase the FRIDAY client value as well.

## 7. Method, hygiene, and disclosures

- All key comparisons were equality checks in server memory (MATCH/DIFFER booleans only);
  values were never printed, logged, stored in a file, or posted. The fleet value moved
  S1→S2 over SSH into memory only (no transfer file). Probe scripts held values in memory
  only and printed names + statuses.
- The bridge MCP endpoint (`friday-universe.duckdns.org/bridge/mcp`, v1.30.0) was used for
  all fleet reads/writes/restarts. It was transiently unreachable for several minutes
  mid-task (repeated init timeouts); public ingress stayed 200 throughout and the bridge
  recovered on its own. No fleet action was taken during the outage.
- This task's live probes: direct key-presentation probes against Cortex :8009 (S1 + S2),
  plus one `ask cortex` message through live FRIDAY `/api/chat` (§5). That message left one
  conversation-history entry and one task record (`task_a9dccb5dc54d`) in FRIDAY's store,
  and the probe requests appear in Cortex's access log — the same disclosure pattern as
  TASK-ORCH-010's live probes.
- FRIDAY's `.env` was not modified and FRIDAY was not restarted in this task.
- `CORTEX_API_KEY` itself was not rotated and no other agent's `.env` was touched.
- The server checkout on S2 (`/opt/friday_universe`) was on another worker's branch
  (`muse7/task-str-fwd-035-daemon-timeframe-label`) during this run; no git operations were
  performed in it and no files were written to it except the intended `Cortex/.env` edit
  and its backup.

— Muse 1
