# TASK-OBS-015 — S1 RAM pressure: diagnosis checkpoint 1 (2026-11-23 ~23:35 IST)

**Task:** TASK-OBS-015 (P1, owner muse_17) — "Fleet: diagnose S1 RAM pressure
(FRIDAY at 92.4 percent RAM) and file whether it threatens voice or Stratex,
fix or file the mitigation."

**Claim:** hub claim on #1483, comment 7109516286; branch `muse17/obs-015`
created from main `13cdf268` (ref create 201, re-read confirmed). No claim PR,
per the coordinator's instruction in watch 7109363715. Board owner flip rides
in the next consolidated board PR (do NOT file a competing board PR; #1541 is
the coordinator's board PR in flight). Queue: OBS-015 → VYR-050.

**Status of this checkpoint:** DIAGNOSIS IN PROGRESS — checkpoint 1 filed from
verified records + one live public re-probe. Acceptance NOT yet met: the
responsible process is not yet identified from live S1 data, and no fix or
mitigation has been applied. No live change was made to any service this run.

## Verified timeline (all first-hand reads this run)

- **07:00 IST, 2026-11-23:** S1 RAM 90.0 percent (Muse 11 self-check
  7091847142).
- **08:03:47 IST:** FRIDAY OOM-killed on S1 (FRD-041 board record; Muse 2
  claim 7109102445, 23:15 IST). Sibling investigation TASK-FRD-041 (Muse 2)
  owns the OOM root cause + memory guard; this task does not duplicate it.
- **~09:13 IST:** FRIDAY restarted — Muse 13's cleared ORCH-014 G1 restart
  (Muse 11 self-check 7091847142).
- **10:02:54 IST:** RAM warning again, **92.4 percent (0.86 of 0.93 GB)**, up
  from 90.0 percent at 07:00 (Muse 11 self-check 7091847142, FRIDAY PID
  2758868). Pressure rebounded to above the pre-OOM level within ~1h of the
  restart: this is regrowth, not a one-off spike.
- **21:28 IST:** FRIDAY restarted again (Muse 7 hourly self-check
  7106624921).
- **23:31 IST (this run):** live `GET /api/agents/status` re-probe
  (public ingress, `2026-11-23T18:01:51Z`): overall `degraded`,
  9 agents — ONLINE 1, REACHABLE 4, DEGRADED 2, UNREACHABLE 2.
  - **Stratex UNREACHABLE** — probe error `ConnectError: All connection
    attempts failed` on `127.0.0.1:18003`.
  - Memora ONLINE; Inference / Cortex / Forge / Sentinel REACHABLE.
  - IntelX + Futuris DEGRADED — known by-design honest degradation, no live
    probe (OBS-016, Muse 4, merged PR #1488).
  - VyralX UNREACHABLE — `ConnectTimeout` to AWS `16.176.9.247:8010`
    (U2 is gone; VyralX lives on S2 — separate lane, not this task).

## Threat assessment (provisional — from verified records only)

- **FRIDAY voice: THREAT REAL, ongoing.** She was already OOM-killed once
  today (08:03 IST); RAM rebounded past the pre-kill level within an hour of
  restart and she has been restarted again since (21:28 IST). A second OOM
  kill drops voice with no warning. Provisional because the growing process
  is not yet identified from live S1 data.
- **Stratex: THREAT UNVERIFIED.** Stratex is UNREACHABLE on the just-now
  probe, but RAM is not yet proven as the cause — it may be stopped, masked,
  or restarting for another reason. Needs a live S1 check before any claim.
- **Structural note:** S1 reports 0.93 GB total RAM while running six agents
  (FRIDAY, Inference, Memora, Stratex, Forge, Sentinel) under the 6/4 layout.
  Even a healthy FRIDAY leaves almost no headroom; any growth anywhere on
  the box threatens voice first. This is the context the mitigation must
  address, not just the single growing process.

## Blocker — live S1 per-process diagnosis still owed

Identifying the responsible process needs live S1 data: per-process RSS
(`ps`/`smem`), the OOM-killer journal around 08:03 IST, and the FRIDAY
service journal — all via bridge `run_shell` on Server 1. That step was NOT
taken this run: bridge MCP initialize remains unconfirmed for Muse 17
(recorded onboarding constraint — the unauthenticated initialize probe timed
out awaiting approval and is not to be retried unless Surendra asks). No
live S1 shell step was attempted, and no credential was read.

**Next:** coordinator direction on bridge access for Muse 17, or build on
Muse 2's FRD-041 findings (OOM root cause, due on her lane). When live S1
access lands: name the growing process with RSS evidence, confirm or clear
the Stratex link, then fix or file the mitigation with before/after numbers.

## What this run did not do

- No fix applied, no service restarted, no live change of any kind.
- No board edit in this branch (board flips ride in the coordinator's
  consolidated board PR).
- No claim of implemented / tested / merged / deployed / production-verified
  status: this is a checkpoint, not a completion.

— Muse 17
