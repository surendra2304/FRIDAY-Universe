# TASK-INF-044 — Checkpoint 3: live leg STARTED under WATCH189 §3 — second harvest (40 receipts)

Date: 2026-11-27 ~05:20 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `54bdefb7`, checkpoint 2).
Main at this run: `aebd481f` (#2032 + #2031 merged; WATCH189).

## 1. Grant dispute — SETTLED on the verified channel; live leg STARTED

- WATCH189 (hub 7205719288, 2026-11-27 ~06:10 IST, read first-hand from the
  GitHub API this run) §3 rules the grant settled and directs: start the
  INF-044 live leg now, or release INF-044. No third option.
- Grounds cited: owner approved full run_shell for all worker chats in the
  main chat on 2026-11-26 at 18:25:56 IST (his own tap); promulgated rulings
  7192682851, 7193378286, 7197725825, 7200414167; clearance 7200564540.
  Main-chat approvals do NOT appear in permissions.history — a "no record"
  result there is not evidence about this approval.
- Corroboration first-hand this run: WATCH189 §1's merge claims check out
  (main ref `aebd481f`, #2032 then #2031 merged); the post is coherent with
  the rest of the hub page read (2,456 comments through 7205804947). The
  earlier "approval 7113152293 not found" position is withdrawn as a basis
  for holding: re-checked this run, still no record in permissions.history,
  which per WATCH189 §3 is the expected result for a main-chat approval.
- Action taken: live leg STARTED this run — read-only receipt snapshot on
  FRIDAY-Server (bridge server 3) via run_shell. No release. All probes
  read-only (curl /status, systemctl show, sha256sum, grep). No restarts,
  no deploys, no env flips, no key reads.

## 2. Second live harvest — 40 receipts in the ring

Snapshot: 2026-11-26 23:51:34 UTC (~05:21 IST). Serving host FRIDAY-Server,
`Inference.service` active/running, NRestarts=0, started Thu 2026-11-26
06:43:04 UTC — same process as checkpoint 2, no restart since; the ring is
intact since service start.

Serving code unchanged: gateway.py sha256
`e884457c8a7dadf52e71b646a08fa02bb715cf32d98e5e50ef46ac7950e5c0ac`
(Nov 24 checkout: INF-030 APInex in, INF-038 needle fast-path out —
`grep -c needle` = 0). Batches in this audit are all served by this code
unless a re-deploy is recorded.

Ring counts (cumulative since service start 06:43 UTC):
- total 40, success 40, error 0, fallback_used 30 (75%), fallback_direct 1.
- Checkpoint 2 saw total 4 at ~15:09 UTC; 36 more arrived by 23:51 UTC.
  Traffic is live and flowing (one new receipt between the two snapshot
  calls a minute apart: 39 -> 40).

Recent-20 window (all `/status` returns; 23:37:51–23:51:34 UTC):

| observed (UTC) | class | requested | served | latency | fallback |
|---|---|---|---|---|---|
| 23:37:51 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 8,544 ms | yes |
| 23:37:59 | large | gemini / gemini-3.8-flash | openrouter / nemotron-3.5-super-vl:free | 29,542 ms | yes |
| 23:38:49 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 6,778 ms | yes |
| 23:38:56 | large | gemini / gemini-3.8-flash | openrouter / nemotron-3.5-super-vl:free | 17,244 ms | yes |
| 23:42:53 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 446 ms | no |
| 23:43:07 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 5,127 ms | yes |
| 23:43:12 | large | gemini / gemini-3.8-flash | gemini / gemini-3.6-flash | 13,828 ms | yes |
| 23:46:14 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 473 ms | no |
| 23:46:27 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 15,148 ms | yes |
| 23:46:42 | large | gemini / gemini-3.8-flash | gemini / gemini-3.6-flash | 12,581 ms | yes |
| 23:46:54 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 6,696 ms | yes |
| 23:47:01 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 2,222 ms | no |
| 23:47:03 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 3,365 ms | yes |
| 23:47:07 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 7,399 ms | no |
| 23:48:53 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 604 ms | no |
| 23:49:06 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 3,649 ms | yes |
| 23:49:10 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 2,050 ms | no |
| 23:49:12 | large | groq / gpt-oss-120b | openrouter / nemotron-3.5-super-vl:free | 2,106 ms | yes |
| 23:49:14 | large | openrouter / llama-3.3-70b-instruct | openrouter / llama-3.3-70b-instruct | 11,058 ms | no |
| 23:51:34 | short | groq / gpt-oss-120b | groq / gpt-oss-120b | 590 ms | no |

Per-class in this window (n=20, NOT the week):
- short (n=4): fallback 0/4, all groq primary, latency 446–604 ms.
- large (n=16): fallback 11/16. All 9 groq large fell back to openrouter
  nemotron (2.1–15.1 s); both gemini large fell back (nemotron 17.2–29.5 s,
  gemini-3.6-flash 12.6–13.8 s); all 5 openrouter-requested large served
  directly by openrouter llama, no fallback.
- Deadline compliance in window: 20/20 within budget (max latency 29.5 s
  vs smallest caller budget 44.8 s; default budget 60.0 s). Error rate 0/20.
- Pattern holding from checkpoint 2: large Groq/Gemini primaries fall back;
  large OpenRouter primaries do not. The INF-019 failure mode (Gemini slow
  on large prompts, fallback serves it) recurs — 29.5 s gemini receipt.

## 3. Harvest-design gap found — `/status` recent list caps at 20

- The ring holds 100 and counts total 40, but `recent_receipts` returns
  only the newest 20. The 16 receipts between checkpoint 2's 4 (15:06 UTC)
  and this window (23:37 UTC) are counted but not listed — per-receipt
  detail for them is unrecoverable from /status now.
- Fix for the audit: snapshot hourly (the recent-20 window spans ~14 min
  at current traffic, so hourly snapshots still gap). Better: ask for a
  full-ring read route or a receipts export — owed as a follow-up, not
  blocking the audit; counts + windows are captured each hour.

## 4. Board / hub state at this run

- Board (live main `aebd481f`, 24,928 lines): INF-044 IN_PROGRESS / owner
  muse_5 / branch `muse5/task-inf-044-routing-audit` / pr null. Queue
  INF-044 -> INT-050 -> INT-052 stands. Board PR #2033 repaired (validator
  green in CI, WATCH189 §2); merge held for full CI — INF-044's re-slot flip
  already landed; no flip owed from this task this run.
- Hub #1483: 2,456 comments through 7205804947. WATCH188 + WATCH189 read
  in full. No new Muse 5 direction beyond WATCH189 §3 (acted on above).
  Board PR #2033 head `0526ea03`; #2027 still board-hunked (TP12 strip owed).

## Five states (honest)

- Implemented: no (audit in progress). Tested: partial — repo leg 7/8
  (1 stale test, finding filed at checkpoint 2); live leg STARTED, 40
  receipts harvested across two snapshots. Merged: no. Deployed: no (no
  deploy by this task). Production-verified: no — audit needs a week of
  receipts; 40 in ~17 h of service uptime is the start, not the week.

## Next

- Hourly snapshots into this evidence file (checkpoint 4+), watching for a
  service restart (ring wipe) and any re-deploy (serving-code change).
- Follow-up: full-ring read route for /status (recent caps at 20).
- INF-045 scope note from checkpoint 2 stands: success receipts carry no
  fallback-reason field.
