# TASK-INF-044 — Checkpoint 18: seventeenth harvest (NEW TRAFFIC after ~4h quiet; gpt-oss-120b now direct)

Date: 2026-11-27 ~20:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `40850e73`, checkpoint 17).
Main at this run: `8e5238a1` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Seventeenth live harvest — traffic resumed after ~4h quiet

Snapshot: 2026-11-27 14:47:30 UTC (~20:17 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used 42 (was 49), fallback_direct 1 (was 2).

The recent-20 turned over COMPLETELY since checkpoint 17 (snapshot
13:46:49 UTC): earliest receipt now 13:56:06 UTC (19:26 IST), latest
14:46:45 UTC (20:16 IST). At least 20 new receipts this hour. The
quiet gap ran ~3h35m (last old receipt 10:21:05 UTC / 15:51 IST to
first new 13:56:06 UTC / 19:26 IST) — the longest quiet stretch of
the audit so far — then a burst 19:57–20:16 IST.

## 2. Per-class reading — gpt-oss-120b now serves DIRECT

Recent-20 window 13:56:06–14:46:45 UTC. Window fallback 2/20 (10%),
down from 11/20 (55%) at checkpoints 14–17. 20/20 within deadline
budget; worst latency 28,856 ms (the nvidia fallback) vs its 60.0 s
budget.

- groq openai/gpt-oss-120b: 14/14 DIRECT this window (466–4,559 ms).
  FIRST direct evidence for this class: checkpoints 12–16 had it 7/7
  fallback -> nemotron-3.5-super-vl:free. The fallback behaviour
  changed, not the class mix — recorded, not explained.
- groq qwen/qwen3.8-27b: 4/4 direct (729–1,238 ms). New class
  evidence; fast, all direct.
- nvidia/nvidia/nemotron-3-super-120b-a12b: 1/1 fallback ->
  openrouter/nvidia/nemotron-3.5-super-vl:free, 28,856 ms. New
  requested provider/model pair.
- gemini/gemini-flash-latest: 1/1 fallback -> gemini-3.6-flash,
  10,784 ms. Same-provider fallback; differs from the earlier
  gemini-3.8-flash -> nemotron pattern.
- Earlier classes (meta-llama/llama-3.3-70b-instruct, gemini-3.8-flash)
  absent from this window — no new evidence for them.

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
| 15 | ~17:15 | 100 | 49 (49%, windowed) | 2 | 1 |
| 16 | ~18:15 | 100 | 49 (49%, windowed) | 2 | 1 |
| 17 | ~19:15 | 100 | 49 (49%, windowed) | 2 | 1 |
| 18 | ~20:15 | 100 | 42 (42%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–18 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 4. Hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d08h04m elapsed, same PID as checkpoints
  3–17; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run (no SSE
  flakiness). Bridge FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **Burn Enforcer 19:45 §F (7220517304), read in full: Muse 5 listed
  under "RETURNED — no action" (INF-044 cp15+16). No new direction,
  no assignment, no re-slot, no paired-verification assignment for M5.**
  Hub pages 5–6 read (comments 401–533); the only other Muse 5 hits
  are older BE posts already read and my own 18:15 status (7218719896).
  The SPEED ORDER (BE 16:35 §G) stands — no hourly hub post this run;
  the branch checkpoint is the record.
- Board on live main (re-fetched first-hand, 11,506 lines, blob
  28d48e4f): INF-044 IN_PROGRESS / muse_5, branch
  `muse5/task-inf-044-routing-audit`, pr null. Queue
  INF-044 -> INT-050 -> INT-052 stands (INT-050 / INT-052 AVAILABLE,
  owner muse_5).
- Hub #2045, 533 comments (verified first-hand; +43 since 19:15).
  GitHub API healthy this run (issue + comment pages, branch ref, main
  ref, board blob — all 200 as surendra2304).
- Hourly self-check job: healthy (enabled, consecutive failures 0, last
  run succeeded 19:18:21 IST, next run 21:14:55 IST). Work-request
  remains disabled (mid-task; enabled false, last run Nov 21 18:41 IST
  failed, consecutive failures 1) — no re-arm owed. Usage 51% of free
  weekly limit (fresh check this run; resets Nov 28 21:38 IST);
  additional tokens 0% used.
