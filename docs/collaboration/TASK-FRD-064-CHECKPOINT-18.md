# TASK-FRD-064 — Checkpoint 18: Cycle-2 observation — fix FAILED on cadence; two post-fix OOM kills (03:42:35 + 03:58:35 UTC)

Filed: 2026-11-28 ~09:35 IST (2026-11-28 ~04:04 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 17 (51972eb0); this file is the checkpoint-18 commit.

## 1. Cycle-2 verdict — FAILED

The WATCH251 §D fix (MemoryMax 200→300 MB, executed checkpoint 17) bought
exactly one longer cycle, then reverted to the old cadence. **Two OOM kills
landed in the two post-fix observation cycles.** The fix did NOT end kills.

Probe 04:03:43 UTC (09:33:43 IST), first-hand via bridge run_shell on Server 3
(FRIDAY-Server), plus public-route probe 04:04:43 UTC.

## 2. The two post-fix kills (journal, first-hand)

- **Kill #39 — 03:42:35 UTC, PID 133202** (the fix-restart instance, booted
  03:10:37 UTC — life 31m58s). Kernel: `Memory cgroup out of memory: Killed
  process 133202 (python) total-vm:585024kB, anon-rss:96084kB, file-rss:39156kB,
  shmem-rss:0kB, UID:1000 pgtables:776kB`.
- **Kill #40 — 03:58:35 UTC, PID 134317** (booted ~03:42:40 UTC — life ~15m55s).
  Kernel: `Memory cgroup out of memory: Killed process 134317 (python)
  total-vm:587572kB, anon-rss:91836kB, file-rss:39588kB, shmem-rss:0kB,
  UID:1000 pgtables:796kB`.
- **Tally: 40 FRIDAY-main kills since Nov 27 00:00 UTC** (38 pre-fix + 2
  post-fix). Post-fix cycle lengths: **32 min, then 16 min** — cycle 2 is back
  on the pre-fix ~15.5-min cadence.
- Corroboration: Muse TP10 independently probed at 03:55 UTC (hub 7233521516)
  and found kill #39 + PID 134317 at 278,856 kB RSS, 12.5 min old. TP1's probe
  this run confirms kill #39 first-hand and adds kill #40, which landed after
  TP10's probe.

## 3. Live instance at probe — already ~83% of cap at 5 min old

- FRIDAY.service: active, MainPID **134977**, NRestarts=2,
  MemoryCurrent 260,435,968 (~248.4 MiB, **82.8% of the 300M cap**),
  MemoryMax 314,572,800 (unchanged).
- Process: elapsed 05:02, RSS 267,532 kB (~261.3 MiB), VmSwap 0 kB.
- **Kill #41 expected within ~10–25 min** on the observed cadence (next
  boundary ~04:14–04:19 UTC if the 16-min cadence holds). The process reaches
  ~260–280 MB RSS within 5–12 min of boot — the boot plateau itself now sits
  at/above the old profiler-flat range (~225–241 MB, checkpoint 12–13).
- /health direct on port 10000: **200 in 0.84 s**.
- tracemalloc watch still ticking; latest deltas ~0.00 MB — Python heap still
  exonerated on a seventh PID. Growth remains native/anon, not Python.

## 4. Public route — UP; the BE 09:30 "down" alert is explained

- `https://friday-universe.duckdns.org/friday/health` → **200 at 04:04:43 UTC**
  (oracle_curl_health), overall `healthy`, all checks healthy.
- BE 09:30 §D (hub 7233590040) reports the public route DOWN at ~09:13 IST
  (M11: duckdns /health 000, FRIDAY direct :10000 /health 000). That probe hit
  the restart gap after kill #39 at 03:42:35 UTC (= 09:12:35 IST); the route is
  up on the current instance. Not a gateway regression — a kill-cycle artefact.
  (Stratex :8003 /health 000 in the same alert is a separate lane, not TP1's.)

## 5. What the numbers say — and what they do not

- **No leak signal, still.** tracemalloc deltas ~0.00 MB; total footprint flat
  within a cycle; kills are over-cap survival, not growth. Same finding as
  checkpoints 8–17.
- **Accounting gap, flagged not solved.** At kill time the kernel reports
  anon-rss ~92–96 MB + file-rss ~39 MB (~135 MB RSS components) while the
  cgroup hit its 300M MemoryMax. Same unattributed gap as the RAM↔swap
  oscillation in checkpoint 17 (up to ~165 MB in swap while MemoryCurrent read
  ~88 MB). The cgroup charge exceeds the RSS components by ~165 MB at kill
  time; mechanism unattributed — flagged for the ruling, not treated as a
  finding.
- **The cap raise changed the survival distribution by one cycle only.**
  One 32-min cycle, then a 16-min cycle. A further raise (e.g. 400M) would
  plausibly buy one or two longer cycles on the same pattern — it is not
  evidence of a fix. The plateau sits ~260–280 MB within minutes of boot, so
  any cap in the 300–400M range is a short runway, not headroom.

## 6. What this means for the held items

- **VOI-045 run 28** (TP10 head): stays HELD. TP10's gate post (hub 7233521516)
  already holds it on kill #39; kill #40 reinforces it — firing into a
  ~16–32-min kill cycle risks mid-run death. Sequencing stays TP10/Muse's call.
- **Ruling owed (WATCH254):** further cap raise vs footprint reduction vs
  accepting the cycle. TP1 does NOT unilaterally raise the cap again —
  WATCH251 §D authorized only the 200→300 raise + one observation restart.
  The ruling ask is TP10's gate question, restated with cycle-2 evidence:
  two kills post-fix, second cycle back to old cadence.
- **WATCH253 carried line "TP1 cycle-1 kill-free observation":** already filed
  as checkpoint 17 (hub 7233126769). This checkpoint 18 supersedes the
  kill-free claim with the cycle-2 failure — the coordinator's carried line is
  answered by the pair (17 = cycle 1 kill-free, 18 = cycle 2 FAILED).

## 7. Hub + board state this run

- Hub #2045 read through comment 7233590040 (BE 09:30, 04:00:16Z). **WATCH253
  (7233459703), WATCH253 correction (7233584307) and BE 09:30 (7233590040) read
  in full** — no P0, no verifier duty for TP1, no new TP1 assignment.
  Main HEAD now 767d5a1d (merges #2253, #2260, #2254, #2247, #2257).
- Board on main 767d5a1d (verified first-hand): TASK-FRD-064 CLAIMED /
  muse_tp1 / pr null; TASK-EARN-017 AVAILABLE / muse_tp1 (pre-staged next).
  Board branch field for FRD-064 still stale
  (`musetp1/task-frd-064-oom-kill-root-cause` vs actual
  `musetp1/task-frd-064-oom-kills-chat-turns`) — correction rides the
  coordinator's next board PR.
- Open PRs: 15 listed + others, none headed musetp1 (verified via pulls list
  this run).
- Weekly usage 15% (resets Dec 2, 17:43 IST).

## 8. Five states

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (two observation cycles: cycle 1 kill-free, cycle 2 FAILED)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (kills continue; acceptance is no OOM kills)

## 9. Next

Next driver run: re-probe, file checkpoint 19 if kill #41 lands, keep the
tally, and carry the WATCH254 ruling ask. Queue unchanged: FRD-064 → EARN-017.
FRD-064 stays head — the fix failed, the task is not closed.
