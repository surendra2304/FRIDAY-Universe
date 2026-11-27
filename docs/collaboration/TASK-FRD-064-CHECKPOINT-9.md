# TASK-FRD-064 — Checkpoint 9: eleventh + twelfth OOM kills; native heap identified as glibc malloc arenas

Filed: 2026-11-28 ~01:30 IST (2026-11-27 ~19:53 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 8 (65800fa1); this file is the checkpoint-9 commit.

## 1. Two more kills since checkpoint 8 — twelfth kill at 19:51 UTC, interval now ~16 min

Journal (FRIDAY.service, Server 3, read first-hand via bridge run_shell):

- **Eleventh kill — 2026-11-27 19:35:36 UTC, PID 116459.** `FRIDAY.service: A process of this unit has been killed by the OOM killer.` Main process exited, code=killed, status=9/KILL, result `oom-kill`. Restart counter 6; new PID 117526 started 19:35:41 UTC.
- **Twelfth kill — 2026-11-27 19:51:13 UTC, PID 117526.** Same signature. Restart counter 7; new PID 118075 started 19:51:18 UTC.
- Kill tally today (UTC): 00:56, 06:21, 08:07, 09:37, 13:22, 14:42, 16:19, 17:56, 18:33, 18:49, 19:35, 19:51 — **twelve kills**. Last three gaps: 46 min, 16 min, 16 min. Interval is compressing.
- At 19:53:21 UTC (~2 min after the twelfth restart) PID 118075 already shows MemoryCurrent 202,256,384 bytes = **192.9 MB of the 200 MB cap (96.5%)**. A thirteenth kill is imminent at filing time.

## 2. Boot profile confirmed again — the floor is set at startup, zero chat turns

PID 117526 timeline (its own memory-pressure notifications):

- Booted 19:35:41 UTC; tracemalloc watch started 19:35:56 UTC.
- 19:37:26 UTC: 191.9 MB (96.0% of cap) — ~90 s after boot.
- 19:42:27 UTC: 199.9 MB (100.0%). 19:47:54 UTC: 199.9 MB (99.9%).
- Pinned at the cap until the 19:51:13 kill. No chat turns in the window.
- **Fresh process reaches ~193–200 MB within ~90–120 s of start, then sits pinned at the cap until a small spike trips the cgroup OOM.** Same shape as checkpoint 8 (PID 116213: 162 MB at +30 s, 199.8 MB at +90 s). The "OOM kills under chat turns" framing is retired: this is a boot-time allocation floor + cap problem; turns are incidental.

## 3. Native-heap attribution — the allocator structure is now identified

smaps analysis, PID 117526, ~19:49–19:50 UTC (first-hand, full parse written to /tmp/frd064_maps.txt on Server 3):

- 558 regions, 119 anonymous regions.
- **Anonymous RSS total: 150.5 MB; anonymous Swap total: 32.0 MB. Anonymous virtual reservations: 1,336.1 MB.**
- `[heap]` (main arena): size 64.7 MB, RSS 41.5 MB, anon 41.5 MB, swap 22.9 MB.
- File-backed RSS total: 39.0 MB (all .so/code mappings).
- Tracemalloc tick (PID 116459 era, 18:50:33Z): `rss_mb=222.5 traced_mb=8.22 traced_peak_mb=8.59` — Python heap still ~8 MB. **Python heap exonerated a third time.**

The large anonymous regions are **glibc per-thread malloc arenas**, not individual allocations:

- Repeated pattern in /proc/PID/maps: `---p` (PROT_NONE) reservations of exactly 63.9–64.0 MB — glibc's 64 MB per-arena virtual reservation (HEAP_MAX_SIZE on 64-bit) — interleaved with 8.0 MB `rw-p` heap segments and 3–8 MB `rw-p` regions.
- 13–20 threads observed (20 at 19:48 UTC, 13 at probe-4 time) → up to ~20 arenas × 64 MB virtual ≈ the 1,336 MB anon virtual total. The `---p` guard regions carry ~0 RSS; the RSS lives in the touched `rw-p` arena segments.
- **No jemalloc, no tcmalloc, no torch** in the maps. numpy: 31 .so files; oracledb: 20 .so files. Largest file-backed RSS: oracledb arrow_impl 23.8 MB, libsqlite3 7.7 MB, _sqlite3 6.6 MB, cryptography _rust 6.2 MB, multidict 5.9 MB.
- Histogram of anon regions by virtual size: 16 in 32–128 MB, 25 in 8–32 MB, 34 in 1–8 MB, 44 under 1 MB.
- Top anon RSS regions (non-heap): 26.0 MB size / 19.8 MB RSS, 15.0 / 12.8, 13.6 / 10.7, 9.1 / 8.9, 9.0 / 8.6, 8.0 / 7.7, 7.0 / 6.7, 7.0 / 6.2, 6.0 / 5.8, 6.0 / 5.3, then a long tail of 5.0 / 3–5 MB regions.

**Attribution, stated precisely:** the ~150 MB anonymous RSS is ~41.5 MB main-heap + ~109 MB spread across per-thread malloc arenas. The arena *structure* is identified; the *owning allocations inside the arenas* (which library / call-site fills them at boot) are still unidentified — smaps cannot see that, and tracemalloc cannot see native allocations. Adjacency in the maps (anon regions sitting after oracledb/arrow_impl, pillow libjpeg, uvloop, sqlite3, multidict mappings) is address-order coincidence, not evidence of ownership; not claimed.

## 4. What this rules in / out for the fix

- **Ruled out:** Python object leak (tracemalloc ~8 MB across three probes); `_conversation_history` (checkpoint 3); Memora recall/cursor/retry (checkpoint 6); goal_loop JSONResponse (fixed on main, checkpoint 6); single leaked structure (no single culprit region — the anon heap is spread across ~119 arena regions).
- **Ruled in:** glibc malloc arenas as the container. Two candidate fix directions, in order of cheapness:
  1. **Cap arena count / force trimming via env:** `MALLOC_ARENA_MAX=1` (or 2) + `MALLOC_TRIM_THRESHOLD_=<small>` on the FRIDAY.service environment, env-gated like the tracemalloc watch. If the ~109 MB arena spread is mostly per-thread arenas holding freed-but-unreturned memory, this directly lowers the floor. Testable with one observation restart + the same smaps probe.
  2. **Identify the owning allocation:** malloc-level sampling across the first 90 s after boot (e.g. `PYTHONMALLOC=malloc` + heap profiler, or an arena-content dump) to name the library that fills the arenas at startup. Boot-time correlation (NOT attribution): every restart logs the embeddings-factory init (`gemini-embedding-2`, dimension 768) within seconds of start (checkpoint 8 §4).
- **No restart was performed this run** beyond systemd's own auto-restarts after the kills. Direction (1) needs a coordinator ruling + an observation restart; direction (2) needs a profiler run against a live boot. Neither is taken unilaterally — service restarts are coordinator/owner-gated.

## 5. Board note (correction for the next board PR)

Board on main dbaf142a: TASK-FRD-064 CLAIMED / owner muse_tp1 / **branch musetp1/task-frd-064-oom-kill-root-cause** / pr null. The branch field is stale: the working branch carrying checkpoints 1–9 is **musetp1/task-frd-064-oom-kills-chat-turns** (remote head 65800fa1 before this commit, verified via ls-remote this run). Correction rides the next board PR; no separate board PR from TP1.

## 6. States

- implemented: tracemalloc watch live (checkpoint 7) — YES
- tested: watch + smaps attribution verified live across three kills — YES
- merged: no (checkpoint docs only, no code PR yet)
- deployed: watch deployed on Server 3 via the observation restart — YES
- production-verified: NO — twelve kills today; acceptance (no OOM kills under chat turns, stable service) is not met.

## 7. Fix PR — still NOT fileable, honestly blocked on one of two gates

Either (a) the owning allocation is identified (direction 2 above), or (b) the coordinator rules that an env-gated arena-cap trial (direction 1) may be tested via an observation restart, with the smaps probe as the before/after evidence. A fix PR guessing at the allocator would repeat the checkpoint-8 error. Next probe, in order:

1. Coordinator ruling on the MALLOC_ARENA_MAX / trim-threshold trial.
2. Arena-content identification across a boot window (profiler or allocation-site sampling).
3. Only then: fix PR against the identified cause, with a live stability sweep as proof.

## Evidence sources (all first-hand this run)

- Bridge run_shell, Server 3: journalctl kill lines 19:35:36 + 19:51:13 UTC; `systemctl show FRIDAY.service` (NRestarts 6→7, PIDs 117526→118075, MemoryCurrent 209,313,792 → 202,256,384); /proc/PID/status + smaps_rollup + full smaps parse (PID 117526, /tmp/frd064_maps.txt); /proc/PID/maps adjacency attribution (/tmp/frd064_attr.txt); /tmp/friday_tracemalloc.log tail; process environ (FRIDAY_TRACEMALLOC=1, interval 60 s).
- Hub #2045 read through comment 7226819320 (M18, 19:44:08Z); WATCH237 (7226239723) + Burn Enforcer 00:59 (7226631918) read in full. No TP1 direction; no P0; no verifier assignment for TP1. BE 00:59 §E: hourly self-check posts abolished — this run posts one status line only, per the driver directive.
- Board on main dbaf142a: TASK-FRD-064 CLAIMED / muse_tp1 (§5). Open PRs: 45, none headed musetp1 (verified via pulls list this run).
- Usage 11% of free weekly limit (subscription-status, verified this run; resets Dec 2, 17:43 IST).
