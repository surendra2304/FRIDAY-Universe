# TASK-CTX-016 — Cortex escalation-ratio live check run 9 — fires vs messages actually sent (last 48h)

- Claim: TASK-CTX-016, WATCH263 §D.5, adopted BE 13:45 §B / WATCH264 (hub #2045). Claimed ~14:00 IST 2026-11-28; branch `musetp2/task-ctx-016-escalation-ratio` from main `e5343bac` (full `7683f2658b73321d38b4ac4471a9d43fb873abe2`), created this run (201, verified by ls-remote).
- Board (live main `e5343bac`, verified first-hand this run): TASK-CTX-016 CLAIMED / muse_tp2 / P2, blockers []. The CLAIMED flip already landed via the coordinator's board PR; per WATCH244 §C, board flips are coordinator-only — **no board hunk in this work PR**.
- Live leg: 2026-11-28 ~15:25–15:55 IST, Oracle Server 1 (+ Server 2 cross-check), under the owner grant (2026-11-26) + standing clearance 7200564540, as ruled in WATCH264 addendum (hub #2045 comment 7236522800): the grant covers own-task live verification via run_shell. Read-only throughout: no restart, no config change, no deploy, no key copied or committed (see §6).

## 0. Verdict — ratio filed over the last 48h

| covered span | fires (cycles) | attempts | delivered | suppressed |
|---|---|---|---|---|
| 48h requested (Nov 26 15:26 → Nov 28 15:26 IST); 46.44h directly counted, 1.55h head estimated from measured cadence | **~5,370** (5,168 counted + ~173 est.) | **8** | **2** | **6** |

- **Fires vs messages actually sent: ~5,370 : 2 (≈ 2,685 : 1).** The two in-window deliveries were the Nov 27 16:15 IST ai_universe escalation and the Nov 28 06:37 IST ai_universe escalation (both Telegram HTTP 200, confirmed in the journal to the second).
- **Post-#1054 behaviour HOLDS.** The window contains the first multi-fire burst since #1054: 7 ai_universe fires in ~5.8h (Nov 28 01:07–06:55Z). The two #1054 layers turned 7 fires into 1 new message: each fire is a distinct failure streak (the subsystem recovers between streaks, so the streak layer lets each through once), and the notifier's 6h dedupe suppressed the other 6. No delivery gap beyond the designed dedupe.
- `ratio_check`: `consecutive_failed_deliveries` 0, `channel_broken` false, `last_alert` null — PASS.

## 1. Live state — both servers, first-hand

**Oracle Server 1 (`friday-universe-vnic`) — the live Cortex:**

- `Cortex.service`: `ActiveState=active`, `SubState=running`, `MainPID=3771939`, `NRestarts=0`, started **Tue 2026-11-24 19:34:23 IST** — up 91.87h at snapshot; never restarted since (same PID as runs 6/7/8). `:8009` LISTENING. `/ready` HTTP 200.
- Endpoint `GET /v1/friday/self_healing` snapshot `2026-11-28T09:56:22Z` (15:26:22 IST), via `X-Friday-Api-Key` from the service `.env` (read inside the probe shell only; Bearer does not work, per CTX-014 §2):
  - `background.cycles` **10,323** (112.4/h over uptime); `errors` 0.
  - `escalation_delivery`: channel `telegram:api.telegram.org`, configured true; **attempts 9, delivered 3, suppressed_duplicates 6** (cumulative since process start; run 8 was 2/2/0).
  - `escalations` list: 9 entries — redis 2026-11-24T14:06:06Z (pre-window) + ai_universe 2026-11-27T10:45:11Z + 7 ai_universe on 2026-11-28 (01:07:45Z, 01:30:03Z, 01:44:13Z, 01:48:20Z, 03:48:12Z, 05:43:15Z, 06:55:47Z). `last_attempt` 06:55:47Z, delivered false, "duplicate suppressed within dedupe window".
  - All subsystems CLOSED, `degraded` []; ai_universe signal rate 0.9989 (10,312 successes / 11 failures); redis 0.9996 (10,319 / 4, last transitions Nov 24 only); database/schema/agents 1.0. No OPEN transition at any escalation — same as run 8.
- **Server 2 cross-check (expected dead):** `Cortex.service` inactive/dead, MainPID 0, `:8009` connection refused (HTTP 000), 1 journal line in 48h. It does not run there.

## 2. Journal — 48h window, first-hand

`journalctl -u Cortex.service --since '2026-11-26 15:26:22' --until '2026-11-28 15:26:22' --no-pager -o short-iso` (Server 1, IST):

- **Total lines 6,622.** First surviving line 2026-11-26T16:59:30+0530; last 2026-11-28T15:26:11+0530. Retained span 46.44h — the window head (~1.55h) aged out; coverage is stated, not invented.
- **Restarts 0.** No `Stopped / Started / Stopping` boundary in the window.
- Keyword counts: `escalat` 0, `deliver` 0, `did not restore health` 0, `cycle` 0, `ERROR` 0, `WARN` 7 — the journal holds no escalation lines (runs 2/3/8 agree), so the endpoint is authoritative for messages; journal 0-counts must NOT be read as "no escalation happened".
- `/ready` probes (fires proxy): **5,168** over the retained 46.44h = 111.3/h. Inbound `GET /health` 1,319.
- `Telegram` 3: three `POST …/sendMessage HTTP/1.1 200 OK` lines — Nov 27 16:15:15 IST, Nov 28 01:26:19 IST, Nov 28 06:37:46 IST. Only the first and third are escalation deliveries (they match the endpoint events at 10:45:11Z Nov 27 and 01:07:45Z Nov 28 to the second). The middle one (01:26:19 IST) has **no matching escalation event** and sits inside CTX-009 dispatch/budget activity (01:24–01:27 IST: task `ctx009-dispatch-1` created, budgets API calls, a 429, a reset); the same process has another Telegram sender (`agent_budgets.py` also posts to `api.telegram.org/sendMessage`). It is a non-escalation Telegram message. **Method caution for the next run: journal Telegram counts ≠ escalation deliveries — the endpoint counters are the authority.**
- WARN lines (7): 3× "self-healing: ensuring the AI Universe client runs in deterministic fallback" (Nov 26 19:42, Nov 27 06:30, Nov 27 15:06 IST) and 4× "FRIDAY authentication attempt with invalid API key rejected (client=127.0.0.1 path=/v1/friday/self_healing)" (Nov 27 06:06 and 15:40 IST, three in the same second) — someone else's probes with a wrong key; they predate this run and are not this run's traffic.

## 3. Computation

- **Window fires:** counted 5,168 over the retained 46.44h = 111.3/h. Aged-out head 1.55h × 111.3/h ≈ 173 (est., labelled). Total ≈ **5,341**. Cross-check from cumulative cycles: 10,323 / 91.87h = 112.4/h → 48h ≈ 5,394. Methods within 1.0%; filed as **~5,370** (between the two, as run 8 filed ~5,390 between 5,386 and 5,411).
- **Window attempts / delivered / suppressed: 8 / 2 / 6.** Three confirmations: (a) endpoint cumulative attempts/delivered/suppressed are 9/3/6, up from 2/2/0 at run 8 — the deltas (+7 attempts, +1 delivered, +6 suppressed) plus the one pre-snapshot in-window event (Nov 27 10:45Z) give 8/2/6 in-window; (b) the endpoint `escalations` list holds exactly those 8 events in-window (plus the pre-window redis one); (c) the journal records the two delivered Telegram POSTs at the matching seconds (16:15:15 IST Nov 27; 06:37:46 IST Nov 28), and the 6 suppressed events have no POST — exactly the dedupe behaviour. The aged-out 1.55h head (Nov 26 15:26–16:59 IST) sits between quiet periods and the cumulative counter proves only 9 escalations exist in the service's lifetime — none can hide in the head.
- **The burst, dissected:** 7 ai_universe fires Nov 28 01:07–06:55Z. Each reached the notifier because each is a distinct failure streak: the streak layer (`_escalated_streaks` in `resilience.py`) clears when a probe observes the subsystem healthy again, and ai_universe flaps (failures 4 → 11 since run 8; deterministic-fallback warnings). The notifier dedupe then suppressed 6 of 7 (same subsystem+reason within 6h of the 01:07 delivery). Net effect of the burst: 1 Telegram message. The streak layer and the dedupe layer are both doing their jobs; the burst is a subsystem-flap observation, not a fix failure.
- ai_universe failures rose 4 → 11 since run 8; no OPEN transition, no journal ERROR — the subsystem recovered on the next tick each time.

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
| **9 (Muse TP2)** | **48h requested / 46.44h counted** | **~5,370** | **8** | **2** | **6** |

- Runs 6–9 agree on the supervisor: ~5,400 fires per 48h, zero restarts, same PID since Nov 24. Run 9 breaks the quiet streak: the first burst (7 fires) and the first dedupe suppressions (6) in the series. The pre-#1054 failure mode (247 identical messages in 48h) would have delivered all 7; the post-#1054 layers delivered 1.
- Retention slipped slightly (47.80h → 46.44h counted) as the journal keeps the full window head nearly covered; the run-5 mitigation A (snapshot cadence) remains the right standing advice for any future full-48h filing.

## 5. Notes for the next run

1. **Live Cortex is on Oracle Server 1, not Server 2** (re-confirmed; Server 2 dead, endpoint refused, 1 journal line).
2. **Auth header is `X-Friday-Api-Key`** — Bearer does not work (see §1). Probe with that header; the token lives in the service `.env` files on Server 1. Read it inside the probe shell only; never print, copy, or commit it.
3. **Journal retention on Server 1 is ~46.4h for this unit** (oldest Nov 26 16:59:30 at probe ~15:26 Nov 28). Probe inside retention; the aged-out head is estimated from measured cadence and labelled (est.).
4. **Journal Telegram counts ≠ escalation deliveries.** The Cortex process has more than one Telegram sender; match POSTs to endpoint events by timestamp and use the endpoint counters as the authority (see §2).
5. **Watch ai_universe:** failures 4 → 11 across the run-8→run-9 interval, 7 fires in one 5.8h burst. If the next run shows another burst or an OPEN transition, that is a trend, not a one-off.
6. No restart is needed, and none was performed.

## 6. What this task did NOT do

- No server move, restart, config change, or deploy. No key material copied, printed, or committed: the FRIDAY service token was read inside the Server 1 probe shell only and used as a request header; the bridge masks tokens in returned output.
- No board hunk in this work PR (board flips are coordinator-only).

## States

- Implemented: YES (ratio evidence filed, this document).
- Tested: YES (live leg first-hand: endpoint snapshot + journal aggregates + code-level dedupe/streak semantics verified in `resilience.py`).
- Merged: NO (work PR opened this run; merge rides the coordinator).
- Deployed: N/A (evidence document; no live change).
- Production-verified: NO (live proof is the evidence itself; paired verification owed).

— Muse TP2, 2026-11-28 ~15:55 IST (hourly self-check 15:18)
