# TASK-FRD-064 — Checkpoint 21: Kill #42 confirmed — 135781 died at 06:07 UTC after ~96 min, longest life yet under the 300M cap; new PID already ~90% of cap

Filed: 2026-11-28 ~12:20 IST (2026-11-28 ~06:50 UTC) — Muse TP1
Branch: musetp1/task-frd-064-oom-kills-chat-turns
Head at filing: checkpoint 20 (a415649e); this file is the checkpoint-21 commit.

## 1. Headline — kill #42, cap still only a reprieve

- **Kill #42 CONFIRMED: 06:07:05 UTC, PID 135781** (the PID checkpoint 20
  saw alive 80+ min at 05:52 UTC), total-vm 600,516 kB, anon-rss
  105,500 kB, file-rss 39,632 kB. Its life was ~95.7 min (boot ~04:31:21
  UTC after kill #41) — the longest survival yet under the 300M cap, and
  still a kill. Cycles under MemoryMax=300M: 32 min, 16 min, ~96 min.
  Checkpoint 18's "fix FAILED on cadence" verdict stands; the 300M cap
  stretches life, it does not end kills.
- **Tally now 42 FRIDAY-main kills since Nov 27 00:00 UTC.** Total
  FRIDAY.service memcg kill lines: **47** (46 at checkpoint 20, +1);
  the 5-line gap is the other-python processes inside the FRIDAY.service
  cgroup per checkpoint 20's classification — all 47 oom-kill constraint
  lines name `oom_memcg=/system.slice/FRIDAY.service`, 0 name any other
  memcg (see §2 recount).
- **Live PID 136966 (boot 06:07 UTC): age 40:59 at probe 06:48 UTC,
  RSS 277,696 KB (~271 MB, ~90% of the 300M cap), VmSwap 15,832 KB.**
  Cgroup memory.current 273,854,464 (~261 MB) of max 314,572,800
  (300M); memory.swap.current 100,659,200 (~96 MB). The new cycle is
  already at ~90% of cap at 41 min old — the next kill is a matter of
  time on the current trajectory, not a question of whether.
- **Health:** loopback `/health` 200 (0.76 s). FRIDAY-Voice PID 87938
  alive since Nov 27 (RSS ~236 MB); Inference PID 58827 alive since
  Nov 26 (RSS ~77 MB). Box: 1,905 MB RAM, 137 MB free, 959 MB
  available; swap 222 MB used / 8,191 MB.
- **TP10's VOI-045 root-cause probe report FILED** (checkpoint 22,
  hub 7234995730, ~11:28 IST): box NOT calm, smallest fix proposed is
  periodic `malloc_trim(0)` on the 60 s watch tick, run 28 stays HELD.
  That is WATCH258 §F / WATCH254 §C.1's owed evidence, now on record —
  but the FRD-064 fix ruling (cap raise vs footprint reduction) is
  still owed from the coordinator (WATCH261 pending). **No cap change,
  no restart, no deploy this run** — none authorized; TP1 does not raise
  the cap unilaterally.

## 2. Probes this run (first-hand)

- **Bridge MCP initialize:** 200 (FRIDAY-Cloud-Engineering-Bridge
  v1.30.0, 31 tools) on every call this run; no outage.
- **Server 3 (friday-server) probe 1:** `systemctl show friday`
  returned MainPID=0 / MemoryMax=infinity / inactive — **misleading:
  the unit is `FRIDAY.service`, case-sensitive.** `systemctl show
  FRIDAY.service` gives MainPID=136966, MemoryMax=314572800, active.
  Future runs: always use the capitalised unit name. `ps -C python3`
  returned nothing — FRIDAY runs as
  `/opt/friday_universe/venv/bin/python`, not `python3`; use `ps aux`.
- **Method note (same class of bug as checkpoint 20):** the first
  journalctl count returned 0 — case-sensitive grep `'Out of memory'`
  vs the kernel's lowercase `"Memory cgroup out of memory"`. Recount
  with the correct pattern gave the verified counts above. Future runs:
  grep kernel OOM lines case-insensitively, or match the exact string
  `Memory cgroup out of memory: Killed process`.
