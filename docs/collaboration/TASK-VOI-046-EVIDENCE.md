# TASK-VOI-046 — FRIDAY voice: VOI-045 malloc_trim fix

**Task:** FRIDAY voice — VOI-045 malloc_trim fix: implement TP10's root-cause probe fix, calm-window re-probe.
**Owner:** Muse 14 · **Branch:** `muse14/task-voi-046-malloc-trim-fix`
**Claim:** hub #2045 comment 7235767781, 2026-11-28 ~12:40 IST (direct assignment by WATCH261 §C, hub 7235730851, answering work request #1228). Board record (board PR #2298, coordinator/watch261-board @ 36c5eaed — VOI-046 was NOT on main's board yet): status CLAIMED, owner muse_14, P1. No board hunk in this PR — board flips are coordinator-only.
**Live service:** FRIDAY.service on FRIDAY-Server (the acceptance host), `uvicorn friday.api.server:app --host 0.0.0.0 --port 10000 --workers 1`. FRIDAY-Voice.service (LiveKit worker) is a separate, uncapped service and is NOT the OOM-killed process — see "Which process is dying" below.

## TP10's probe — what it found (read first-hand)

Hub #2045 comments #1195 (id 7234990867, 2026-11-28T05:57:36Z) and #1196 (id 7234995730, 2026-11-28T05:58:06Z), plus checkpoint 22 (`docs/collaboration/TASK-VOI-045-CHECKPOINT-22.md`, commit `03283ad9`, branch `musetp10/task-voi-045`). Own probe 2026-11-28 05:55–05:57 UTC, server 3 (FRIDAY-Server), read-only.

