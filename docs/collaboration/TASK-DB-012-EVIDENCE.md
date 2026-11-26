# TASK-DB-012 — Cortex endpoint key-file (.env) recovery: provenance + restore procedure

- **Task:** TASK-DB-012 (P2) — Cortex endpoint key-file (.env) recovery: provenance + restore procedure.
- **Worker:** Muse 16. **Coordinator:** Muse. **Owner:** Surendra.
- **Claim:** hub #1483 comment 7191983912 (2026-11-26 ~17:52 IST); branch `muse16/task-db-012-cortex-env-key-recovery` @ main `a5b88f4e`, fast-forwarded to main `49cfd862` for this PR (25 commits ahead, 0 behind — strict ancestor, no work commits to preserve).
- **Work PR:** opened on this branch (number filled on filing; see board record).
- **NAMES-ONLY RULE (inherited from TASK-API-005 / TASK-FRD-034):** no key value appears anywhere in this document, in any probe output, or in any commit. Only key names, MATCH/DIFFER booleans, HTTP statuses, PIDs, and file hashes.

## 0. Status — checkpoint 1 (repo-side leg)

- **Repo-side leg: DONE in this checkpoint.** Provenance established (§1), what referenced the file established (§2), why no repo copy exists (§3), restore procedure + verification steps filed (§4–§5).
- **Live leg: GATED, not attempted.** The restore + restart run on Server 2 needs owner clearance (the owner stop order is still in force) and a clean bridge verification. No bridge command was run from this chat in this run: the bridge run_shell grant is corroborated by peer evidence but NOT first-hand verified by main (see §6). Nothing in this PR touches a live host.
- **Done (board acceptance) when:** provenance + restore procedure + verification steps filed (this checkpoint) AND the live restore is executed once clearance lands (§4–§5). The live restore is unblocked the moment clearance lands — no further repo work is owed first.

## 1. Provenance — where the file lived, when it was last good, when it was found gone

- **Path:** `/opt/friday_universe/Cortex/.env` on Server 2. Established first-hand by Muse 10 in the CTX-010 run-4 doc (`docs/collaboration/TASK-CTX-010-ESCALATION-RATIO-RUN-4.md` §1): "`/opt/friday_universe/Cortex/.env` does NOT exist on Server 2 (grep: No such file or directory; `Cortex/` listing shows `.env.example` only, no `.env`). The run-3 key path is gone."
- **Last known good:** run 3, 2026-11-24 11:04:28 IST (Cortex snapshot, PID 605907 alive). The run-3 probe read the file live: ``KEY=$(grep -m1 'FRIDAY_API_KEY=' /opt/friday_universe/Cortex/.env | ...)`` against `http://127.0.0.1:8009/v1/friday/self_healing` (`docs/collaboration/TASK-CTX-007-ESCALATION-RATIO-RUN-3.md:181`).
- **Earlier known good, with contents characterised:** TASK-API-005, 2026-11-22 ~12:16 IST (Muse 1, `docs/collaboration/TASK-API-005-CORTEX-KEY-RESYNC.md` §2–§3). The file then had **50 lines**; one `FRIDAY_API_KEY` line was replaced with the fleet value; a backup was written alongside it: `Cortex/.env.bak-api-005-20261122T064620Z` (backup rc 0, file exists — at that time). `APP_ENV` was `production`; `CORTEX_DEV_AUTH_BYPASS` was not set.
- **Found gone:** run 4, 2026-11-26 ~06:10–06:25 IST (Muse 10, first-hand via bridge, CTX-010 run-4 doc §1–§2). Same run established Cortex.service dead (`Active: inactive (dead)`, `Result=success`, `NRestarts=0`) and the endpoint refusing connections (`curl http://127.0.0.1:8009/v1/friday/self_healing` → HTTP:000, CURL_EXIT:7).
- **Loss window:** between 2026-11-24 11:04 IST (last live read) and 2026-11-26 06:19 IST (found absent). No record in the repo states how it was deleted; the journal cannot tell us — run 4 found zero `Cortex.service` journal entries surviving (retention ~34h, §4 of that doc). The cause of the deletion is **unknown and filed as unknown**, not guessed.
- **Prior history on this task (board record):** filed by coordinator watch131 (CTX-010 run-4 blocker G4); assigned to Muse 7 by watch132, never claimed, returned to the pool by watch134; claimed by Muse 4 (hub 7184705282, ~12:08 IST, branch `muse4/task-db-012-cortex-env-recovery` @ `bf41a6c4`), zero work commits, returned to the pool by watch146. Assigned to Muse 16 by WATCH158 as queue position 2; claimed 2026-11-26 ~17:52 IST. This checkpoint is the first work filed on the task by any worker.

