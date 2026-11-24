# TASK-FRD-041 — FRIDAY OOM memory guard: root cause + guard

## What happened

FRIDAY (the `FRIDAY.service` uvicorn master dispatcher on Server 1) was killed by
the kernel OOM-killer on **2026-11-23 at 08:03:47 IST**, and again in identical
form the day before. systemd (`Restart=always`, 5 s) brought her back 23 s
later (08:04:15 IST); the owner-facing symptom is FRIDAY dying silently and
restarting, with no warning first.

## Root cause (evidence, read-only live probes on Server 1)

### 1. The kill was a cgroup kill, not system-RAM exhaustion

`/var/log/kern.log`, 2026-11-23 02:33:47 UTC (= 08:03:47 IST):

```
Nov 23 02:33:47 friday-universe-vnic kernel: [3444285.653251] python invoked oom-killer: gfp_mask=0x100cca(GFP_HIGHUSER_MOVABLE), order=0, oom_score_adj=0
Nov 23 02:33:47 friday-universe-vnic kernel: [3444285.722577] [  pid  ]   uid  tgid total_vm      rss rss_anon rss_file rss_shmem pgtables_bytes swapents oom_score_adj name
Nov 23 02:33:47 friday-universe-vnic kernel: [3444285.722585] [2606173]  1001 2606173   358295     9970     8146     1824         0   704512    33920             0 python
Nov 23 02:33:47 friday-universe-vnic kernel: [3444285.723296] [2704298]  1001 2704298   190493    42010    40122     1888         0   872448    15072             0 python
Nov 23 02:33:47 friday-universe-vnic kernel: [3444285.723307] oom-kill:constraint=CONSTRAINT_MEMCG,nodemask=(null),cpuset=FRIDAY.service,mems_allowed=0,oom_memcg=/system.slice/FRIDAY.service,task_memcg=/system.slice/FRIDAY.service,task=python,pid=2704298,uid=1001
Nov 23 02:33:47 friday-universe-vnic kernel: [3444285.723336] Memory cgroup out of memory: Killed process 2704298 (python) total-vm:761972kB, anon-rss:160488kB, file-rss:7552kB, shmem-rss:0kB, UID:1001 pgtables:852kB oom_score_adj:0
```

The unit file sets the cap (`systemctl cat FRIDAY.service`):

```
[Service]
ExecStart=/opt/friday_universe/venv/bin/python -m uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1
Restart=always
RestartSec=5
MemoryMax=200M
# /etc/systemd/system/FRIDAY.service.d/swapmax.conf
[Service]
MemorySwapMax=192M
```

At the kill, the cgroup was at its ceiling
(`memory: usage 204800kB, limit 204800kB, failcnt 7492923`;
`swap: usage 196368kB, limit 196608kB, failcnt 199206` — a fail count of
~7.5M means chronic saturation, not a one-off spike), and the triggering fault
was a swap-in: `do_swap_page → swapin_readahead → mem_cgroup_swapin_charge_folio`
— the victim was already deep in swap and touching a swapped-out page pushed the
charge over the cap.

### 2. Two processes shared the 200 MB cap

The OOM task table lists two python processes in the FRIDAY cgroup:

| pid | total_vm | rss | rss_anon | swapents | note |
|-----|----------|-----|----------|----------|------|
| 2606173 | ~1.4 GB | ~39 MB | ~32 MB | 33920 (~132 MB) | sibling, module load logged 04:50:22, still resident 3h13m later |
| 2704298 | ~744 MB | ~164 MB | ~157 MB | 15072 (~59 MB) | **killed** — friday.log identifies it as the API worker started 07:57:47 |

The victim grew to ~164 MB RSS within ~6 minutes of starting (LLM providers,
149 tools, embeddings, 370 conversation-history entries restored). The sibling
held ~132 MB in swap — most of the cgroup's 192 MB swap budget — while serving
nothing. **Honest bound:** the kernel dump records pid/rss only; the sibling's
exact role (stale worker vs supervisor) is not recorded in the evidence and is
not claimed here.

A regular heavyweight co-tenant in the same cgroup was observed live on
2026-11-24 ~00:08–00:21 IST: the reflex brain's `scan_imports` child
(`friday/cognition/reflex.py`, `subprocess.run(python -c walk_packages(...))`,
300 s timeout) importing every `friday` + `friday_deep` module, reaching
~135 MB RSS. It is a contributor to cgroup pressure, not proven as the 08:03
trigger — the kill predates any observation of it that morning.

### 3. Recurrence

The same cgroup, same signature, 2026-11-22 05:45:04 UTC (11:15:04 IST):
killed pid 2074982, total-vm 761932kB, anon-rss 182760kB. Two OOM kills in the
retained kern.log window (Nov 19–23); none in the rotated logs before that.

