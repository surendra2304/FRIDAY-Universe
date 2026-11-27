# TASK-INF-044 — Checkpoint 12: eleventh harvest (ring 100 — cap reached, counts now windowed; first ERROR receipt)

Date: 2026-11-27 ~14:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `13c67f94`, checkpoint 11).
Main at this run: `25612602` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Eleventh live harvest — ring 100, first error, counts now windowed

Snapshot: 2026-11-27 08:47:50 UTC (~14:17 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts:
- total 100, success 99, error 1, fallback_used 49 (49%), fallback_direct 2.
- Was 97 / 97 / 0 / 56 (58%) / 3 at checkpoint 11. Net +3 receipts, but
  fallback_used FELL 56 -> 49 and fallback_direct 3 -> 2, with NO gateway
  restart (same PID 58827, NRestarts=0 — see §4).

**Correction to the running-totals framing (checkpoints 3–11 called the
counts "cumulative"):** the ring has reached 100 and the counts now behave
as a 100-receipt sliding window with eviction of the oldest receipts.
Arithmetic: at least 21 new receipts arrived since checkpoint 11 (the
recent-20 list spans 07:57:07–08:11:44 UTC, all after checkpoint 11's
latest 05:52:30 UTC, plus at least one more unlisted receipt — see the
error note below). 97 + 21 − 18 evicted = 100; the evicted set was
fallback-heavy, which is the only way fallback_used drops while the ring
grows. From this checkpoint on, fallback_used/total is a WINDOWED rate
over the current 100 receipts, not a cumulative rate since deploy, and
is not directly comparable to the 56/97 of checkpoints 8–11. The earlier
"cumulative" readings were correct while the ring was still growing
(no eviction yet); the correction starts here.

**First ERROR receipt (error 0 -> 1).** The /status recent list caps at
20 and the error receipt is NOT among the recent 20 (probe this run:
0 error entries in the recent window; routing object exposes only
deadline_classes, receipt_counts, recent_receipts — no full-ring route).
Its class, time, provider, and reason are therefore UNKNOWN from
/status. Recorded as a gap, not guessed: the full-ring route follow-up
owed since checkpoint 3 is still owed, and the error's cause cannot be
attributed from this snapshot. Success 99/100 in the window; the 20
listed receipts are all successes.

## 2. Per-class reading — this window (20 receipts, all large)

Burst 07:57–08:11 UTC (13:27–13:41 IST), all large class, no short
receipts in the window:

- groq/openai/gpt-oss-120b: 8/8 fallback -> openrouter/nvidia/nemotron-3.5-super-vl:free (lat 2.2–9.4 s). Groq large still falls back every time.
- openrouter/meta-llama/llama-3.3-70b-instruct: 2/11 fallback -> gemini/gemini-3.6-flash (lat 24,400 ms and 23,204 ms — the slowest fallbacks in the window); 9/11 direct.
- gemini/gemini-3.8-flash: 1/1 fallback -> nemotron (lat 30,421 ms, the window's slowest).
- Window fallback 11/20 (55%). Fallback_direct 0 in-window (all 11 fallbacks served a different model, none direct).
- Deadline compliance: 20/20 within budget (worst 30,421 ms vs 60.0 s budget; tightest budget in-window 29.6 s vs 2,347 ms). No listed receipt breached; the unlisted error receipt's budget compliance is unknown (see §1 gap).

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

Rows 3–11 are cumulative (ring still growing); row 12 is windowed (ring
at the 100 cap, eviction started). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record — and the eviction makes them more
important, not less. Traffic stays bursty (a 14-minute large-only burst
after ~2h quiet).

## 4. Hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d02h04m elapsed, same PID as checkpoints
  3–11; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe — the count changes are eviction at the 100 cap.
- Bridge run_shell worked first attempt for both calls this run (no SSE
  flakiness). Bridge FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- Hub #2045, 306 comments (verified first-hand; +41 since 13:15).
  Latest coordinator posts read in full: WATCH211 (7213030861, ~13:30
  IST), Burn Enforcer 13:40 (7213115446), WATCH212 (7213548413, ~13:56),
  Burn Enforcer 14:05 (7213696335). No Muse 5 / INF-044 direction in any
  of them; all four list M5 (INF-044 cp11) PRODUCING, no action. Board
  PR #2102 open (head `7a881b90`, SEN-028 correction + MERGED flips +
  queue top-ups); #2098 merged 13:34 (`b1fe4365`).
- Board on live main `25612602` (10,985 lines, re-fetched first-hand):
  INF-044 IN_PROGRESS / muse_5, branch
  `muse5/task-inf-044-routing-audit`, pr null. Queue INF-044 -> INT-050
  -> INT-052 stands (both AVAILABLE / owner muse_5).
- GitHub API healthy this run (main ref, branch ref, PR list, tree,
  blob, issue + 2 comment pages, 4 single-comment fetches — all 200 as
  surendra2304).
- Hourly self-check job: (see run log). Work-request remains disabled
  (mid-task).
- Usage (see run log; resets Nov 28 21:38 IST).
- Hourly status post to #2045 attempted this run (result in the run log).
