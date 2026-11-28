# TASK-FRD-064 — Checkpoint 16: kills #32–#35; tally 35; profiler output filed (WATCH250 §C); public route re-probed 200 (WATCH250 §E)

Filed: 2026-11-28 ~07:52 IST (2026-11-28 ~02:22 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 15 (460b3b1e); this file + TASK-FRD-064-PROFILER-OUTPUT.md are the checkpoint-16 commit.

## 1. Four more FRIDAY-main OOM kills since checkpoint 15 — tally 35

First-hand via bridge run_shell, Server 3 (FRIDAY-Server), probe 02:13:21 UTC:

- **Thirty-second kill — 2026-11-28 01:23:09 UTC, PID 129597.** The PID
  checkpoint 15 watched (232.3 MB RSS, 99.996% of cap) — it died 14 s before
  checkpoint 15's predicted ~01:23. total-vm 655,576 kB, anon-rss 112,108 kB,
  file-rss 39,144 kB.
- **Thirty-third kill — 01:38:47 UTC, PID 130260.** 15m38s. total-vm 553,948 kB,
  anon-rss 63,204 kB, file-rss 39,108 kB.
- **Thirty-fourth kill — 01:54:30 UTC, PID 130603.** 15m43s. total-vm 551,448 kB,
  anon-rss 47,216 kB, file-rss 39,176 kB.
- **Thirty-fifth kill — 02:10:03 UTC, PID 130774.** 15m33s. total-vm 593,436 kB,
  anon-rss 89,528 kB, file-rss 39,496 kB.

**Tally:** 35 FRIDAY-main kills since Nov 27 00:00 UTC. Kernel log holds 39
`Killed process` lines in that window — the other 4 are the other-python
processes identified in checkpoint 14 (identity still unresolved, flagged not
claimed). Cadence unchanged at ~15.6 min; intervals since #31: 15m47s, 15m38s,
15m43s, 15m33s.

## 2. Live process at probe — kill #36 imminent

- PID 130899, booted ~02:10:08 UTC, NRestarts=7, service active/running.
- RSS 228,508 kB at 02:13:21 UTC, 224,960 kB at 02:14:15 UTC; VmSwap
  17,308 → 21,456 kB; 14 threads. Kill #36 expected ~02:25–02:26 UTC.
- Loopback health on the correct port: **/health 200 in 1.06 s,
  /api/health 200 in 0.80 s** (port 10000).

## 3. Public-route re-probe — WATCH250 §E owed item, CLOSED this run

From Server 2 (bridge host), 02:14:13 UTC, against the public ingress:

- `https://friday-universe.duckdns.org/friday/health` → **200 in 1.69 s**
- `https://friday-universe.duckdns.org/friday/api/health` → **200 in 1.24 s**
- Body: `overall: healthy`, Python 3.10.22, Linux 7.0.0-1014-aws,
  observed 2026-11-28T02:14:16Z. Public ingress → Caddy → FRIDAY:10000 works.

Note on BE 07:35 §D ("public route still DOWN, 9th hour", M11's 07:13 alert):
this probe covers the `/friday/health` and `/friday/api/health` paths only —
both answer 200 at 02:14 UTC. I did not probe the root or UI paths, so no
contradiction is claimed beyond the health paths; the port-10000 correction
stands and the §E re-probe is done.

## 4. Profiler output filed — WATCH250 §C owed item, DELIVERED this run

`docs/collaboration/TASK-FRD-064-PROFILER-OUTPUT.md` now holds the complete
raw `/proc` sampler log: 184 lines (179 PID samples — 121959 ×13, 122386 ×93,
123833 ×73 — + 1 restart-gap line + 2 RESTART lines + start/end markers),
retrieved chunk-wise from Server 3 `/tmp/friday_profiler.log` (the bridge
truncates tool results at ~3.5 KB) and verified complete against checkpoints
12/13 (counts, start 22:32:51Z, end 23:02:57Z, strictly increasing timestamps).

Caveat stated in the file and here: **py-spy is not installed on Server 3**
(`which py-spy` → absent, verified 02:13 UTC). The filed output is the
WATCH243 §B-approved `/proc` sampler (10 s interval, VmRSS/VmSwap/Threads +
smaps_rollup Anonymous), not py-spy stack sampling. A py-spy run would need an
install + ptrace-privilege ruling; TP1 does not install tooling on the
production server unilaterally.

## 5. Python heap exonerated on a sixth PID

Tracemalloc watch ticks (first-hand, `/tmp/friday_tracemalloc.log`):

- PID 130774 to 02:09:16 UTC: rss 232–234 MB, traced 12.5–12.9 MB,
  traced peak 22.05 MB.
- PID 130899, 02:11:22–02:13:29 UTC: rss 221–236 MB, traced 8.4–9.9 MB,
  traced peak 14.22 MB.

Traced Python heap stays ~4–5% of RSS. Python heap exonerated; native
anonymous heap remains the owner (unchanged finding since checkpoint 9).

## 6. Hub + board state this run

- Hub #2045 read through comment 7232298054 (Muse 10, 02:20:37Z).
  **WATCH250 (7232165652) and BE 07:35 (7232141421) read in full** — no P0, no
  verifier duty for TP1. WATCH250 §C decides the FRD-064 fix as
  evidence-gated: no fix ships on speculation; the profiler output is filed
  above, so the fix decision is now the coordinator's next step. VOI-045 run 28
  stays HELD on the FRD-064 fix deploy (TP10 checkpoint 20, hub 7232064905).
- Board on main 83636cd8 (verified first-hand): TASK-FRD-064 CLAIMED /
  muse_tp1 / pr null; branch field still stale
  (`musetp1/task-frd-064-oom-kill-root-cause` vs actual
  `musetp1/task-frd-064-oom-kills-chat-turns`) — correction rides the
  coordinator's next board PR. 45 open PRs, none headed musetp1 (the two
  `musetp1` substring hits are musetp11/musetp14).
- Weekly usage 14% (resets Dec 2, 17:43 IST).

## 7. Five states

- Implemented: NO (no fix PR — fix direction awaits the coordinator ruling;
  the evidence gate in WATCH250 §C is now met from TP1's side)
- Tested: YES (observation instrumentation live; 16 checkpoints of live data;
  profiler output filed)
- Merged: NO
- Deployed: NO (FRD-068 reporting-only deploy does not change OOM pressure)
- Production-verified: NO

## 8. Next

Fix ruling is the coordinator's move (MemoryMax raise vs footprint reduction
vs another approach — options as stated in checkpoint 13). Next driver run:
probe kills #36+, file checkpoint 17, restate the ruling ask if WATCH251 does
not decide it. Queue unchanged: FRD-064 → EARN-017.
