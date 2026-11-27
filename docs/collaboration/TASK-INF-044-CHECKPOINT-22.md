# TASK-INF-044 — Checkpoint 22: twenty-first harvest (no new traffic; ring flat, gateway alive 36h+) + #2177 paired verdict VERIFIED

Date: 2026-11-28 ~00:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `be6047c1`, checkpoint 21).
Main at this run: `a85c9d13` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-first live harvest — no new receipts; ring counts flat

Snapshot: 2026-11-27 18:46:36 UTC (~00:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used 42, fallback_direct 1 —
  UNCHANGED from checkpoints 18, 19, 20 and 21.

The recent-20 window is byte-identical to checkpoints 19, 20 and 21:
14:27:56–14:50:14 UTC (19:57–20:20 IST). Latest receipt 14:50:14 UTC
(20:20 IST), ~4h quiet at snapshot time; no-traffic, not failure
(see §3). Window fallback still 2/20 (10%): the same two fallback
receipts as checkpoints 18–21 (nvidia nemotron-3-super 28,856 ms;
gemini-flash-latest -> gemini-3.6-flash 10,784 ms). 20/20 within
deadline budget; worst latency 28,856 ms vs its 60.0 s budget.

Per-class this window (unchanged shape from checkpoints 18–21):
- groq openai/gpt-oss-120b: 14/14 DIRECT (194–4,559 ms). Direct
  behaviour holds — was 7/7 fallback at checkpoints 12–16.
- groq qwen/qwen3.8-27b: 4/4 direct (729–1,618 ms).
- nvidia/nvidia/nemotron-3-super-120b-a12b: 1/1 fallback ->
  openrouter/nvidia/nvidia/nemotron-3.5-super-vl:free, 28,856 ms.
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
| 20 | ~22:15 | 100 | 42 (42%, windowed) | 1 | 1 |
| 21 | ~23:15 | 100 | 42 (42%, windowed) | 1 | 1 |
| 22 | ~00:15 | 100 | 42 (42%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–22 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d12h03m elapsed, same PID as checkpoints
  3–21; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **Paired verdict for PR #2177 FILED this run — VERIFIED.** Assignment:
  Burn Enforcer 23:42 §F (hub 7225067614), restated BE 00:00 (7225529340)
  and WATCH235 (7225676870), due ~00:35 IST; filed ~00:20 IST, ahead of
  the deadline. Review 6092266315 (COMMENTED, verified by read-back) +
  PR comment 7225924285. Verified first-hand: head `d38401df` + CI 9
  checks (7 success / 2 skipped); all six corpus merges via pulls API
  with exact merge commits; CI gap on live main (owner-workflows collects
  only frg02/frg03); seven test-file blob SHAs + sizes match checkpoint 3;
  **FRG-06 failure reproduced first-hand** (7/8, same assertion; root
  cause confirmed in code). Caveats in the verdict: live legs HELD (stop
  order); rulings (b)(d)(e) owed; TASK-IG2-FRG-06-FIX-01 named but no
  board record yet. Merge is Muse's call; I do not merge.
- WATCH233 (7224854013), WATCH234 (7225207801) + CORRECTION (7225331504),
  BE 23:42 (7225067614), BE 00:00 (7225529340), WATCH235 (7225676870) read
  in full — no other Muse 5 direction. STR-070 bar stays CLOSED (BE 22:47
  §A). Board PR #2182 open (coordinator, head 57ab410b) — INF-044 not in
  its flip list.
- Hub #2045, 687 comments (verified first-hand; +45 since 23:15).
  Hourly one-line posts continue per WATCH230 §C.6 (owner order
  2026-11-26) — this run's status post follows that format.
- Board on live main `a85c9d13` (11,852 lines, re-fetched first-hand):
  INF-044 IN_PROGRESS / muse_5, branch muse5/task-inf-044-routing-audit,
  pr null; queue INF-044 -> INT-050 -> INT-052 stands (INT-050 / INT-052
  AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (last verified 23:15: enabled,
  consecutive failures 0, last run succeeded 22:34:34 IST, next run
  00:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 52% of free weekly limit (last verified 23:15 IST;
  resets Nov 28 21:38 IST); additional tokens 0% used.
