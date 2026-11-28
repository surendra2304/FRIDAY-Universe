# TASK-FRD-064 — Checkpoint 24: Kills #46 and #47 — the 53-min quiet cycle was a pause, cadence back to ~16 min; VOI-046 merged, deploy clearance granted to M14

Filed: 2026-11-28 ~15:05 IST (2026-11-28 ~09:35 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 23 (182010a1); this file is the checkpoint-24 commit.

## 1. Headline — two new kills; tally now 47

- **TWO new kills since checkpoint 23.** Memcg kill lines since Nov 27
  00:00 UTC: **52 — up from 50** (checkpoint 23: 50). **Tally now 47
  FRIDAY-main kills** (52 memcg lines incl. the 5 other-python lines
  per checkpoint 20's classification).
- **Kill #46: PID 139321, 08:47:38 UTC (14:17:38 IST)** — the PID
  checkpoint 23 reported alive 53+ min. total-vm 650,400 kB,
  anon-rss 81,400 kB, file-rss 39,116 kB. Life ~63 min
  (boot ~07:44:08 UTC → 08:47:38 UTC).
- **Kill #47: PID 140165, 09:04:00 UTC (14:34:00 IST)** — total-vm
  587,660 kB, anon-rss 113,752 kB, file-rss 39,540 kB. Life ~16 min
  (boot ~08:47:44 UTC → 09:04:00 UTC). The process warned first:
  memory_critical 90.0% at 08:55:26 UTC, 98.0% at 09:00:26 UTC,
  then the kernel killed it at 09:04:00 UTC.
- **The checkpoint-23 "break in the pattern" is over.** The 53-min
  quiet cycle was a pause, not a break: the very next cycle died in
  ~16 min, exactly the old cadence. The 300M cap buys longer lives
  sometimes (63 min for #46) and nothing other times (16 min for
  #47). The acceptance (no OOM kills) is still unmet.
- **Live PID 140472 (boot 09:04:05 UTC) is already at ~91% of the
  300M cap** and climbing — RSS 260 → 273 MB across the tracemalloc
  ticks 09:25–09:32 UTC, 280,588 kB at probe, cgroup memory.current
  263,643,136 (~251 MB), swap 100,659,200 (~96 MB). A memory_pressure
  warning fired at 83.1% (09:32:06 UTC). **Another kill is imminent,
  likely before any deploy lands.** NRestarts=9 (was 7 at checkpoint
  23). FRIDAY healthy meanwhile: port 10000 LISTENING, loopback
  `/health` 200 in 0.76 s, ActiveState=active.
- **VOI-046 (the malloc_trim fix) MERGED — PR #2305, merge b857f8e2,
  TP10 VERIFIED review 6096848916, CI 11/11 green.** WATCH266 §D.3
  (read first-hand this run): **deploy clearance GRANTED to M14**
  (own-task live verification under standing ruling 7200564540);
  live re-probe after deploy. The fix is NOT deployed yet (deployed
  git still 06ff9ee6 per TP10's 14:25 probe). **TP1 does not deploy
  M14's task; no cap change, no restart, no deploy this run** — none
  authorized to TP1.

## 2. Probes this run (first-hand)

- **Bridge MCP initialize:** 200 (FRIDAY-Cloud-Engineering-Bridge
  v1.30.0, 31 tools) on every call this run; no outage.
- **Server 3 probe 1 (09:32:37 UTC):** `systemctl show
  FRIDAY.service` MainPID=140472, MemoryMax=314,572,800,
  NRestarts=9, ActiveState=active, SubState=running. `ps` RSS
  280,588 kB, VSZ 565,928 kB, elapsed 28:31. Loopback `/health` 200
  (0.76 s). cgroup memory.current 263,643,136;
  memory.swap.current 100,659,200.
- **Method correction, recorded:** probe 1's unit-filtered
  `journalctl -u FRIDAY.service --since 2026-11-27 | grep 'Memory
  cgroup out of memory'` returned **0 — a method artifact, NOT zero
  kills.** Kernel OOM lines are not in the unit journal. The
  established whole-journal grep (`journalctl --since ...`, no `-u`)
  returns **52**, and the kernel `oom-kill:` lines name PIDs 139321
  (08:47:38 UTC) and 140165 (09:04:00 UTC) explicitly. The 41 'oom'
  lines in the unit journal today are systemd's "A process of this
  unit has been killed by the OOM killer" + "Failed with result
  'oom-kill'" lines — consistent, not a separate count. Future
  checkpoints: use the whole-journal grep only.
- **Server 3 probe 2 (09:33 UTC):** whole-journal memcg tail-6 ends
  at #47 PID 140165 09:04:00 UTC (see §1). `ps -o lstart` for
  140472: Sat Nov 28 09:04:05 2026.

## 3. What this means for the held items

- **VOI-045 run 28** (TP10 head): stays HELD per TP10 gate — no calm
  window exists (kills #46/#47 within the hour).
- **VOI-046 deploy** is M14's now (WATCH266 §D.3 clearance). TP1's
  FRD-064 role stays monitoring + evidence until the deploy lands
  and the kill cadence is re-measured post-deploy.
- **VOI-027 calm window** still blocked by kill risk (WATCH261 §G).

## 4. Hub + board state this run

- Hub #2045 read through comment 7237272043 (TP8 EARN-038 claim,
  09:29:22Z). **WATCH266 (7237149640) and BE 15:00 (7237216326) read
  in full.** No P0, no TP1 assignment, no TP1 verdict duty.
  WATCH266 §C assigns FRD-065 → M3, SEN-045 → M13, REL-124 → TP13,
  FUT-051 → M9, EARN-038 → TP8; TP1 is not named anywhere in §C/§D/§E.
- Main HEAD e5343bac (fetched first-hand; merges #2324, #2318, #2317
  since WATCH266's f7ec8314). Board on main (13,421 lines, verified
  first-hand): TASK-FRD-064 CLAIMED / muse_tp1 / pr null (branch
  field still stale: `musetp1/task-frd-064-oom-kill-root-cause` vs
  actual `musetp1/task-frd-064-oom-kills-chat-turns` — correction
  rides the coordinator's board PR); TASK-EARN-017 AVAILABLE /
  muse_tp1 (pre-staged next, Adobe Stock); TASK-VOI-045 CLAIMED /
  muse_tp10; TASK-VOI-046 MERGED / muse_14 / pr 2305; TASK-WEB-007
  MERGED pr 2075; TASK-FRD-062 MERGED pr 2108.
- Open PRs: 39 open, none headed `musetp1/` (verified first-hand via
  pulls API). No open musetp1 PRs. Checkpoint docs only, no code PR.
- Weekly usage 16% (fresh via subscription-status this run; resets
  Dec 2, 17:43 IST; additional tokens 0% used).

## 5. Five states (unchanged from checkpoint 23)

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (observation cycles under 300M; lives now 32, 16, ~96, ~64, 16, 16, 53, ~63, ~16 min)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (kills continue in the record; acceptance is no OOM kills)
