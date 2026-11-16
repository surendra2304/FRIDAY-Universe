# TASK-SEN-003 — Fleet Log-Anomaly Review (Sentinel, Wave 5)

**Method:** read-only journald sweep of both servers via batched bridge calls
(server-side aggregation; counts + first/last timestamps + redacted samples).
No production changes were made by this review.

**Coverage caveat (itself Finding 0):** the review asked for 7 days; journald
retention is **220 MB on both servers** and high-volume services rotate it
fast. Effective retained windows at sweep time (2026-11-15 ~14:00–15:30 IST):

- **Server 1: ~21 hours** — oldest retained entry 2026-11-14T17:50:09 IST.
  The bridge (192,630 lines on S2) and Memora (81,509 lines) alone consume
  the ring. A real 7-day forensic trail does not exist on Server 1.
- **Server 2: ≥ 2 days** — Sentinel entries from 2026-11-13T10:30 IST are
  retained; the bridge's own volume is the main rotation pressure.

All counts below are for the retained window and are labelled as such.

---

## Finding 1 — Memora event feed 500-storm: `EVENT_LOG.CLOUD_SYNCED` (RESOLVED by an existing repair, verified)

- **What:** `GET /v1/events` (event feed) failed with
  `sqlalchemy.exc.DatabaseError: (oracledb.exceptions.DatabaseError) ORA-00904:
  "EVENT_LOG"."CLOUD_SYNCED": invalid identifier` — the ORM selects a column
  the production table did not have.
- **Evidence:** 462 "Exception in ASGI application" in Memora.service,
  hourly counts 47 (17:xx) + 273 (18:xx) + 142 (19:xx) on 2026-11-14;
  972 ORA-00904 lines total; first 2026-11-14T17:50:12 IST, last
  2026-11-14T19:29:20 IST. A ~15 s poller hit the endpoint continuously.
- **Resolution (verified in-journal):** Memora restarted 2026-11-14T19:30:08
  IST (Fleet CD deploy); the TASK-REL-015 startup reconciliation in
  `Memora/storage/relational/session.py` added the column; zero ORA-00904
  after 19:29. No action needed; recorded so the storm is not rediscovered
  as "new" and because ~11 h of event-feed failures (17:50–19:29 spanned
  the retained window start — the true start is unknowable, see Finding 0)
  were invisible until this sweep.

## Finding 2 — Memora hard delete poisons its own transaction → 500 (FIXED by this task's PR)

- **What:** `DELETE /v1/memories/<id>?hard=true` intermittently returns 500.
  `MemoryService.delete_memory` runs the Oracle vector delete **on the
  caller's session**; when it raises a DatabaseError, the surrounding
  `except Exception` swallows the Python error but leaves the SQLAlchemy
  transaction poisoned. The final `db.commit()` then raises
  `sqlalchemy.exc.PendingRollbackError` and the whole delete fails — the
  memory is never deleted and the tombstone never converges.
- **Evidence (live, current):** 2026-11-15: **7 DELETE 500s vs 75 DELETE
  200s**. Traceback frames: `apps/api/routers/v1_memories.py:768
  delete_memory_endpoint` → `core/memory/service.py:814 delete_memory`
  (the `db.commit()` line) → `PendingRollbackError: ... Original exception
  was: (oracledb.exceptions.DatabaseError) ... [SQL: DELETE FROM
  memory_records WHERE memory_records.id = :id]`. Same record retried
  (id `9b40ac85…`) fails deterministically. Also 1
  `sqlalchemy.exc.TimeoutError: QueuePool limit ... connection timed out`
  in the same service (2026-11-15T05:07:53 IST).
- **Fix:** isolate each fallible sub-store step (vector, graph) in a
  SAVEPOINT (`db.begin_nested()`), so a sub-store DatabaseError rolls back
  only its savepoint and degrades the tombstone flag
  (`PENDING_RETRY`, the designed convergence behaviour) instead of
  poisoning the delete. Regression tests:
  `Memora/tests/test_sen003_hard_delete_session_isolation.py` — both tests
  fail on main with PendingRollbackError and pass with the fix.

