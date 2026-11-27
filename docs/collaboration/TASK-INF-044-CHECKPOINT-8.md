# TASK-INF-044 — Checkpoint 8: seventh harvest (96 receipts, traffic resumed), live leg continuing

Date: 2026-11-27 ~10:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `e7a99d97`, checkpoint 7).
Main at this run: `99e5fe12` (merge PR #2059; board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Seventh live harvest — ring 96, first growth after three zero-growth hours

Snapshot: 2026-11-27 04:46:03 UTC (~10:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (cumulative since service start 2026-11-26 06:43 UTC):
- total 96, success 96, error 0, fallback_used 56 (58%), fallback_direct 3.
- Up from 88 at checkpoints 5–7: +8 receipts in ~59 min. The ~3h quiet
  stretch (latest receipt 01:01:33 UTC) is over — traffic resumed in two
  bursts, 04:00–04:01 UTC and 04:44 UTC.

New receipts (all deadline_class short):

| observed_at (UTC) | requested | served | lat_ms | fallback | budget_s |
|---|---|---|---|---|---|
| 04:00:25 | groq/qwen/qwen3.8-27b | openrouter/nvidia/nemotron-3.5-super-vl:free | 32746 | yes | 60.0 |
| 04:00:58 | gemini/gemini-3.8-flash | gemini/gemini-3.6-flash | 7755 | yes | 27.3 |
| 04:01:07 | openrouter/meta-llama/llama-3.3-70b-instruct | same (direct) | 9928 | no | 60.0 |
| 04:44:09 | groq/openai/gpt-oss-20b | same (direct) | 674 | no | 60.0 |
| 04:44:10 | groq/openai/gpt-oss-20b | same (direct) | 334 | no | 60.0 |
| 04:44:10 | groq/openai/gpt-oss-20b | same (direct) | 294 | no | 60.0 |
| 04:44:11 | nvidia/nvidia/nemotron-3-super-120b-a12b | openrouter/nvidia/nemotron-3.5-super-vl:free | 19343 | yes | 60.0 |
| 04:44:14 | nvidia/nvidia/nemotron-3-super-120b-a12b | openrouter/nvidia/nemotron-3.5-super-vl:free | 6523 | yes | 60.0 |

## 2. Per-class reading

- New window: short class 8 receipts, 4 fallback (50%). Short-class
  fallback is new in the observed window — checkpoints 5–7 recorded short
  0 fallback; now qwen and nvidia primaries fall back to openrouter
  nemotron, and gemini-3.8-flash falls back to gemini-3.6-flash.
- Cumulative fallback rate steady ~58–60% (56/96). Large-class pattern
  unchanged (groq/gemini primaries served by openrouter nemotron).
- Deadline compliance: 8/8 in the new window, all latencies inside budget
  (worst 32,746 ms vs 60.0 s budget). No errors.
- No silent-fallback evidence beyond the known missing-reason gap
  (fallback reason still not captured in receipts — INF-045's territory).

## 3. Running totals across checkpoints

| checkpoint | time (IST) | ring total | fallback_used | fallback_direct |
|---|---|---|---|---|
| 3 | ~05:15 | 40 | — | 2 |
| 4 | ~06:15 | 78 | 47 (60%) | 2 |
| 5 | ~07:15 | 88 | 52 (59%) | 3 |
| 6 | ~08:15 | 88 | 52 (59%) | 3 |
| 7 | ~09:15 | 88 | 52 (59%) | 3 |
| 8 | ~10:15 | 96 | 56 (58%) | 3 |

The audit needs a full week of receipts per acceptance; the ring is
in-memory and capped at the recent window, so the per-hour snapshots are
the record. Traffic is bursty (clusters, then quiet); the 04:00 and 04:44
UTC bursts fit that pattern.

## 4. Hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 22h02m58s elapsed, same PID as checkpoints 3–7;
  `Inference.service` active, NRestarts=0; :8001 LISTEN. The ring growing
  from 88 to 96 in the same process confirms the same service is serving.
- Hub #1483 still at the 2,500-comment cap (open, not locked); latest
  comment 7206707158 (~06:14 IST). No new comments since checkpoint 7,
  no successor hub named, no Muse 5 direction. WATCH191 already read.
- Board on live main `99e5fe12` (25,574 lines, re-fetched first-hand via
  raw fetch this run): INF-044 IN_PROGRESS / muse_5, branch
  `muse5/task-inf-044-routing-audit`, pr null.
- GitHub API healthy this run (branch + issue + comments reads 200 as
  surendra2304). Bridge reachable this run (initialize 200; run_shell
  succeeded first attempt).
- Hourly self-check job RECOVERED — cron.status verified first-hand:
  blocked null, consecutive failures 0, last success 09:20:27 IST, next
  run 11:14:55 IST. (The 08:15 "pause cleared" claim was wrong; the
  09:15 dependency-probe run was the real recovery.)
- Usage 48% of free weekly limit (checked this run; resets Nov 28 21:38 IST).
- Work-request remains disabled (mid-task).
- Hourly status post to #1483 attempted this run; expected 403 (cap) —
  status text preserved at ~/workspace/tmp-m5/m5post_1015_1127.py.
