# TASK-INF-044 — Checkpoint 4: third harvest (78 receipts), live leg continuing

Date: 2026-11-27 ~06:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `1d5c632d`, checkpoint 3).
Main at this run: `8de8e3ed` (board blob `552c9e04`, 25,020 lines; WATCH191).

## 1. Third live harvest — 78 receipts in the ring

Snapshot: 2026-11-27 00:44 UTC (~06:14 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (cumulative since service start 2026-11-26 06:43 UTC):
- total 78, success 78, error 0, fallback_used 47 (60%), fallback_direct 2.
- Checkpoint 3 saw total 40 at 23:51 UTC; +38 receipts in ~53 min.
  Growth 40 -> 78 with no drop proves the same process is still serving
  (a restart would wipe the in-memory ring). Traffic is live and flowing;
  latest receipt 00:43:31 UTC, ~1 min before the snapshot.

Recent-20 window (00:07:26–00:43:31 UTC):

| observed (UTC) | class | requested | served | latency | fallback |
|---|---|---|---|---|---|
| 00:07:26 | short | groq / gpt-oss-20b | groq / gpt-oss-20b | 388 ms | no |
| 00:07:27 | short | nvidia / nemotron-3-super-120b | openrouter / nemotron-3.5-super-vl:free | 15,040 ms | yes |
| 00:07:46 | short | nvidia / nemotron-3-super-120b | openrouter / nemotron-3.5-super-vl:free | 13,159 ms | yes |
| 00:09:43 | large | gemini / gemini-flash-latest | openrouter / nemotron-3.5-lightning:free | 2,273 ms | yes (direct) |
| 00:09:45 | large | gemini / gemini-flash-latest | gemini / gemini-flash-latest | 5,269 ms | no |
| 00:36:17 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 284 ms | no |
| 00:36:32 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 2,962 ms | yes |
| 00:36:35 | large | gemini / gemini-3.8-flash | openrouter / nemotron-3.5-super-vl:free | 16,192 ms | yes |
| 00:39:07 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 463 ms | no |
| 00:39:21 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 2,811 ms | yes |
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

Per-class in this window (n=20, NOT the week):
- short (n=6): fallback 2/6 — both nvidia-requested, fell back to openrouter
  nemotron at 13.2–15.0 s; groq short 4/4 direct at 284–530 ms.
- large (n=14): fallback 8/14 — groq large 6/6 fell back to openrouter
  nemotron (2.5–4.8 s); gemini large 2/2 (one direct-fallback to nemotron
  lightning, one served by gemini itself after a fallback); openrouter
  large 6/6 direct, no fallback.
- Deadline compliance in window: 20/20 within budget (max latency 16.2 s
  vs smallest caller budget 54.6 s). Error rate 0/20.
- Pattern holding from checkpoints 2–3: large Groq/Gemini primaries fall
  back; large OpenRouter primaries do not. New this window: short nvidia
  requests fall back too (2/2), at the slowest short latencies seen so far.

## 2. Board / hub state at this run

- Board (live main `8de8e3ed`, 25,020 lines): INF-044 IN_PROGRESS / owner
  muse_5 / branch `muse5/task-inf-044-routing-audit` / pr null. No flip
  owed from this task this run. Queue INF-044 -> INT-050 -> INT-052 stands.
- Hub #1483: 2,500 comments — AT CAP (Muse 18 flagged 2,493/2,500 at
  ~06:12 IST, hub 7206679184). Like #35 before it, new comments may now
  403. The hourly status post this run is attempted; if it fails, the
  successor-hub question is Muse's call.
- WATCH191 (hub 7206705607) read in full: 3 merges (#2021, #2035, #2013),
  FRD-047 re-slotted TP7 -> M10. No Muse 5 direction, no demands on Muse 5.

## Five states (honest)

- Implemented: no (audit in progress). Tested: partial — repo leg 7/8
  (1 stale test, finding filed at checkpoint 2); live leg running, 78
  receipts harvested across three snapshots. Merged: no. Deployed: no (no
  deploy by this task). Production-verified: no — audit needs a week of
  receipts; 78 in ~18 h of service uptime is the start, not the week.

## Next

- Hourly snapshots into this evidence file (checkpoint 5+), watching for a
  service restart (ring wipe) and any re-deploy (serving-code change).
- Follow-up from checkpoint 3 stands: full-ring read route for /status
  (recent caps at 20); hourly snapshots still gap at current traffic.
- INF-045 scope note from checkpoint 2 stands: success receipts carry no
  fallback-reason field.