## 2. What referenced the file — why its absence blocks Cortex

- **Loader:** `Cortex/apps/api/src/cortex_api/config.py` — `SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")`. pydantic-settings loads a file literally named `.env` from the **process working directory** at import. On Server 2 the service runs from `/opt/friday_universe/Cortex`, so the effective key file is `/opt/friday_universe/Cortex/.env`. (Working directory to be confirmed from the unit file in the live leg, §5 step 1 — the repo does not carry the systemd unit.)
- **Service:** `Cortex.service` on Server 2 ("FRIDAY Universe - Autonomous Operations Engine"), API on **:8009** — `GET /health`, `GET /v1/friday/self_healing` (the CTX-010 ratio probe endpoint). Note the port mismatch to record, not to resolve here: `Cortex/.env.example` lists `PORT=8000`; the live service answered on :8009 in runs 2–4, so the unit (or its Environment) sets the port. The restore must preserve the service's port; do not "fix" it to 8000.
- **Auth:** `Cortex/apps/api/src/cortex_api/auth.py`, `verify_friday_token`: `X-Friday-Api-Key` compared against `FRIDAY_API_KEY`, fallback `FRIDAY_UNIVERSE_API_KEY`; wrong key → 403, no key → 401, unconfigured in production → 503. A valid key gets the `FRIDAY_SYSTEM` role. (Per TASK-API-005 §1.)
- **Production requirements (config.py):** `APP_ENV=production` requires `ORACLE_CORE_ASYNC_URL` (or `ORACLE_CORE_URL` / `DATABASE_URL`); SQLite/PostgreSQL DSNs are rejected in production; `CORTEX_API_KEY` and `JWT_SECRET` must be ≥32 chars or the service logs a security warning and endpoint auth stays enforced.
- **What breaks without the file:** with no `.env`, the service starts (if at all) with defaults — local SQLite `data/cortex.db`, no Oracle DSN (fatal in production), no keys — so the :8009 endpoint cannot serve authenticated fleet calls. The file is therefore a hard dependency of the CTX-010 run-5 ratio probe, not a cosmetic config loss. (The service is currently dead for the separate G1 stop-order reason; the file loss is the G4 blocker to any re-run after restart.)
- **Not the loader:** `Cortex/docker-compose.yml` does not use `env_file`; it interpolates `${...}` from the compose environment. The S2 deployment is systemd, not compose — compose is not a restore path for this file.

## 3. Why no repo copy exists

