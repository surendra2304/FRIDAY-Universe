# TASK-FRD-064 — Checkpoint 2: memory-sampling investigation (live numbers)

**Task:** FRIDAY: investigate + fix FRIDAY.service OOM-kills under chat turns.
**Owner:** Muse TP1. **Branch:** `musetp1/task-frd-064-oom-kills-chat-turns` (@ `f5374e4c`).
**Probed:** 2026-11-27 ~17:00–17:20 IST (11:30–11:50 UTC), bridge Server 3 = FRIDAY-Server, first-hand.
**Board on live main `caa597bc`:** CLAIMED / owner `muse_tp1` / pr null / P1.
Board note: the record's `branch` field reads `musetp1/task-frd-064-oom-kill-root-cause`;
the real branch is `musetp1/task-frd-064-oom-kills-chat-turns` (verified via ls-remote at
claim) — coordinator correction owed in the next board PR, not a work-PR hunk.

## 1. Live state now

- `FRIDAY.service`: active / running, MainPID `100296`, active since 09:37:09 UTC.
- `MemoryCurrent=38,498,304` (~36.7 MB) / `MemoryMax=209,715,200` (200M) at 11:31:56 UTC.
- `/proc/100296/status` at ~11:35 UTC: `VmRSS 73,184 kB`, `VmSwap 120,632 kB`,
  `VmSize 978,160 kB`. The process has ~120 MB swapped out right now.
- **No OOM kill since 09:37 UTC** — current activation stable ~2h, but still at
  warning level (see §3).

## 2. Correction to checkpoint 1: FOUR kills today, not three

Journal (`FRIDAY.service`, first-hand):

| Kill (UTC) | Kill (IST) | systemd note |
|---|---|---|
| 00:56:14 | 06:26 | oom-kill (missed by the cp1 probe window) |
| 06:21:02 | 11:51 | oom-kill; 200.0M memory peak, 167.7M swap peak |
| 08:07:14 | 13:37 | oom-kill |
| 09:37:04 | 15:07 | oom-kill; 200.0M memory peak, 180.0M swap peak |

Checkpoint 1 listed three kills; the 00:56 kill was outside its journal query.
All four activations died the same way: RAM at the 200M cap with swap nearly
exhausted (swap cap 192M).

## 3. The monitor, read first-hand (code + journal)

- `friday/observability/proactive_engine.py`: `read_cgroup_memory()` reads the
  process's OWN cgroup v2 `memory.current / memory.max` — **RAM only, not swap**.
  `MEMORY_WARN_PERCENT = 75.0`, `MEMORY_CRITICAL_PERCENT = 90.0`,
  `MEMORY_RECOVERED_PERCENT = 60.0`. Cadence ~16 min.
- Warning/critical timeline (cgroup RAM % of 200M), activation PID 82582 → kill 06:21:
  03:59 warn 75.9 → 04:02 crit 91.0 → 04:09 warn 79.3 → 04:25 crit 97.3 →
  04:43 crit 92.9 → 04:59 crit 99.9 → 05:15 crit 90.4 → 05:31 crit 100.0 →
  05:47 crit 93.8 → 06:04 crit 92.0 → **06:20:21 warn 75.2 → 06:21:02 KILL**.
- Activation PID 95071 → kill 08:07: 06:36 warn 85.9 → 06:49 warn 77.5 →
  06:54 crit 91.8 → 07:00 warn 86.8 → 07:16 warn 79.7 → 07:32 warn 81.2 →
  07:48 warn 81.2 → 07:52 warn 75.9 → 07:57 warn 86.9 → 08:02 warn 89.8 →
  08:03 crit 90.2 → 08:07:14 KILL.
- Activation PID 98045 → kill 09:37: 08:12 warn 75.0 → 08:32 warn 83.5 →
  08:48 crit 99.7 → 09:04 crit 98.6 → 09:20 crit 99.9 → 09:37:00 crit 99.9 → KILL.
- Activation PID 100296 (current): 09:52 warn 83.3 → 10:08 warn 78.8 →
  10:24 warn 78.9 → 10:40 warn 78.1 → 10:56 warn 79.0 → 11:12 warn 76.8 →
  11:28 warn 75.9.

## 4. What the numbers say (root-cause shape)

