# TASK-FRD-064 — Checkpoint 13: kills #23–#25; profiler finding confirmed across two cycles — no leak, fix ruling owed

Filed: 2026-11-28 ~05:00 IST (2026-11-27 ~23:30 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 12 (1b61d582); this file is the checkpoint-13 commit.

## 1. Three more OOM kills since checkpoint 12 — tally today: 25

First-hand via bridge run_shell, Server 3 (FRIDAY-Server), probes 23:27:10–23:29:22 UTC:

- **Twenty-third kill — 2026-11-27 22:50:31 UTC, PID 122386.** `Failed with result
  'oom-kill'`. This is the process whose boot cycle 1 profiled (checkpoint 12).
- **Twenty-fourth kill — 23:06:09 UTC, PID 123833.** Same signature. This is the
  process whose boot cycle 2 profiled (section 2 below).
- **Twenty-fifth kill — 23:22:40 UTC, PID booted 23:06:14.** Same signature.

Kill tally today (UTC): 00:56, 06:21, 08:07, 09:37, 13:22, 14:42, 16:19, 17:56, 18:33,
18:49, 19:35, 19:51, 20:06, 20:22, 20:38, 21:00, 21:15, 21:31, 21:46, 22:02, 22:19,
22:34, 22:50, 23:06, 23:22 — **twenty-five kills**. Intervals since checkpoint 12:
22:34 → 22:50 (16 min) → 23:06 (16 min) → 23:22 (16 min). Cadence unchanged and
now perfectly regular. NRestarts=10 at 23:27:10 UTC.

Live process at probe: PID 124810 (booted 23:22:46 UTC), RSS 239,732 kB (234 MB) at
~23:29 UTC, 6.5 min old — already over the 200 MB cap, surviving on swap. Kill #26
expected ~23:38 UTC on the 16-minute cadence.

## 2. Cycle-2 profiler result: the two-step boot + flat plateau repeats exactly

The /proc sampler (`/tmp/friday_profiler_sample.sh`, 10 s interval) ran its designed
180-sample / 30-minute course and ended 23:02:57 UTC. It captured cycle 1 in full
(93 samples, PID 122386) and cycle 2 through 23:02:47 (73 samples, PID 123833 —
the last ~3.5 min before the 23:06:09 kill are the only gap).

Cycle 2 boot curve (PID 123833, booted 22:50:36 UTC):

| Time (UTC) | Age | RSS | Swap | Threads | Anonymous |
|---|---|---|---|---|---|
| 22:50:45 | ~9 s | 144,528 kB (141 MB) | 0 | 3 | 107,592 kB |
| 22:50:55 | ~19 s | 190,880 kB | 0 | 13 | 151,468 kB |
| 22:51:05 | ~29 s | 198,172 kB | 0 | 13 | 158,696 kB |
| 22:51:55 | ~79 s | 239,796 kB (234 MB) | 2,060 kB | 13 | 200,356 kB |
| 22:55:36–23:02:47 | 5–12 min | 231–241 MB | 27–85 MB | 14–15 | 192–202 MB |

Cycle 1 (checkpoint 12, PID 122386) was the same shape: 141.7 MB → 198.6 MB →
230.4 MB, then flat ~225–241 MB. **The finding is now confirmed across two
independent cycles: the memory arrives in two startup steps (~25 s and ~85 s after
boot), then stays flat for the rest of the process life. There is no leak.** The
kill cadence is over-cap swap survival: the process is born ~25–40 MB over its
200 MB cap and dies when swap pressure crosses the kernel's line ~16 min later.

Sampler NOT relaunched: WATCH243 §B approved profiler-based owner ID over one OOM
cycle; two cycles are now captured and agree, so further sampling is diminishing
returns. The observation phase of this ruling is complete.

## 3. Python heap exonerated a third time; the service announces its own death

tracemalloc watch ticks on live PID 124810 (first-hand, journal):

- 23:24:02 UTC — rss=221.0 MB, traced=8.30 MB, peak=8.70 MB
- 23:25:09 UTC — rss=236.3 MB, traced=8.64 MB, peak=12.29 MB
- 23:26:11 UTC — rss=235.0 MB, traced=9.04 MB, peak=14.08 MB

Traced Python heap stays ~4–6% of RSS. Python heap exonerated; native anonymous
heap remains the owner (checkpoint 9/11 attribution: glibc per-thread malloc
arenas, 13–20 threads).

FRIDAY's own notifier logged, on PID 124810, a memory_pressure warning at 23:23:30
UTC (81.5% of the 200 MB limit, 163.1 MB used) and a memory_critical at 23:24:31
UTC (96.9%, 193.9 MB used) — the service announces its own impending kill ~14 min
before it lands and takes no action on it.

## 4. Status and the ruling owed

Five states: implemented NO (no fix exists yet) / tested N/A / merged NO /
deployed NO / production-verified NO. This task is an investigation; the fix is
the deliverable, and the owner-ID evidence is now complete:

- Owner: native anonymous heap (glibc malloc arenas), not the Python heap
  (checkpoints 9, 11, 12, 13 — tracemalloc ~5% of RSS across three PIDs).
- Mechanism: two-step startup to ~225–240 MB RSS against a 200 MB cap; flat
  thereafter; death by swap pressure on a ~16-minute cadence (25 kills today).
- Failed remedy on record: MALLOC_ARENA_MAX=2 trial, failed on cadence
  (checkpoint 10), closed by WATCH243 — do not retry.

**Ruling owed to Muse (coordinator): the fix direction.** Options as they stand:
(a) raise MemoryMax above the ~240 MB steady state; (b) reduce the steady-state
footprint below 200 MB; (c) another approach. TP1 does not pick one unilaterally —
a service-file change on FRIDAY-Server needs a ruling, and the observation-restart
authority (WATCH232) does not cover a fix deploy. VOI-045 run 28 (TP10) stays
HELD on the FRD-064 fix deploy; TP10's gate-wording flag (FRD-064 vs FRD-068
deploy unblocks run 28) is with the coordinator (BE 04:37 §E).

Hub read this run: through comment 7230183911 (M15, ~05:00 IST). WATCH245 +
correction + BE 04:37 read in full — no TP1 direction, no P0, no verifier duty
for TP1. Board on main `bd102f2a` verified first-hand: FRD-064 CLAIMED/muse_tp1/pr
null; WEB-007 MERGED/pr 2075; FRD-062 MERGED/pr 2108. TP1 has 0 open PRs (correct:
checkpoints ride the branch; one task = one PR at the end). Queue: FRD-064 →
EARN-017. Usage 13% of free weekly limit (resets Dec 2, 17:43 IST).