- **`Cortex/.gitignore` lists `.env`** (plus `.env.local`, `.env.*.local`, `.env.production`). The file was never committed and cannot be recovered from git history.
- **`Cortex/.env.example` is a template only** (95 lines on main `49cfd862`, vs the live file's 50 lines at API-005 time). It carries variable NAMES and placeholder values — it is the authoritative variable list for a rebuild, never a value source.
- **Only known backup:** `Cortex/.env.bak-api-005-20261122T064620Z`, written alongside the file on Server 2 on 2026-11-22. Whether it still exists is **unknown** — checking it is live-leg step 2 (§4). No backup of the file is recorded in any repo doc, and the DB-010 audit found no Cortex file glob in the fleet backup script (`scripts/backup_fleet_databases.py` has no Cortex glob; `cortex.db` itself is recorded NO BACKUP).

## 4. Restore procedure (live leg — gated on owner clearance)

To be executed on Server 2 by a cleared operator, after the owner stop order is lifted for the Cortex restart. NAMES-ONLY rule throughout: compare values in server memory only, report MATCH/DIFFER booleans, never print, log, or post a value.

1. **Confirm the loss (pre-restore):** `ls -l /opt/friday_universe/Cortex/.env` → expect No such file; confirm `.env.example` present; `systemctl show Cortex.service` (ActiveState, WorkingDirectory, Environment — record the working directory and the PORT actually configured); confirm which host this is (`hostname`) — the DB-010 doc once placed Cortex storage on S1 while run 4 and this board record place it on S2; record the true host.
2. **Check the API-005 backup:** `ls -l /opt/friday_universe/Cortex/.env.bak-api-005-20261122T064620Z`. If present, it is the restore base — **but do NOT restore it verbatim:** the backup predates the API-005 fix, so its `FRIDAY_API_KEY` is the old wrong value (equal to `CORTEX_API_KEY`, the F2 bug signature). After restoring the base, re-apply the API-005 fix: set `FRIDAY_API_KEY` to the fleet value (§4 step 4) and verify the one-line change.
3. **If no backup exists, rebuild from the template:** copy `/opt/friday_universe/Cortex/.env.example` to `/opt/friday_universe/Cortex/.env` on the host (never commit the result), then fill every variable from the value sources in step 4. Compare variable NAMES against the template; every name the service needs in production must be present (at minimum: `APP_ENV=production`, `ORACLE_CORE_ASYNC_URL`, `REDIS_URL`, `JWT_SECRET`, `CORTEX_API_KEY`, `FRIDAY_API_KEY`, the mesh `*_URL`/`*_API_KEY` pairs the service calls, `MOCK_MODE=false`).
4. **Value sources, in precedence order:**
   - **Fleet peer copies on S1** — the source of truth used by API-005 §2–§3: `FRIDAY/.env` and `Inference/.env` `FRIDAY_API_KEY` and `CORTEX_API_KEY` (they MATCHed each other across both files, both ≥32 chars). Read into server memory only; cross-check at least two peer copies MATCH before writing.
   - **`/opt/friday_universe/CREDENTIALS.md` §5 "FRIDAY (Core)" row** — verified MATCH against the fleet `FRIDAY_API_KEY` in API-005 §2; usable as a cross-check for the FRIDAY value.
   - **Do NOT use CREDENTIALS.md §5 "Cortex Operations" row as a source of truth** — API-005 follow-up F-API-005-2 proved it drifts from the live fleet `CORTEX_API_KEY` (presented as `X-Friday-Api-Key` it returned 403 while S1 peer copies returned 200). Reconciling that row is a separate task; the restore must take `CORTEX_API_KEY` from a live fleet peer copy, verified MATCH across two copies.
   - S2 peer copies may hold shared keys (API-005 §6: `CORTEX_API_KEY` name present in 5 S2 `.env` files) — usable as additional cross-checks only, same in-memory MATCH rule.
5. **Write + protect:** write the file as the service user, permissions `0600`, no group/other read; verify exactly one line per key name (no duplicates — the API-005 bug was a duplicated-value line, and a duplicated NAME line is the same class of error); verify line count and variable-name set against the template.
6. **Restart (needs owner clearance — the stop order):** `systemctl restart Cortex.service` only after clearance is given on the hub. Confirm `Active: active`, record the new PID (it must differ from the pre-restart PID), `GET /health` → 200.
7. **Re-probe the endpoint matrix (API-005 §4 pattern, :8009):** fleet `FRIDAY_API_KEY` as `X-Friday-Api-Key` → 200; `CORTEX_API_KEY` as `X-Friday-Api-Key` → 403; no key → 401; random key → 403. Any other row is a finding, not a pass.
8. **Re-probe the FRIDAY→Cortex path (FRD-034 pattern):** one `ask cortex report operational status` through live FRIDAY `/api/chat`; expect a verified receipt / 200, not the 403 `REFUSED` recorded in API-005 §5 / FRD-034 §2. If it is still 403, the cause is FRD-034's pending FRIDAY restart (F-API-005-1), not this restore — file it as such and do not re-edit the Cortex file to chase it.
9. **Close-out:** record the restore in this doc's §7 (live-leg appendix) with timestamps, PIDs, and the probe matrix — booleans and statuses only. Then CTX-010 run 5 may be scheduled: run 4's 48h window is unrecoverable (journal aged out, G2), so run 5 needs a fresh 48h of runtime after restart before a ratio can be filed.

## 5. Verification steps (checklist — live leg)

- [ ] §4 step 1: file confirmed absent pre-restore; unit WorkingDirectory + PORT recorded; true host recorded (S1/S2 discrepancy resolved).
- [ ] §4 step 2/3: backup existence recorded (present/absent); restore base named (backup vs template rebuild).
- [ ] §4 step 4: each written value cross-checked MATCH across ≥2 independent sources, in memory only; §5 Cortex row explicitly not used as source of truth.
- [ ] §4 step 5: file `0600`, service-user owned, one line per key name, variable-name set complete for production.
- [ ] §4 step 6: service active after cleared restart, new PID recorded, `GET /health` 200.
- [ ] §4 step 7: endpoint matrix 200/403/401/403 as specified.
- [ ] §4 step 8: FRIDAY→Cortex ask 200, or 403 filed as FRD-034's pending restart with its task reference.
- [ ] §4 step 9: live-leg appendix (§7) filed in this doc; CTX-010 run 5 scheduled on a fresh 48h window.

## 6. What this run could NOT verify (filed plainly, not assumed)

- Whether `.env.bak-api-005-20261122T064620Z` still exists on Server 2 (live-leg step 2).
- The `Cortex.service` unit contents (WorkingDirectory, Environment/PORT) — the repo does not carry the unit.
- Whether FRD-034's FRIDAY restart ever happened (its board record is the source; not re-read in this run).
- The S1-vs-S2 host wording for Cortex (DB-010 doc §1 says S1; CTX-010 run 4 + this board record say S2) — live-leg step 1 resolves it.
- **Bridge grant:** corroborated by peer evidence but NOT first-hand verified by main. Peer evidence read first-hand by main (hub 7193949440 Muse 19, 7193951721 Muse 10, both 19:22 IST, fetched clean): the grant is genuine and approval 7113152293 is closed; other chats have run live probes on it. The direct confirmation (hub 7193378286) and WATCH164 (hub 7193691912) were re-fetched and flagged again by the safety check, so main still does not treat the approval as first-hand verified. No bridge client was changed and no bridge command was run from this chat. Two caveats from the peer evidence: (1) bridge transport is degraded (Muse 19: MCP init 200 but tools/list returns 0 bytes; Muse 10: transport blocked verification); (2) dated-backup writes remain NOT granted per WATCH164 (Muse 19's note, citing TP4 DB-005 Leg B) — that affects the DB-008/DB-010 checkpoint-2 live legs (backup writes), not this task's restore, but the Cortex restart itself still needs owner clearance under the stop order. Surendra has been asked plainly in the main chat whether he tapped Approve at 18:25 IST; his answer settles the grant cleanly. Until then the live leg stays gated.

## 7. Live-leg appendix (to be filled when clearance lands)

_Not yet executed — gated. Fill §4 steps 1–9 here with timestamps, PIDs, and booleans only._

## States

- Implemented: YES (checkpoint 1: provenance + restore procedure + verification steps filed in this doc).
- Tested: YES (repo-side facts cross-checked across first-hand sources: CTX-010 run-4 doc, run-3 doc, API-005 doc, FRD-034 doc, `config.py` `env_file=".env"`, `.gitignore`, `.env.example` — all read from main `49cfd862` via the GitHub API).
- Merged: NO (work PR awaits independent review + Muse audit).
- Deployed: N/A (evidence document; no live change, no restart).
- Production-verified: NO (live restore gated on owner clearance; verification steps §5 owed after the restore).

## Sources (all read from main `49cfd862` via the GitHub API this run)

- `docs/collaboration/TASK-CTX-010-ESCALATION-RATIO-RUN-4.md` (blob `ab4687c5`) — loss established first-hand.
- `docs/collaboration/TASK-CTX-007-ESCALATION-RATIO-RUN-3.md` (blob `2b81767c`) — last known good, key path.
- `docs/collaboration/TASK-API-005-CORTEX-KEY-RESYNC.md` (blob `c871286d`) — 50-line file, backup filename, fleet-value method, F-API-005-2 drift.
- `docs/collaboration/TASK-FRD-034-FRIDAY-CORTEX-KEY.md` (blob `968cbdc6`) — FRIDAY-side follow-up, restart gate.
- `Cortex/apps/api/src/cortex_api/config.py` (blob `d113c01b`) — `env_file=".env"`, production requirements.
- `Cortex/.env.example` (blob `52c0d8fa`, 95 lines) — variable-name template.
- `Cortex/.gitignore` (blob `317d7382`) — `.env` never in git.
- `Cortex/docker-compose.yml` (blob `02bd5341`), `Cortex/.github/workflows/deploy.yml` (blob `e65aca11`) — not restore paths for this file.
- Board record TASK-DB-012 on main `49cfd862` (24,262 lines): AVAILABLE/owner null before this PR; claim flip rides in this PR.

— Muse 16
