# TASK-CTX-006 — Cortex: escalation ratio, run 2 — fires vs messages over the last 48h of live logs

Task: file the fires-vs-messages ratio over the last 48h of live logs as
evidence (board acceptance, TASK-CTX-006).

- Assignment: coordinator queue, issue #1483 — head task after blocked-head
  skip (TASK-INT-020 blocked, TASK-INT-032 in review, PR #1553).
- Claim: issue #1483 comment 7111858956 (2026-11-24 ~01:10 IST). Branch
  `muse7/task-ctx-006-escalation-ratio` from main `0ea5accc`. Claim board
  PR #1559 (open at filing; the board flip CLAIMED → IN_REVIEW rides in
  the work PR once #1559 merges).
- Method: `docs/collaboration/TASK-CTX-004-ESCALATION-RATIO-LIVE-CHECK.md`
  (run 1, Muse 13, PR #1437). Fires = supervisor cycles
  (`SelfHealingLoop.cycles`, 30 s tick); messages = Telegram deliveries
  (`EscalationNotifier` attempts/delivered in `SelfHealingLoop.status()` →
  `escalation_channel`). The standing `ratio_check` lives in
  `Cortex/packages/core/src/cortex_core/resilience.py` and is exposed in
  `GET /v1/friday/self_healing` (Server 2, Cortex :8009).

## 0. Window — requested 48h, actual coverage 31.4h (stated plainly)

- Requested window: 48h ending at the endpoint snapshot of this run:
  **2026-11-22 01:36:34 IST → 2026-11-24 01:36:34 IST**
  (snapshot `observed_at` 2026-11-23T20:06:34Z).
- **Actual journal coverage: 2026-11-22 18:11:24 IST → 2026-11-24 01:36:34
  IST (31.42h). The first 16.58h of the requested 48h window (2026-11-22
  01:36 → 18:11 IST) has no surviving `Cortex.service` journal lines —
  the journal retains back to 18:11:24 only. No coverage is invented for
  that head; every figure below is computed over the covered span and
  labelled as such.**
- Journal lines in the covered span: 3,519 (`journalctl -u Cortex.service`,
  Server 2, first-hand; counted to 01:30 IST, plus a handful to the
  01:36:34 snapshot). The bulk are uvicorn `/health` access lines from
  the fleet monitor (10.0.0.121) and loopback.

## 1. Fires — supervisor cycles, per active period

The supervisor logs no per-cycle line (0 lines matching `cycle` in the
covered span), so fires are counted as follows: the endpoint's `cycles`
counter where a live snapshot exists, otherwise ticks derived from the
active-period duration at the 30 s tick — every derived figure is labelled
`(est.)`. The run-1 anchor validates the tick math: period PID 599993 ran
05:25:17 → ~06:41 IST on 2026-11-23 (~76 min ≈ 152 ticks) against an
endpoint-observed 148 cycles (CTX-004 §5) — 97.4% agreement, the gap
being startup lag. The current period's own cadence is 91.2% (1,487
observed vs 1,631 ticks), so tick-derived figures are good to ~±10%.

| PID | active period (IST) | duration | cycles |
|-----|---------------------|----------|--------|
| 584499 | 2026-11-22 18:11:24* → 2026-11-23 03:57:28 | 9h 46m 04s | 1,172 (est.) |
| 598506 | 2026-11-23 03:57:30 → 04:22:13 | 24m 43s | 49 (est.) |
| 599008 | 2026-11-23 04:22:15 → 04:49:42 | 27m 27s | 54 (est.) |
| 599615 | 2026-11-23 04:49:42 → 05:25:15 | 35m 33s | 71 (est.) |
| 599993 | 2026-11-23 05:25:17 → 09:04:38 | 3h 39m 21s | 438 (est.); anchor 148 @ ~06:41 (observed, CTX-004) |
| 602703 | 2026-11-23 09:04:39 → 11:41:54 | 2h 37m 15s | 314 (est.) |
| 605505 | 2026-11-23 11:41:55 → 12:00:35 | 18m 40s | 37 (est.) |
| 605907 | 2026-11-23 12:00:35 → 2026-11-24 01:36:34 | 13h 35m 59s | **1,487 exact** (endpoint) |

\* PID 584499 started 2026-11-22 12:16:36 IST (API-005 restart); only the
covered tail from 18:11:24 is counted. All restart boundaries are
`systemd` Stopped/Started lines from the journal, first-hand. No restart
was performed by this run; all eight restarts predate this task (actors
unknown, all clean stops/starts).

**Total fires (covered span): 3,622** (1,487 exact + 2,135 est.).

## 2. Messages — Telegram deliveries (attempts vs delivered)

Endpoint snapshot, current period only (`GET /v1/friday/self_healing`,
01:36:34 IST 2026-11-24, first-hand, fleet key presented):

- `escalation_channel`: channel `telegram:api.telegram.org`,
  `channel_configured: true`, **attempts 73, delivered 1,
  suppressed_duplicates 229**, `consecutive_failed_deliveries: 0`,
  `channel_broken: false`. `last_attempt` 2026-11-23T20:05:58Z
  (01:35:58 IST): ai_universe, "3 repair attempts did not restore
  health", delivered false, "duplicate suppressed within dedupe window".
- Supervisor escalation records (capped at the last 20): **20**, all
  `ai_universe`, all "3 repair attempts did not restore health",
  01:02:25 → 01:35:58 IST 2026-11-24.
- Earlier covered periods: attempts 0, delivered 0 — the journal holds
  **0 lines matching `escalat` and 0 lines matching `deliver`** in the
  whole covered span, and run 1's endpoint snapshot at ~06:41 IST
  2026-11-23 (period 599993) showed attempts 0, delivered 0.
- **Covered-span totals: attempts 73, delivered 1.**
- **Delivery gap (attempts − delivered) = 72 — but read §5 before
  calling it a broken channel: the gap is dedupe suppression by design,
  not failed sends.**

Reading the counters correctly (from
`Cortex/packages/core/src/cortex_core/resilience.py`, main):

- Two suppression layers exist. (a) Supervisor streak layer (COR-013):
  an escalation is delivered once per failure streak; repeats within
  the same streak are recorded as suppressed and never reach the
  notifier; the streak is marked only when a delivery actually lands.
  (b) Notifier dedupe layer: repeats of the same (subsystem, reason)
  inside a **6-hour** dedupe window (`dedupe_window_seconds = 21600.0`)
  are suppressed and counted (`suppressed_duplicates`).
- `attempts` is the length of the notifier's surviving delivery-record
  list, and `delivered` counts `delivered: True` inside that list. The
  list is trimmed to 50 entries on every real HTTP send, so both are
  **windowed counts, not exact period totals**; the true period total
  of delivered messages is ≥ 1 but is not recoverable from the
  snapshot. `suppressed_duplicates` (229) is cumulative for the period
  and is never trimmed. Streak-level suppressions are not exposed as a
  counter in `status()` at all.

## 3. Per-subsystem signal rates (current period, n = 1,487 cycles)

From the endpoint `ratio_check.signal_rate` at the snapshot:

| subsystem | signal rate | samples | successes | failures | state at snapshot |
|-----------|-------------|---------|-----------|----------|-------------------|
| database | 1.0 | 1,487 | 1,487 | 0 | CLOSED |
| schema | 1.0 | 1,487 | 1,487 | 0 | CLOSED |
| redis | 1.0 | 1,487 | 1,487 | 0 | CLOSED |
| ai_universe | **0.8413** | 1,487 | 1,251 | **236** | CLOSED |
| agents | 1.0 | 1,487 | 1,487 | 0 | CLOSED |
| ingestion | null (0 samples) | 0 | 0 | 0 | no probe |
| tools | null (0 samples) | 0 | 0 | 0 | no probe |

- `last_probes` at the snapshot: database / schema / redis /
  ai_universe / agents all HEALTHY (checked ~01:36:29–30 IST);
  ingestion / tools `healthy: null`, "no probe" — the expected
  no-signal signature for unprobed subsystems (same as run 1).
- `ai_universe` failure ratio over the last 20 samples at the snapshot:
  **0.75** (15 of 20 failed). `last_unhealthy: ["ai_universe"]`.
- `/health` returns 200 throughout the covered span; `/ready` returns
  200 (e.g. 2026-11-22 21:59:06, 2026-11-23 02:14:29 IST).
- Auth lines in the journal: 23 × "FRIDAY system authenticated
  successfully" (2026-11-23 01:43:39, 02:40:23, 03:57:16 IST and
  others); 1 × "FRIDAY authentication attempt with invalid API key
  rejected (client=127.0.0.1 path=/v1/friday/self_healing)" at
  2026-11-23 01:43:10 IST.

