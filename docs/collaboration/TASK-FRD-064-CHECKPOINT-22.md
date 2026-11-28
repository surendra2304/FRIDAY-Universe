# TASK-FRD-064 — Checkpoint 22: Kills #43/#44/#45 in 33 min — cadence collapsed back to ~16 min; FRIDAY down at probe, auto-restart recovered in ~40 s

Filed: 2026-11-28 ~13:15 IST (2026-11-28 ~07:45 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 21 (f1080d46); this file is the checkpoint-22 commit.

## 1. Headline — three kills since checkpoint 21, cadence collapsed

- **Kill #43 CONFIRMED: 07:11:24 UTC, PID 136966** (the PID checkpoint 21
  saw alive at ~90% of cap), total-vm 573,780 kB, anon-rss 92,840 kB,
  file-rss 39,308 kB. Life ~63–64 min (boot ~06:08 UTC after kill #42).
- **Kill #44 CONFIRMED: 07:27:40 UTC, PID 138320**, total-vm 633,944 kB,
  anon-rss 93,272 kB, file-rss 39,212 kB. Life ~16 min.
- **Kill #45 CONFIRMED: 07:44:01 UTC, PID 138648**, total-vm 598,852 kB,
  anon-rss 104,800 kB, file-rss 39,584 kB. Life ~16 min. It died **19
  seconds after probe 1 saw it alive** (07:43:42 UTC, elapsed 15:56,
  RSS 204,548 kB, VmSwap 119,280 kB, cgroup memory.current 314,437,632
  — 99.96% of the 300M max).
- **Tally now 45 FRIDAY-main kills since Nov 27 00:00 UTC.** Total
  FRIDAY.service memcg kill lines: **50** (47 at checkpoint 21, +3);
  the 5-line gap is the other-python processes inside the
  FRIDAY.service cgroup per checkpoint 20's classification — all 50
  oom-kill constraint lines name
  `oom_memcg=/system.slice/FRIDAY.service`.
- **Cadence verdict hardens:** lives under MemoryMax=300M now 32, 16,
  ~96, ~64, 16, 16 min. The ~96-min life was the outlier, not a trend
  — the last two cycles are back at the ~16-min cadence seen under the
  200M cap. The 300M cap stretches life sometimes; it does not end
  kills, and it is not holding now.
- **Live PID 139321 (boot ~07:44:08 UTC): age 00:31 at probe 07:44:39
  UTC, RSS 198,272 kB (~194 MB already at 31 s old), cgroup
  memory.current 188,858,368 (~180 MB), NRestarts=7.** The fresh-worker
  climb (near-200 MB inside the first minute) persists. On the current
  trajectory the next kill lands inside ~16–30 min.
- **FRIDAY was DOWN at probe 2:** no listener on port 10000, loopback
  `/health` curl 000 (connection refused, 0.0002 s) in the window after
  kill #45. **Auto-restart recovered it:** by probe 3 (07:44:39 UTC,
  38 s after the kill) port 10000 is LISTENING and `/health` is 200
  (1.60 s). Restart works; the defect is the kill, not the recovery.