### 4. Why the existing guard missed it

FRIDAY already has a RAM watch (`ProactiveEngine.ram_critical`, system RAM
≥90%). It **did** fire, 07:59:54 IST — four minutes before the kill:

```
[2026-11-23 07:59:54] [INFO] [friday.observability.notifications]: Queued proactive notification [ram_critical/warning]: Before you ask - RAM usage is at 91.4% (0.85/0.93 GB). Might want to close a few things.
```

Two defects, both structural:

1. **Wrong metric.** It measures system RAM (956 MB). The kill threshold is
   the cgroup cap (200 MB). System RAM can sit below 90% while the cgroup is
   at 100%.
2. **Queued-only delivery dies with the process.** The `NotificationManager`
   in the production server is in-memory (persistence is only enabled in the
   CLI). The warning sat in the queue; FRIDAY died ~4 minutes later, before
   any turn surfaced it. No warning ever reached the owner.

Live corroboration that pressure persists: 2026-11-23 23:42:54 IST the engine
queued `[cpu_hot/warning] CPU is running hot at 88.0%. Top offender: kswapd0`
— the swap daemon as top CPU consumer is the signature of ongoing swap thrash.

## The guard (this PR)

`FRIDAY/src/friday/observability/proactive_engine.py` — cgroup-aware memory
watch, wired into the ProactiveEngine 30 s poll that already runs inside the
FRIDAY worker (started at server boot by `friday.api.server`):

- `read_cgroup_memory()` — stdlib-only reader for cgroup v2
  (`memory.max` / `memory.current` / `memory.swap.*`) with v1 fallback;
  `"max"` (unlimited) and missing files degrade to "no cgroup data", never raise.
- `SystemSnapshot` gains `cgroup_mem_percent`, `cgroup_mem_used_mb`,
  `cgroup_mem_limit_mb`, `cgroup_swap_percent`; `capture_snapshot()` fills them.
- Thresholds: **warning ≥75%**, **critical ≥90%**, **recovered <60%** of
  `memory.max`. On a 200 MB cap that is ~50 MB headroom at warning, ~20 MB at
  critical. The 2026-11-23 victim grew ~164 MB in ~6 minutes, so these are
  minutes of warning by design — the 30 s poll is what makes them useful.
- Warning posts a `memory_pressure` notification via the existing
  `NotificationManager` (same channel as `cpu_hot` / `ram_critical`).
- Critical posts a `memory_critical` notification **and** sends a direct
  Telegram message via the existing gateway (`friday.proactive.telegram_gateway`,
  lazy import, injectable sender for tests, daemon thread, never raises).
  The direct send is gated by the same 5-minute per-category cooldown as the
  queue post, so it fires at most once per 5 minutes while the condition holds.
- Recovery posts a `memory_recovered` info note when use drops back below 60%
  after a warning/critical (mirrors `cpu_cooled`).
- `FridayAgent.get_system_diagnostics()` exposes the four cgroup fields so the
  HUD shows the limit the kernel will enforce, not just system RAM.

Regression tests: `FRIDAY/tests/test_frd041_memory_guard.py` (12 tests) —
cgroup v2/v1/unlimited/missing parsing, threshold boundaries, warning vs
critical posting, Telegram fired once at critical and never at warning, 5-minute
cooldown dedupe, recovery, no-cgroup silence, snapshot wiring, diagnostics
exposure. Added to the `owner-workflows.yml` FRIDAY test list (REL-068
collection audit requires it).

## Verification

- Repo CI on this PR (check-runs; green required before merge).
- No local pytest was run on fetched content (execution-risk constraint);
  verification rests on repo CI.

## What remains (needs Muse's clearance on the hub)

- **Staged memory-pressure proof on the live copy**: drive the FRIDAY cgroup
  toward its cap in staging and confirm the warning fires at 75%, the critical
  Telegram arrives at 90%, and the recovery note follows — the acceptance
  criterion. Not attempted in this PR (no live writes, no restarts).
- **Deploy**: the guard ships with the next FRIDAY deploy after merge; no
  config change rides in this PR (the 200 MB cap itself is untouched — raising
  it would mask the pressure, not fix it).
- **Follow-up question for Muse**: whether the critical Telegram should be
  routed through Sentinel's API instead of the direct gateway (this PR uses
  the gateway — the fleet's established owner-phone channel). Also whether
  the lingering sibling process (2606173 pattern) deserves its own
  investigation: a worker that stays resident for hours while mostly swapped
  out consumes the swap budget a fresh worker needs.
