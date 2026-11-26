# TASK-CTX-011 — Cortex escalation-ratio run-5 readiness (restart-clearance request + fresh-48h window plan + journal-retention mitigation)

Repo-side prep ONLY. No live leg was run by this task: nothing was
restarted, no server command was run, no endpoint was probed. The live
leg is gated on owner clearance for the Cortex restart (see §5).

- Assignment: coordinator watch, issue #1483 — WATCH169 (hub #1483 comment
  7196189703, 2026-11-26 ~20:40–21:10 IST) returned CTX-011 to the pool
  after TP11 released it following a ~3h+ stall (zero commits, checkpoint 1
  absent, branch still @ claim base `087e05d6`).
- Claim: issue #1483 comment 7196468585 (2026-11-26 21:04:59 IST).
  Branch `musetp9/task-ctx-011` from main `49cfd862`, rebased onto main
  `371738ec` (merge of PR #1993) for this PR.
- Method: runs 1–4 —
  `docs/collaboration/TASK-CTX-004-ESCALATION-RATIO-LIVE-CHECK.md` (run 1,
  Muse 13, PR #1437),
  `docs/collaboration/TASK-CTX-006-ESCALATION-RATIO-RUN-2.md` (run 2,
  Muse 7, PR #1559),
  `docs/collaboration/TASK-CTX-007-ESCALATION-RATIO-RUN-3.md` (run 3,
  Muse 12) and
  `docs/collaboration/TASK-CTX-010-ESCALATION-RATIO-RUN-4.md` (run 4,
  Muse 10, PR #1926). Fires = supervisor cycles
  (`SelfHealingLoop.cycles`, 30 s tick); messages = Telegram deliveries
  (`EscalationNotifier` attempts/delivered in `SelfHealingLoop.status()`
  → `escalation_channel`). The standing `ratio_check` lives in
  `Cortex/packages/core/src/cortex_core/resilience.py` and is exposed in
  `GET /v1/friday/self_healing` (Server 2, Cortex :8009). All four
  references verified present on main `371738ec`.

## 0. What is verified here, and what is NOT

- **Verified from the repo/board first-hand this run:** the CTX-011 board
  record (status AVAILABLE, owner muse_tp11, acceptance as quoted in
  §1–§4), the run-4 NO-DATA findings (§1), the run-2/run-3 ratios, and
  the WATCH169 rulings (pool return; approval 7113152293 still not found;
  no live leg cleared). The method files named above exist on main
  `371738ec`.
- **NOT re-verified by this run:** the current live state of
  `Cortex.service`, the :8009 endpoint, the journal, and the key file.
  No live leg was run, so the last verified live state remains run 4's
  (§1, 2026-11-26 ~06:10–06:25 IST). Nothing in this doc claims a
  fresher live state. The run-5 worker MUST re-probe service, endpoint,
  journal, and key file after the restart, under its own clearance,
  before filing any ratio.

## 1. Starting state — run 4 filed NO DATA (Muse 10, 2026-11-26 ~06:10–06:25 IST)

- `Cortex.service` on Server 2: **Active: inactive (dead)**
  (`systemctl show`: `ActiveState=inactive`, `Result=success`,
  `NRestarts=0`).
- Endpoint probe: `curl http://127.0.0.1:8009/v1/friday/self_healing` →
  **HTTP:000, CURL_EXIT:7 (connection refused)** — no listener on :8009.
  No snapshot, no `cycles` counter, no `escalation_channel` counters.
- Key file: `/opt/friday_universe/Cortex/.env` does NOT exist on Server 2
  (`Cortex/` listing shows `.env.example` only). A re-run after restart
  needs the key location re-established before the endpoint leg can run.
- Journal: **zero** `Cortex.service` entries in the requested 48h window,
  zero since 2026-11-20, zero at all on Server 2. Unfiltered journal on
  the host retains ~34h across all units (oldest surviving entry
  2026-11-24T20:17:57+0530; `journalctl --disk-usage` 212.0M;
  `--verify` PASS — the journal is healthy, the Cortex entries are
  absent, not corrupted). No `*.log` fallback under
  `/opt/friday_universe/Cortex` (maxdepth 2); no cortex/friday files in
  `/var/log`.
- Ratio run 4: **UNDEFINED, not 0:0.** Filing `0:0` would falsely claim a
  quiet supervisor when the truth is an absent supervisor.
- Last observed alive: run-3 snapshot 2026-11-24 11:04:28 IST (PID 605907
  running through the window end).

Prior runs for comparison (both filed a real ratio over a stated covered
span, never a full 48h — see §4):

| run | covered span | fires | attempts | delivered |
|-----|--------------|-------|----------|-----------|
| 2 (Muse 7) | 31.42h | 3,622 | 73 | 1 |
| 3 (Muse 12) | 32.30h | 3,651 (2,547 exact + 1,104 est.) | 147 | 1 |
| 4 (Muse 10) | 0h | 0 countable | unobservable | unobservable |

Run 3 reading note (carried forward, not re-derived here): the
attempts−delivered gap is dedupe suppression by design — supervisor
streak layer (COR-013, one delivery per failure streak) plus notifier
dedupe layer (6-hour window, `dedupe_window_seconds = 21600.0`); the
delivery-record list is trimmed to 50 entries, so `attempts`/`delivered`
are windowed counts, not exact period totals. All 20 surviving run-3
escalation records were ai_universe "3 repair attempts did not restore
health" (signal rate 0.8229, 451 failures in 2,547 cycles; every other
probed subsystem at 1.0).

## 2. Restart-clearance request — draft for the hub (Muse → owner)

Filed here as the request text. It is NOT yet granted; the live leg
starts only when clearance lands on hub #1483.

> **TASK-CTX-011 — clearance requested: restart `Cortex.service` on
> Server 2 (Oracle S2, 10.0.0.120) — Muse TP9, 2026-11-26.**
>
> **Why:** run 4 (CTX-010, 2026-11-26 ~06:10 IST) found the supervisor
> dead — service inactive, :8009 connection refused, journal empty,
> ratio UNDEFINED. A run-5 ratio cannot be filed until the supervisor
> has run for a fresh 48h. The restart is the single unblocker (run-4
> blocker G1).
>
> **Asked for:** (a) one `systemctl restart Cortex.service` on Server 2
> by the cleared worker, at a time Muse names; (b) re-establishing the
> endpoint key location (`/opt/friday_universe/Cortex/.env` is absent on
> Server 2 — run-4 blocker G4), so the run-5 endpoint leg can run.
>
> **Explicitly NOT asked for:** no config change, no journald change, no
> code deploy, no other service touched, no live trading or money
> movement (none is involved in this task). If the restart fails or the
> service does not stay up, the worker reports the failure and stops —
> it does not retry on its own initiative.
>
> **After clearance:** the run-5 worker restarts, confirms the service
> is active and :8009 answers, records T0 (restart completion, IST),
> and runs the fresh-48h window plan in §3 with the snapshot cadence in
> §4. The 2026-11-24 → 2026-11-26 window is unrecoverable (run-4
> blocker G2) and is NOT re-filed.

## 3. Fresh-48h window plan — run 5

- **Preconditions (all must hold before T0):** (1) restart clearance
  granted on hub #1483 and the restart performed by the cleared worker;
  (2) `Cortex.service` confirmed active and
  `GET /v1/friday/self_healing` answering on :8009 (baseline snapshot
  taken at T0, including `cycles` and `escalation_channel` counters);
  (3) the key-file location re-established (§2b). If any precondition
  fails, the worker files the failure as the run-5 finding and stops —
  it does not improvise a window.
- **Window:** T0 → T0+48h, where T0 is restart completion (IST),
  recorded to the second. The window is anchored to runtime, NOT to the
  calendar dates of run 4 — the Nov 24–26 window is gone (§2).
- **Probe steps (same method as runs 2/3, under the run-5 leg's own
  clearance):** endpoint snapshot at T0 and at each cadence point (§4);
  `journalctl -u Cortex.service --since T0 --until <probe time>` with
  `wc -l`, `head -3`, `tail -3`, boundary grep (`Started`/`Stopped
  FRIDAY Universe`), and `grep -ci` for `escalat` / `deliver` /
  `did not restore health` / `cycle`; restart-boundary table (PID,
  active period, duration, cycles — endpoint `cycles` where a snapshot
  exists, otherwise 30 s tick math, labelled `(est.)`, per run 3 §1).
- **Acceptance:** a fires-vs-messages ratio filed over the covered span
  with the coverage stated plainly (requested 48h vs actual covered
  hours, exactly as runs 2/3 did). If the service dies mid-window, the
  ratio is filed over the covered span only, the outage is named, and no
  coverage is invented.
- **Fallback:** if the service will not stay up for 48h, file the ratio
  over the longest continuous covered span with the same method, and
  name the uptime failure as the finding — a partial-span ratio with an
  honest coverage label beats another NO-DATA run.

## 4. Journal-retention mitigation — ~34h retention vs a 48h window

- **Problem (run-4 blocker G3, restated):** the Server 2 journal
  retains ~34h across all units, shorter than the 48h window. Runs 2/3
  already hit this: they covered only ~31–32h of a requested 48h
  because the window head had aged out before the run executed. A
  run-5 worker that waits until T0+48h to read the journal will lose
  the first ~14h the same way.
- **Mitigation A — snapshot cadence (RECOMMENDED, no server change):**
  the run-5 worker captures, at T0+12h, T0+24h, T0+36h, and T0+48h,
  (i) the endpoint snapshot (`GET /v1/friday/self_healing`, full JSON,
  kept in the worker workspace, not committed) and (ii) a journal
  export for the interval since the previous capture
  (`journalctl -u Cortex.service --since <last capture> --until <now>`,
  counted and boundary-checked per §3). Each capture is ≤12h old at
  read time, inside the ~34h retention. The full 48h is then
  reconstructed from the four captures even though no single journal
  read at T0+48h could cover it. Cost: four small probe legs instead
  of one; each needs the same read-only clearance as the run-5 leg.
- **Mitigation B — shorter window (fallback):** file the ratio over
  ~32h (the coverage runs 2/3 actually achieved) and label it as such.
  Honest, but weaker — it concedes the 48h ask. Use only if the
  cadence captures in (A) are missed.
- **Mitigation C — raise retention / ship logs to a file (NOT requested
  here):** journald `SystemMaxUse`/`MaxRetentionSec`, or a persistent
  Cortex file log, would fix the root cause — but either is a server
  change needing its own clearance and is outside this task's repo-side
  scope. Flagged for Muse/owner as a separate decision; not changed,
  not requested, in this PR.
- **Recommendation:** (A) primary, (B) fallback if a capture is missed,
  (C) separate future decision.

## 5. Gated — what this task did NOT do

- **Live leg NOT run.** No restart, no server command, no endpoint
  probe, no journal read by this task. The run-5 re-run is unblocked the
  moment restart clearance lands — and not before.
- **Owner stop order still in force** (~16:42 IST 2026-11-24, per
  WATCH169). No restart was requested by any earlier watch and none is
  performed here.
- **Approval 7113152293 (run_shell grant) still NOT found** in the
  permission record (WATCH169 re-check, same as WATCH168). The 20:41 IST
  relay post asserting the grant is owner-approved is a hub relay, not a
  confirmation in the permission record, and the direction stands:
  workers do NOT add `run_shell` to any bridge client on a hub relay
  alone, and no live leg is cleared until the grant is confirmed through
  the permission/approval record or a verifiable owner confirmation.
  The run-5 probe legs will therefore need their own clearance when the
  restart is cleared — this doc does not grant it.

## States

- Implemented: YES (clearance request + window plan + retention
  mitigation filed in this doc).
- Tested: N/A (repo-side prep; no live leg run, nothing to test live).
- Merged: NO (work PR awaits independent review + Muse audit).
- Deployed: N/A (evidence document; no live change, no restart).
- Production-verified: NO (the live re-run is gated; verification is the
  run-5 ratio itself, filed after clearance).

— Muse TP9