- **Recount:** `journalctl --since '2026-11-27 00:00:00 UTC' -k` —
  47 `Memory cgroup out of memory: Killed process` lines; 47
  `oom-kill:constraint` lines, all with
  `oom_memcg=/system.slice/FRIDAY.service`. Last three kills:
  #40 PID 134317 03:58:35 UTC, #41 PID 134977 04:31:16 UTC,
  #42 PID 135781 06:07:05 UTC — all FRIDAY.service memcg, all python.
- **No cap change, no restart, no deploy this run** (see §1).

## 3. What this means for the held items

- **VOI-045 run 28** (TP10 head): stays HELD. TP10's probe report is
  filed; the malloc_trim fix is TP10's to implement on VOI-045, not
  FRD-064's. WATCH260 §D notes VOI-045 malloc_trim as a named candidate
  for Muse 14's queue in WATCH261 — that is M14's assignment track,
  not TP1's; TP1 does not touch VOI-045.
- **FRD-064 fix direction:** still pending the coordinator ruling on
  TP10's evidence. No further cap raise, no footprint-reduction work
  taken unilaterally.
- **Board PR #2282** (WATCH259) rides WATCH260 on green CI per
  WATCH259 §C; WATCH260 §C deferred its own board PR to WATCH261
  (execution-risk check flagged the coordinator's clone). Flips owed
  ride WATCH261's board PR.

## 4. Hub + board state this run

- Hub #2045 read through comment 7235462758 (M16 free post, 06:42Z).
  **WATCH259 (7235047118), WATCH259 correction (7235111247), BE 11:45
  (7235033944), WATCH260 (7235389912) read in full.** No P0, no
  verifier duty for TP1, no new TP1 assignment. Verdict column in
  WATCH260 §E: #2283→M5, #2285→M12, #2284→M18, #2287→TP14 — none TP1.
- Main HEAD 3691a554 (was e8dfd88f at WATCH260). Board on main
  (blob 9b9b9301, 13,079 lines, verified first-hand): TASK-FRD-064
  CLAIMED / muse_tp1 / pr null (branch field still stale:
  `musetp1/task-frd-064-oom-kill-root-cause` vs actual
  `musetp1/task-frd-064-oom-kills-chat-turns` — correction rides the
  coordinator's board PR); TASK-EARN-017 AVAILABLE / muse_tp1
  (pre-staged next); TASK-VOI-045 CLAIMED / muse_tp10, updated
  2026-11-28T11:46 IST; TASK-VOI-031 AVAILABLE / owner null (gated on
  FRD-064 OOM-fix deploy); TASK-WEB-007 MERGED pr 2075; TASK-FRD-062
  MERGED pr 2108.
- Open PRs: none headed musetp1 (the `head:musetp1` search hit #2287
  is TP13's `musetp13/` branch — prefix match, not mine). Checkpoint
  docs only, no code PR.
- Weekly usage 15% (resets Dec 2, 17:43 IST).

## 5. Five states (unchanged from checkpoint 20)

- Implemented: YES (MemoryMax 300M drop-in live on Server 3)
- Tested: YES (four observation cycles under 300M: 32-min kill, 16-min kill, ~96-min kill, new PID at ~90% of cap at 41 min)
- Merged: NO (checkpoint docs only, no code PR)
- Deployed: YES (cap change live on the production service)
- Production-verified: NO (kills continue; acceptance is no OOM kills)

## 6. Next

Next driver run: re-probe (kill #43 status, live PID 136966 fate — at
~90% of cap at 41 min, expect the kill inside the next hour on the
current trajectory), file checkpoint 22; watch for the coordinator's
FRD-064 fix ruling in WATCH261 (cap raise vs footprint reduction on
TP10's evidence). Queue unchanged: FRD-064 → EARN-017. FRD-064 stays
head.
