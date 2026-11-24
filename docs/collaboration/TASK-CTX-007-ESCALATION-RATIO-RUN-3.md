# TASK-CTX-007 — Cortex: escalation ratio, run 3 — fires vs messages over the last 48h of live logs

Task: file the fires-vs-messages ratio over the last 48h of live logs as
evidence (board acceptance, TASK-CTX-007).

- Assignment: coordinator queue, issue #1483 — claimed under the blocked-head
  rule (TASK-FUT-028 head still blocked on FUT-027, run 2, Muse 5).
- Claim: issue #1483 comment 7121141082 (2026-11-24 ~08:59 IST). Branch
  `muse12/task-ctx-007-escalation-ratio-run-3` from main `d9f514cb`. Claim
  board PR #1623 MERGED 2026-11-24 ~11:02 IST (merge `6105828b`, CI 9/9).
- Method: `docs/collaboration/TASK-CTX-004-ESCALATION-RATIO-LIVE-CHECK.md`
  (run 1, Muse 13, PR #1437) and
  `docs/collaboration/TASK-CTX-006-ESCALATION-RATIO-RUN-2.md` (run 2, Muse 7,
  PR #1559). Fires = supervisor cycles (`SelfHealingLoop.cycles`, 30 s tick);
  messages = Telegram deliveries (`EscalationNotifier` attempts/delivered in
  `SelfHealingLoop.status()` → `escalation_channel`). The standing
  `ratio_check` lives in `Cortex/packages/core/src/cortex_core/resilience.py`
  and is exposed in `GET /v1/friday/self_healing` (Server 2, Cortex :8009).

## 0. Window — requested 48h, actual coverage 32h 17m 54s (stated plainly)

- Requested window: 48h ending at the endpoint snapshot of this run:
  **2026-11-22 11:04:28 IST → 2026-11-24 11:04:28 IST**
  (snapshot `observed_at` 2026-11-24T05:34:28Z).
- **Actual journal coverage: 2026-11-23 02:46:34 IST → 2026-11-24 11:04:28
  IST (32.30h). The first 15h 42m 06s of the requested 48h window
  (2026-11-22 11:04:28 → 2026-11-23 02:46:34) has no surviving
  `Cortex.service` journal lines — the journal retains back to 02:46:34
  only. No coverage is invented for that head; every figure below is
  computed over the covered span and labelled as such.**
- Journal lines in the covered span: **4,389**
  (`journalctl -u Cortex.service`, Server 2, first-hand; see §5 for the exact
  commands). The bulk are uvicorn `/health` access lines from the fleet
  monitor (10.0.0.121) and loopback.

## 1. Fires — supervisor cycles, per active period

The supervisor logs no per-cycle line (0 lines matching `cycle` in the
covered span), so fires are counted as follows: the endpoint's `cycles`
counter where a live snapshot exists, otherwise ticks derived from the
active-period duration at the 30 s tick (floor) — every derived figure is
labelled `(est.)`. The run-1 anchor validates the tick math: period PID
599993 ran 05:25:17 → ~06:41 IST on 2026-11-23 (~76 min ≈ 152 ticks) against
an endpoint-observed 148 cycles (CTX-004 §5) — 97.4% agreement, the gap
being startup lag. The current period's own cadence is 92.0% (2,547
observed vs 2,768 ticks), so tick-derived figures are good to ~±10%.

| PID | active period (IST) | duration | cycles |
|-----|---------------------|----------|--------|
| 584499 | 2026-11-23 02:46:34* → 03:57:28 | 1h 10m 54s | 141 (est.) |
| 598506 | 2026-11-23 03:57:30 → 04:22:13 | 24m 43s | 49 (est.) |
| 599008 | 2026-11-23 04:22:15 → 04:49:42 | 27m 27s | 54 (est.) |
| 599615 | 2026-11-23 04:49:42 → 05:25:15 | 35m 33s | 71 (est.) |
| 599993 | 2026-11-23 05:25:17 → 09:04:38 | 3h 39m 21s | 438 (est.); anchor 148 @ ~06:41 (observed, CTX-004) |
| 602703 | 2026-11-23 09:04:39 → 11:41:54 | 2h 37m 15s | 314 (est.) |
| 605505 | 2026-11-23 11:41:55 → 12:00:35 | 18m 40s | 37 (est.) |
| 605907 | 2026-11-23 12:00:35 → 2026-11-24 11:04:28 | 23h 03m 53s | **2,547 exact** (endpoint) |

\* PID 584499 started 2026-11-22 12:16:36 IST (API-005 restart); only the
covered tail from 02:46:34 is counted. All seven restart boundaries are
`systemd` Stopped/Started lines from the journal, re-verified first-hand
this run (timestamps match run 2's table exactly; PIDs per run 2's
first-hand table, with 584499 and 605907 confirmed from this run's own
first/last journal lines). No restart was performed by this run; all seven
restarts predate this task (all clean stops/starts). No restart after
12:00:35 IST 2026-11-23 — PID 605907 runs through to the window end.

**Total fires (covered span): 3,651** (2,547 exact + 1,104 est.).

## 2. Messages — Telegram deliveries (attempts vs delivered)

Endpoint snapshot, current period only (`GET /v1/friday/self_healing`,
11:04:28 IST 2026-11-24, first-hand, fleet key presented; snapshot JSON kept
in the worker workspace, not committed):

- `escalation_channel`: channel `telegram:api.telegram.org`,
  `channel_configured: true`, **attempts 147, delivered 1,
  suppressed_duplicates 443**, `consecutive_failed_deliveries: 0`,
  `channel_broken: false`. `last_attempt` 2026-11-24T05:17:39Z
  (10:47:39 IST): ai_universe, "3 repair attempts did not restore
  health", delivered false, "duplicate suppressed within dedupe window".
- Supervisor escalation records (capped at the last 20): **20**, all
  `ai_universe`, all "3 repair attempts did not restore health",
  10:01:52 → 10:47:39 IST 2026-11-24.
- Earlier covered periods: attempts 0, delivered 0 — the journal holds
  **0 lines matching `escalat`, 0 lines matching `deliver`, and 0 lines
  matching `did not restore health`** in the whole covered span
  (first-hand this run), and run 1's endpoint snapshot at ~06:41 IST
  2026-11-23 (period 599993) showed attempts 0, delivered 0.
- **Covered-span totals: attempts 147, delivered 1.**
- **Delivery gap (attempts − delivered) = 146 — but read §4 before
  calling it a broken channel: the gap is dedupe suppression by design,
  not failed sends.**

Reading the counters correctly (from
`Cortex/packages/core/src/cortex_core/resilience.py`, main — same reading as
run 2 §2):

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
  snapshot. `suppressed_duplicates` (443) is cumulative for the period
  and is never trimmed. Streak-level suppressions are not exposed as a
  counter in `status()` at all.

## 3. Per-subsystem signal rates (current period, n = 2,547 cycles)

From the endpoint `ratio_check.signal_rate` at the snapshot:

| subsystem | signal rate | samples | successes | failures | state at snapshot |
|-----------|-------------|---------|-----------|----------|-------------------|
| database | 1.0 | 2,547 | 2,547 | 0 | CLOSED |
| schema | 1.0 | 2,547 | 2,547 | 0 | CLOSED |
| redis | 1.0 | 2,547 | 2,547 | 0 | CLOSED |
| ai_universe | **0.8229** | 2,547 | 2,096 | **451** | CLOSED |
| agents | 1.0 | 2,547 | 2,547 | 0 | CLOSED |
| ingestion | null (0 samples) | 0 | 0 | 0 | no probe |
| tools | null (0 samples) | 0 | 0 | 0 | no probe |

Snapshot also: `errors: 0`, `running: true`, `self_healing_enabled: true`,
`last_unhealthy: []`, `last_unconfigured: []`, `unconfigured_streaks: {}`,
`last_alert: null`. ai_universe transitions in the period: OPEN → CLOSED
04:01:26Z, CLOSED → OPEN 04:34:37Z ("3 consecutive failures"), OPEN →
CLOSED 04:35:47Z ("probe succeeded").

## 4. Ratio — the verdict

- **Fires 3,651 : delivered 1** over the covered 32.30h span.
- Attempts 147 / 3,651 fires = **4.0%** of fires produce a notifier
  attempt; **1 delivery per 3,651 fires** (0.027%).
- The 146-attempt delivery gap is dedupe suppression by design (§2), not
  failed sends: `consecutive_failed_deliveries: 0`, `channel_broken:
  false`, and the single delivery landed at the start of the current
  ai_universe failure streak; the 443 suppressed duplicates are repeats
  inside the 6h dedupe window.
- The live signal behind the ratio: ai_universe is the only failing
  subsystem (signal rate 0.8229, 451 failures in 2,547 cycles); every
  other probed subsystem is at 1.0. All 20 surviving escalation records
  are ai_universe "3 repair attempts did not restore health".
- Comparison with run 2 (31.42h covered, 3,622 fires, 73 attempts,
  1 delivered): the current period's attempt count grew 73 → 147 as the
  ai_universe failure streak continued into the morning of 2026-11-24;
  the delivery count is unchanged at 1 — the dedupe layers are holding
  exactly as designed.

## 5. Journal-leg provenance — clearance, commands, outputs

The journal leg ran under coordinator watch 7123397267 (hub #1483,
~11:25 IST 2026-11-24): **"M12 CTX-007 journal leg — GRANTED (a):
read-only `journalctl -u Cortex.service` on S2 only, for run 3, same
API-005 precedent as the endpoint probe. No other commands, no writes."**
The endpoint probe ran earlier under watch 7122541986 (~10:50 IST).

- Transport: FRIDAY Bridge MCP (`https://friday-universe.duckdns.org/bridge/mcp`),
  one-off client `/tmp/bridge_run_shell.py` (run_shell only; the shared
  `bridge.py` helper and its allow-list are unchanged). Bridge transport
  was flaky at the start of the run (initialize timed out 2×, matching
  other workers' reports) and recovered; the probe ran 11:57–12:05 IST.
- Exact commands (read-only; aggregation via pipes only; no server-side
  files written; no key material involved — journalctl needs no key):
  - `journalctl -u Cortex.service --since '2026-11-22 11:04:28' --until '2026-11-24 11:04:28' --no-pager -o short-iso | wc -l` → **4389**
  - same query `| head -3` → first line `2026-11-23T02:46:34+0530 ... python[584499]`
  - same query `| tail -3` → last line `2026-11-24T11:04:20+0530 ... python[605907]`
  - same query `| grep -e 'Stopped FRIDAY Universe' -e 'Started FRIDAY Universe' -e 'Stopping FRIDAY Universe'` → 21 lines, the 7 boundaries in §1
  - same query `| grep -ci escalat` → **0**; `| grep -ci deliver` → **0**; `| grep -ci 'did not restore health'` → **0**; `| grep -ci cycle` → **0**
  - (Correction note: the first boundary attempt used the pattern
    `Stopped Cortex.service`, which matches nothing — the systemd lines
    carry the unit description, "FRIDAY Universe - Autonomous Operations
    Engine", not the unit name. Re-run with the description pattern
    returned all 7 boundaries.)
- Endpoint probe (under watch 7122541986, 11:02–11:04 IST):
  `KEY=$(grep -m1 'FRIDAY_API_KEY=' /opt/friday_universe/Cortex/.env | ...); curl -s -m 25 -H "X-Friday-Api-Key: $KEY" http://127.0.0.1:8009/v1/friday/self_healing`
  — key extracted into a shell variable only, never printed, never
  copied, never recorded. Snapshot saved in the worker workspace
  (`~/workspace/agents/muse12/task-ctx-007/SNAPSHOT-2026-11-24.json`).

## States

- Implemented: YES (evidence filed in this doc).
- Tested: YES (figures cross-checked: endpoint cycles vs tick math 92.0%;
  all 7 boundaries re-verified first-hand; counts re-run in the covered span).
- Merged: NO (work PR awaits independent review + Muse audit).
- Deployed: N/A (evidence document; no live change, no restart).
- Production-verified: NO (live proof is the evidence itself; no deployment
  to verify).
