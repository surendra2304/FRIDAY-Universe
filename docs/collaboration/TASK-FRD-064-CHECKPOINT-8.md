# TASK-FRD-064 — Checkpoint 8: ninth + tenth OOM kills; Python heap exonerated, growth is native anonymous heap

Filed: 2026-11-28 ~00:25 IST (2026-11-27 ~18:55 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 7 (29a12c45); this file is the checkpoint-8 commit.

## 1. Two more kills since checkpoint 7 — kill interval now ~16 min

Journal (FRIDAY.service, Server 3, read first-hand via bridge run_shell):

- **Ninth kill — 2026-11-27 18:33:35 UTC, PID 116156.** `FRIDAY.service: A process of this unit has been killed by the OOM killer.` Main process exited, code=killed, status=9/KILL, result `oom-kill`.
- **Tenth kill — 2026-11-27 18:49:13 UTC, PID 116213.** Same signature.
- Observation-restart PID 116459 (booted 18:49:32 UTC) alive at 18:51–18:52 UTC, already over the cap (see §3). Next kill imminent at filing time.
- Kill cadence is accelerating: six kills across the day to 14:42 UTC, seventh 16:19 UTC, eighth 17:56 UTC, ninth 18:33 UTC, tenth 18:49 UTC.

## 2. Tracemalloc across the kills — Python heap exonerated

Tick 2026-11-27T18:50:33Z (PID 116459, ~60 s after boot):

- `rss_mb=222.5 traced_mb=8.21 traced_peak_mb=8.59`
- Largest tick diffs, all < 2 MB: threading.py +1.63 MB, runpy.py +0.74 MB, threading.py +0.51 MB, compat.py +0.25 MB, server.py +0.15 MB, importlib < 0.15 MB.
- **Finding: traced Python heap is 8.2 MB while RSS is 222.5 MB. The growth is NOT Python objects.** Tracemalloc cannot see it; the allocator is native (C-extension / library / malloc-arena memory).

## 3. smaps / pmap attribution (PID 116459, 18:51–18:52 UTC, first-hand)

smaps_rollup:

- VmRSS 227,824 KB (~222.5 MB) — over the 200 MB cap; VmSwap 19,816 KB; VmData 375,036 KB; VmSize 1,174,392 KB.
- **Anonymous: 188,472 KB (83% of RSS).** Private_Dirty 150,100 KB. Shared_Clean 34,688 KB, Private_Clean 43,036 KB.
- AnonHugePages 0; no hugetlb.

pmap -x (top RSS regions, all `[ anon ]`, rw):

- 46,048 KB RSS / 57,260 KB virt at 0000000018cce000 — main heap arena.
- Then 26,052 / 17,980 / 8,572 / 6,744 / 6,676 / 6,560 / 6,056 / 6,048 / 5,832 / 5,032 KB RSS across separate anon regions.
- **No single file-backed mapping of note; no single culprit region.** The anon heap is spread across dozens of 5–26 MB arenas plus one 46 MB arena — consistent with glibc malloc arenas / native-library allocations, not one leaked Python structure.

## 4. Growth happens at boot, not during chat turns

PID 116213 timeline (from its own memory-pressure notifications):

- Booted 18:33:55 UTC (embeddings factory init logged at boot, as at every restart).
- 18:34:25 UTC: 162.3 MB (81.2% of cap) — ~30 s after boot.
- 18:35:25 UTC: 199.8 MB (99.9%) — ~90 s after boot.
- Pinned at ~100% (18:40:40, 18:45:49 notifications) until the 18:49:13 kill.
- **~38 MB growth in ~60 s immediately after boot, then flat at the cap.** No chat turns in the window; only `/api/memory/browser` GETs at 18:28–18:29 UTC on the prior PID. The "OOM kills under chat turns" framing is now doubtful: the kills are a boot-time growth + cap problem, and turns are incidental.
- Boot-time correlation (NOT attribution): every restart logs `friday.memory.embeddings.factory: Initializing Google Gemini Cloud Embedding Provider (model: gemini-embedding-2, dimension: 768)` within seconds of start. It is the prime suspect for a subsystem bisect, not a proven cause.

## 5. States

- implemented: tracemalloc watch live (checkpoint 7) — YES
- tested: watch verified live across two kills — YES
- merged: no (checkpoint docs only, no code PR yet)
- deployed: watch deployed on Server 3 via the observation restart — YES
- production-verified: NO — the service is still being killed every ~16 min; acceptance (no OOM kills under chat turns, stable service) is not met.

## 6. Fix PR — NOT fileable yet, honestly blocked on allocator identification

WATCH235 directed "file the diffs + fix PR". The diffs are filed here (§2: the tracemalloc diffs show nothing material — that IS the result). A fix PR now would be guessing at the allocator. Next probe, in order:

1. Native-heap attribution at boot: malloc-level sampling (e.g. `PYTHONMALLOC=malloc` + gdb/heap profiler, or jemalloc profiling) across the first 90 s after a restart, to name the allocating library.
2. Subsystem bisect, cheapest first: boot-time embeddings-init suspect — test whether the ~38 MB post-boot jump tracks the embeddings provider init (staging/diagnostic run, no service behaviour change).
3. Only then: fix PR against the identified allocator, with a live stability sweep as proof.

## Evidence sources (all first-hand this run)

- Bridge run_shell, Server 3: `journalctl -u FRIDAY.service --since "2026-11-27 17:56:00 UTC"` (kill lines 18:33:35 + 18:49:13 UTC); `tail /tmp/friday_tracemalloc.log` (tick 18:50:33Z); `/proc/<pid>/status`, `smaps_rollup`, `pmap -x` on PID 116459.
- Board on main a85c9d13: TASK-FRD-064 CLAIMED / muse_tp1; TASK-FRD-062 MERGED / pr 2108.
- Hub #2045 read through comment 7225862022 (TP6, 18:46:51Z); WATCH235 (7225676870) + Burn Enforcer 00:20 (7225856022) read in full. No new assignment for TP1; no P0.
