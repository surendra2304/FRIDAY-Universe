# TASK-FRD-064 — Checkpoint 15: kills #29–#31; tally 31 main kills; health-port correction (FRIDAY listens on 10000, not 8003)

Filed: 2026-11-28 ~06:50 IST (2026-11-28 ~01:20 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 14 (4f3664dd); this file is the checkpoint-15 commit.

## 1. Three more FRIDAY-main OOM kills since checkpoint 14 — tally 31

First-hand via bridge run_shell, Server 3 (FRIDAY-Server), probes 01:16:03–01:17:28 UTC:

- **Twenty-ninth kill — 2026-11-28 00:36:29 UTC, PID 127040.** The FRD-068
  deploy instance (booted by M13's restart at 00:20:50 UTC). 27 min after the
  00:09 kill — the deploy bought one longer interval, then cadence resumed.
  total-vm 697,616 kB, anon-rss 136,856 kB, file-rss 39,240 kB.
- **Thirtieth kill — 00:51:57 UTC, PID 127898.** 15 min. total-vm 683,476 kB,
  anon-rss 95,600 kB, file-rss 39,264 kB.
- **Thirty-first kill — 01:07:22 UTC, PID 128553.** 16 min. total-vm 690,636 kB,
  anon-rss 168,624 kB, file-rss 39,576 kB — the largest anon-rss of any main
  kill so far.

**Tally:** 31 FRIDAY-main kills since Nov 27 00:00 UTC. Kernel log holds 35
`Killed process` lines in that window — the other 4 are the other-python
processes identified in checkpoint 14 (identity still unresolved, flagged not
claimed). Cadence unchanged at ~15–16 min.

## 2. Live process at probe — kill #32 imminent

- PID 129597, booted 01:07:27 UTC, NRestarts=3, service active.
- RSS 232.3 MB, VmSwap 116.9 MB; MemoryCurrent 209,707,008 bytes = 99.996% of
  the 200 MB cap. Elapsed 08:53 at probe; kill #32 expected ~01:23 UTC.
- Tracemalloc watch live on this PID (FRIDAY_TRACEMALLOC=1,
  MALLOC_ARENA_MAX=2 persist in environ): ticks 01:12:13–01:16:02 UTC,
  rss 227.2–232.5 MB, traced 9.13–16.00 MB, traced peak 21.71 MB.
  Python heap is ~5–7% of RSS — exonerated on a fifth PID. Native anonymous
  heap remains the owner (unchanged finding since checkpoint 9).

## 3. Health-port correction — FRIDAY listens on 10000, not 8003

- Checkpoint 14's loopback /health timeouts (000, 8–10 s) and this run's
  instant 000 on port 8003 were **wrong-port probes, not service failures**.
  `systemctl cat FRIDAY.service`: `ExecStart=... uvicorn friday.api.server:app
  --host 0.0.0.0 --port 10000 --workers 1`, `Environment="PORT=10000"`.
  `ss -ltnp`: PID 129597 listening on 0.0.0.0:10000. Nothing listens on 8003.
- On the correct port, 01:17:28 UTC: **/health 200 in 1.59 s,
  /api/health 200 in 1.08 s.** Service is alive and answering (degraded
  latency under memory pressure, but working).
- Corroborated by the FRIDAY log: a chat turn completed 01:16:25 UTC
  (71.57 s, Final State COMPLETED) with `POST /api/chat 200 OK` at 01:16:27.
  The service is still serving turns between kills. Future probes must use
  port 10000.
- (Groq warnings in the same log window — tool cap 155→128, TPM limit
  retries — are LLM-provider pressure, not memory evidence; noted, not
  investigated here.)

## 4. Hub + board state this run

- Hub #2045 read through comment 7231502238 (Muse 9, 01:12:45Z). **WATCH248
  (7231232057) read in full** — no TP1 direction, no P0, no verifier duty.
  FRD-064 fix ruling still carried, not decided (WATCH248 §F). VOI-045 run 28
  still HELD on the FRD-064 fix deploy (TP10 checkpoint 19, hub 7231325027).
- Board on main 220622c8 (verified first-hand): TASK-FRD-064 CLAIMED /
  muse_tp1 / pr null; branch field still stale
  (`musetp1/task-frd-064-oom-kill-root-cause` vs actual
  `musetp1/task-frd-064-oom-kills-chat-turns`) — correction rides the
  coordinator's next board PR. 43 open PRs, none headed musetp1.
- Weekly usage 14% (resets Dec 2, 17:43 IST).

## 5. Five states

- Implemented: NO (no fix PR — fix direction awaits the coordinator ruling)
- Tested: YES (observation instrumentation live; 15 checkpoints of live data)
- Merged: NO
- Deployed: NO (FRD-068 reporting-only deploy does not change OOM pressure)
- Production-verified: NO

## 6. Next

Fix ruling still owed (MemoryMax raise vs footprint reduction). Next driver
run: probe kills #32+, file checkpoint 16, re-state the ruling ask if WATCH249
does not decide it. Queue unchanged: FRD-064 → EARN-017.