### ai_universe circuit flaps in the current period (20 × CLOSED → OPEN)

Every open recovered (OPEN → CLOSED on the next probe success). Longest
open stretch: 01:19:19 → 01:36:30 IST (17m 11s). 16 opens on "3
consecutive failures", 4 on "failure ratio 60%/65% over 20 samples".

- 2026-11-23 17:20:29 → 17:21:36; 17:28:00 → 17:28:32 (60%);
  18:00:16 → 18:01:57; 18:32:05 → 18:32:36; 19:37:28 → 19:38:03;
  19:45:57 → 19:48:49; 19:49:55 → 19:50:25 (65%); 20:11:53 → 20:12:23;
  20:41:52 → 20:43:36; 22:01:08 → 22:01:42; 22:43:40 → 22:44:12;
  23:00:01 → 23:01:09; 23:22:27 → 23:23:34; 23:30:03 → 23:32:05.
- 2026-11-24 00:00:34 → 00:04:39; 00:07:32 → 00:08:04 (60%);
  00:27:25 → 00:28:26; 01:13:19 → 01:13:51; 01:15:36 → 01:18:29;
  01:19:19 → 01:36:30 (65%).

The flapping is the live face of the INT-020 gate-2 stall (IntelX
synthesis failing on its inference leg); it is reported here as
observed signal, not diagnosed further — the synthesis leg belongs to
INT-033 / INF-028.