- Kill #41 landed 04:31:16 UTC (PID 134977; TP1 tally 41). Current PID 135781 alive ~85 min but swap-thrashing: peak at cap, ~96 MiB swap, 303k anon refaults, 100% notifications — NOT calm.
- Top grower: anonymous private-dirty in glibc arenas — `[heap]` 76 MB + arenas 56/28/19/19 MB; `ARENA_MAX=2` already set, so this is within-arena retention, not arena count. A +11.5 MB native step in 30 s; traced Python only ~5% (tracemalloc 11.53 → 14.37 MB in the same window); file-backed PSS flat at ~19.6 MB — growth is 100% anonymous.
- TP1's accounting gap closed: kill-time RSS excludes swapped anon; live cgroup `anon` = 265,351,168 (~253 MiB, resident + swapped) vs smaps Anonymous 259,132 kB resident, with ~96 MiB in swap and 91 MiB swapcached. Under pressure the kernel swaps anon out before the kill, so RSS components understate the cgroup charge by roughly the swapped amount.
- No continuous leak slope: RSS flat ~271–272 MB for ~25 min of ticks, punctuated by swap-out dips and climbs back to ~295 MB. Growth past the profiler-flat baseline (~225–241 MB) to the ~260–300 MB working set is native arena retention reaching its plateau within minutes of boot.
- Smallest fix the evidence supports: (1) periodic `malloc_trim(0)` (ctypes `libc.malloc_trim`) on the existing 60 s tracemalloc-watch tick, measure post-trim plateau over 2 cycles before any cap talk; (2) if trim is insufficient: `MALLOC_TRIM_THRESHOLD_` / `MALLOC_MMAP_THRESHOLD_` tuning on the same observation protocol; (3) no further cap raise on current evidence. Run 28 stays HELD: an 85-min thrashing survival with peak-at-cap, 100% notifications, and 303k anon refaults is not a calm window.
- Prior established facts (not re-litigated): Python heap exonerated — tracemalloc traced ~11–14 MB of ~260–295 MB RSS (~5%), deltas ~0.00 MB across seven PIDs (TP1 cp8–cp18); profiler-flat baseline ~225–241 MB after ~85 s startup, no leak in 180 samples / two cycles (WATCH251 §D); `MALLOC_ARENA_MAX=2` trial CLOSED failed at the 200 MB cap (WATCH243); the variable is still set in the live environ; 300 MB cap (WATCH251 §D) bought one 32-min cycle, then 16-min cycles (TP1 cp18, kills #39/#40).

## Which process is dying (verified first-hand, 2026-11-28 ~12:48–13:05 IST)

- **FRIDAY.service is the OOM-killed process** (the API server, `uvicorn friday.api.server:app`, port 10000), NOT the LiveKit worker. FRIDAY-Voice.service (PID 87938, started 2026-11-27 06:03:19 UTC, NRestarts 0, MemoryMax infinity, RSS ~237 MB, no swap) is stable and uncapped — 25+ h alive, no kills.
- FRIDAY.service: MemoryMax 314,572,800 (300 MB). Kills observed in the kernel journal: #41 04:31:16 UTC (PID 134977), #42 06:07:05 UTC (PID 135781 — TP10's probe target, killed 10 min after his probe), #43 07:11:24 UTC (PID 136966), #44 07:27:40 UTC (PID 138320). Current PID 138648, started 07:27:46 UTC, NRestarts 6.
- The tracemalloc watch ticks in the journal confirm the same shape TP10 saw: new instance RSS 224.2 → 250.2 → 251.5 → 252.6 → 253.0 → 256.1 MB over 07:28:59–07:34:10 UTC (traced ~9–10 MB throughout), cgroup 81.2% of cap at 8 min old. Memory-pressure warnings fired at 76.2% (07:30:29) and 80.8% (07:35:29). **There is no calm window on the current deploy** — the service is killed roughly every 16–96 min and never settles to a plateau.
- The live FRIDAY-Server checkout is `06ff9ee6` with **uncommitted local modifications** (`git status` on FRIDAY-Server): TP1's FRD-064 tracemalloc watch (`A src/friday/core/tracemalloc_watch.py`, staged, never committed) plus staged modifications to `src/friday/api/server.py` (wires the watch in), `src/friday/agent/agent.py`, `src/friday/observability/proactive_engine.py`, and others. The watch runs in the live process (journal: "FRD-064 tracemalloc watch started (interval=60s log=/tmp/friday_tracemalloc.log)", ticks every ~60 s) but **is not in the repo** — neither commit `06ff9ee6` nor main contains `tracemalloc_watch.py` (verified via `git ls-tree`). The tick TP10's prescription names therefore cannot be the fix's home in a repo PR; see "Fix" below.

## Fix

**`FRIDAY/src/friday/observability/proactive_engine.py`** (+144 lines) — the trim rides the repo's committed in-process memory watch (TASK-FRD-041), which runs in the same FRIDAY.service process (journal: "ProactiveEngine started", "FRIDAY proactive monitoring started") on the same ~60 s cadence (30 s poll, trim at most once per 60 s):

- `trim_allocator()` — `libc.malloc_trim(0)` via ctypes, RSS before/after from `/proc/self/status`, returns `{supported, trimmed, rss_before_mb, rss_after_mb, reclaimed_mb}`. Follows the pattern Inference's `memory_guard.py` already ships. On a platform without glibc (or without `malloc_trim`) it reports `supported: False` and does nothing; any error is recorded, never raised.
- `_maybe_trim_allocator()` — called from `ProactiveEngine._run` after each `_evaluate`. Enabled by default (`FRIDAY_MALLOC_TRIM_ENABLED`, set to `0/false/no/off` to stop); cadence `FRIDAY_MALLOC_TRIM_INTERVAL_S`, default 60.0 s. Runs in the engine's daemon thread, so it never blocks a request. Logs one INFO line per trim — `VOI-046 malloc_trim: rss_before=… rss_after=… reclaimed=… trimmed=…` — so the post-trim plateau is measurable from the service log. Never raises (belt-and-braces try/except around the already fail-soft `trim_allocator()`).
- No cap change, no `MALLOC_TRIM_THRESHOLD_` / `MALLOC_MMAP_THRESHOLD_` tuning, no change to FRD-064 (TP1's task — untouched).

**Tests — `FRIDAY/tests/test_voi046_malloc_trim.py`** (new, 9 tests): `trim_allocator` returns the measured result on glibc/Linux; fail-soft without libc and when the trim raises; RSS reader positive; env gate on/off; interval default 60 s + bad-value fallback; engine trims at most once per interval (second call within 60 s is a no-op, trims again after the interval elapses); disabled env is a no-op; trim failure never raises.

**CI — `.github/workflows/friday-universe-ci.yml`** (+6 lines): the new test file is added to the FRIDAY tier-1 pytest invocation (REL-068 guard: a PR test must run in PR CI), with the standard ride-along comment.

**Test results (local, venv `~/workspace/venvs/muse14-voi046`, FRIDAY requirements + pytest 9.2.0):**
- New file + FRD-041 + FRD-068 suites: **39 passed in 1.81 s**.
- Full FRIDAY tier-1 list exactly as CI runs it (same 25 files + the new file, same 3 deselects): **443 passed, 3 deselected in 15.54 s**. The 3 deselects are the pre-existing `test_reliability` deselects from CI, unrelated to this change.

## Calm-window re-probe — pre-fix baseline (current deploy, fix NOT deployed)

The fix is code-only in this PR; it is **not deployed** to FRIDAY-Server. A deploy needs Muse's clearance on the hub first (owner stop order freezes server moves) — **deploy clearance is owed**, and the post-trim plateau measurement (TP10's "measure post-trim plateau over 2 cycles") is the follow-up once deployed. What was probed here is the pre-fix baseline against the current deploy, via bridge `run_shell` (server 3, standing clearance 7200564540), 2026-11-28 07:35:44 UTC (13:05:44 IST), PID 138648 (8 min old, cgroup 267,833,344 B = 255.4 MB = 81.2% of the 300 MB cap, NRestarts 6):

| Probe | Result | Latency |
|---|---|---|
| `GET /health` #1 | 200 PASS | 0.762 s |
| `GET /health` #2 | 200 PASS | 0.759 s |
| `GET /health` #3 | 200 PASS | 0.760 s |
| `GET /api/livekit/token` #1 | 200 PASS | 0.733 s |
| `GET /api/livekit/token` #2 | 200 PASS | 0.016 s |
| `GET /api/livekit/token` #3 | 200 PASS | 0.024 s |

6/6 PASS. Endpoints answer correctly (first token call warms the key path, as TP10 also saw: 1.06 s). But this is **not a calm window**: kill #44 landed 8 min before the probe, RSS was climbing 224 → 256 MB in 5 min, and memory-pressure warnings fired at 76.2% and 80.8% in the same window. No `malloc_trim` lines exist in the journal — expected, the fix is not deployed. Run 28 stays HELD per TP10.

## Verdict

**Fix implemented and tested; live proof PARTIAL.** The code implements exactly TP10's smallest fix (periodic `malloc_trim(0)` on the memory-watch tick, with before/after measurement), 9 new tests pass, and the full FRIDAY tier-1 suite is green (443 passed). The live leg is a pre-fix baseline only: endpoints 6/6 PASS, but no calm window exists on the current deploy and the post-trim plateau cannot be measured until the fix is deployed. Deploy clearance from Muse is owed; once deployed, the follow-up is to read the `VOI-046 malloc_trim:` journal lines over 2 cycles and compare the plateau against this baseline (RSS ~256 MB at 8 min, kill cadence ~16–96 min).

## States

- **implemented:** YES (fix + tests in this PR)
- **tested:** YES (9 new tests; full FRIDAY tier-1 443 passed)
- **merged:** NO
- **deployed:** NO (deploy clearance owed — see above)
- **production-verified:** NO (post-trim plateau measurement owed after deploy)

## Open items / carried

- Deploy clearance for the VOI-046 fix to FRIDAY-Server (Muse, hub) — then the post-trim plateau measurement over 2 cycles (follow-up leg, same observation protocol as TP10).
- TP1's FRD-064 tracemalloc watch (`src/friday/core/tracemalloc_watch.py` + server.py wiring) is uncommitted on FRIDAY-Server only; it is not in this PR and not in the repo. Whether it should be committed (TP1/FRD-064) is a coordinator call — this task did not import TP1's uncommitted work.
- FRD-064 (OOM kills) remains TP1's task; VOI-045 firing (run 28) stays HELD per TP10/WATCH215.
- No cap raise: TP10's prescription explicitly rules it out on current evidence; the 300 MB cap stands.
- Kills #42/#43/#44 (06:07, 07:11, 07:27 UTC) postdate TP10's probe — the kill cadence continues on the current deploy.

— Muse 14
