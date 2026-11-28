# TASK-CTX-017 — Cortex escalation-ratio live check run 10 — fires vs messages actually sent (last 48h)

- Claim: TASK-CTX-017, WATCH267 §D.2 / WATCH268 §D.2 (replacement head after SEN-045 release, hub #2045). Claimed ~15:40 IST 2026-11-28 (hub #2045 comment 7237720700); branch `muse13/task-ctx-017-escalation-ratio` from main `ed0bd3eb` (verified by API read-back).
- Board (live main `3b5091de`, blob `94fd349d`, verified first-hand this run): TASK-CTX-017 CLAIMED / muse_13 / P2, blockers []. The CLAIMED flip already landed via the coordinator's board PR; per WATCH244 §C, board flips are coordinator-only — **no board hunk in this work PR**.
- Live leg: 2026-11-28 ~16:39–16:41 IST, Oracle Server 1 (+ Server 2 cross-check), under the owner grant (2026-11-26) + standing clearance 7200564540: the grant covers own-task live verification via run_shell. Read-only throughout: no restart, no config change, no deploy, no key copied or committed (see §6).
- Provenance note: claimed 15:40 IST with the branch at main and zero commits; the 16:36 hourly self-check found the stall (~56 min, no work product) and repaired it in-run by executing the live legs first-hand this run. No coordinator direction was needed — the legs are the task's own acceptance route.

## 0. Verdict — ratio filed over the last 48h

| covered span | fires (cycles) | attempts | delivered | suppressed |
|---|---|---|---|---|
| 48h requested (Nov 26 16:39 → Nov 28 16:39 IST); 47.65h directly counted, 0.34h head estimated from measured cadence | **~5,360** (5,297 counted + ~38 est.) | **8** | **2** | **6** |

- **Fires vs messages actually sent: ~5,360 : 2 (≈ 2,680 : 1).** The two in-window deliveries were the Nov 27 16:15 IST ai_universe escalation and the Nov 28 06:37 IST ai_universe escalation (both Telegram HTTP 200, confirmed in the journal to the second).
- **Post-#1054 behaviour HOLDS.** No new escalation event since run 9: the endpoint cumulative counters are frozen at attempts 9 / delivered 3 / suppressed 6, the `escalations` list is byte-identical to run 9, ai_universe failures are still 11, and the journal holds no new Telegram POST since run 9's snapshot. The Nov 28 burst (7 fires, 1 delivered, 6 suppressed) has not repeated — the subsystem flap has quieted.
- `ratio_check`: `consecutive_failed_deliveries` 0, `channel_broken` false, `last_alert` null — PASS.

## 1. Live state — both servers, first-hand

**Oracle Server 1 (`friday-universe-vnic`) — the live Cortex:**

- `Cortex.service`: `ActiveState=active`, `SubState=running`, `MainPID=3771939`, `NRestarts=0`, started **Tue 2026-11-24 19:34:23 IST** — up 93.09h at snapshot; never restarted since (same PID as runs 6/7/8/9). `:8009` LISTENING (python pid 3771939). `/ready` HTTP 200.
- Endpoint `GET /v1/friday/self_healing` snapshot `2026-11-28T11:09:41Z` (16:39:41 IST), via `X-Friday-Api-Key` from the service `.env` (read inside the probe shell only; Bearer does not work, per CTX-014 §2):
  - `background.cycles` **10,454** (112.3/h over uptime); `errors` 0.
  - `escalation_delivery`: channel `telegram:api.telegram.org`, configured true; **attempts 9, delivered 3, suppressed_duplicates 6** (cumulative since process start; run 9 was 9/3/6 — unchanged).
  - `escalations` list: 9 entries — redis 2026-11-24T14:06:06Z (pre-window) + ai_universe 2026-11-27T10:45:11Z + 7 ai_universe on 2026-11-28 (01:07:45Z, 01:30:03Z, 01:44:13Z, 01:48:20Z, 03:48:12Z, 05:43:15Z, 06:55:47Z). `last_attempt` 06:55:47Z, delivered false, "duplicate suppressed within dedupe window".
  - All subsystems CLOSED, `degraded` []; ai_universe signal rate 0.9989 (10,443 successes / 11 failures); redis 0.9996 (10,450 / 4, last transitions Nov 24 only); database/schema/agents 1.0. No OPEN transition at any escalation — same as runs 8/9.
- **Server 2 cross-check (expected dead):** `Cortex.service` inactive/dead, MainPID 0, `:8009` connection refused (HTTP 000), 1 journal line in 48h. It does not run there.

## 2. Journal — 48h window, first-hand

`journalctl -u Cortex.service --since '2026-11-26 16:39:00' --until '2026-11-28 16:39:00' --no-pager -o short-iso` (Server 1, IST):

- **Total lines 6,795.** First surviving line 2026-11-26T16:59:30+0530; last 2026-11-28T16:38:29+0530. Retained span 47.65h — the window head (~0.34h) aged out; coverage is stated, not invented.
- **Restarts 0.** No `Stopped / Started` boundary in the window.
- Keyword counts: `escalat` 0, `deliver` 0, `did not restore health` 0, `cycle` 0, `ERROR` 0, `WARN` 26 — the journal holds no escalation lines (runs 2/3/8/9 agree), so the endpoint is authoritative for messages; journal 0-counts must NOT be read as "no escalation happened".
- `/ready` probes (fires proxy): **5,297** over the retained 47.65h = 111.2/h. Inbound `GET /health` 1,352.
- `Telegram` 3: three `POST …/sendMessage HTTP/1.1 200 OK` lines — Nov 27 16:15:15 IST, Nov 28 01:26:19 IST, Nov 28 06:37:46 IST. Only the first and third are escalation deliveries (they match the endpoint events at 10:45:11Z Nov 27 and 01:07:45Z Nov 28 to the second). The middle one (01:26:19 IST) has **no matching escalation event** and sits inside CTX-009 dispatch/budget activity (per run 9); the same process has another Telegram sender (`agent_budgets.py` also posts to `api.telegram.org/sendMessage`). **Method caution (carried): journal Telegram counts ≠ escalation deliveries — the endpoint counters are the authority.**
- WARN lines (26): 3× "self-healing: ensuring the AI Universe client runs in deterministic fallback" (Nov 26 19:42, Nov 27 06:30, Nov 27 15:06 IST); 11× "FRIDAY authentication attempt with invalid API key rejected (client=127.0.0.1 path=/v1/friday/self_healing)" — 1× Nov 27 06:06:54, 3× Nov 27 15:40:03, **7× Nov 28 16:31:18 (new since run 9 — a burst of 7 wrong-key attempts in one second, ~8 min before this run's probe; unattributed, not this run: my probe used the correct key plus one no-key 401, which logs no such WARN; no escalation followed, endpoint healthy)**; 12× FastAPI `UserWarning: Duplicate Operation ID` + `warnings.warn` stack lines in a single burst at Nov 27 02:06:03 (HEAD-operation ID collisions in the API router; a schema-generation burst, no restart — PID unchanged, cycles continuous).

## 3. Computation

- **Window fires:** counted 5,297 over the retained 47.65h = 111.2/h. Aged-out head 0.34h × 111.2/h ≈ 38 (est., labelled). Total ≈ **5,335**. Cross-check from cumulative cycles: 10,454 / 93.09h = 112.3/h → 48h ≈ 5,390. Methods within 1.0%; filed as **~5,360** (between the two, as run 9 filed ~5,370 between 5,341 and 5,394).
- **Window attempts / delivered / suppressed: 8 / 2 / 6.** Three confirmations: (a) endpoint cumulative attempts/delivered/suppressed are 9/3/6, identical to run 9 — the deltas since run 9 are 0/0/0, and the 8 in-window events are exactly run 9's set (one pre-snapshot event Nov 27 10:45Z + 7 on Nov 28); (b) the endpoint `escalations` list holds exactly those 8 events in-window (plus the pre-window redis one); (c) the journal records the two delivered Telegram POSTs at the matching seconds (16:15:15 IST Nov 27; 06:37:46 IST Nov 28), and the 6 suppressed events have no POST — exactly the dedupe behaviour. The aged-out 0.34h head (Nov 26 16:39–16:59 IST) sits between quiet periods and the cumulative counter proves only 9 escalations exist in the service's lifetime — none can hide in the head.
- **The burst is over, not ongoing:** ai_universe failures 11, unchanged since run 9; no new failure streak, no OPEN transition, no journal ERROR. The run-9 watch item ("if the next run shows another burst or an OPEN transition, that is a trend") resolves as **no trend this run** — one burst, then quiet.
- Cycles delta check: 10,323 (run 9, 15:26 IST) → 10,454 (this run, 16:39 IST) = +131 over 73.3 min ≈ 107/h, consistent with the ~112/h long-run cadence within tick phase noise.

## 4. Comparison with earlier runs

| run | covered span | fires | attempts | delivered | suppressed |
|-----|--------------|-------|----------|-----------|------------|
| 2 (Muse 7) | 31.42h | 3,622 | 73 | 1 | — |
| 3 (Muse 12) | 32.30h | 3,651 (2,547 exact + 1,104 est.) | 147 | 1 | — |
| 4 (Muse 10) | 0h | 0 countable | unobservable | unobservable | — |
| 5 (Muse TP9) | — | — | — | — | repo-side prep only; restart-clearance request, no live leg |
| 6 (Muse TP13) | 48h requested / 45.04h counted | ~5,420 | 0 | 0 | 0 |
| 7 (Muse TP14) | 48h requested / 46.85h counted | ~5,410 | 0 | 0 | 0 |
| 8 (Muse 15) | 48h requested / 47.80h counted | ~5,390 | 1 | 1 | 0 |
| 9 (Muse TP2) | 48h requested / 46.44h counted | ~5,370 | 8 | 2 | 6 |
| **10 (Muse 13)** | **48h requested / 47.65h counted** | **~5,360** | **8** | **2** | **6** |

- Runs 6–10 agree on the supervisor: ~5,400 fires per 48h, zero restarts, same PID since Nov 24. Runs 9 and 10 file the identical 8/2/6 window — the second consecutive filing of the same burst, with no new event between them. The pre-#1054 failure mode (247 identical messages in 48h) would have delivered all 7 burst fires; the post-#1054 layers delivered 1.
- Retention improved slightly (46.44h → 47.65h counted) as the window moved forward; the run-5 mitigation A (snapshot cadence) remains the right standing advice for any future full-48h filing.

## 5. Notes for the next run

1. **Live Cortex is on Oracle Server 1, not Server 2** (re-confirmed; Server 2 dead, endpoint refused, 1 journal line).
2. **Auth header is `X-Friday-Api-Key`** — Bearer does not work (see §1). Probe with that header; the token lives in the service `.env` files on Server 1 (`FRIDAY_API_KEY` in `/opt/friday_universe/FRIDAY/.env`). Read it inside the probe shell only; never print, copy, or commit it.
3. **Journal retention on Server 1 is ~47.65h for this unit** (oldest Nov 26 16:59:30 at probe ~16:39 Nov 28). Probe inside retention; the aged-out head is estimated from measured cadence and labelled (est.).
4. **Journal Telegram counts ≠ escalation deliveries.** The Cortex process has more than one Telegram sender; match POSTs to endpoint events by timestamp and use the endpoint counters as the authority (see §2).
5. **Watch ai_universe:** failures held at 11 across the run-9→run-10 interval, burst over, no new streak. If a later run shows another burst or an OPEN transition, that is a trend, not a one-off.
6. **Wrong-key probes keep appearing:** 7× invalid-key WARNs in one second at 16:31:18 IST Nov 28, minutes before this run. Unattributed; they log as WARNs but cause no escalation. Worth a coordinator note if the pattern repeats — someone (or something) is probing `/v1/friday/self_healing` with a wrong key.
7. No restart is needed, and none was performed.

## 6. What this task did NOT do

- No server move, restart, config change, or deploy. No key material copied, printed, or committed: the FRIDAY service token was read inside the Server 1 probe shell only and used as a request header; the bridge masks tokens in returned output (Telegram lines show `bot***`).
- No board hunk in this work PR (board flips are coordinator-only).

## States

- Implemented: YES (ratio evidence filed, this document).
- Tested: YES (live leg first-hand: endpoint snapshot + journal aggregates + Server 2 cross-check + WARN inventory follow-up).
- Merged: NO (work PR opened this run; merge rides the coordinator).
- Deployed: N/A (evidence document; no live change).
- Production-verified: NO (live proof is the evidence itself; paired verification owed).

— Muse 13, 2026-11-28 ~16:50 IST (hourly self-check 16:36 — stall repair in-run)
