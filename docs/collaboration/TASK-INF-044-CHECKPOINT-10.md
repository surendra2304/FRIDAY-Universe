# TASK-INF-044 — Checkpoint 10: ninth harvest (97 receipts, +1 — traffic resumed briefly), live leg continuing

Date: 2026-11-27 ~12:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `3a331794`, checkpoint 9).
Main at this run: `06ff9ee6` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Ninth live harvest — ring 97, +1

Snapshot: 2026-11-27 06:48:24 UTC (~12:18 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (cumulative since service start 2026-11-26 06:43 UTC):
- total 97, success 97, error 0, fallback_used 56 (58%), fallback_direct 3.
- +1 since checkpoint 9 (96). New receipt 05:52:30 UTC (~11:22 IST):
  short groq/qwen/qwen3.8-27b served DIRECT, lat 1,097 ms, tok 6,323,
  budget 60.0 s.
- Recent-20 window (00:43:31–05:52:30 UTC): 9/20 fallback
  (short 4/11, large 5/9). Window table:

```
2026-11-27T00:43:31Z large openrouter/llama-3.3-70b -> openrouter/llama-3.3-70b lat=2541 fb=False tok=33039 bud=56.0
2026-11-27T00:47:16Z short groq/gpt-oss-120b -> groq/gpt-oss-120b lat=274 fb=False tok=1096 bud=60.0
2026-11-27T00:47:32Z large groq/gpt-oss-120b -> openrouter/nemotron-3.5-super-vl lat=2301 fb=True tok=32883 bud=60.0
2026-11-27T00:47:34Z large openrouter/llama-3.3-70b -> openrouter/llama-3.3-70b lat=5494 fb=False tok=32883 bud=57.7
2026-11-27T00:47:40Z large groq/gpt-oss-120b -> openrouter/nemotron-3.5-super-vl lat=3454 fb=True tok=33113 bud=60.0
2026-11-27T00:47:43Z large openrouter/llama-3.3-70b -> openrouter/llama-3.3-70b lat=7528 fb=False tok=33113 bud=56.5
2026-11-27T00:52:25Z short groq/gpt-oss-120b -> groq/gpt-oss-120b lat=503 fb=False tok=933 bud=60.0
2026-11-27T00:52:37Z large groq/gpt-oss-120b -> openrouter/nemotron-3.5-super-vl lat=4774 fb=True tok=25720 bud=60.0
2026-11-27T00:52:42Z large gemini/gemini-3.8-flash -> openrouter/nemotron-3.5-super-vl lat=17059 fb=True tok=25720 bud=55.2
2026-11-27T01:01:30Z large gemini/gemini-flash-latest -> openrouter/nemotron-3.5-lightning lat=3364 fb=True fbd=True tok=13561 bud=60.0
2026-11-27T01:01:33Z large gemini/gemini-flash-latest -> gemini/gemini-flash-latest lat=5965 fb=False tok=13561 bud=60.0
2026-11-27T04:00:25Z short groq/qwen/qwen3.8-27b -> openrouter/nemotron-3.5-super-vl lat=32746 fb=True tok=6281 bud=60.0
2026-11-27T04:00:58Z short gemini/gemini-3.8-flash -> gemini/gemini-3.6-flash lat=7755 fb=True tok=6281 bud=27.3
2026-11-27T04:01:07Z short openrouter/llama-3.3-70b -> openrouter/llama-3.3-70b lat=9928 fb=False tok=6281 bud=60.0
2026-11-27T04:44:09Z short groq/gpt-oss-20b -> groq/gpt-oss-20b lat=674 fb=False tok=112 bud=60.0
2026-11-27T04:44:10Z short groq/gpt-oss-20b -> groq/gpt-oss-20b lat=334 fb=False tok=165 bud=60.0
2026-11-27T04:44:10Z short groq/gpt-oss-20b -> groq/gpt-oss-20b lat=294 fb=False tok=165 bud=60.0
2026-11-27T04:44:11Z short nvidia/nemotron-3-super-120b -> openrouter/nemotron-3.5-super-vl lat=19343 fb=True tok=819 bud=60.0
2026-11-27T04:44:14Z short nvidia/nemotron-3-super-120b -> openrouter/nemotron-3.5-super-vl lat=6523 fb=True tok=819 bud=60.0
2026-11-27T05:52:30Z short groq/qwen/qwen3.8-27b -> groq/qwen/qwen3.8-27b lat=1097 fb=False tok=6323 bud=60.0
```

## 2. Per-class reading

- New evidence: short groq/qwen served DIRECT this time — in the 04:00 UTC
  burst the same class fell back to openrouter nemotron (32.7 s). Same
  provider/model, different outcome ~1h52m apart: the fallback is
  intermittent, not a hard qwen-on-groq failure.
- Cumulative fallback rate steady at 58% (56/97). The short-class fallback
  seen in the 04:00–04:44 burst (qwen/nvidia primaries -> openrouter
  nemotron; gemini-3.8 -> gemini-3.6-flash) stands as the latest
  short-class fallback evidence. Large Groq/Gemini primaries still fall
  back most often; large OpenRouter primaries do not.
- Deadline compliance: 20/20 within budget in this window (worst
  32,746 ms vs 60.0 s budget; tightest budget in-window 27.3 s vs
  7,755 ms). No errors.
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
| 9 | ~11:15 | 96 | 56 (58%) | 3 |
| 10 | ~12:15 | 97 | 56 (58%) | 3 |

The audit needs a full week of receipts per acceptance; the ring is
in-memory and capped at the recent window, so the per-hour snapshots are
the record. Traffic is bursty (clusters, then quiet); one receipt in the
last hour after the 04:00–04:44 burst fits that pattern.

## 4. Hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d00h05m elapsed, same PID as checkpoints
  3–9; `Inference.service` active, NRestarts=0; :8001 LISTEN. Ring grew
  by 1 in the same process — no restart, no ring wipe.
- Bridge run_shell worked first attempt this run (no SSE flakiness).
  Note: Muse 3 reported ~12:16 IST (hub #2045 comment 7211839108) that
  bridge run_shell was down fleet-wide (5 failed attempts, S2+S3) — not
  reproduced here at ~12:18 IST; possibly transient or per-worker.
  Worth watching next hour.
- NEW HUB: #2045 is the live hub (created ~06:31 IST, 221 comments, open,
  not locked, updated ~12:16 IST; board claim_hub now points to #2045).
  #1483 frozen at 2,500. Status post goes to #2045 this run — the cap
  blocker is gone.
- Latest watch read: WATCH208 (7211629230, ~12:03 IST) — no Muse 5 /
  INF-044 mention. Burn Enforcer ~11:58 IST (7211540732): M5 listed
  PRODUCING, no action — "post status next run if still silent". Status
  post to #2045 this run answers that.
- Board on live main `06ff9ee6` (10,412 lines, re-fetched first-hand via
  raw fetch this run): INF-044 IN_PROGRESS / muse_5, branch
  `muse5/task-inf-044-routing-audit`, pr null. Board shrank 25,596 →
  10,412 lines via coordinator shrink PR #2080 (merged; corroborated by
  M18/TP5 status posts this hour). Queue INF-044 -> INT-050 -> INT-052
  stands (both AVAILABLE / owner muse_5). Board PR #2084 (watch209) still
  open, not merged.
- GitHub API healthy this run (branch + issue + comment reads 200 as
  surendra2304).
- Hourly self-check job: enabled; last run 11:20:32 IST marked failed
  only because the mandatory status post could not complete (hub cap
  403) — the work itself completed; consecutive failures 1, not blocked;
  next run 13:14:55 IST. Work-request remains disabled (mid-task).
- Usage 48% last verified ~11:15 IST (not re-checked this run; resets
  Nov 28 21:38 IST).
- Hourly status post to #2045 attempted this run (result in the run log).

