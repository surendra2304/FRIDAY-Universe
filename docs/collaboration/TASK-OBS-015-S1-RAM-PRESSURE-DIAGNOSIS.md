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

**Status after checkpoint 2 (2026-11-24 ~01:00 IST):** DIAGNOSIS COMPLETE —
live S1 data obtained first-hand via the bridge; responsible processes
identified with RSS evidence; voice/Stratex verdicts filed; mitigation filed
(NOT implemented — live changes need Muse's clearance). See "Checkpoint 2"
below. Queue now: OBS-015 → VYR-050 → OBS-022 (watch 7110882697).

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

## Checkpoint 2 — live S1 diagnosis complete (2026-11-24 ~00:55–01:00 IST)

**Status:** DIAGNOSIS COMPLETE. Live S1 data obtained first-hand via the
bridge (MCP initialize confirmed 00:51 IST — FRIDAY-Cloud-Engineering-Bridge
v1.30.0; all tool calls first-hand). Acceptance met on diagnosis + mitigation
filed: the responsible processes are identified with RSS evidence, the
voice/Stratex verdicts are filed below, and the mitigation is filed (NOT
implemented — live changes need Muse's clearance). No live change was made to
any service this run.

### Live S1 data (bridge oracle_* tools + run_shell, Server 1)

**Fleet health, 00:55 IST:** S1 (10.0.0.121, 7 agents), uptime 40 days 13:36,
load 1.53/1.50/2.12. Memory total 956 MB — used 489, free 71, buff/cache 395,
available 314; swap 8191 MB total, **1595 MB in use**. Disk 97G, 29% used.
S2 (10.0.0.120): uptime 32 days 6:28, load 1.88/4.23/7.05; Mem 956 MB, used
473, free 329, available 332; swap 874 MB in use; disk 49G, 66% used.

**Per-process, full cmdlines (`ps -eo pid,ppid,%mem,%cpu,etime,cmd`,
~00:58 IST), top by %MEM:**
- PID 3179089, 14.8% (~141 MB), 3.1% CPU, elapsed 01:14:07 —
  `/opt/friday_universe/venv/bin/python src/friday/voice/livekit_worker.py start`
  — the FRIDAY voice LiveKit worker. Largest single consumer on S1.
- PID 2585237, 9.0% (~86 MB), elapsed 8-06:35:00 —
  `/usr/bin/python3 /home/ubuntu/rd17-carry-sim/carry_paper_sim.py daemon ...`
  — an RD17 carry-paper sim, NOT one of the 10 fleet agents, running 8+ days.
- PID 3187555, 8.7% — Memora (uvicorn :8002).
- PID 3188109, 8.5%, **49.6% CPU**, elapsed 56:09 — Stratex autonomy daemon
  (`Stratex/autonomy/run_daemon.py`). The CPU hog: about half of S1's CPU.
- PID 3187605, 5.6% — Stratex dashboard (`dashboard.py`).
- PID 3077924, 2.9%, elapsed 6-04:46:11 —
  `/opt/friday-arm-sniper/venv/bin/python -m scripts.oci_a1_continuous` —
  non-fleet, 6+ days.
- FRIDAY API server PID 3187196, 1.8% (15.4 MB) — small; the voice worker,
  not the API server, is the memory weight in FRIDAY's lane.
- Inference (:8001) 1.8%, Forge (:8006) 1.0%, Sentinel (:8008) 0.9%;
  caddy 2.4%, containerd 1.5%, journald 1.5%.

**Service status, 00:55 IST:**
- FRIDAY.service: active (running) since 00:00:01 IST (restarted at midnight;
  no OOM event in the kernel record for Nov 24, so this was a scheduled
  restart, not a kill — reason beyond that unverified). Main PID 3187196,
  Memory 15.4M (max 200.0M, swap max 192.0M). /health 200s throughout. Her own
  proactive monitor queued ram_critical warnings at 90.5% (00:06), 91.2%
  (00:26), 91.4% (00:33), 90.3% (00:38) IST.
- Stratex.service: active (running) since 00:00:30 IST. Main PID 3187605,
  Memory 24.3M (max 180.0M). Analysis cycles completing (ML ensemble signals,
  cTrader bracket adjustments). One anomaly: `GET /health` returned 503 once
  at 00:50:18 IST.

**OOM-killer history (dmesg, kernel record):**
- Nov 17 11:26:44 — FRIDAY.service cgroup, PID 2817851 killed, anon-rss 183 MB.
- Nov 17 18:33:22 — FRIDAY-Voice.service cgroup, PID 3011062 killed,
  anon-rss 297 MB, total-vm 1.8 GB.
- Nov 22 11:14:22 — FRIDAY.service cgroup, PID 2074982 killed, anon-rss 183 MB.
- Nov 23 08:03:47 IST — FRIDAY.service cgroup, PID 2704298 killed,
  anon-rss 160 MB (kern.log 02:33:47 UTC; agrees with FRD-041).
- No OOM event on Nov 24. The journal grep since Nov 23 returned only
  Stratex forward-scorecard "kill[drawdown]: SAFE" lines (trading kill-switch
  checks, not OOM).

### Root cause (building on FRD-041 — Muse 2, PR #1548, CI green)

FRD-041 proved first-hand that the kills are **cgroup kills, not system-RAM
kills**: FRIDAY.service carries MemoryMax=200M and MemorySwapMax=192M; at the
08:03 kill the cgroup sat at its ceiling (usage 204800kB, limit 204800kB,
failcnt ~7.5M — chronic saturation) and the triggering fault was a swap-in.
Two processes shared the 200 MB cap: the victim (164 MB RSS, grown in ~6 min
from a 07:57 start) and a sibling holding ~132 MB in swap while serving
nothing. My live data agrees and extends it:
- The voice worker (LiveKit) is now the largest single process (14.8%) and
  sits in the voice lane that was already killed once (Nov 17, 297 MB anon).
- The box itself is at 90%+ with 1595 MB swap in use, so the cgroup caps are
  the tripwire and the box pressure is the context.
- Two non-fleet processes (rd17 carry sim 9.0%, arm-sniper 2.9%) hold ~12% of
  S1's RAM for 6–8 days without being part of the 10-agent fleet.
- The Stratex autonomy daemon burns 49.6% CPU — the box's CPU is also
  saturated (FRIDAY logged cpu_hot 100% at 00:06 IST).

### Threat verdicts (final for this task)

- **FRIDAY voice: THREAT REAL AND CONFIRMED.** Four kernel OOM kills (3x
  FRIDAY.service, 1x FRIDAY-Voice), the voice worker currently the largest
  consumer on the box, FRIDAY's own monitor at 90.3–91.4% RAM through the
  night, and the cgroup cap at 200 MB with chronic saturation (failcnt
  ~7.5M). The next kill is a matter of load, not chance. FRD-041's guard
  (warn 75%, escalate 90% via Telegram) gives minutes of warning; it does
  not remove the threat.
- **Stratex: NO OOM KILL ON RECORD; at risk via shared box pressure.** No
  Stratex cgroup kill appears in the kernel record. Stratex.service is
  running and its analysis cycles complete; its cap is 180 MB and it is
  currently at 24.3 MB (dashboard) + the autonomy daemon at 8.5% of box RAM.
  The one /health 503 at 00:50:18 IST is noted but a single 503 is not proof
  of a RAM link. Verdict: not currently threatened by a proven kill path,
  but exposed to the same box-wide pressure that kills FRIDAY — if the box
  tips over, Stratex goes with it.

### Mitigation filed (NOT implemented — live changes need Muse's clearance)

1. **Adopt FRD-041's memory guard (PR #1548, CI green, mergeable).** Warning
   layer only: cgroup-aware warn at 75% / escalate at 90% with direct
   Telegram send. It does not fix pressure. Merge is Muse's.
2. **Find and stop the sibling holding ~132 MB of FRIDAY's swap budget.**
   FRD-041's record shows a sibling process in the FRIDAY cgroup resident
   3h13m, serving nothing, holding most of the 192 MB swap budget. Identify
   it (needs a cgroup process list at the next saturation) and stop or move
   it; it is the cheapest headroom on the box.
3. **Move or cap the non-fleet load on S1.** rd17 carry sim (9.0%) and
   arm-sniper (2.9%) are not fleet agents; move them to S2/AWS or give them
   their own cgroup caps so they cannot crowd FRIDAY's lane. Frees ~12% of
   S1 RAM.
4. **Watch the LiveKit voice worker's growth.** One snapshot proves size, not
   growth. A follow-up probe (same ps, 2–3 samples hours apart) should
   confirm whether it grows unboundedly; if it does, the fix is in the
   worker (restart policy / memory discipline), not in the cap.
5. **Do NOT raise FRIDAY.service MemoryMax blindly.** The box has 956 MB
   total and 1595 MB swap already in use; raising the cap trades a cgroup
   kill for a box-wide OOM that takes Stratex and the rest of S1 with it.
   Raise only if the guard shows the cap, not the box, is the binding
   constraint — and only with Muse's clearance.

**What this run did not do:** no fix applied, no service restarted, no live
change of any kind. No board edit in this branch (board flips ride in the
coordinator's consolidated board PR; OBS-015 IN_PROGRESS + VYR-050 flips
landed in #1545). Queue now: OBS-015 → VYR-050 → OBS-022 (watch 7110882697).

## What this run did not do

- No fix applied, no service restarted, no live change of any kind.
- No board edit in this branch (board flips ride in the coordinator's
  consolidated board PR).
- No claim of implemented / tested / merged / deployed / production-verified
  status: this is a checkpoint, not a completion.

— Muse 17
