# TASK-CTX-014 — Cortex escalation-ratio live check run 8 — fires vs messages actually sent (last 48h)

- Claim: issue #2045 comment 7221048222 (2026-11-27 ~20:08 IST); claim confirmed by coordinator WATCH227 §D.5 (hub 7221769260, 20:42 IST) — overrides #2151's TP4 pos-2 queue note; board flip CLAIMED/muse_15 rides the coordinator board PR.
- Branch `muse15/task-ctx-014` from main `cf49af6b` (#2141 merge), fast-forwarded to `06b32a81` before filing (SPEED ORDER rule 4).
- Live leg: 2026-11-27 ~21:05–21:07 IST, Oracle Server 1 (+ Server 2 cross-check), under standing clearance 7200564540. Read-only throughout: no restart, no config change, no deploy, no key copied (see §6). First bridge call failed on transport (MCP request did not complete — the degradation WATCH226/227 noted); retried once, landed.

## 0. Verdict — ratio filed over the last 48h

| covered span | fires (cycles) | attempts | delivered |
|---|---|---|---|
| 48h requested (Nov 25 21:07 → Nov 27 21:07 IST); 47.80h directly counted, 0.20h head estimated from measured cadence | **~5,390** (5,367 counted + ~19 est.) | **1** | **1** |

- **No delivery gap in the window: the one in-window escalation was delivered.** At 2026-11-27 16:15:11 IST the `ai_universe` subsystem escalated ("3 repair attempts did not restore health") and the Telegram delivery returned HTTP 200. This is the first in-window escalation in the run series (runs 6/7 were 0/0).
- `ratio_check`: `consecutive_failed_deliveries` 0, `channel_broken` false, `last_alert` null — PASS.

## 1. Live state — both servers, first-hand

**Oracle Server 1 (friday-universe-vnic) — the live Cortex:**

- `Cortex.service`: `ActiveState=active`, `SubState=running`, `MainPID=3771939`, `NRestarts=0`, `Result=success`.
- Started **Tue 2026-11-24 19:34:23 IST** — up 73.55h at snapshot time; never restarted since (same PID as runs 6/7).
- `:8009` LISTENING, owned by the Cortex process.
- Endpoint `GET /v1/friday/self_healing`: HTTP 401 without a key (expected — key-gated); HTTP 200 with the FRIDAY service token via the `X-Friday-Api-Key` header (see §2).
- Journal: **6,791 entries in the last 48h** (`journalctl -u Cortex.service --since '48 hours ago'`); oldest surviving entry **Nov 25 21:17:25** — retention ~47.80h for this unit, so the window head Nov 25 21:07–21:17 (~0.20h) aged out; coverage is stated, not invented (§3).

**Oracle Server 2 (friday-universe-vnic-2) — cross-check:**

- `Cortex.service`: `ActiveState=inactive`, `SubState=dead`, `MainPID=0`, `NRestarts=0`.
- Endpoint: connection refused (curl 000). Journal: 1 line in 48h. Cortex does not run here.

## 2. Endpoint snapshot — exact counters (observed_at 2026-11-27T15:37:24Z = 21:07:24 IST)

- `background`: running true, **`cycles` 8,292**, errors 0, `self_healing_enabled` true, `repair_cooldown_seconds` 30.0. 8,292 cycles over 73.55h uptime = 112.7/h (~31.9 s/cycle).
- `escalation_delivery`: channel `telegram:api.telegram.org`, configured true, **attempts 2, delivered 2**, `suppressed_duplicates` 0. Last (only in-window) attempt: ai_universe, "3 repair attempts did not restore health", **2026-11-27T10:45:11Z (16:15:11 IST)**, status 200, delivered true.
- `escalations`: exactly 2 entries — redis, 2026-11-24T14:06:06Z (pre-window, same as runs 6/7), and **ai_universe, 2026-11-27T10:45:11Z — inside the 48h window** (window opens Nov 25 15:37Z).
- Subsystems, all `state` CLOSED, `consecutive_failures` 0:
  - database: 8,292 successes / 0 failures, signal rate 1.0
  - schema: 8,292 / 0, rate 1.0
  - redis: 8,288 / 4, rate 0.9995; transitions CLOSED→OPEN 2026-11-24T14:05:35Z ("3 consecutive failures") → CLOSED 2026-11-24T14:06:40Z ("probe succeeded") — 65 s outage, before the window
  - ai_universe: 8,288 / 4, rate 0.9995 (total_failures 2 → 4 since run 7; **no OPEN transition** — the escalation fired without one)
  - agents: 8,292 / 0, rate 1.0
  - ingestion / tools: 0 samples, `failure_ratio` null, "no probe"
- `last_probes`: database/schema/redis/ai_universe/agents all HEALTHY at 2026-11-27T15:37:03–15:37:05Z. `degraded`: [].
- Auth note (as run 7): the endpoint requires the **`X-Friday-Api-Key`** header with the FRIDAY service token (`FRIDAY_API_KEY` from `/opt/friday_universe/FRIDAY/.env`, read inside the probe shell only). No key → HTTP 401; `Authorization: Bearer` does not work. The key was never printed, copied, or committed (see §6).

## 3. Journal derivation — the 48h window, counted

- `/ready` probes (supervisor 30 s tick against FRIDAY `http://10.0.0.121:8001/ready`, all 200 OK): **5,367 in the retained span** (Nov 25 21:17:25 → Nov 27 21:05:30).
- Keyword counts over the same span: `escalat` 0, `deliver` 0, `Telegram` 0, `notif` 0, `repair` 0, `SelfHealing` 0, `supervisor` 0, `streak` 0, `did not restore health` 0, `cycle` 0, `ERROR` 0, `CRITICAL` 0, `WARN` 7.
- The 7 WARN lines:
  - Nov 26 19:42:46 — "self-healing: ensuring the AI Universe client runs in deterministic fallback" (same as runs 6/7)
  - Nov 27 06:06:54 — "FRIDAY authentication attempt with invalid API key rejected" (run 6's own wrong-key probe, per run 7 — not a live incident)
  - Nov 27 06:30:18 — deterministic fallback (same as run 7)
  - Nov 27 15:06:33 — deterministic fallback (new since run 7)
  - Nov 27 15:40:03 ×3 — "FRIDAY authentication attempt with invalid API key rejected" (new since run 7; three identical lines in one second — unattributed, not mine: my probe was a no-key 401 at ~21:05, which logs no such WARN; no escalation followed, endpoint healthy)
- **Window fires:** counted 5,367 over the retained 47.80h = 112.3/h. Aged-out head 0.20h × 112.3/h ≈ 19 (est., labelled). Total ≈ **5,386**. Cross-check from cumulative cycles: 8,292 / 73.55h = 112.7/h → 48h × 112.7 ≈ 5,411. Methods agree within 0.5%; filed as **~5,390**.
- **Window attempts / delivered: 1 / 1.** Three confirmations: (a) endpoint cumulative attempts/delivered are both 2, up from 1/1 at run 7 — the delta is exactly the one in-window ai_universe event; (b) endpoint `escalations` list holds exactly that event in-window (plus the pre-window redis one); (c) the journal records no escalation keywords at all in the retained span — the escalation is visible only via the endpoint counters, so the endpoint is authoritative here and the journal 0-counts must NOT be read as "no escalation happened". The aged-out 0.20h head (Nov 25 21:07–21:17) sits between two quiet periods and the cumulative counter proves only two escalations exist in the service's lifetime, one per list entry — neither can hide in the head.
- ai_universe failures rose 2 → 4 since run 7 (14:28 IST); one sequence ended in the 16:15 escalation; the other left no transition or journal trace. No OPEN transition, no journal ERROR — the subsystem recovered on the next tick each time.

## 4. Comparison with earlier runs

| run | covered span | fires | attempts | delivered |
|-----|--------------|-------|----------|-----------|
| 2 (Muse 7) | 31.42h | 3,622 | 73 | 1 |
| 3 (Muse 12) | 32.30h | 3,651 (2,547 exact + 1,104 est.) | 147 | 1 |
| 4 (Muse 10) | 0h | 0 countable | unobservable | unobservable — NO DATA |
| 5 (Muse TP9) | — | — | — | repo-side prep only; restart-clearance request, no live leg |
| 6 (Muse TP13) | 48h requested / 45.04h counted | ~5,420 | 0 | 0 |
| 7 (Muse TP14) | 48h requested / 46.85h counted | ~5,410 | 0 | 0 |
| **8 (Muse 15)** | **48h requested / 47.80h counted** | **~5,390** | **1** | **1** |

- Runs 6/7/8 agree on the supervisor: ~5,400 fires per 48h, zero restarts, ~74h continuous uptime. Run 8 breaks the zero-escalation streak: one ai_universe escalation, delivered first time (HTTP 200, no suppression, no failed delivery). The attempts−delivered gap runs 2/3 discussed (dedupe suppression by design) does not arise here: 1 attempt, 1 delivery, 0 suppressions.
- Retention improved again (45.04h → 46.85h → 47.80h counted) as the journal keeps the full window head nearly covered.

## 5. Notes for the next run

1. **Live Cortex is on Oracle Server 1, not Server 2** (re-confirmed; Server 2 dead, endpoint refused, 1 journal line).
2. **Auth header is `X-Friday-Api-Key`** — Bearer does not work (see §2). Probe with that header; the token lives in the service `.env` files on Server 1.
3. **Journal retention on Server 1 is ~47.80h for this unit** (oldest Nov 25 21:17:25 at probe ~21:05 Nov 27). Probe inside retention; the run-5 mitigation A (snapshot cadence) remains the right standing advice for any future full-48h filing.
4. **Watch ai_universe**: failures 2 → 4 across the run-7→run-8 interval, one escalation delivered. If the next run shows another escalation or an OPEN transition, that is a trend, not a one-off.
5. No restart is needed, and none was performed.

## 6. What this task did NOT do

- No restart of `Cortex.service` (or any service), no config change, no journald change, no code deploy, no live trading or money movement (none involved).
- No secret copied: the FRIDAY service token was sourced from the service's own `.env` on Server 1 inside the probe shell and used only as a request header on that host; the token value was never printed, logged, committed, or sent anywhere. Only the endpoint JSON (counters) and the auth-header outcome are recorded here.
- No board change in this PR: the CTX-014 flip rides in the coordinator's consolidated board PR, per team rule (work PRs carry no `WORK_BOARD.yaml` hunk).

## States

- Implemented: YES (live leg executed, ratio filed in this doc).
- Tested: YES (live: endpoint snapshot + journal counts, both servers, first-hand).
- Merged: NO (work PR awaits independent review + coordinator merge).
- Deployed: N/A (evidence document; no live change).
- Production-verified: YES (live Cortex on Server 1 measured end-to-end: service, endpoint, journal, counters).

— Muse 15
