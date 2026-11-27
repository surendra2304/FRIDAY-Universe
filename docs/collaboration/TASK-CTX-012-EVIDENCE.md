# TASK-CTX-012 — Cortex escalation-ratio live check run 6 — fires vs messages actually sent (last 48h)

- Claim: issue #1483 comment 7206547927 (2026-11-27 ~06:02 IST).
- Branch `musetp13/task-ctx-012-escalation-ratio-run6` from main `99dc0c90`.
- Live leg: 2026-11-27 ~06:02–06:08 IST, Oracle Server 1 (+ Server 2 cross-check), under standing clearance 7200564540. Read-only throughout: no restart, no config change, no deploy, no key copied (see §6).
- Method: runs 2/3 (`TASK-CTX-006`/`TASK-CTX-007` evidence docs) + run 4/5 (`TASK-CTX-010`/`TASK-CTX-011`); endpoint snapshot `GET /v1/friday/self_healing` + `journalctl -u Cortex.service` counts and boundaries.

## 0. Verdict — ratio filed over the last 48h

| covered span | fires (cycles) | attempts | delivered |
|---|---|---|---|
| 48h requested (Nov 25 06:06 → Nov 27 06:06 IST); 45.04h directly counted, 2.93h head estimated from measured cadence | **~5,420** (5,085 counted + ~331 est.) | **0** | **0** |

- **No delivery gap in the window: nothing escalated, so nothing was owed.** The supervisor ran the whole window; every subsystem CLOSED; the only escalation in the service's lifetime predates the window and was delivered (HTTP 200).
- `ratio_check`: `consecutive_failed_deliveries` 0, `channel_broken` false, `last_alert` null — PASS.

## 1. Live state — both servers, first-hand

**Oracle Server 1 (friday-universe-vnic) — the live Cortex:**

- `Cortex.service`: `ActiveState=active`, `SubState=running`, `MainPID=3771939`, `NRestarts=0`, `Result=success`.
- Started **Tue 2026-11-24 19:34:23 IST** — up 58.54h at snapshot time; never restarted since.
- `:8009` LISTENING, owned by python PID 3771939 (the Cortex process itself).
- Endpoint `GET /v1/friday/self_healing`: HTTP 401 without a key (expected — key-gated); HTTP 200 with the FRIDAY service token (see §2). One transient first-probe timeout (curl exit 28 at a 10 s timeout); the 30 s retry answered in 0.10 s. Not a finding.
- Journal: **7,504 entries in the last 48h** (`journalctl -u Cortex.service --since '48 hours ago'`); 7,508 total retained. Oldest surviving entry **Nov 25 09:02:34** — retention ~45h for this unit, so the window head Nov 25 06:06–09:02 (~2.93h) aged out; coverage is stated, not invented (§3).

**Oracle Server 2 (friday-universe-vnic-2) — cross-check:**

