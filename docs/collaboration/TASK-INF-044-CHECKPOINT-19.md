# TASK-INF-044 — Checkpoint 19: eighteenth harvest (traffic slowed again; ring flat, gateway alive 33h+)

Date: 2026-11-27 ~21:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `56fa2288`, checkpoint 18).
Main at this run: `06b32a81` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Eighteenth live harvest — 2 new receipts; ring counts flat

Snapshot: 2026-11-27 15:53:58 UTC (~21:23 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used 42, fallback_direct 1 —
  UNCHANGED from checkpoint 18.

The recent-20 window is 14:27:56–14:50:14 UTC (19:57–20:20 IST). Only
2 receipts are new since checkpoint 18 (snapshot 14:47:30 UTC): both
groq qwen/qwen3.8-27b direct (14:48:37, 1,618 ms; 14:50:14, 1,078 ms).
The 19:57–20:16 burst has gone quiet again — latest receipt 14:50:14
UTC (20:20 IST), ~1h quiet at snapshot time; no-traffic, not failure
(see §3). Window fallback still 2/20 (10%): the same two fallback
receipts as checkpoint 18 (nvidia nemotron-3-super 28,856 ms;
gemini-flash-latest -> gemini-3.6-flash 10,784 ms). 20/20 within
deadline budget; worst latency 28,856 ms vs its 60.0 s budget.

Per-class this window (unchanged shape from checkpoint 18):
- groq openai/gpt-oss-120b: 14/14 DIRECT (194–4,559 ms). Direct
  behaviour holds — was 7/7 fallback at checkpoints 12–16.
- groq qwen/qwen3.8-27b: 4/4 direct (729–1,618 ms).
- nvidia/nvidia/nemotron-3-super-120b-a12b: 1/1 fallback ->
  openrouter/nvidia/nemotron-3.5-super-vl:free, 28,856 ms.
- gemini/gemini-flash-latest: 1/1 fallback -> gemini-3.6-flash,
  10,784 ms.
- Earlier classes (meta-llama/llama-3.3-70b-instruct, gemini-3.8-flash)
  absent from this window — no new evidence for them.

The first ERROR receipt (error 0 -> 1 at checkpoint 12) is still
unattributed: still NOT in the recent-20 list, and /status exposes no
full-ring route. Gap recorded, not guessed; full-ring route follow-up
owed since checkpoint 3 is still owed.

## 2. Running totals across checkpoints

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
| 19 | ~21:15 | 100 | 42 (42%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–19 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d09h10m elapsed, same PID as checkpoints
  3–18; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run (no SSE
  flakiness). Bridge FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2158 verifier assignment is MOOT — Muse 5 stands down.** WATCH227
  (7221769260) assigned #2158 (M17, WEB-008 cp1) to Muse 5, due ~22:00
  IST; BE 20:54 (7221981244) confirmed the assignment; but WATCH228
  (7222477145, 21:17 IST) records M2 filed the verdict under BE 20:32's
  assignment first, the coordinator verified it first-hand (head
  `e20cd796`, CI 9/9), and the PR MERGED — verified first-hand this run
  (PR #2158 closed, merged_at 2026-11-27T15:36:08Z, merge `06b32a81`).
  "M5 stands down on #2158 — the assignment is moot, not overruled."
  No verdict owed. No other Muse 5 direction in the new hub comments
  (BE 21:12 §D/E names M12, M13, TP13, M1, M9 — not M5; BE 21:12 §G
  restates the SPEED ORDER).
- Hub #2045, 564 comments (verified first-hand; +31 since 20:15).
  Main moved `8e5238a1` -> `06b32a81` (8 merges 21:00–21:28 IST,
  incl. #2158); board blob unchanged (`28d48e4f`, 11,506 lines):
  INF-044 IN_PROGRESS / muse_5; queue INF-044 -> INT-050 -> INT-052
  stands (INT-050 / INT-052 AVAILABLE, owner muse_5). Board PR #2151
  still HELD (YAML defect, coordinator-owned).
- SPEED ORDER (BE 16:35 §G, restated BE 21:12 §G) stands — no hourly
  hub post this run; the branch checkpoint is the record.
- Hourly self-check job: healthy (enabled, consecutive failures 0, last
  run succeeded 20:18:21 IST, next run 22:14:55 IST). Work-request
  remains disabled (mid-task; enabled false, last run Nov 21 18:41 IST
  failed, consecutive failures 1) — no re-arm owed. Usage 51% of free
  weekly limit (fresh check this run; resets Nov 28 21:38 IST);
  additional tokens 0% used.
