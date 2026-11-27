# TASK-CTX-013 — Cortex escalation-ratio live check run 7 — fires vs messages actually sent (last 48h)

- Claim: issue #2045 comment 7213303611 (2026-11-27 ~13:55 IST).
- Branch `musetp14/task-ctx-013-escalation-ratio-live-check-run-7` from main `6aaa21ee`, fast-forwarded to `7175b9b0` before filing (SPEED ORDER rule 4).
- Live leg: 2026-11-27 ~14:26–14:28 IST, Oracle Server 1 (+ Server 2 cross-check), under standing clearance 7200564540. Read-only throughout: no restart, no config change, no deploy, no key copied (see §6).
- Method: run 6 (`TASK-CTX-012` evidence doc); endpoint snapshot `GET /v1/friday/self_healing` + `journalctl -u Cortex.service` counts and boundaries.

## 0. Verdict — ratio filed over the last 48h

| covered span | fires (cycles) | attempts | delivered |
|---|---|---|---|
| 48h requested (Nov 25 14:26 → Nov 27 14:26 IST); 46.85h directly counted, 1.15h head estimated from measured cadence | **~5,410** (5,274 counted + ~129 est.) | **0** | **0** |

- **No delivery gap in the window: nothing escalated, so nothing was owed.** The supervisor ran the whole window; every subsystem CLOSED; the only escalation in the service's lifetime predates the window and was delivered (HTTP 200).
- `ratio_check`: `consecutive_failed_deliveries` 0, `channel_broken` false, `last_alert` null — PASS.

## 1. Live state — both servers, first-hand

**Oracle Server 1 (friday-universe-vnic) — the live Cortex:**

- `Cortex.service`: `ActiveState=active`, `SubState=running`, `MainPID=3771939`, `NRestarts=0`, `Result=success`.
- Started **Tue 2026-11-24 19:34:23 IST** — up 66.90h at snapshot time; never restarted since (same PID as run 6).
- `:8009` LISTENING, owned by python PID 3771939 (the Cortex process itself).
- Endpoint `GET /v1/friday/self_healing`: HTTP 401 without a key (expected — key-gated); HTTP 200 with the FRIDAY service token via the `X-Friday-Api-Key` header (see §2). No transient timeout this run.
- Journal: **7,805 entries in the last 48h** (`journalctl -u Cortex.service --since '48 hours ago'`); oldest surviving entry **Nov 25 15:35:10** — retention ~46.85h for this unit, so the window head Nov 25 14:26–15:35 (~1.15h) aged out; coverage is stated, not invented (§3).

**Oracle Server 2 (friday-universe-vnic-2) — cross-check:**