1. **Steady-state floor ~75–80% (150–160 MB total footprint).** Every activation
   climbs to warning level within ~15 min of restart and never comes back below
   ~75% — even the current activation, 2h old, sits at 76–83%. The sawtooth
   (75 → 100 → 75) is GC + kernel swap-out, not real recovery: at 11:28 the
   monitor read 75.9% RAM while `/proc` showed 120 MB swapped — total footprint
   ≈ 38 MB RAM + 120 MB swap ≈ 158 MB. The process lives permanently
   swap-thrashing, which also fits TP10's slow `/health` (4.18 s): page faults
   on swapped pages.
2. **Kills are spikes, not the slow climb.** The 06:21 kill came 41 s after a
   75.2% reading — a fast allocation between 16-min monitor samples. Headroom
   above the ~150 MB floor is only ~40–50 MB; any heavy turn tips it over.
3. **Pre-kill activity differs per kill — no single turn type is the trigger.**
   - 08:07: a `start_goal_loop` tool run failed at 08:04:33 after 76.3 s
     (`AttributeError: 'JSONResponse' object has no attribute 'get'`,
     `goal_loop.py:273` — the executor's reply extraction), followed by
     Inference escalation calls carrying multi-KB provenance dicts
     (quarantined alternates, per-model servability tables).
   - 09:37: NO turn activity in the 09:32–09:37 window (daemon alive,
     0 queued, 0 running); the service itself warned at 09:36:59 (99.9%,
     199.9 MB) one second before the kill. The climb in that window left no
     chat-turn log lines.
   - 06:21: tail shows only the kill lines (earlier window lines not recovered
     this run — see §6).
4. **Hypothesis 1 (per-turn ratchet) is now: floor + spike, not a monotonic
   ratchet.** Memory does not climb monotonically per turn; it oscillates
   75–100% and dies on a spike. Hypothesis 3 (baseline too close to the cap)
   is the confirmed shape; the remaining question is WHAT holds the ~150 MB
   floor.

## 5. Code scan: floor suspects (read first-hand, local clone)

- **Prime suspect: `_conversation_history: deque(maxlen=10000)`**
  (`FRIDAY/src/friday/api/server.py:5482`), `ConversationEntry` (Pydantic)
  per turn, hydrated from Oracle at startup (`_ensure_history_hydrated`) and
  appended per turn. The cap is 10,000 entries — at even ~5 KB/entry that is
  ~50 MB in-process, and entries carry full turn text. Unquantified: entry
  count + average bytes on the live service (next step, §6).
- **Not the floor:** `TTLCache` defaults (`core/cache.py`: maxsize 256, TTL 60 s;
  server uses maxsize 16) — small. No local ML models: no
  sentence-transformers / torch / transformers loads in `FRIDAY/src/friday`.
- **Spike contributors to check:** per-turn Inference escalation provenance
  dicts (large, retained where? — the 08:04 lines show them logged per call);
  goal-loop steps each run a full brain turn through `_run_brain_sync`
  (`goal_loop.py: _default_executor`); the `JSONResponse` reply-extraction bug
  at `goal_loop.py:273` is a real defect on the 08:07 path (fixable in code,
  though not proven to be the leak).
- **Cap change is NOT the fix route:** any `MemoryMax` / unit-file change is a
  server move needing coordinator clearance (cp1 §4.4). The fix is code-side:
  shrink the floor and/or cap the spike.

## 6. Next (checkpoint 3 = fix PR with live evidence)

1. Quantify the floor: Oracle `conversation_history` row count + average
   entry bytes (read-only), and a live `smaps_rollup` / heap sample of PID
   100296 (read-only) to split the ~150 MB by owner.
2. Controlled per-turn sampling: `MemoryCurrent` + `memory.swap.current`
   before/after one chat turn of each type (plain, goal-loop, file-op) — the
   spike owner, if any single type dominates.
3. Fix in code (repo PR): bound/shrink the in-memory history (and/or hydrate
   lazily), fix the `goal_loop.py:273` JSONResponse handling, cap escalation
   provenance retention — then a live verification sweep of chat turns with the
   service stable throughout, which is the acceptance bar.
4. VOI-045 (TP10) firing stays HELD until the fix is deployed (WATCH215 §3) —
   no change; TP10 re-checks each run.

## 7. Five states

- Implemented: NO. Tested: NO. Merged: NO. Deployed: NO. Production-verified: NO.
- Investigation (this checkpoint): DONE — numbers above are first-hand live reads.

## 8. Queue

- FRD-064 (head) → TASK-EARN-015 (pre-staged next) → TASK-REL-069 (pos 3 top-up,
  board AVAILABLE / muse_tp1) → TASK-EARN-017 (queued). Hold ≤ 2 (1 + 1 pre-staged).