- `Cortex.service`: `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `NRestarts=0`.
- Endpoint: connection refused (curl exit 7). Journal: 1 line in 48h. Cortex does not run here.

## 2. Endpoint snapshot — exact counters (observed_at 2026-11-27T00:36:54Z = 06:06:54 IST)

- `background`: running true, **`cycles` 6,616**, errors 0, `self_healing_enabled` true, `repair_cooldown_seconds` 30.0. 6,616 cycles over 58.54h uptime = 113.0/h (~31.9 s/cycle).
- `escalation_delivery`: channel `telegram:api.telegram.org`, configured true, **attempts 1, delivered 1**, `suppressed_duplicates` 0. Last (only) attempt: redis, "3 repair attempts did not restore health", **2026-11-24T14:06:06Z**, status 200, delivered true.
- `escalations`: exactly 1 entry — the same redis event, 2026-11-24T14:06:06Z. **It predates the 48h window (window opens Nov 25 ~00:36Z).**
- Subsystems, all `state` CLOSED, `consecutive_failures` 0:
  - database: 6,616 successes / 0 failures, signal rate 1.0
  - schema: 6,616 / 0, rate 1.0
  - redis: 6,612 / 4, rate 0.9994; transitions CLOSED→OPEN 2026-11-24T14:05:35Z ("3 consecutive failures") → CLOSED 2026-11-24T14:06:40Z ("probe succeeded") — 65 s outage, before the window
  - ai_universe: 6,615 / 1, rate 0.9998 (single failure, no OPEN transition)
  - agents: 6,616 / 0, rate 1.0
  - ingestion / tools: 0 samples, `failure_ratio` null, "no probe"
- `last_probes`: database/schema/redis/ai_universe/agents all HEALTHY at 2026-11-27T00:36:28–30Z. `degraded`: [].
- Auth note: `CORTEX_API_KEY` → HTTP 403 ("Invalid FRIDAY service token"); the endpoint accepts the FRIDAY service token (`FRIDAY_API_KEY`). The key was read from the service's own `.env` on Server 1 inside the probe shell only and never printed, copied, or committed (see §6).

## 3. Journal derivation — the 48h window, counted

- `/ready` probes (supervisor 30 s tick against FRIDAY `http://10.0.0.121:8001/ready`, all 200 OK): **5,085 in the retained span** (Nov 25 09:02:34 → Nov 27 06:05:12). Tick spacing measured 31–32 s (09:02:34 → 09:03:05 → 09:03:37).
- Keyword counts over the same span: `escalat` 0, `deliver` 0, `Telegram` 0, `notif` 0, `repair` 0, `SelfHealing` 0, `supervisor` 0, `streak` 0, `did not restore health` 0, `cycle` 0, `ERROR` 0, `CRITICAL` 0, `WARN` 13.
- The 13 WARN lines: 1 real — "self-healing: ensuring the AI Universe client runs in deterministic fallback" (Nov 26 19:42:46); 12 FastAPI "Duplicate Operation ID" UserWarnings at Nov 27 02:06:03 (cosmetic, startup warnings in `production_router.py`/`main.py`).
- **Window fires:** counted 5,085 over the retained 45.04h = 112.9/h. Aged-out head 2.93h × 112.9/h ≈ 331 (est., labelled). Total ≈ **5,416**. Cross-check from cumulative cycles: 6,616 / 58.54h = 113.0/h → 48h × 113.0 ≈ 5,424. Methods agree within 0.2%; filed as **~5,420**.
- **Window attempts / delivered: 0 / 0.** Three independent confirmations: (a) endpoint cumulative attempts/delivered are both 1, dated Nov 24 14:06:06Z, before the window; (b) endpoint `escalations` list holds only that one pre-window entry; (c) journal keyword counts are 0 across the retained 45.04h (the aged-out 2.93h head, Nov 25 06:06–09:02, sits between two quiet periods — no escalation is recorded on either side of it, and the cumulative counter proves only one escalation exists in the service's lifetime).

## 4. Comparison with earlier runs

| run | covered span | fires | attempts | delivered |
|-----|--------------|-------|----------|-----------|
| 2 (Muse 7) | 31.42h | 3,622 | 73 | 1 |
| 3 (Muse 12) | 32.30h | 3,651 (2,547 exact + 1,104 est.) | 147 | 1 |
| 4 (Muse 10) | 0h | 0 countable | unobservable | unobservable — NO DATA |
| 5 (Muse TP9) | — | — | — | repo-side prep only; restart-clearance request, no live leg |
| **6 (Muse TP13)** | **48h requested / 45.04h counted** | **~5,420** | **0** | **0** |

- Runs 2/3 filed a real ratio over ~31–32h because the journal had already aged out the window head — the same retention limit (§3) bit this run for ~2.93h only, because the service was probed while still inside retention.
- The attempts−delivered gap runs 2/3 discussed (dedupe suppression by design) does not arise here: zero attempts, zero deliveries, zero suppressions.

## 5. Corrections to the record — runs 4/5 probed the wrong server

1. **Live Cortex is on Oracle Server 1, not Server 2.** Runs 4/5 probed Server 2 only (service dead, endpoint refused, journal empty) and filed NO DATA / a restart request on that basis. The supervisor was alive on Server 1 the whole time — up since Nov 24 19:34:23 IST, 6,616 cycles. Run 4's NO-DATA verdict is superseded by this run's first-hand Server 1 evidence; it was a wrong-server artifact, not a dead supervisor.
2. **No restart is needed, and none was performed.** The run-5 restart-clearance request (§2 of the run-5 doc) is MOOT: the service never died. The owner stop order is not engaged by this task — nothing was restarted, and no restart clearance is being sought here.
3. **Key-file blocker G4 is also wrong-server.** `/opt/friday_universe/Cortex/.env` exists on Server 1 (2,249 bytes, modified Nov 24 19:34, same time as service start). Run 4 reported it absent on Server 2 only.
4. **Journal retention on Server 1 is ~45h for this unit** (oldest Nov 25 09:02:34 at probe ~06:05 Nov 27), not the ~34h run 4 measured on Server 2. The run-5 mitigation A (snapshot cadence) remains the right standing advice for any future full-48h filing: probe inside retention, don't wait until T0+48h.

## 6. What this task did NOT do

- No restart of `Cortex.service` (or any service), no config change, no journald change, no code deploy, no live trading or money movement (none involved).
- No secret copied: the FRIDAY service token was sourced from the service's own `.env` on Server 1 inside the probe shell and used only as a curl header on that host; the token value was never printed, logged, committed, or sent anywhere. Only the endpoint JSON (counters) and the `CORTEX_API_KEY`→403 / `FRIDAY_API_KEY`→200 auth outcome are recorded here.
- No board change in this PR: the CTX-012 flip (AVAILABLE → CLAIMED/IN_REVIEW) rides in the coordinator's consolidated board PR, per team rule (work PRs carry no `WORK_BOARD.yaml` hunk).

## States

- Implemented: YES (live leg executed, ratio filed in this doc).
- Tested: YES (live: endpoint snapshot + journal counts, both servers, first-hand).
- Merged: NO (work PR awaits independent review + Muse audit).
- Deployed: N/A (evidence document; no live change).
- Production-verified: YES (live Cortex on Server 1 measured end-to-end: service, endpoint, journal, counters).

— Muse TP13
