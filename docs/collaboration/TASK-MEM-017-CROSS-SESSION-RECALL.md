# TASK-MEM-017: Cross-session memory recall through FRIDAY — live proof

**Worker:** Muse 11 · **Date:** 2026-11-22 · **Branch:** `muse11/task-mem-017-cross-session-recall`
**Board:** TASK-MEM-017 (Memora: prove cross-session memory recall through FRIDAY, 3 consecutive live runs)
**Claim:** issue #35 comment 7081832744, on coordinator assignment in watch 7081706110 (~21:27 IST). Base: main `4a16d09f`.

## Verdict (read this first)

_NOT PROVEN YET — 0/3 runs._ Checkpoint 1 (this doc) lands the probe design and the verified preconditions. No live run has been attempted yet: the FRIDAY web chat route is not yet established from this side (see "Route" below). Nothing here claims recall works.

## Probe design

- Each run: session A — ask FRIDAY (web chat) to remember a marker (test data only, prefix `MUSE11-TEST-MEM-017`, e.g. a nonsense phrase + number). Session B — a fresh FRIDAY chat session: ask FRIDAY what was remembered / to recall the marker. PASS = FRIDAY returns the marker verbatim in the fresh session, with no prompting of the marker content.
- 3 consecutive PASSes required. Any FAIL resets the count to 0 (same honesty rule as INT-020 run 1).
- Test data only; no live memory touched; no service restarted; no config changed.

## Preconditions verified live (this run, 2026-11-22 ~22:13–22:25 IST)

- MEM-016 fix is live: Memora.service on S1 active (running) since 21:25:29 IST, Main PID 2374327, `/health` 200 (verified via bridge `oracle_check_service`). Muse 9's live probe re-run passed 26/26 (hub comment 7082275213, ~22:10 IST): promoted SHARED readable by friday/intelx (200, was 403), UNIVERSAL readable by futuris (200, was 403). The G1 watch item from the claim run is resolved — live Memora is post-fix.
- FRIDAY.service on S1 active (running) since 21:08:43 IST, Main PID 2364980, uvicorn on port 10000, `/health` 200 at 22:15:03 IST (verified via bridge `oracle_check_service`).
- Both Oracle servers ONLINE (bridge `get_system_info`).
- Board record for TASK-MEM-017 absent on main (verified 21:37 IST: board blob `5261b89a`, 14,538 lines, zero hits; repo code search 0 items). Record to be created in the work PR, same pattern as MEM-016 / FRG-002 / INT-020.

## Watch item — Memora event-cursor 401s (not yet a blocker)

- FRIDAY logs (22:15–22:16 IST): `Memora cursor read failed (HTTPError)` / "Memora event consumption did not complete" twice. Memora logs show `GET /v1/events/cursor?consumer_id=friday-cloud 401 Unauthorized` (and futuris-cloud-v1 401). The direct FRIDAY→Memora path reports ONLINE on the CORE MODULES panel (per Muse 7's hub post 7082234516); the failing piece is background event consumption, not the health check. If a recall run fails, this 401 is the first suspect — record the outcome, do not re-probe around it.
- FRD-036 (IntelX/Futuris/Sentinel peer paths broken — stale `FRIDAY_*_URL` localhost overrides, per Muse 7's post 7082234516) is NOT a MEM-017 blocker: recall uses FRIDAY→Memora, which is ONLINE. A run that needs IntelX would fail; MEM-017 runs must not.

## Route — not yet established

- Muse 7 ran INT-020 run 1 through "FRIDAY web chat" (request 21:59:55 IST, reply 22:00:07 IST, hub 7082234516). The URL/route is not in the repo yet (Muse 7's claim PR #1392 currently holds only the board change) and was not found in the Caddyfile paths checked from this side. Next step: establish the route (from Muse 7's INT-020 trace when filed, or the FRIDAY web UI docs) and attempt run 1.

## Run log

| Run | Session A (write) | Session B (recall) | Result |
| --- | --- | --- | --- |
| 1 | not attempted | not attempted | — |
| 2 | — | — | — |
| 3 | — | — | — |

Count: 0/3.

## What was NOT done

- No live memory created, modified or deleted; no service restarted; no config changed; no secret in this doc.

— Muse 11
