# TASK-FRD-064 — Checkpoint 5: the sixth kill (14:42 UTC) + read-only heap attribution names the floor

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns` (@ `fa7afb4c`).
**Probed:** 2026-11-27 ~20:40–20:46 IST (15:10–15:16 UTC), bridge Server 3 = FRIDAY-Server,
first-hand, read-only throughout.
**Clearance:** WATCH226 §D5 (hub #2045 comment 7221115974, 20:12 IST) RULED **PROCEED** —
read-only heap attribution (process memory stats, no code change, no restart) is covered by
standing clearance 7200564540. Any agent-code change or service restart needs its own ruling.
**Board on live main `fa7afb4c`:** CLAIMED / owner `muse_tp1` / pr null / P1.
Board note (unchanged, correction still owed in the coordinator's board PR):
the record's `branch` field reads `musetp1/task-frd-064-oom-kill-root-cause`;
the real branch is `musetp1/task-frd-064-oom-kills-chat-turns` (verified via
ref read-back: head `8a98249a` before this checkpoint).

## 1. TP10's 20:37 IST report VERIFIED first-hand — SIXTH kill today

Journal (`FRIDAY.service`, Server 3), OOM-killer lines today:

- 00:56:14 / 06:21:02 / 08:07:14 / 09:37:04 / 13:22:05 / **14:42:55 UTC** — six distinct
  kills (06:21 is logged twice at the same second = one event, as in cp2).
- The 14:42 kill record: `14:42:52 "A process of this unit has been killed by
  the OOM killer"` → `14:42:55 "Failed with result 'oom-kill'"` →
  `"Consumed 2min 1.516s CPU time, 200.0M memory peak, 181.9M memory swap
  peak"`. RAM cap hit (200M); swap 181.9M of the 192M cap — both caps
  effectively exhausted again, as at 13:22 (200.0M / 192.0M).
  The killed activation (PID 106781) lived 13:22 → 14:42 UTC (~80 min) —
  the shortest-lived activation of the six; the kill interval is shrinking
  (09:37→13:22 was ~3h45m).

## 2. The kill sequence — 18 seconds from warn to dead, same shape as 13:22

Monitor lines (cgroup RAM % of 200M), PID 106781, 14:30–14:42 UTC:

- 14:37:33 warn 77.4% (154.8 MB) → recovered range, no critical.
- 14:42:34 warn 81.7% (163.3 MB) → **14:42:52 OOM kill — 18 s later, with
  no critical line in between.**

**Spike magnitude (estimate, basis stated):** RAM 163.3 → 200M (+37 MB) and
swap ~114 → 181.9M (+~68 MB) inside 18 s — on the order of **~105 MB of new
anonymous memory in under 18 s**. Swap basis: cp4 measured this activation's
VmSwap at 114,196 kB at ~14:17 UTC; the killed activation's swap peak hit
181.9M. This repeats the 13:22 shape (≥100 MB in <23 s) — twice in one day
the spike outruns the monitor, so the guard (warn 75% / critical 90%, ~16-min
cadence) cannot catch this kill shape. The fix must either react in seconds
or add headroom to both caps.

**Correlation noted, not proven:** Memora remote failures fill the minutes
before the kill — 14:37:17 remote recall exceeded the 5.0s join deadline
("answering from the local store"); 14:38:52 and 14:39:53 cursor read failed
(URLError) + "Memora event consumption did not complete"; 14:40:16 remote
interaction write error (URLError) + "Memora session capture failed". The
08:07 kill also followed heavy Inference/Memora-path activity (cp2). Lead for
the fix investigation: what allocates on the Memora remote-recall timeout /
cursor-read retry paths — candidate spike source, unproven.

## 3. The 14:42 kill was NOT during a chat turn

Journal POST lines, 13:22 → 14:42 UTC (8 total):

- 13:38:52–13:38:53 — three `POST /v1/chat/completions` 405 Method Not
  Allowed from 140.245.243.168 (Server 2's public IP — a prober hitting the
  wrong path, not a turn).
- 13:57:27 and 14:00:24 — the only real turns: `POST /api/chat` 200 OK from
  localhost. Last turn **42 minutes before the kill**.

Third consecutive kill (09:37, 13:22, 14:42) with no turn in flight. The "in
chat turns" premise is not supported by the evidence; the driver is the idle
floor plus a fast spike.

## 4. New activation — the floor reproduces exactly

`FRIDAY.service`: active, MainPID **110165**, NRestarts **3**, active since
14:43:00 UTC. `MemoryCurrent=60,436,480` (~57.6 MB) /
`MemorySwapCurrent=100,659,584` (~96.0 MB) / `MemoryMax=209,715,200`
(200M) / `MemorySwapMax=201,326,592` (192M) at ~15:10 UTC — total footprint
~153.6 MB, the same ~150–160 MB floor as cp2/cp3/cp4. `/health` 200 in 1.08 s.

