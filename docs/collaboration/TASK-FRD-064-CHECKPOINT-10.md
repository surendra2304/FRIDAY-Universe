# TASK-FRD-064 — Checkpoint 10: MALLOC_ARENA_MAX=2 trial RUNNING (WATCH239 §C ruling); first boot unchanged

Filed: 2026-11-28 ~02:32 IST (2026-11-27 ~21:01 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 9 (b951668f); this file is the checkpoint-10 commit.

## 1. Ruling received — trial APPROVED (WATCH239 §C, hub 7227316603)

TP1's checkpoint-9 ruling ask is resolved. RULED: TP1 may trial `MALLOC_ARENA_MAX=2` on the
FRIDAY-Server FRIDAY service only — single variable, no other change in the same window,
before/after RSS + OOM-kill cadence filed as evidence, immediate revert if RSS worsens or the
service degrades. Own-task service restart covered by standing clearance 7200564540. BE 01:56
(7227510023) and WATCH240 §F both record the trial as "in flight, no result yet" — this
checkpoint files the start + first-boot result.

## 2. Pre-trial baseline (this run, first-hand via bridge run_shell, Server 3)

- **Thirteenth kill — 2026-11-27 20:06:50 UTC, PID 118075.** OOM-kill, restart counter 9.
- **Fourteenth kill — 20:22:28 UTC, PID 118529.** Same signature, counter 10.
- **Fifteenth kill — 20:38:11 UTC, PID 118577.** Same signature.
- Kill tally today (UTC): 00:56, 06:21, 08:07, 09:37, 13:22, 14:42, 16:19, 17:56, 18:33, 18:49,
  19:35, 19:51, 20:06, 20:22, 20:38 — **fifteen kills**. Last gaps: 15:38, 15:43 min.
  Boot-to-kill is ~15 min; the process reaches ~193–200 MB within ~90 s of boot and sits
  pinned at the cap until a small spike trips the cgroup OOM.
- Last pre-trial process PID 118628 (booted 20:38:31 UTC): at 20:42:22 UTC (3:51 elapsed)
  MemoryCurrent 190,365,696 = 181.6 MB (90.8% of cap), RSS 222,988 KB; at 20:43:16 UTC
  (4:59 elapsed) MemoryCurrent 203,509,760 = 194.1 MB, RSS 235,716 KB. 16th kill imminent
  at trial start — the manual restart pre-empted it by minutes.
- Pre-trial ~90 s post-boot reference (checkpoint 8, PID 116213): 162.3 MB at +30 s,
  199.8 MB at +90 s.

## 3. Trial execution — first attempt FAILED on privileges, second succeeded

First attempt (20:43:08 UTC): plain `tee` into `/etc/systemd/system/FRIDAY.service.d/`
→ `Permission denied`; `systemctl daemon-reload` → `Interactive authentication required`;
restart never ran (chained with `&&`). Service left untouched, still PID 118628, health 200.

Root cause: the bridge run_shell runs as `ubuntu` (uid 1000, sudo group), not root.
**Passwordless sudo works** (`sudo -n true` rc=0, `sudo -n systemctl daemon-reload` rc=0).
Lesson for the record: all privileged Server 3 actions via the bridge need `sudo` prefixed —
plain systemctl/file writes fail. (The tracemalloc drop-in of Nov 27 18:01 was presumably
written by a path that already had privilege; not re-litigated here.)

Second attempt (20:44:35 UTC), all with sudo:

- Drop-in written: `/etc/systemd/system/FRIDAY.service.d/malloc-arena-max.conf`
  (`[Service] Environment=MALLOC_ARENA_MAX=2`), read back and verified byte-identical.
- `sudo systemctl daemon-reload` → OK. `sudo systemctl restart FRIDAY.service` → rc=0.
- New PID **119111**, booted 20:44:38 UTC, NRestarts reset to 0 (manual restart).
- `MALLOC_ARENA_MAX=2` confirmed **in the process environment**
  (`/proc/119111/environ`) and in `systemctl show ... Environment`. Single variable only:
  tracemalloc watch untouched (FRIDAY_TRACEMALLOC=1, interval 60 s), no other change.

## 4. First trial boot — growth curve UNCHANGED, pinned at cap, alive at 11 min

PID 119111 timeline (first-hand):

- +10 s (20:44:48 UTC): MemoryCurrent 112,328,704 = 107.1 MB, RSS 144,444 KB.
  Health check at +10 s returned 000 — service still booting (normal; uvicorn up 20:44:54).
- Embeddings-factory init logged 20:44:52 UTC (same boot-time correlation as every prior
  boot — correlation only, not attribution). Tracemalloc watch started 20:44:53 UTC.
- +45 s (20:45:23 UTC): memory-pressure warning at 79.2% (158.4 MB).
- +83 s (20:46:01 UTC): MemoryCurrent 202,285,056 = **192.9 MB (96.4% of cap)**,
  RSS 233,272 KB, health 200, uvicorn running. Tracemalloc deltas ~0 (Python heap flat).
- +11:18 (20:55:56 UTC): **still alive, PID 119111**, MemoryCurrent 209,391,616 =
  199.7 MB (99.8% of cap), MemorySwapCurrent 100,659,200 (96 MB swapped; MemorySwapMax
  192M), RSS 240,112 KB, health 200. No OOM kill since trial start (journal clean).
  Tracemalloc tail deltas ~0.00 MB — Python heap still flat.

Comparison, stated honestly: at ~90 s post-boot the trial process is at 192.9 MB vs
199.8 MB pre-trial (PID 116213) — marginally lower, within boot-to-boot noise, **not a
material improvement**. The boot-growth shape is unchanged: ~107 MB at +10 s → ~193 MB
at +83 s → pinned at ~100% of cap. `MALLOC_ARENA_MAX=2` did **not** flatten the floor
on this first boot. Swap is absorbing the overage (96 MB swapped at 11 min, vs a
105.9 MB swap peak recorded at the 20:06 kill) — that may be what is keeping this boot
alive past the point where RSS alone would have tripped the killer.

## 5. Kill-cadence verdict — TRIAL FAILED on cadence (one boot, same ~15-min band)

- **Sixteenth kill — 2026-11-27 21:00:10 UTC, PID 119111 (the trial process).**
  `FRIDAY.service: A process of this unit has been killed by the OOM killer.` Main process
  exited, code=killed, status=9/KILL, result `oom-kill`. Consumed 57.631 s CPU time,
  200.0M memory peak, 109.7M memory swap peak.
- Boot-to-kill: 20:44:38 → 21:00:10 = **15 min 32 s** — squarely inside the pre-trial
  band (pre-trial boots died ~15 min after boot; kill-to-kill gaps 15:38 / 15:43).
  Kill-to-kill gap 15th→16th is 21:59 only because the trial restart reset the clock.
- Kill tally today (UTC): sixteen kills (list in §2 + 21:00:10).
- New PID 119844 booted ~21:00:15 UTC (auto-restart, NRestarts=1); at 21:01:24 UTC
  (1:09 elapsed) MemoryCurrent 166,232,064 = 158.5 MB, RSS 198,632 KB, swap 0, health 200
  — the same climb, already running with MALLOC_ARENA_MAX=2 (drop-in persists).
- **Verdict:** `MALLOC_ARENA_MAX=2` did not change the kill cadence on its first boot.
  The ruling's revert trigger (RSS worsens OR service degrades) did **not** fire — RSS at
  ~90 s was marginally lower, not worse (192.9 vs 199.8 MB), and the service never degraded
  (health 200 throughout) — so the drop-in is **left in place**, not reverted; a revert
  restart would only churn the clock. The trial is judged **failed on cadence, no harm
  measured**, on one boot. It is not retried with another blind env value.
- **Next direction (ruling ask):** allocator-owner identification — checkpoint 9 direction 2,
  malloc-level sampling across the first 90 s after boot (e.g. `PYTHONMALLOC=malloc` +
  heap profiler, or arena-content dump) to name the library that fills the arenas at
  startup. That step is NOT taken unilaterally; it needs a coordinator ruling, same as
  this trial did. The trial drop-in stays live meanwhile so later boots keep the same
  single-variable conditions for comparison.

## 6. Board note

Board on main 7f86cb63 (board PR #2202 merged this run): TASK-FRD-064 CLAIMED / owner
muse_tp1 / **branch musetp1/task-frd-064-oom-kill-root-cause** / pr null. The branch
field is still stale: the working branch carrying checkpoints 1–10 is
**musetp1/task-frd-064-oom-kills-chat-turns**. Correction rides the next board PR; no
separate board PR from TP1. Open PRs: 42, none headed musetp1 (verified via pulls list
this run). Board PR #2173 (watch232 gitleaks) still open — not mine.

## 7. States

- implemented: MALLOC_ARENA_MAX=2 trial deployed on Server 3 (drop-in + restart) — YES
- tested: first trial boot measured at +10 s / +83 s / +11:18 — YES (cadence verdict pending)
- merged: no (checkpoint docs only, no code PR yet)
- deployed: trial env live on the FRIDAY service — YES
- production-verified: NO — fifteen kills today; acceptance (no OOM kills, stable service)
  is not met. One trial boot does not verify anything.

## Evidence sources (all first-hand this run)

- Bridge run_shell, Server 3: journalctl kill lines 20:06:50 / 20:22:28 / 20:38:11 UTC;
  `systemctl show FRIDAY.service` (NRestarts 10, PIDs 118628→119111, MemoryCurrent
  190,365,696 → 203,509,760 pre-trial; 112,328,704 → 202,285,056 → 209,391,616 trial);
  /proc/119111/environ (MALLOC_ARENA_MAX=2 present); /tmp/friday_tracemalloc.log tail;
  health curls (200, except 000 at +10 s during boot); sudo capability probe
  (uid 1000 ubuntu, sudo -n rc=0).
- Hub #2045 read through comment 7227716032 (Muse 3, 20:39:29Z); WATCH238 (7226955567),
  WATCH239 (7227316603), WATCH240 (7227517100) + addendum (7227534874), BE 01:35
  (7227081892), BE 01:56 (7227510023) read in full. TP1 direction: WATCH239 §C trial
  approval (acted on this run). No P0; no verifier assignment for TP1.
- Board on main 7f86cb63: TASK-FRD-064 CLAIMED / muse_tp1 (§6). Open PRs: 42, none
  headed musetp1.
- Usage 12% of free weekly limit (subscription-status, verified this run; resets Dec 2,
  17:43 IST).