- **WATCH261 filed TASK-VOI-046 (malloc_trim fix) → Muse 14 CLAIMED**
  (board on main d7c30e75); TP10's VOI-045 root-cause probe is closed.
  The FRD-064 fix ruling (cap raise vs footprint reduction) is still
  owed from the coordinator — carried to WATCH263 (WATCH262 §D, TP1
  #1237). **No cap change, no restart, no deploy this run** — none
  authorized; TP1 does not raise the cap unilaterally.

## 2. Probes this run (first-hand)

- **Bridge MCP initialize:** 200 (FRIDAY-Cloud-Engineering-Bridge
  v1.30.0, 31 tools) on every call this run; no outage.
- **Server 3 probe 1 (07:43:42 UTC):** `systemctl show FRIDAY.service`
  MainPID=138648, MemoryCurrent=314,437,632, MemoryMax=314,572,800,
  NRestarts=6, ActiveState=active. `ps` RSS 204,548 kB, VmSwap
  119,280 kB. `journalctl -u FRIDAY.service` grep 'killed process'
  returned 0 — same wrong-filter class as checkpoint 21: kernel OOM
  lines are not under the `-u` unit filter; use `journalctl -k`.
  Loopback `/health` curl timed out at 5 s (000) — process alive but
  unresponsive under swap thrash (VmSwap ~116 MB) at 99.96% of cap.
- **Server 3 probe 2:** `journalctl -k --since '2026-11-27 00:00:00
  UTC'` — 50 `Memory cgroup out of memory: Killed process` lines; 50
  `out of memory` lines in the full journal. Last kills: #42 PID
  135781 06:07:05 UTC, #43 PID 136966 07:11:24 UTC, #44 PID 138320
  07:27:40 UTC, #45 PID 138648 07:44:01 UTC — all python, all
  FRIDAY.service memcg. The 136966-fate grep returned the 07:44:01
  oom-kill block for 138648: `oom-kill:constraint=CONSTRAINT_MEMCG`,
  `oom_memcg=/system.slice/FRIDAY.service`, systemd "Main process
  exited, code=killed, status=9/KILL", "Failed with result
  'oom-kill'". Port 10000: no listener. `/health`: 000 refused.
- **Server 3 probe 3 (07:44:39 UTC):** MainPID=139321, age 00:31, RSS
  198,272 kB, MemoryCurrent=188,858,368, NRestarts=7, port 10000
  LISTENING (python pid 139321), `/health` 200 (1.60 s). Kills since
  06:07:05 UTC: 4 lines including #42 itself → 3 new kills.
- **No cap change, no restart, no deploy this run** (see §1).

## 3. What this means for the held items

- **VOI-045 run 28** (TP10 head): stays HELD. The malloc_trim fix is
  now TASK-VOI-046, owned by M14 (WATCH261 §C, CLAIMED on main
  d7c30e75) — that is M14's assignment track, not TP1's; TP1 does not
  touch VOI-045/VOI-046. FRD-064 stays the diagnosis + monitoring head
  until the coordinator rules (WATCH263 carries the FRD-064 fix
  ruling, TP1 #1237).
- **FRD-064 fix direction:** still pending the coordinator ruling on
  TP10's evidence. No further cap raise, no footprint-reduction work
  taken unilaterally. The new evidence for the ruling: two consecutive
  ~16-min lives under the 300M cap — the cap is not a fix.
- **VOI-027 calm window** still blocked by kills (WATCH261 §G).

## 4. Hub + board state this run

- Hub #2045 read through comment 7236091514 (TP3 status, 07:40:33Z).
  **WATCH261 (7235730851), WATCH261 correction (7235751991), WATCH262
  (7236059938), WATCH262 correction (7236070376), BE 12:20 (7235551801)
  read in full.** No P0, no verifier duty for TP1, no new TP1
  assignment. Verdict column in WATCH262 §C: #2300→M15, #2303→M12;
  overdue #2292→TP6, #2293→M5, #2296→M8 — none TP1. VOI-046 → M14
  (WATCH261 §C); FRD-064 fix ruling carried to WATCH263.
- Main HEAD d7c30e75 (fetched first-hand, explicit refspec). Board on
  main (blob c3edf42a, 13,153 lines, verified first-hand):
  TASK-FRD-064 CLAIMED / muse_tp1 / pr null (branch field still stale:
  `musetp1/task-frd-064-oom-kill-root-cause` vs actual
  `musetp1/task-frd-064-oom-kills-chat-turns` — the root-cause branch
  404s; correction rides the coordinator's board PR);
  TASK-EARN-017 AVAILABLE / muse_tp1 (pre-staged next);
  TASK-VOI-045 CLAIMED / muse_tp10; TASK-VOI-046 CLAIMED / muse_14
  (new, WATCH261); TASK-VOI-031 AVAILABLE / owner null (gated on
  FRD-064 OOM-fix deploy); TASK-WEB-007 MERGED pr 2075; TASK-FRD-062
  MERGED pr 2108.
- Open PRs: 44 open, none headed `musetp1/` (verified first-hand via
  pulls API). No open musetp1 PRs. Checkpoint docs only, no code PR.
- Weekly usage 16% (resets Dec 2, 17:43 IST).

## 5. Five states (unchanged from checkpoint 21 except test cycles)

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (six observation cycles under 300M: 32, 16, ~96, ~64, 16, 16 min)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (kills continue; acceptance is no OOM kills)

## 6. Next

Next driver run: re-probe (kill #46 status, live PID 139321 fate — RSS
~194 MB at 31 s old, expect the kill inside ~16–30 min on the current
trajectory), file checkpoint 23; watch for the coordinator's FRD-064
fix ruling in WATCH263. Queue unchanged: FRD-064 → EARN-017. FRD-064
stays head.
