# TASK-FRD-064 — Checkpoint 12: kills #19–#22; profiler ruling executed — memory arrives in two startup steps, then flat (no leak)

Filed: 2026-11-28 ~04:10 IST (2026-11-27 ~22:40 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 11 (0dd479d0); this file is the checkpoint-12 commit.

## 1. Four more OOM kills since checkpoint 11 — tally today: 22

First-hand via bridge run_shell, Server 3 (FRIDAY-Server), probes 22:31:28–22:39:10 UTC:

- **Nineteenth kill — 2026-11-27 21:46:45 UTC, PID 120811.** The kill checkpoint 11
  predicted as imminent (live PID at 234.7 MB). `Failed with result 'oom-kill'`,
  `200.0M memory peak, 113.2M memory swap peak`.
- **Twentieth kill — 22:02:22 UTC, PID 121246.** Same signature, `200.0M memory
  peak, 113.2M memory swap peak`.
- **Twenty-first kill — 22:19:13 UTC, PID 121891.** Same signature.
- **Twenty-second kill — 22:34:52 UTC, PID 121959.** Same signature.

Kill tally today (UTC): 00:56, 06:21, 08:07, 09:37, 13:22, 14:42, 16:19, 17:56, 18:33,
18:49, 19:35, 19:51, 20:06, 20:22, 20:38, 21:00, 21:15, 21:31, 21:46, 22:02, 22:19,
22:34 — **twenty-two kills**. Intervals: 21:31 → 21:46 (15 min) → 22:02 (16 min) →
22:19 (17 min) → 22:34 (15 min). Cadence unchanged. NRestarts=7 at 22:38:42 UTC.

## 2. Profiler ruling executed (WATCH243 §B) — py-spy absent, /proc sampling per ruling

WATCH243 §B (hub 7228739726) RULED profiler-based owner ID APPROVED: py-spy or /proc
RSS sampling, read-only, over one OOM cycle; if py-spy needs elevated ptrace, use
/proc sampling instead. `which py-spy` on Server 3 returns nothing — py-spy is not
installed — so the /proc branch of the ruling is what ran. No env flips, no service
changes, no installs.

Sampler: `/tmp/friday_profiler_sample.sh` (launched 22:32:51 UTC, PID 122199),
10-second interval, 180 samples (~30 min), log `/tmp/friday_profiler.log`, follows
`FRIDAY.service` MainPID across restarts. Each sample: timestamp, PID, VmRSS,
VmSwap, Threads, smaps_rollup Anonymous. First cycle (kill of 121959 + full boot
of 122386) is captured below; the sampler keeps running into the next cycle and the
next driver run reads the full log.

Process identity (first-hand): `/opt/friday_universe/venv/bin/python -m uvicorn
friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1` — single worker,
13 threads at steady state.

## 3. First-cycle finding: the memory arrives in two startup steps, then stays flat

Boot curve of PID 122386 (booted ~22:34:57 UTC, right after the 22:34:52 kill):

| Time (UTC) | Age | RSS | Swap | Threads | Anonymous |
|---|---|---|---|---|---|
| 22:35:02 | ~5 s | 141,724 kB (138 MB) | 0 | 3 | 106,572 kB |
| 22:35:12 | ~15 s | 144,364 kB | 0 | 3 | 107,596 kB |
| 22:35:22 | ~25 s | 198,644 kB (194 MB) | 0 | 13 | 159,352 kB |
| 22:35:22–22:36:12 | ~25–75 s | 198,644–198,656 kB — flat | 0 | 13 | ~159,360 kB |
| 22:36:22 | ~85 s | 230,384 kB (225 MB) | 0 | 13 | 191,092 kB |
| 22:36:22–22:38:33 | ~85–215 s | 224,608–230,412 kB — flat | 0 → 16,888 kB | 13 | 185,468–191,120 kB |

- **Step 1 (+54 MB in one 10-s interval, ~25 s after boot):** RSS 144 → 199 MB,
  threads 3 → 13. Coincides with the worker thread-pool spawn.
- **Step 2 (+32 MB in one 10-s interval, ~85 s after boot):** RSS 199 → 230 MB
  after 50 s dead flat. A second discrete allocation event, not a ramp.
- **After ~90 s: flat.** RSS holds 224–230 MB for the whole observed window;
  the only movement is swap 0 → ~17 MB as the kernel pages the over-cap process
  out. No gradual growth, no per-minute creep.

The dying process tells the same story from the other end. PID 121959, last
2 minutes of life: RSS 237,392 → 241,040 → 239,616 kB — flat within ±2 MB. In its
final 10 s the kernel swapped it out hard (22:34:42 RSS 131,892 kB / swap
143,232 kB; 22:34:52 RSS 95,228 kB / swap 179,896 kB) and then the kill line
fired at 22:34:52.

Composition at 22:32 UTC (PID 121959, smaps_rollup): Anonymous 198,364 kB
(~194 MB, 83% of RSS), Pss_File 19,297 kB, Private_Dirty 178,876 kB.
Tracemalloc watch: latest ticks ~0.00 MB deltas — Python heap still ~5% of RSS,
exoneration holds.

**Interpretation (finding, not a fix):** there is no leak in the ordinary sense.
The process is born at ~225 MB RSS within ~90 seconds of boot and then holds
that plateau; the ~15-min kill cadence is how long the kernel tolerates an
over-cap process surviving on swap, not a leak rate. Owner-ID therefore narrows
to the startup path — the thread-pool spawn step and the ~85-s step — not to any
per-turn or per-request allocation. The ~85-s step's component is NOT yet
identified: correlating it against the boot log lines (embeddings provider init
window) is owed to the next run, from the sampler log + journal, before any
component is named as the owner.

## 4. Hub + board state this run

- Hub #2045 read through comment 7229381548 (M16, 04:00 IST); WATCH244
  (7229329225) read in full. No TP1 assignment, no P0, no new ruling for TP1.
  WATCH244 adopts the BE 03:42 post; FRD-068 deploy ruled APPROVED for M13
  (unblocks TP10 VOI-045 run 28 once #2207 lands — VOI-045 firing stays HELD
  until the fix deploys, unchanged).
- Board on main `901a1114`: WEB-007 MERGED / pr 2075; FRD-062 IN_REVIEW / pr 2108
  (board behind the merged PR #2108 — flip rides the coordinator board PR);
  FRD-064 CLAIMED / owner `muse_1` (stale owner on the board; the hub claim of
  record is TP1, hub 7216255692 — flip rides the coordinator board PR);
  EARN-017 AVAILABLE / owner muse_tp1 (pre-staged next). No open TP1 PRs.
- MALLOC_ARENA_MAX=2 trial stays CLOSED per WATCH243 §B (do not retry); the
  inert drop-in remains in place until the profiler ruling's owner-ID lands.

Five states: implemented NO (no fix yet) / tested YES (profiler first cycle
captured; tracemalloc watch live) / merged NO / deployed NO (sampler + watch
live on the server, not a fix) / production-verified NO.

## 5. Queue

FRD-064 (head, in progress — profiler cycle 2 read owed next run) → EARN-017
(queued). VOI-045 firing stays HELD until the fix deploys (WATCH244 §B).
