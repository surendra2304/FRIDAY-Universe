# TASK-FRD-043 — FRIDAY OOM memory guard: live proof

## Task

Deploy the FRD-041 OOM memory guard live with staged pressure proof and
Telegram delivery. Clearance: WATCH196 §3 (hub #2045 comment 7208049564) —
conditionally granted to Muse 15: staged pressure proof on the FRIDAY
service + Telegram delivery, under standing clearance 7200564540 (own-task
live verification). Any production restart beyond the task's own service
needs a fresh ruling.

Acceptance (board): "Guard live on S1, staged memory-pressure proof and
Telegram delivery evidenced." Note: the live FRIDAY service no longer runs
on Server 1 — S1 `FRIDAY.service` is disabled/inactive (verified 2026-11-27
~09:00 IST, no journal entries, nothing on :10000) and the live service
runs on FRIDAY-Server (AWS 15.134.130.145, bridge server 3). The proof runs
where FRIDAY lives; no agent is moved between servers.

## Finding 1 — the FRD-041 guard as merged could never fire (verified live)

`FRIDAY/src/friday/observability/proactive_engine.py` (merged via PR #1548)
reads the cgroup through `CGROUP_BASE = "/sys/fs/cgroup"` — the hierarchy
root — and never resolves the process's own cgroup. On the live host the
root carries no `memory.*` files at all:

- `/sys/fs/cgroup/memory.current`: No such file or directory (same for
  `memory.max`, `memory.swap.*`), on FRIDAY-Server (verified via bridge
  run_shell, server 3).
- The service cgroup DOES have them:
  `/sys/fs/cgroup/system.slice/FRIDAY.service/memory.max` = 209715200,
  `memory.current` live, `memory.swap.max` = 201326592.
- The guard's own reader, executed with the production venv on
  FRIDAY-Server against the live checkout: `read_cgroup_memory()` returned
  `None`, `percent: None`. The guard degrades silently to "no cgroup data",
  so `memory_pressure_warning()` / `memory_pressure_critical()` are always
  False and no warning, critical, or Telegram can ever fire.

Corroboration from the live log
(`/opt/friday_universe/FRIDAY/logs/friday.log`, FRIDAY-Server):

- ZERO `memory_pressure` / `memory_critical` / `memory_recovered` entries,
  ever — while the cgroup hit its cap 12,138 times
  (`memory.events`: `max 12138`, `oom 0`, `oom_kill 0`).
- The kernel OOM-killed FRIDAY in this same cgroup at **2026-11-27 00:56:12
  UTC** (`kern.log`: `oom-kill:constraint=CONSTRAINT_MEMCG`,
  `oom_memcg=/system.slice/FRIDAY.service`, killed pid 78229, anon-rss
  194 MB). systemd restarted her at 00:56:19 UTC (current worker pid 78303).
  The exact failure FRD-041 was built to prevent happened again this
  morning, with no warning — because the guard was blind.
- Cgroup use observed this run: 46.9 MB (~22%) at 03:32 UTC, 56.6 MB
  (~27%), a spike to 179.1 MB (**85.4% — past the 75% warning bar**) with
  no warning fired, then 42.1 MB. `memory.swap.current` ~122–130 MB of
  192 MB (60%+): chronic swap pressure continues.

## The fix (this work PR)

`read_cgroup_memory()` now resolves the process's OWN cgroup from
`/proc/self/cgroup` first (v2 `0::` line; v1 `memory` controller fallback)
and reads the files under `<CGROUP_BASE>/<own-path>`; the bare hierarchy
root is kept last so dev machines and containers without a service cgroup
behave exactly as before. No threshold, cooldown, Telegram, or snapshot
logic changed.

- `FRIDAY/src/friday/observability/proactive_engine.py`: new
  `_own_cgroup_relpath()` and `_cgroup_file_bases()`; `_read_cgroup_int()`
  searches each candidate base for each relative name; `read_cgroup_memory()`
  also tries the bare v1 names (`memory.usage_in_bytes`, …) for the
  `<base>/memory/<own>` layout.
- `FRIDAY/tests/test_frd041_memory_guard.py`: 6 new tests — v2/v1/missing
  own-cgroup parsing; own-cgroup read; own-cgroup beats a root decoy
  (root 1 GB/10% vs service 200 MB/75% → 75.0); missing root files but
  present service files (the exact production shape → 90.0).

## Verification so far

- **Tests:** `tests/test_frd041_memory_guard.py` — **18 passed in 1.09 s**
  on FRIDAY-Server with the production venv (`/opt/friday_universe/venv`),
  from a scratch clone of this branch
  (`/tmp/frd043-test`, head `b3baadca`).
- **Live in-cgroup read (fixed code):** a verifier process using the
  branch code was moved into `/system.slice/FRIDAY.service` via
  `cgroup.procs` and read
  `CgroupMemory(limit_bytes=209715200, used_bytes=51900416,
  swap_limit_bytes=201326592, swap_used_bytes=122122240) percent=24.7`.
  Before the move (session cgroup, unlimited) it read `limit_bytes=None,
  percent=None`. The fixed reader returns the service's real numbers
  in-process. Verifier killed after; cgroup procs back to the worker alone.
- **Branch:** `muse15/task-frd-043-oom-memory-guard` fast-forwarded from
  `b9a4c8cf` (a board-PR merge, 698 behind main, zero unique commits) to
  current main `091bc349`, then the fix pushed as `b3baadca` (parent
  `091bc349`, 2 files). Verified via ls-remote.

## Staged pressure proof — [TO BE FILLED AFTER THE RUN]

Planned stages (allocator process moved into the FRIDAY.service cgroup;
killed instantly to release pressure; abort if `memory.current` > 185 MB):

1. Baseline (~25%): no alert expected.
2. ~77% (allocate ~105 MB): `memory_pressure` warning queued, no Telegram.
3. ~92% (allocate ~135 MB total): `memory_critical` queued AND direct
   Telegram sent; log line + gateway send recorded.
4. Release all (<60%): `memory_recovered` info note.

Evidence to record: `memory.current` at each stage, the exact log lines
with timestamps, and the Telegram send (gateway log / message record).
