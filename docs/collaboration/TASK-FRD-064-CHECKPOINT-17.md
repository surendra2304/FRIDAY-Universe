# TASK-FRD-064 — Checkpoint 17: WATCH251 §D fix EXECUTED — MemoryMax 200→300 MB live; cycle 1 KILL-FREE past the old kill boundary

Filed: 2026-11-28 ~09:00 IST (2026-11-28 ~03:30 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 16 (7eb0ac20); this file is the checkpoint-17 commit.

## 1. Ruling received — fix DECIDED and APPROVED (WATCH251 §D, hub 7232592508)

> "TP1 FRD-064 fix — DECIDED, evidence-gated, APPROVED. ... Fix: TP1 raises
> MemoryMax 200→300 MB in the FRIDAY service unit on FRIDAY-Server, restarts,
> and files the kill-cadence observation over the next 2 cycles. ... Owner TP1;
> change + first observation due next run."

This checkpoint files the change + first observation. Executed this run, first-hand
via bridge run_shell on Server 3 (FRIDAY-Server).

## 2. Pre-fix baseline — three more kills, tally 38, cadence unchanged

Probe 03:09:50 UTC (before the change):

- **Kill #36 — 02:25:48 UTC.** **Kill #37 — 02:41:21 UTC.** **Kill #38 — 02:56:54 UTC.**
  Gaps 15m33s / 15m33s — cadence still ~15.6 min.
- **Tally: 38 FRIDAY-main kills since Nov 27 00:00 UTC** (35 at checkpoint 16 + 3).
- Live process at probe: PID 132754, booted 02:56:59 UTC, NRestarts=10,
  MemoryCurrent 209,649,664 = 199.97 MB (**99.98% of the 200M cap**),
  MemorySwapCurrent 100,671,488 = 96 MB, RSS 240,672 kB. Kill #39 expected ~03:12 UTC
  — the restart below pre-empted it by ~2 min.
- Pre-change unit state: base unit `MemoryMax=200M`; drop-ins dispatch-env,
  malloc-arena-max, swapmax (MemorySwapMax=192M), tracemalloc. `systemctl cat`
  warned the loaded unit was outdated vs disk — the daemon-reload in §3 cleared it.

## 3. The change — single variable only

At 03:10:16 UTC, all with sudo (bridge runs as ubuntu, passwordless sudo verified
in checkpoint 10):

- Drop-in written: `/etc/systemd/system/FRIDAY.service.d/memory-max-300.conf`
  (`[Service]` / `MemoryMax=300M`), read back byte-identical.
- `sudo systemctl daemon-reload` → OK. Verified **MemoryMax=314572800** (300M),
  MemorySwapMax unchanged 201326592 (192M).
- `sudo systemctl restart FRIDAY.service` → rc=0. New PID **133202**, booted
  03:10:37 UTC, NRestarts=0. Status: `Memory: 125.5M (max: 300.0M swap max:
  192.0M ...)` at +5 s.
- Nothing else touched: MALLOC_ARENA_MAX=2, tracemalloc watch, swapmax drop-ins
  all intact; no code change, no other service restarted.

## 4. Cycle-1 observation — KILL-FREE past the old boundary

| Probe (UTC) | Elapsed | MemoryCurrent | % of 300M cap | Swap | RSS | Health |
|---|---|---|---|---|---|---|
| 03:12:30 | +1m53s | 222,142,464 (211.9 MB) | 70.6% | 0 | 230,472 kB | 200 / 200 |
| 03:18:12 | +7m35s | 256,999,424 (245.1 MB) | 81.7% | 0 | 264,444 kB | 200 |
| 03:26:44 | +16m07s | 88,322,048 (84.2 MB) | 28.1% | 165.1 MB | 119,784 kB | 200 (2.62 s) |
| 03:27:57 | +17m20s | 248,885,248 (237.4 MB) | 79.1% | 96.0 MB | 269,688 kB | — |

- **PID 133202 alive at +17m20s, NRestarts=0, ZERO OOM-kill lines in the journal
  since the 03:10:37 restart.** The old cadence killed every boot at ~15.5 min;
  this boot survived past that boundary. **Cycle 1 is kill-free.**
- Total footprint (RAM + swap) stays flat ~245–253 MB across all four probes —
  the same plateau the profiler measured pre-fix, now sitting at ~80% of the new
  cap instead of ~100% of the old one. No leak signal; tracemalloc deltas ~0.00 MB.
- RAM↔swap oscillation noted honestly: between +7m35s and +16m07s the kernel moved
  ~160 MB of anon pages to swap (MemoryCurrent 245 → 88 MB, swap 0 → 165 MB),
  then back (237 MB RAM / 96 MB swap at +17m20s). Host is NOT under pressure
  (`free -m`: 1905 MB total, 991 MB available; top RSS after FRIDAY is PID 87938
  at 239 MB). Mechanism unattributed — idle-page reclaim under cgroup accounting
  is the leading guess, not a finding. Total footprint flat, service healthy
  throughout; flagged for the next run to watch, not treated as a defect.
- Public route re-probed from Server 2 at ~03:28 UTC:
  `https://friday-universe.duckdns.org/friday/health` → **200 in 1.64 s**;
  `/friday/api/health` → **200 in 1.14 s**.

## 5. What this means for the held items

- **VOI-045 run 28** (TP10 head): WATCH251 §D holds it "until one kill-free cycle
  is observed". That condition is now met on cycle 1 (this checkpoint). TP1 states
  the fact; firing run 28 is TP10's lane, sequenced via Muse — TP1 does not fire it.
- **Cycle 2 observation is owed next run**: PID 133202 must still be alive at
  ~03:42 UTC (+31 min, two old-cadence intervals) with 0 kills. If a kill lands
  before then, the fix verdict flips to FAILED on cadence and the ruling ask
  re-opens (footprint reduction vs a higher cap).

## 6. Hub + board state this run

- Hub #2045 read through comment 7232759899 (Muse 7, 03:02:57Z). **WATCH251
  (7232592508) and BE 08:00 (7232438956) read in full** — no P0, no verifier duty
  for TP1. WATCH251 §D is the ruling acted on above.
- Board on main 9321b0d1 (verified first-hand): TASK-FRD-064 CLAIMED / muse_tp1 /
  pr null; TASK-WEB-007 MERGED pr 2075; TASK-FRD-062 MERGED pr 2108. Board branch
  field for FRD-064 still stale (`musetp1/task-frd-064-oom-kill-root-cause` vs
  actual `musetp1/task-frd-064-oom-kills-chat-turns`) — correction rides the
  coordinator's next board PR.
- Open PRs: 46, none headed musetp1 (verified via pulls list this run).
- Weekly usage 14% (resets Dec 2, 17:43 IST).

## 7. Five states

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (cycle-1 kill-free observation, four probes + public route)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (needs cycle-2 observation + sustained kill-free run;
  acceptance is no OOM kills, stable service)

## 8. Next

Next driver run: probe PID 133202 at ~+31 min (cycle 2), file checkpoint 18,
report whether the kill-free run holds. Queue unchanged: FRD-064 → EARN-017.
