# TASK-CTX-004 — Cortex: escalation ratio as a standing live check: evidence

Task: turn the escalation ratio into a standing live check — fires-vs-messages
computed per cycle, alert when the ratio breaks.

- Assignment: coordinator per-worker queue, issue #35 comment 7084110569
  (~01:00 IST), queue confirmed 7085971598 (~03:06 IST): CTX-004 → ORCH-012 → CTX-005*.
  Auto-claim on finish of TASK-CTX-003 (MERGED, PR #1416 + follow-up #1426).
- Claim: issue #35 comment 7086907954 (2026-11-23 ~04:10 IST). Branch
  `muse13/task-ctx-004-escalation-ratio-live-check` from main `63765f6b`.
- Work PR: to be opened with the implementation chunk (see §4).

## 0. Live baseline at claim (Server 2 via bridge, first-hand, 2026-11-23 ~04:01 IST)

Post-G4-restart state — the baseline the standing check must report
"signal present" on:

- Cortex.service active since 03:57:30 IST, Main PID **598506** (restarted
  per coordinator direction 7085971598; evidence filed in PR #1434).
- Supervisor: background running, **cycles 7**, errors 0, `last_unconfigured: []`,
  `last_unhealthy: []`; `ai_universe` last probe **HEALTHY** (samples 7,
  successes 7, failures 0); siblings healthy 7/7; escalation attempts 0,
  delivered 0.
- S2 checkout still `muse10/task-frd-037-chat-live-runs` @ `db933cfc`;
  on-disk probe is `/health` (0 `/ready` strings) — the /ready code is on
  main, not deployed; /ready verification stays open under TASK-CTX-005*.

Counterfactual baseline (what the check must have caught): pre-restart,
**1,878 cycles** with `ai_universe` UNCONFIGURED throughout (samples 0,
successes 0, failures 0), `last_unconfigured: ["ai_universe"]`, delivered 0
— the probe contributed no health signal for ~15h and nothing alerted,
because UNCONFIGURED never enters the repair/escalation path by design
(TASK-COR-014).

## 1. The ratio, defined precisely

CTX-002 framed it as "1,612 fires vs 0 messages". In the supervisor's own
terms (`Cortex/packages/core/src/cortex_core/resilience.py`, main):

- **Fires** = supervisor cycles (`SelfHealingLoop.cycles`, 30 s tick).
  Every cycle probes every subsystem (`run_cycle`).
- **Messages** = Telegram deliveries (`EscalationNotifier` attempts/delivered
  in `SelfHealingLoop.status()` → `escalation_channel`).
- The raw ratio fires/messages is **degenerate**: deliveries are once per
  failure streak (TASK-COR-013), and UNCONFIGURED subsystems never escalate
  at all — so 0 messages is the correct output of a healthy fleet AND the
  output of a fleet whose probe observes nothing. A ratio of two counters
  cannot distinguish those states.

The standing check is therefore defined on the **per-cycle run data**, not
on the raw counter ratio:

1. **Signal rate** per subsystem: healthy observations / cycles
   (circuit `samples` / `total_successes` in the registry snapshot).
2. **Unconfigured streak**: consecutive cycles a subsystem appears in
   `run.unconfigured` — the exact CTX-002/003 failure mode.
3. **Delivery gap**: escalations recorded vs delivered over a window
   (notifier `attempts` vs `delivered`) — the alert channel's own health.

## 2. Design (first draft, grounded in the code read this run)

- **Where it lives:** `SelfHealingSupervisor.run_cycle()` /
  `SelfHealingLoop.tick()` in `Cortex/packages/core/src/cortex_core/resilience.py`.
  The supervisor already tracks `_unconfigured_noticed` (a set, logged once
  per streak); the check adds a per-subsystem **streak counter** (consecutive
  runs in `run.unconfigured`) evaluated at the end of each cycle.
- **Alert conditions (thresholds to pin after observing the live baseline):**
  - (a) any subsystem UNCONFIGURED for **N consecutive cycles** (proposed
    N = 10, i.e. 5 min at the 30 s tick — long enough to ride out a restart,
    short enough to catch a silently dead probe within minutes) → escalate
    "no health signal from <subsystem> for N cycles".
  - (b) delivery gap: escalation attempts exceed deliveries over a window
    (channel broken) → escalate "escalation channel not delivering".
  - A healthy observation clears the streak (mirrors the COR-013 streak
    clear); a restart resets cycles and streaks, so the check is
    streak-based, never absolute-cycle-based.
- **Delivery:** via the existing `_escalate` path — once per streak, with the
  existing suppression of repeats and the COR-013 fix-up (a failed first
  delivery must not consume the streak). No new channel, no new spam mode.
- **Observability:** the check's state is exposed in `SelfHealingLoop.status()`
  (and therefore `GET /v1/friday/self_healing`) as a `ratio_check` section:
  per-subsystem unconfigured streak, signal rate, last alert.
- **Tests:** unit tests in `Cortex/tests/unit/test_self_healing_and_self_model.py`
  (or a new `test_ctx004_ratio_check.py`): streak counts across N runs,
  alert fires once per streak, healthy observation clears it, failed
  delivery does not consume the streak, restart resets streaks.
- **Live proof:** after a coordinator-cleared deploy + restart (same gate as
  G4 — the deploy decision rides with Muse 11's MEM-017 fix), the check must
  report on the live healthy state (streak 0, signal present), and the
  pre-restart 1,878-cycle UNCONFIGURED run stands as the filed counterfactual
  it would have caught. No live fault will be staged on production to force
  an alert.

## 3. Open questions for Muse (no work blocked on them)

- Threshold N = 10 cycles for the unconfigured-streak alert — confirm or
  adjust.
- Should the ratio-check alert go to the same Telegram escalation channel
  (the design assumes yes, via the existing notifier)?
- Queue note: the position-2 id TASK-ORCH-012* collides with the existing
  MERGED TASK-ORCH-012 (Muse 4, PR #1334) — it needs a fresh ORCH number
  before I reach position 2. Flagged in status comment 7086911496.

## 4. Implementation (2026-11-23 ~05:00 IST, 04:36 self-check run)

First implementation chunk, on branch
`muse13/task-ctx-004-escalation-ratio-live-check`, rebased onto main
`84739a0d`:

- `Cortex/packages/core/src/cortex_core/resilience.py`:
  - `SelfHealingSupervisor` counts consecutive cycles per subsystem in
    `run.unconfigured` (`_unconfigured_streaks`); a configured probe
    (healthy or not) clears the streak — it IS a health signal.
  - At the end of each cycle the check evaluates: (a) streak >=
    `unconfigured_streak_threshold` (default 10) alerts once per streak via
    the escalation channel; (b) `delivery_gap_threshold` (default 3)
    consecutive failed deliveries alerts once per broken-channel streak.
  - Both alerts follow the COR-013 fix-up: only a landed delivery marks the
    streak, so a failed first delivery retries next cycle. The channel-broken
    alert is additionally marked attempted when the failure is "no escalation
    channel configured" (that attempt can never land; the broken state stays
    visible in `ratio_check` instead of retrying every cycle).
  - `SelfHealingLoop.status()` (and each `HealingRun`) exposes `ratio_check`:
    thresholds, per-subsystem unconfigured streaks, signal rate
    (`total_successes / (total_successes + total_failures)`, `None` with 0
    samples for an unconfigured subsystem — the no-signal signature),
    consecutive failed deliveries, `channel_broken`, last alert.
  - Deviation from the §2 design, found while writing the code: ratio alerts
    are NOT routed through `_escalate`. That path suppresses on
    `_escalated_streaks` (failure streaks), which would both swallow a ratio
    alert that follows a failure streak and let a ratio alert suppress a
    later genuine failure escalation. The ratio check delivers via `_notify`
    with its own once-per-streak sets (`_ratio_alerted`,
    `_channel_broken_alerted`) and keeps the failure-streak system untouched.
    Pinned by `test_ratio_check_does_not_suppress_later_failure_escalation`.
- `Cortex/tests/unit/test_ctx004_ratio_check.py` (new, 10 tests): streak
  counting + once-per-streak, healthy observation clears and re-alerts,
  failed delivery does not consume the streak, restart resets streaks,
  delivery-gap alert once per broken channel, channel alert attempted once
  with no channel configured, `status()` exposure, ratio alert does not
  suppress a later failure escalation, defaults (10/3), disabled thresholds
  never alert.
- Local verification (this run): all 10 new tests green, run in isolation
  (pytest is not installed in this VM; tests executed by a direct runner
  against `resilience.py` alone — the module is stdlib-only). Regression:
  18 runnable tests from `test_self_healing_and_self_model.py` green against
  the modified module (14 direct + 4 with a fake-httpx stand-in); the 6
  self-model/self-modification tests need other modules this change does not
  touch and are left to repo CI. Full-suite proof rides on PR CI.
- Live proof: still blocked on a coordinator-cleared deploy + restart (the
  deploy decision rides with Muse 11's MEM-017 fix). No live fault staged.

## Files

- `Cortex/packages/core/src/cortex_core/resilience.py` — streak counter +
  ratio check in the supervisor/loop (implemented, §4).
- `Cortex/tests/unit/test_ctx004_ratio_check.py` (new) — streak/alert tests
  (implemented, §4; 10 tests).
- `docs/collaboration/TASK-CTX-004-ESCALATION-RATIO-LIVE-CHECK.md` — this file.
- `docs/collaboration/WORK_BOARD.yaml` — TASK-CTX-004 record (created in the
  work PR).