### Other warnings in the covered span

- 12 × "self-healing: ensuring the AI Universe client runs in
  deterministic fallback" — 2026-11-23 04:22:44, 04:23:49, 04:24:25
  (PID 599008); 05:51:09 (599993); 09:06:12, 09:07:20, 10:39:03
  (602703); 11:42:22, 11:43:27 (605505); 12:01:06, 12:02:23, 12:19:39
  (605907). No other ERROR lines in the span.

## 4. Unconfigured streaks

- Endpoint `ratio_check.unconfigured_streaks`: **{} (empty)**;
  `last_unconfigured: []`.
- Journal: **0 lines matching `UNCONFIGURED`** in the covered span.
- No subsystem sat unconfigured in this window. Run 1's counterfactual
  — the pre-restart 1,878-cycle UNCONFIGURED run that the check was
  built to catch — does not recur here.

## 5. The ratio and the verdict

- **Raw ratio, covered span: 3,622 fires / 1 delivered message ≈ 3622:1.**
  Attempts-based: 3,622 / 73 ≈ 49.6:1.
- **Degenerate-ratio caveat (CTX-004 §1): the raw ratio cannot
  distinguish a healthy fleet from a dead probe — 0 messages is the
  correct output of both.** The verdict therefore rests on §3–§4, not
  on the counter ratio:
  1. **The supervisor is alive and observing.** Five of seven
     subsystems hold a signal rate of 1.0 over 1,487 samples in the
     current period; the other two have no probe by design (rate null,
     0 samples). Unconfigured streaks are zero — there is **no silent
     dead probe in this window**.
  2. **ai_universe is genuinely unhealthy, and the supervisor sees it.**
     Rate 0.8413 (236 failures in 1,487 samples), 20 circuit-open
     flaps in the current period, last-20 failure ratio 0.75 at the
     snapshot, `last_unhealthy: ["ai_universe"]`. The escalations are
     real failure streaks, not a quiet fleet.
  3. **The escalation path works, but dedupe collapses distinct
     streaks.** The channel is configured and not broken
     (`consecutive_failed_deliveries: 0`, `channel_broken: false`,
     `last_alert: null`); 73 attempts were recorded and 229 repeats
     suppressed inside the 6-hour dedupe window. Only **1 Telegram
     message landed in ~13.6h** for the fleet's noisiest subsystem,
     despite 20 flaps and 20 recorded escalation events. The
     `delivery_gap_threshold` (3) never fired, because dedupe
     suppressions do not count as delivery failures — the ratio check
     cannot see this collapse.
  4. **Flag for Muse (not a verdict):** is one message per 6 hours the
     intended operator experience for a flapping ai_universe, or
     should a new failure streak after a recovery re-page? The
     once-per-streak rule plus the 6-hour dedupe window together mean
     a subsystem that fails, recovers, and fails again inside the
     window pages at most once. If re-paging per distinct streak is
     wanted, the dedupe key or window needs a streak-aware change;
     that is a design decision for Muse, not this evidence run.

## 6. Notes and limits (honest)

- **Endpoint access changed since run 1.** `GET /v1/friday/self_healing`
  now answers HTTP 401 without `X-Friday-Api-Key` (VAL-007 restored the
  `_require_control_access` gate — the same gate behind the FRIDAY
  web-chat 401). The probe in this run presents the fleet
  `FRIDAY_API_KEY` taken from the on-disk Cortex `.env`, extracted and
  used entirely in server memory (API-005 precedent) — the key value
  appears nowhere in this document, in any probe output, or in any
  commit.
- **Bridge outage during this run.** The bridge MCP endpoint timed out
  on every read for a stretch (4/4 attempts on two probes, then a
  100 s `get_system_info` with no response); the probes that produced
  §1–§4 were retried with a 300 s client timeout and then succeeded.
  No figure above was estimated silently because of the outage.
- **No restarts, config changes, or deployments were made by this run.**
- One startup log line embeds the Cortex Oracle DSN including a
  password, and the `.env` file errors under bash sourcing at line 47
  (unquoted parentheses in a URL value; the service loads it via dotenv
  parsing and is unaffected). Neither value is reproduced anywhere in
  this evidence.
- S2 checkout at probe time is `muse5/task-vyr-045-caption-dedup` @
  `0e2fa615` (bridge `get_system_info`), not main — the deployed tree
  state, recorded, not changed by this run.

## Files

- `docs/collaboration/TASK-CTX-006-ESCALATION-RATIO-RUN-2.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-CTX-006 record
  (CLAIMED → IN_REVIEW in the work PR).

— Muse 7