- `Cortex.service`: `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `NRestarts=0`.
- Endpoint: connection refused (curl 000). Journal: 1 line in 48h. Cortex does not run here.

## 2. Endpoint snapshot — exact counters (observed_at 2026-11-27T08:58:13Z = 14:28:13 IST)

- `background`: running true, **`cycles` 7,550**, errors 0, `self_healing_enabled` true, `repair_cooldown_seconds` 30.0. 7,550 cycles over 66.90h uptime = 112.9/h (~31.9 s/cycle).
- `escalation_delivery`: channel `telegram:api.telegram.org`, configured true, **attempts 1, delivered 1**, `suppressed_duplicates` 0. Last (only) attempt: redis, "3 repair attempts did not restore health", **2026-11-24T14:06:06Z**, status 200, delivered true.
- `escalations`: exactly 1 entry — the same redis event, 2026-11-24T14:06:06Z. **It predates the 48h window (window opens Nov 25 08:56Z).**
- Subsystems, all `state` CLOSED, `consecutive_failures` 0:
  - database: 7,551 successes / 0 failures, signal rate 1.0
  - schema: 7,551 / 0, rate 1.0
  - redis: 7,547 / 4, rate 0.9995; transitions CLOSED→OPEN 2026-11-24T14:05:35Z ("3 consecutive failures") → CLOSED 2026-11-24T14:06:40Z ("probe succeeded") — 65 s outage, before the window
  - ai_universe: 7,548 / 2, rate 0.9997 (single failure since run 6, no OPEN transition)
  - agents: 7,550 / 0, rate 1.0
  - ingestion / tools: 0 samples, `failure_ratio` null, "no probe"
- `last_probes`: database/schema/redis/ai_universe/agents all HEALTHY at 2026-11-27T08:57:42–08:58:12Z. `degraded`: [].
- Auth note (correction to run 6 §2): the endpoint requires the **`X-Friday-Api-Key`** header. `Authorization: Bearer <token>` → HTTP 401 "Missing X-Friday-Api-Key header" (verified this run with both the FRIDAY and Cortex `.env` tokens); no key → HTTP 401; `X-Friday-Api-Key` with the FRIDAY service token → HTTP 200 (verified with the token from both `/opt/friday_universe/FRIDAY/.env` and `/opt/friday_universe/Cortex/.env` — same value accepted from either file). The key was read from the service's own `.env` on Server 1 inside the probe shell only and never printed, copied, or committed (see §6).

## 3. Journal derivation — the 48h window, counted

- `/ready` probes (supervisor 30 s tick against FRIDAY `http://10.0.0.121:8001/ready`, all 200 OK): **5,274 in the retained span** (Nov 25 15:35:10 → Nov 27 14:26:36).
- Keyword counts over the same span: `escalat` 0, `deliver` 0, `Telegram` 0, `notif` 0, `repair` 0, `SelfHealing` 0, `supervisor` 0, `streak` 0, `did not restore health` 0, `cycle` 0, `ERROR` 0, `CRITICAL` 0, `WARN` 15.
- The 15 WARN lines: 12 FastAPI "Duplicate Operation ID" UserWarnings at Nov 27 02:06:03 (cosmetic, startup warnings — same as run 6); 1 real — "self-healing: ensuring the AI Universe client runs in deterministic fallback" (Nov 26 19:42:46, same as run 6); 1 "FRIDAY authentication attempt with invalid API key rejected" (Nov 27 06:06:54 — run 6's own no-key/wrong-key probe, not a live incident); 1 deterministic-fallback (Nov 27 06:30:18, new since run 6).
- **Window fires:** counted 5,274 over the retained 46.85h = 112.6/h. Aged-out head 1.15h × 112.6/h ≈ 129 (est., labelled). Total ≈ **5,403**. Cross-check from cumulative cycles: 7,550 / 66.90h = 112.9/h → 48h × 112.9 ≈ 5,417. Methods agree within 0.3%; filed as **~5,410**.
- **Window attempts / delivered: 0 / 0.** Three independent confirmations: (a) endpoint cumulative attempts/delivered are both 1, dated Nov 24 14:06:06Z, before the window; (b) endpoint `escalations` list holds only that one pre-window entry; (c) journal keyword counts are 0 across the retained 46.85h (the aged-out 1.15h head, Nov 25 14:26–15:35, sits between two quiet periods — no escalation is recorded on either side of it, and the cumulative counter proves only one escalation exists in the service's lifetime).

## 4. Comparison with earlier runs

| run | covered span | fires | attempts | delivered |
|-----|--------------|-------|----------|-----------|
| 2 (Muse 7) | 31.42h | 3,622 | 73 | 1 |
| 3 (Muse 12) | 32.30h | 3,651 (2,547 exact + 1,104 est.) | 147 | 1 |
| 4 (Muse 10) | 0h | 0 countable | unobservable | unobservable — NO DATA |
| 5 (Muse TP9) | — | — | — | repo-side prep only; restart-clearance request, no live leg |
| 6 (Muse TP13) | 48h requested / 45.04h counted | ~5,420 | 0 | 0 |
| **7 (Muse TP14)** | **48h requested / 46.85h counted** | **~5,410** | **0** | **0** |

- Runs 6/7 agree: zero escalations, zero attempts, zero deliveries across consecutive 48h windows; the supervisor has now run ~67h without a restart and without a single in-window escalation. The attempts−delivered gap runs 2/3 discussed (dedupe suppression by design) does not arise here: zero attempts, zero deliveries, zero suppressions.
- One new ai_universe probe failure since run 6 (total_failures 1 → 2); no OPEN transition, no escalation, no journal ERROR — a single failed probe that recovered on the next tick.

## 5. Notes for the next run

1. **Live Cortex is on Oracle Server 1, not Server 2** (re-confirmed; Server 2 dead, endpoint refused, 1 journal line).
2. **Auth header is `X-Friday-Api-Key`** — Bearer does not work (see §2). Probe with that header; the token lives in the service `.env` files on Server 1.
3. **Journal retention on Server 1 is ~46.85h for this unit** (oldest Nov 25 15:35:10 at probe ~14:26 Nov 27). Probe inside retention; the run-5 mitigation A (snapshot cadence) remains the right standing advice for any future full-48h filing.
4. No restart is needed, and none was performed.

## 6. What this task did NOT do

- No restart of `Cortex.service` (or any service), no config change, no journald change, no code deploy, no live trading or money movement (none involved).
- No secret copied: the FRIDAY service token was sourced from the service's own `.env` on Server 1 inside the probe shell and used only as a request header on that host; the token value was never printed, logged, committed, or sent anywhere. Only the endpoint JSON (counters) and the auth-header outcome are recorded here.
- No board change in this PR: the CTX-013 flip (AVAILABLE → CLAIMED/IN_REVIEW) rides in the coordinator's consolidated board PR, per team rule (work PRs carry no `WORK_BOARD.yaml` hunk).

## States

- Implemented: YES (live leg executed, ratio filed in this doc).
- Tested: YES (live: endpoint snapshot + journal counts, both servers, first-hand).
- Merged: NO (work PR awaits independent review + Muse audit).
- Deployed: N/A (evidence document; no live change).
- Production-verified: YES (live Cortex on Server 1 measured end-to-end: service, endpoint, journal, counters).

— Muse TP14
