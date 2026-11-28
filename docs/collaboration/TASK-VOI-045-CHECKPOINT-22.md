# TASK-VOI-045 — Checkpoint 22: Root-cause probe report (WATCH254 §C.1, reclaimed per WATCH258 §F)

**Worker:** Muse TP10 · **Task:** FRIDAY voice acceptance run 28 (P1)
**Branch:** `musetp10/task-voi-045` · **State:** RECLAIMED (hub claim 7234990867), firing HELD
**Usage:** 16% of free weekly limit (resets Dec 2, 6:34 PM IST)

## Why this checkpoint exists

WATCH254 §C.1 (hub 7233833233) assigned TP10 the growth-past-profiler-flat
root-cause probe (top growers + smallest fix), due by WATCH255/WATCH256.
TP10 missed it; VOI-045 re-slotted to AVAILABLE (WATCH256, landed via
#2279/#2281). WATCH258 §F (hub 7234793701) DECIDED: TP10 reclaims VOI-045
and files this report; EARN-022 declined. This is that report. It does not
fire run 28, implement a fix, or raise the cap — TP1 owns FRD-064; any cap
decision waits for Muse on this evidence.

## What TP1 already established (not re-litigated)

- Python heap exonerated: tracemalloc traced ~11–14 MB of ~260–295 MB RSS
  (~5%), deltas ~0.00 MB across seven PIDs (TP1 cp8–cp18).
- Profiler-flat baseline ~225–241 MB after ~85 s startup, no leak in
  180 samples / two cycles (WATCH251 §D).
- `MALLOC_ARENA_MAX=2` trial CLOSED failed at the 200 MB cap (WATCH243);
  the variable is still set in the live environ (verified this probe).
- 300 MB cap (WATCH251 §D) bought one 32-min cycle, then 16-min cycles
  (TP1 cp18, kills #39/#40). TP1 flagged an accounting gap: kill-time
  anon-rss ~92–96 MB + file-rss ~39 MB vs a 300M cgroup charge.

## Own probe — 2026-11-28 05:55–05:57 UTC, server 3 (FRIDAY-Server), read-only

Bridge recovered (list-tools + get_system_info OK 05:54:45Z; both Oracles
ONLINE). Three batched read-only `run_shell` probes; no restart, no cap
change, no run-28 probe fired.

### Kill tally — kill #41 landed during the bridge outage

- **Kill #41 — 04:31:16 UTC, PID 134977** (booted ~03:58:40 UTC, life
  ~32.5 min): `anon-rss:101700kB, file-rss:39156kB`. This is the kill TP1
  cp19 could not verify while the bridge was down.
- TP1 FRIDAY-main tally: 40 (cp18) + 1 = **41**. Raw journal
  `Memory cgroup out of memory` lines since Nov 27 00:00 UTC = 46 (includes
  secondary python kills in the same cgroup, e.g. PID 132365 at 02:41:21
  UTC alongside PID 132041); TP1's main-kill tally governs.
- No kill since 04:31:16 UTC (verified: journal since 04:00 UTC shows only
  kill #41).

### Current instance — long survival, but swap-thrashing, NOT calm

- PID **135781**, started 04:31:21 UTC, NRestarts 3, age ~85 min at probe
  (longest survival in the record) — but `MemoryPeak` = 314,576,896, i.e.
  **at the 300 MB cap** (`MemoryMax` 314,572,800), `MemorySwapCurrent`
  100,659,200 (~96 MiB swapped), cgroup `swapcached` 91,045,888,
  `workingset_refault_anon` 303,042 (heavy refaulting = thrash).
- tracemalloc ticks 05:27–05:56 UTC: RSS flat ~271–272 MB for ~25 min,
  punctuated by swap-out dips (159.6 MB at 05:35:06, 166.3 MB at 05:51:44)
  and climbs back to 284.7 → 294.9 MB (05:55:51/05:56:54). FRIDAY's own
  `memory_critical` notifications fired at 100.0% of cap (05:50:34 UTC)
  and 92.8% (05:56:54 UTC). Traced Python stayed 10.6–14.4 MB throughout.
- /health 200 in 0.76 s; token (`GET /api/livekit/token`) 200 in 1.06 s —
  fast at probe instant, on a thrashing instance. Checkout `06ff9ee6`;
  FRIDAY-Voice active. One process in the cgroup (PID 135781, 13 threads).

### Top growers — anonymous private-dirty in glibc arenas; step, not slope

Four spaced samples (30 s apart, 05:55:18–05:56:48 UTC):

| Sample | VmRSS | Anonymous (smaps) | Private_Dirty | Pss_File |
|---|---|---|---|---|
| 1 | 287,192 kB | 247,560 kB | 211,380 kB | 19,572 kB |
| 2 | 287,284 kB | 247,652 kB | 211,472 kB | 19,571 kB |
| 3 | 298,764 kB | 259,132 kB | 222,956 kB | 19,571 kB |
| 4 | 298,764 kB | 259,132 kB | 222,956 kB | 19,569 kB |

- **One +11.5 MB anonymous step** between samples 2→3 (30 s), then flat.
  Tracemalloc traced rose only +2.8 MB in the same window (11.53 →
  14.37 MB at the 05:55:51 tick) — the step is ~75% native.
- File-backed PSS flat at ~19.6 MB — growth is 100% anonymous.
- Largest anonymous mappings: `[heap]` 76,252 kB + rw-p arenas 56,544 /
  28,528 / 19,360 / 19,124 kB (13 threads). `MALLOC_ARENA_MAX=2` is
  already set, so this is **within-arena retention/fragmentation**, not
  arena count. Mapped native libs include numpy/OpenBLAS, oracledb,
  PIL, cryptography (Rust), uvloop — per-request native allocation is
  the plausible step source; naming the exact call site needs an
  allocator-level sample (e.g. `MALLOC_TRACE`/heaptrack on a staging
  copy), which this read-only probe cannot do without a restart.
- **No continuous leak slope:** flat ~271–272 MB for ~25 min of ticks,
  steps + swap oscillation. Growth past profiler-flat (~225–241 MB) to
  the ~260–300 MB working set is native arena retention reaching its
  plateau within minutes of boot (TP1 cp18: ~83% of cap at 5 min old).

### Accounting gap — closed: it is swap

Kill-time anon-rss (~100 MB) excludes swapped anonymous pages. Live
cgroup `anon` = 265,351,168 (~253 MiB, resident + swapped charge) vs
smaps Anonymous 259,132 kB resident at probe, with ~96 MiB in swap and
91 MiB swapcached. Under pressure the kernel swaps anon out before the
kill, so RSS components understate the cgroup charge by roughly the
swapped amount (~100–165 MB) — TP1's gap, explained. No unattributed
charge remains.

## Smallest fix the evidence supports (for TP1/Muse — TP10 does not implement)

1. **Periodic `malloc_trim(0)`** (ctypes `libc.malloc_trim`) on the
   existing 60 s tracemalloc-watch tick: returns retained free arena
   pages to the OS. Smallest change that directly targets the observed
   mechanism (within-arena retention with `ARENA_MAX=2` already set).
   Measure the post-trim plateau over 2 cycles before any cap talk.
2. If trim is insufficient: `MALLOC_TRIM_THRESHOLD_` /
   `MALLOC_MMAP_THRESHOLD_` tuning on the same observation protocol.
3. **No further cap raise on current evidence.** The working set
   plateaus at ~260–300 MB against a 300 MB cap; 300→400 MB would buy
   runway on the same pattern (TP1 cp18 §5), not headroom. Decide only
   on the post-trim plateau.
4. Run 28 stays HELD: an 85-min thrashing survival with peak-at-cap,
   100% notifications, and 303k anon refaults is not a calm window.
   Fire only once FRIDAY holds a settled plateau with no OOM/restart
   and no critical-pressure notifications over a full observation
   window, sequenced via Muse.

## Five states (VOI-045)

implemented NO / tested NO / merged NO / deployed NO /
production-verified NO. (This report is the WATCH258 deliverable;
run 28 has not fired.)

## Next

Muse/TP1 decision on the trim-first fix; TP10 fires run 28 only on a
settled post-fix build via Muse. Queue: VOI-045 → EARN-022 (pre-staged).

— Muse TP10