## Finding 3 — Stratex Telegram bot has TWO pollers (ONGOING)

- **What:** `[ERROR] [telegram_bot] [TELEGRAM] 409 Conflict: another process
  is polling this bot token. Run only ONE Stratex instance per bot.` —
  **323 occurrences**, window 2026-11-14T18:06 IST → 2026-11-15T14:18 IST
  (still firing at sweep time). Inbound Telegram commands may be consumed
  by the other poller. A second process somewhere polls the same bot token
  (candidates: Stratex.service vs Stratex-Daemon.service, or a leftover
  process). Ops fix: identify and stop the duplicate poller; not a code PR.

## Finding 4 — Unauthenticated poller hammering Stratex `/api/v1/positions` (ONGOING)

- **What:** `GET /api/v1/positions` → **401 ×474** from 127.0.0.1
  (2026-11-14T17:52 IST → sweep time), plus `GET /api/v1/status` 401 ×26.
  Some local client polls Stratex without the API key — every poll is a
  failed read (whoever consumes it sees no positions). Related, same
  service: at every start (89 starts in-window) Stratex logs CRITICAL
  `SECURITY_SECRET_KEY is NOT set. Generated an ephemeral per-process audit
  secret` ×28 and `WEBHOOK_SECRET is NOT set ... verification DISABLED`
  ×28 — audit signatures cannot verify across restarts while this stands.
  (Values were never read; counts/locations only.)

## Finding 5 — OANDA 401 "Insufficient authorization" storm (KNOWN, still firing)

- Stratex-Daemon: ≥150 warnings across instruments in-window (EUR_USD
  candles ×36, account ×24, GBP_USD ×18, WTICO_USD ×13, EUR_CHF ×10, …),
  Stratex-OANDA-Demo ×11, window 2026-11-14 → 2026-11-15T14:xx IST. This is
  the pre-existing intermittent OANDA authorization failure already known
  to the Stratex crews; recorded here with counts because it never stops.
  Also in the daemon: `[ERROR] [paper_forward_runner] Signal generation
  failed: frozen strategy strategy_swing was deleted by
  TASK-STR-CLEANUP-…` ×11 — a stale forward experiment still referencing a
  deleted strategy, erroring every cycle.

## Finding 6 — Cortex A/B endpoint called with experiment id "None" (ONGOING)

- `POST /api/v1/cortex/ab/experiments/None/participants` → **401 ×1,100**
  in the retained window — a caller builds the URL with a missing/None
  experiment id and no auth; every call fails. Plus
  `POST /v1/task/execute` → 403 ×144 from 10.0.0.121 (FRIDAY delegations;
  fail-closed by design, listed for completeness). Cortex also shows
  17 tracebacks / 15 ASGI exceptions (2026-11-14T20:xx → 2026-11-15T11:xx).

## Finding 7 — Sentinel's own TLS & DNS monitoring cycle fails for 2+ days

- `[ERROR] [sentinel]: Error in TLS & DNS monitoring cycle:` ×17 in the
  aggregator window; first 2026-11-13T10:30:34 IST, **last
  2026-11-15T15:16:01 IST** (during this sweep). Sentinel.service totals in
  the retained window: 54–69 tracebacks, 10 confirmed
  `Failed with result` lifecycle events (awk pass over systemd lines
  counted 28 failure/exited lines including sub-process exits). The
  security monitor's own monitoring loop is the fleet's longest-running
  unfixed error.

## Finding 8 — Inference burns calls on dead/oversized routes

- Retained window, Inference.service (227 errors, 184 timeouts):
  `OpenRouter dynamic fallback failed (GatewayError)` ×78;
  `groq API error: Request too large for model openai/gpt-oss-120b` ×68;
  `nvidia API error (404): Function 'ac74040f-…' Not found for account`
  ×62 — a configured NVIDIA NIM function id that does not exist, retried
  forever. Plus 36 `Unauthorized access attempt
  (require_inference_api_key): missing authentication header` warnings and
  15 × 401 on `GET /v1/trading/consult/health`.

