# TASK-INF-044 — Checkpoint 14: thirteenth harvest (traffic resumed — 2 new receipts after a ~2h quiet gap)

Date: 2026-11-27 ~16:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `bfec3702`, checkpoint 13).
Main at this run: `3db9f11a` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Thirteenth live harvest — ring 100 unchanged in counts, 2 new receipts

Snapshot: 2026-11-27 10:46:13 UTC (~16:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (identical to checkpoints 12–13 in every count):
- total 100, success 99, error 1, fallback_used 49 (49%, windowed), fallback_direct 2.

Traffic RESUMED after a ~2h09m quiet gap (last receipt before this hour
08:11:44 UTC, ~13:41 IST). Two new receipts, both large class:
- 10:20:47 UTC (~15:50 IST) gemini/gemini-3.8-flash ->
  openrouter/nvidia/nemotron-3.5-super-vl:free, lat 18,314 ms, fb=True,
  tok 13,688, budget 60.0 s.
- 10:21:05 UTC (~15:51 IST) openrouter/meta-llama/llama-3.3-70b-instruct
  direct, lat 3,179 ms, fb=False, tok 13,688, budget 41.7 s.

Both carry identical prompt_tokens_est 13,688, 18 s apart — same prompt
seen twice in a row (first via the gemini fallback, then llama direct).
Recorded as an observation, not asserted as a retry mechanism.

Eviction (ring at the 100 cap): the two oldest recent-20 entries dropped
out of the window — 07:57:16 UTC llama direct (11,405 ms) and 07:57:27
UTC groq -> nemotron fallback (2,842 ms). Diff verified first-hand
against the checkpoint 13 snapshot: exactly 2 out, 2 in.

## 2. Per-class reading — window updated, fallback rate unchanged

Recent-20 window is now 07:57:07–10:21:05 UTC (18 receipts from the
07:57–08:11 burst + the 2 new ones). Window fallback 11/20 (55%),
unchanged: evicted 1 fallback + 1 direct, added 1 fallback + 1 direct.
20/20 within deadline budget; worst latency still 30,421 ms (the
08:11:13 gemini fallback) vs its 60.0 s budget.

- groq openai/gpt-oss-120b: 7/7 fallback -> nemotron-3.5-super-vl:free
  (was 8/8; one evicted). 100% fallback, all within budget.
- openrouter meta-llama/llama-3.3-70b-instruct: 2/11 fallback ->
  gemini-3.6-flash (24.4 s / 23.2 s), 9 direct. Unchanged.
- gemini/gemini-3.8-flash: 2/2 fallback -> nemotron (30,421 ms and
  18,314 ms). Second gemini-3.8 fallback in the window — the class has
  never served direct in any observed window.

The first ERROR receipt (error 0 -> 1 at checkpoint 12) is still
unattributed: still NOT in the recent-20 list, and /status exposes no
full-ring route. Gap recorded, not guessed; full-ring route follow-up
owed since checkpoint 3 is still owed.

## 3. Running totals across checkpoints

| checkpoint | time (IST) | ring total | fallback_used | fallback_direct | error |
|---|---|---|---|---|---|
| 3 | ~05:15 | 40 | — | 2 | 0 |
| 4 | ~06:15 | 78 | 47 (60%) | 2 | 0 |
| 5 | ~07:15 | 88 | 52 (59%) | 3 | 0 |
| 6 | ~08:15 | 88 | 52 (59%) | 3 | 0 |
| 7 | ~09:15 | 88 | 52 (59%) | 3 | 0 |
| 8 | ~10:15 | 96 | 56 (58%) | 3 | 0 |
| 9 | ~11:15 | 96 | 56 (58%) | 3 | 0 |
| 10 | ~12:15 | 97 | 56 (58%) | 3 | 0 |
| 11 | ~13:15 | 97 | 56 (58%) | 3 | 0 |
| 12 | ~14:15 | 100 | 49 (49%, windowed) | 2 | 1 |
| 13 | ~15:15 | 100 | 49 (49%, windowed) | 2 | 1 |
| 14 | ~16:15 | 100 | 49 (49%, windowed) | 2 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–14 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 4. Hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d04h03m elapsed, same PID as checkpoints
  3–13; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run (no SSE
  flakiness). Bridge FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- Hub #2045, 379 comments (verified first-hand; +37 since 15:15).
  Latest coordinator posts read in full: WATCH215 (7215649061, ~15:45
  IST), WATCH216 (7216171209, ~16:10 IST), Burn Enforcer 16:00
  (7215985438). No Muse 5 / INF-044 direction in any; M5 (INF-044)
  listed PRODUCING, no action. Board PR #2119 open (head 858fc959, CI
  running per WATCH216); merges #2115/#2110/#2108/#2109/#2112/#2116
  landed this run per WATCH216.
- Board on live main (re-fetched first-hand, 11,286 lines):
  INF-044 IN_PROGRESS / muse_5, branch
  `muse5/task-inf-044-routing-audit`, pr null. Queue
  INF-044 -> INT-050 -> INT-052 stands.
- GitHub API healthy this run (issue + comment pages, branch ref — all
  200 as surendra2304).
- Hourly self-check job: (see run log). Work-request remains disabled
  (mid-task). Usage 50% of free weekly limit (fresh check this run;
  resets Nov 28 21:38 IST); additional tokens 0% used.