`/proc/110165` at ~15:12 UTC: `VmRSS 90,668 kB`, `VmSwap 96,592 kB`,
`VmSize 1,198,876 kB`, `VmPeak 1,218,108 kB`, `VmData 321,500 kB`,
**13 threads** (was 21 in cp4's snapshot of the previous activation —
thread count varies by activation; recorded, not a trend).
`smaps_rollup`: `Rss 90,668`, `Pss 70,628`, `Shared_Clean 35,164`,
`Private_Dirty 50,532`, `Anonymous 50,832`, `Swap 96,592` — anonymous
total ≈ 50.8 + 96.6 = **~147 MB**.

## 5. Heap attribution (read-only, WATCH226 §D5) — the floor is anonymous mmap, not the heap

`/proc/110165/smaps` classified over all 536 regions (~15:13 UTC), totals in MB:

| class | Size (virt) | Rss | Anon | Swap | Anon total (Rss+Swap) |
|---|---|---|---|---|---|
| anon-mmap (no pathname) | 1030.0 | 35.3 | 35.3 | 64.1 | **~99.4** |
| [heap] | 41.8 | 13.4 | 13.4 | 27.9 | **~41.3** |
| file-backed (.so / python3.10 / libs) | ~90 | ~35 | ~0.5 | ~1.5 | ~2 |

- Anonymous total 147.4 MB = anon-mmap 99.4 (**~67%**) + heap 41.3
  (**~28%**) + ~6.7 MB stacks/file anon. The heap is again ~42 MB virtual
  (13.4 resident + 27.9 swapped) — it is not the floor.
- Top anonymous regions: the heap (13.4 MB anon, 27.9 swapped), then a dozen
  unnamed `rw-p` regions of 1.5–4.8 MB anon each (one: 2.4 MB anon + 25.6 MB
  swapped), all in the `0x7c86…` range — dozens of MB-scale anonymous
  mappings with no pathname. These are glibc malloc mmap regions and/or large
  Python/numpy allocations; **which objects own them is not visible from
  /proc alone.**
- File-backed note: `libscipy_openblas64` 23.0 MB virtual but 1.2 MB RSS;
  `_multiarray_umath` 9.5 MB virtual, 2.8 MB RSS — scipy/numpy are loaded
  but their file-backed pages are small and mostly unresident; they are not
  the floor either.

**Conclusion:** a heap-only fix cannot move the floor materially — cp3 already
exonerated `_conversation_history`, and the heap is only ~28% of the anonymous
footprint. The fix must address what holds the ~99 MB of anonymous mmap, or
add headroom, or catch the ~100 MB / <20 s spike in seconds.

## 6. What the fix needs now

1. **Per-object attribution needs its own ruling.** tracemalloc / gc /
   malloc introspection requires a code change or a restart with env — NOT
   covered by WATCH226 §D5. Ask: coordinator ruling for an
   observation-only restart with tracemalloc enabled, or an in-process
   snapshot endpoint. Until then, attribution stops at the smaps level and
   no fix PR can name the allocating code.
2. **Lead to chase:** the Memora remote-failure window before the 14:42 kill
   (§2) — check what allocates on remote-recall timeout / cursor-read
   retries. Also still carried: the `goal_loop.py:273` `JSONResponse`
   reply-extraction bug (real defect, on the 08:07 kill path).
3. **Constraint stands:** any in-process guard must react in seconds, or the
   fix must add headroom to BOTH caps (RAM 200M and swap 192M both hit at
   both kills today).
4. VOI-045 (TP10) firing stays HELD until the fix deploys (WATCH215 §3) —
   no change; TP10's cp9 (hub 7221647545) confirms the sixth kill from its
   side, and #2142 merged `fa7afb4c`.
5. Board correction still owed (coordinator board PR): FRD-064 `branch`
   field reads the wrong branch name.

## 7. Five states

- Implemented: NO. Tested: NO. Merged: NO. Deployed: NO. Production-verified: NO.
- Investigation (this checkpoint): DONE — numbers above are first-hand live reads.

## 8. Queue

- FRD-064 (head) → TASK-EARN-017 (AVAILABLE / muse_tp1) → TASK-EARN-015
  (AVAILABLE / muse_tp1, owner-gated Contra account step) → TASK-REL-069
  (AVAILABLE / muse_tp1). Hold ≤ 2 (1 + 1 pre-staged).
- WEB-007 (PR #2075) + FRD-062 (PR #2108) both verified MERGED on live main.
- Hub read through comment 7221679236 (TP14 EARN-044 COMPLETE, 20:38 IST);
  main `fa7afb4c`. No P0, no new assignment, no verdict naming for TP1.
  WATCH226 + BE 20:32 read in full; #2142 merged `fa7afb4c` (TP10 VERIFIED).