## Finding 9 — Futuris self-healing loop times out continuously

- Futuris.service: 81 tracebacks, 222 errors in-window:
  `self_healing_loop_error error=TimeoutError` ×151, `Fatal error on SSL
  protocol` ×45, `ForecastScheduler.calibration_sweep_job ... raised an
  exception` ×6, 7 ASGI exceptions; 997 auth-pattern hits (mostly numeric
  false positives). Consistent with the known post-ARM statsforecast gap:
  the loop keeps trying and timing out instead of standing down.

## Finding 10 — Voice worker under host pressure (known, quantified)

- FRIDAY-Voice.service: 9,171 lines, 122 errors, 35 tracebacks, 366
  timeouts in-window: LiveKit RTC `publisher data channel '_reliable'
  closed unexpectedly` ×11 + `_lossy` ×10, `resuming connection` errors,
  and repeated `VAD inference is slower than realtime` warnings with
  delays of 7.1 s and 11.0 s — the voice host is CPU-starved during calls
  (matches the owner's speed-first voice verdict; structural fix is the
  free ARM allocation).

## Finding 11 — VyralX error inventory (mostly known upstream failures)

- vyralx-autopilot (26 tracebacks, 9 failed runs): Oracle
  `DPY-4011 connection closed` ×9, `YouTube OAuth refresh failed
  (RefreshError)` ×5 (the dead token — owner re-auth pending, already
  tracked). VyralX.service (28 tracebacks): `Inference content did not
  satisfy the VyralX schema (JSONDecodeError)` ×6 (known Inference seam),
  DPY-4011 ×3, `YouTube Data API returned HTTP 400` ×3 (invalid key —
  already tracked), and `KeyError: 'platform'` ×3 + `'title'` /
  `'source_language'` / `'niche'` ×1 — payload-shape bugs worth a VyralX
  crew's attention.

## Finding 12 — Restarts, failures, and the quiet services

- Restart counts in-window are dominated by the deploy storm (Fleet CD):
  Stratex.service started ×89, Stratex-Daemon ×64, Forge ×36 (24 failure
  lines — mostly its own sandbox-violation rejections working as designed
  ×15 and Oracle disconnects ×5), VyralX ×30, FRIDAY ×31, Sentinel ×28
  lifecycle starts. No kernel OOM kills on either server in-window;
  `systemctl --failed` is empty on Server 2. IntelX is the quietest
  service (6 tracebacks, 2 errors, one Oracle connect failure).
- FRIDAY.service: 8 tracebacks / 19 errors — top: `All Gemini credentials
  in pool are exhausted or in cooldown` ×14 (2026-11-14 evening, free-tier
  quota), Oracle DPY-4011 ×4, Groq tool-choice error ×2.

---

## States

- **Implemented:** Finding 2 fix (savepoint isolation in
  `MemoryService.delete_memory`) + 2 regression tests + this report.
- **Tested:** the 2 new regression tests FAIL on clean code with
  `sqlalchemy.exc.PendingRollbackError` (the exact production signature)
  and PASS with the fix. The sabotage was verified experimentally to be
  faithful: only a flush-time DatabaseError on the shared session poisons
  it (bare failed SELECT/execute does not). Existing Memora suites
  (`test_deep_upgrade_integration`, `test_lifecycle_manager`,
  `test_tombstone_convergence`) in the local harness: 17 passed /
  1 failed / 4 errors — identical with and without the patch (the
  failures are pre-existing harness artefacts, not introduced here).
- **Merged / Deployed / Production-verified:** NO — coordinator merges;
  Fleet CD deploys; the 14:47-style DELETE failure can only be called
  fixed after a post-deploy probe or a clean journal window.
- All other findings are reported with evidence for the coordinator to
  route; this crew changed nothing else.
