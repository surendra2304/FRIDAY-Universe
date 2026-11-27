# TASK-INF-044 — Checkpoint 23: twenty-second harvest (NEW TRAFFIC — first `large`-class evidence; ring flat) + #2186 verifier assigned to M5

Date: 2026-11-28 ~01:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `106e152c`, checkpoint 22).
Main at this run: `dbaf142a` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-second live harvest — NEW TRAFFIC after ~5h quiet; ring counts flat

Snapshot: 2026-11-27 19:46:29 UTC (~01:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used 42, fallback_direct 1 —
  UNCHANGED from checkpoints 18, 19, 20, 21 and 22.

The recent-20 window turned over: 14 short receipts 14:29:56–14:50:14 UTC
(same as checkpoints 19–22) + 6 NEW `large` receipts 19:18:32–19:21:31 UTC
(00:48–00:51 IST). At least 6 new receipts since checkpoint 22; ring
counts flat via windowed eviction (6 in, 6 out). Window fallback now
6/20 (30%), up from 2/20 (10%) at checkpoints 18–22: the same two short
fallbacks plus 4 new large fallbacks. 20/20 within deadline budget;
worst latency 17,569 ms vs its 56.0 s budget.

Per-class this window:
- SHORT, groq openai/gpt-oss-120b: 9/9 DIRECT (194–4,559 ms). Direct
  behaviour holds — was 7/7 fallback at checkpoints 12–16.
- SHORT, groq qwen/qwen3.8-27b: 4/4 direct (729–1,618 ms).
- SHORT, gemini/gemini-flash-latest: 1/1 fallback -> gemini-3.6-flash,
  10,784 ms (same receipt as checkpoints 18–22).
- LARGE, groq openai/gpt-oss-120b: 3/3 fallback ->
  openrouter/nvidia/nemotron-3.5-super-vl:free (4,043 / 11,835 /
  1,994 ms). FIRST `large`-class evidence in the audit — and all three
  fell back. Prompt tokens ~31–33k in each case.
- LARGE, gemini/gemini-3.8-flash: 1/1 fallback ->
  openrouter/nvidia/nemotron-3.5-super-vl:free, 17,569 ms. First
  gemini-3.8-flash evidence in any window; it fell back.
- LARGE, openrouter/meta-llama/llama-3.3-70b-instruct: 2/2 DIRECT
  (5,651 / 2,104 ms). First llama-3.3-70b evidence since the early
  checkpoints; direct both times, budgets 48.2 s / 58.0 s.

Note the fallback target: all 4 new large fallbacks landed on the same
free-tier model (openrouter/nvidia/nemotron-3.5-super-vl:free). The
`large` class so far is 4/6 fallback (67%) vs `short` 2/14 (14%) in
this window — a class split worth watching as more large receipts
arrive; not yet a breach (all within budget, no deadline miss).

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
| 23 | ~01:15 | 100 | 42 (42%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–23 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d13h03m elapsed, same PID as checkpoints
  3–22; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2177 MERGED 00:36 IST (merge `071b885e`)** — my VERIFIED paired
  verdict (review 6092266315, filed ~00:20, due ~00:35) was used;
  WATCH237 §A credits the first-hand verification (six corpus merges,
  CI 9/9 green). FRG-026 MERGED flip landed via board PR #2189 on main
  `dbaf142a`. TP7 filed the repo-leg COMPLETE post (hub 7226745278).
  Live leg HELD per owner stop order — not production-verified;
  rulings (b)/(d)/(e) + live Forge host naming still owed.
- **NEW ASSIGNMENT — #2186 verifier → Muse 5, due ~02:00 IST.**
  WATCH237 §D (hub 7226239723) assigned PR #2186 (EARN-041 cp2, M9)
  to M5; BE 00:35 §C had assigned it to M18, and BE 00:59 §C (hub
  7226631918) rules the later coordinator post governs — #2186 → M5,
  M18 stands down. Verdict work follows this checkpoint in the same
  run; no #2186 verdict from M18 found in the hub read.
- WATCH236 (7225963308), BE 00:35 (7226089917), WATCH237 (7226239723 /
  duplicate 7226243369), WATCH237 addendum (7226391969), BE 00:59
  (7226631918) read in full — no other Muse 5 direction. BE 00:59 §E
  re-states the speed order (hourly self-check essays abolished; post
  only at claim / completion / genuine block / wrap-up) — this run's
  hub post stays one short status line per WATCH230 §C.6 (owner order
  2026-11-26), covering a genuine state change (new verifier
  assignment + new traffic). STR-070 bar stays CLOSED (BE 22:47 §A).
  Board PR #2189 merged → main `dbaf142a`; INF-044 not in its flip
  list.
- Hub #2045, 728 comments (verified first-hand; +41 since 00:15).
- Board on live main `dbaf142a` (11,859 lines, blob `99e6e2cd`,
  re-fetched first-hand): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; queue INF-044 -> INT-050
  -> INT-052 stands (INT-050 / INT-052 AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (last verified 00:15: enabled,
  consecutive failures 0, last run succeeded 00:14:55 IST, next run
  01:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 52% of free weekly limit (last verified 00:15
  IST; resets Nov 28 21:38 IST); additional tokens 0% used.
