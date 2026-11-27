# TASK-FRD-064 — Checkpoint 11: kills #17 + #18 after the failed MALLOC_ARENA_MAX=2 trial; cadence unchanged, Python heap still ~5% of RSS

Filed: 2026-11-28 ~03:10 IST (2026-11-27 ~21:37 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 10 (cfbdb26c); this file is the checkpoint-11 commit.

## 1. Two more OOM kills since checkpoint 10 — tally today: 18

First-hand via bridge run_shell, Server 3 (FRIDAY-Server), probes 21:36:22 and 21:37:20 UTC:

- **Seventeenth kill — 2026-11-27 21:15:56 UTC, PID 119844.**
  `FRIDAY.service: A process of this unit has been killed by the OOM killer. Main process
  exited, code=killed, status=9/KILL. Failed with result 'oom-kill'.` systemd reports
  `Consumed 1min 5.258s CPU time, 159.0M memory peak, 0B memory swap peak.`
- **Eighteenth kill — 2026-11-27 21:31:21 UTC, PID 120514.** Same signature.
  systemd reports `Consumed 1min 15.890s CPU time, 200.0M memory peak, 143.6M memory
  swap peak.`

Kill tally today (UTC): 00:56, 06:21, 08:07, 09:37, 13:22, 14:42, 16:19, 17:56, 18:33,
18:49, 19:35, 19:51, 20:06, 20:22, 20:38, 21:00, 21:15, 21:31 — **eighteen kills**.
Intervals since the trial restart (20:44:38 UTC): 21:00 → 21:15 (15 min) → 21:31
(16 min). NRestarts=3, matching the three kills since the trial restart.

## 2. Trial verdict stands: MALLOC_ARENA_MAX=2 has no effect on cadence

The drop-in (`/etc/systemd/system/FRIDAY.service.d/malloc-arena-max.conf`,
`MALLOC_ARENA_MAX=2`) is still in place; the trial process and both successors died on
the same ~15–16 min cadence as pre-trial. No harm measured, no benefit measured.
Per the WATCH239 §C revert conditions the drop-in stays in place until the profiler
ruling lands — it is inert, not a fix, and removing it mid-observation would muddy
the cadence record.

## 3. Kill #17 accounting anomaly — noted, not resolved

PID 119844 self-reported 199.6 MB (99.8% of the 200 MB cap) at 21:07:21 UTC and
198.0 MB (99.0%) at 21:12:31 UTC, yet systemd reports that unit run's memory peak as
159.0M with 0B swap peak. The process's own percentage and the cgroup peak disagree
by ~40 MB. Open question: the two numbers measure different things (process RSS vs
cgroup memory.current, possibly sampled at different instants), or the OOM kill was
triggered by a spike the cgroup peak did not capture. Recorded as an anomaly only —
no conclusion drawn, no action taken on it.

## 4. Current process already over the cap — kill #19 imminent

PID **120811**, booted 21:31:41 UTC (NRestarts=3, ActiveState=active):

- 21:32:11 UTC (+30 s): memory_pressure/warning, 81.9% (163.9 MB).
- 21:33:11 UTC (+90 s): memory_critical/critical, 97.4% (194.7 MB).
- 21:36:22 UTC (+4:41): RSS 218,624 KB = 213.5 MB.
- 21:37:20 UTC (+5:39): RSS 240,300 KB = 234.7 MB — ~35 MB over the 200 MB cap,
  still running, surviving on swap. No new kill in the journal up to 21:37:20 UTC.

Tracemalloc watch (live since 18:02:34 UTC, log /tmp/friday_tracemalloc.log) on the
live process:

- 21:34:49Z tick: rss_mb=235.8, traced_mb=14.42, traced_peak_mb=17.27.
- 21:36:05Z tick: rss_mb=233.6, traced_mb=11.79, traced_peak_mb=20.77.

Python heap is ~5% of RSS (11.79–14.42 MB traced vs ~234 MB RSS). The checkpoint-8/9
exoneration holds on the live process: the owner is still the native anonymous heap,
not Python allocations. The traced-heap diffs churn ±1 MB in threading.py / core.py —
noise against a ~220 MB unexplained gap.

## 5. Ruling status — profiler ask still pending, carried to WATCH243

Hub scan this run (issue #2045 through comment 7228544858, 03:03 IST; BE 02:38
7228172325, WATCH242 7228294192, BE 03:02 7228540362): no new assignment, no P0, and
no ruling for TP1. WATCH242 §E carries the TP1 FRD-064 profiler-based owner-ID ruling
ask to WATCH243 — **not decided this run**. TP1 holds FRD-064; nothing was started
beyond observation + this checkpoint. Next: await the WATCH243 ruling; if no ruling
by the next driver run, re-state the ask on the hub.

Five states: implemented NO (no fix yet) / tested YES (MALLOC_ARENA_MAX=2 trial run,
failed on cadence; tracemalloc watch live) / merged NO / deployed NO (watch + inert
drop-in live on the server, not a fix) / production-verified NO.

## 6. Queue

FRD-064 (head, in progress) → EARN-017 (queued). VOI-045 firing stays HELD until the
fix deploys (WATCH242 §E; TP10 checkpoint 15).
