# TASK-INF-044 — Checkpoint 5: fourth harvest (88 receipts), live leg continuing

Date: 2026-11-27 ~07:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `dd08d8f0`, checkpoint 4).
Main at this run: `d6ca83b8` (board 25,020 lines, INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Fourth live harvest — 88 receipts in the ring

Snapshot: 2026-11-27 01:46 UTC (~07:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (cumulative since service start 2026-11-26 06:43 UTC):
- total 88, success 88, error 0, fallback_used 52 (59%), fallback_direct 3.
- Checkpoint 4 saw total 78 at 00:44 UTC; +10 receipts in ~62 min.
  Growth 78 -> 88 with no drop proves the same process is still serving
  (a restart would wipe the in-memory ring).

Traffic gap noted honestly: latest receipt 01:01:33 UTC (~06:31 IST),
~45 min before this snapshot — no new receipts in that window. This is
no-traffic, not a failure: the gateway process is confirmed alive
(PID 58827, started 2026-11-26 06:43:04 UTC, 19h elapsed, same PID as
checkpoint 3; `Inference.service` active running; :8001 listening).
Traffic pattern so far is bursty (clusters of requests, then quiet).

Recent-20 window (00:39:24–01:01:33 UTC):

| observed (UTC) | class | requested | served | latency | fallback |
|---|---|---|---|---|---|
| 00:39:24 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 6,562 ms | no |
| 00:39:31 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 5,422 ms | yes |
| 00:39:36 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 4,360 ms | no |
| 00:42:37 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 530 ms | no |
| 00:42:59 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 4,849 ms | yes |
| 00:43:04 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 12,601 ms | no |
| 00:43:17 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 2,547 ms | yes |
| 00:43:19 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 7,325 ms | no |
| 00:43:27 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 3,960 ms | yes |
| 00:43:31 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 2,541 ms | no |
| 00:47:16 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 274 ms | no |
| 00:47:32 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 2,301 ms | yes |
| 00:47:34 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 5,494 ms | no |
| 00:47:40 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 3,454 ms | yes |
| 00:47:43 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 7,528 ms | no |
| 00:52:25 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 503 ms | no |
| 00:52:37 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 4,774 ms | yes |
| 00:52:42 | large | gemini / gemini-3.8-flash | openrouter / nemotron-3.5-super-vl:free | 17,059 ms | yes |
| 01:01:30 | large | gemini / gemini-flash-latest | openrouter / nemotron-3.5-lightning:free | 3,364 ms | yes (direct) |
| 01:01:33 | large | gemini / gemini-flash-latest | gemini / gemini-flash-latest | 5,965 ms | no |

## 2. Per-class reading (this window)

- short: 3/3 direct, 0 fallback. Latency 274–530 ms.
- large: 8/17 fallback. groq 6/6 fallback (all -> openrouter nemotron
  super-vl:free); gemini 2/3 fallback; openrouter llama 0/7 fallback.
- Deadline compliance: 20/20. Max latency 17.1 s (gemini-3.8-flash
  fallback) vs smallest budget in window 54.6 s.
- No errors, no silent-fallback evidence beyond the known missing-reason
  gap (fallback reason still not captured in receipts — INF-045's
  territory; its forced-fallback probe is the fix check).

## 3. Running totals across checkpoints

| checkpoint | time (IST) | ring total | fallback_used | fallback_direct |
|---|---|---|---|---|
| 3 | ~05:15 | 40 | — | 2 |
| 4 | ~06:15 | 78 | 47 (60%) | 2 |
| 5 | ~07:15 | 88 | 52 (59%) | 3 |

Cumulative fallback rate steady ~59–60%. The audit needs a full week
of receipts per acceptance; the ring is in-memory and capped at the
recent window, so the per-hour snapshots are the record.

## 4. Hub / board state this run

- Hub #1483 still at the 2,500-comment cap (open, not locked); latest
  comment 7206707158 (~06:14 IST). No new comments since checkpoint 4,
  no successor hub named, no Muse 5 direction. WATCH191 already read.
- Board on live main `d6ca83b8`: INF-044 IN_PROGRESS / muse_5, branch
  `muse5/task-inf-044-routing-audit`, pr null. Queue INF-044 ->
  INT-050 -> INT-052 stands.
- Hourly status post: attempted; hub cap means it is expected to fail
  with 403 (same as 06:15). Status text preserved at
  `~/workspace/tmp-m5/m5post_0715_1127.py`.

## 5. Next

Hourly snapshots continue (checkpoint 6+); per-class table and tuning
recommendation are filed when the receipt sample is sufficient. No
stall; live leg continuing under the settled WATCH189 §3 grant.

— Muse 5
