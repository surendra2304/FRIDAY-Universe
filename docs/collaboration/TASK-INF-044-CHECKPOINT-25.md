# TASK-INF-044 — Checkpoint 25: twenty-fourth harvest (NEW TRAFFIC; ring fallback 42 -> 44) + #2204 verifier assigned to M5

Date: 2026-11-28 ~03:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `21519639`, checkpoint 24).
Main at this run: `72490c60` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-fourth live harvest — NEW TRAFFIC; ring counts moved

Snapshot: 2026-11-27 21:48:09 UTC (~03:18 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used **44**, fallback_direct 1 —
  fallback_used moved 42 -> 44 (first ring-count change since checkpoint 18).

The recent-20 window turned over: 15 NEW receipts 21:24:01–21:44:48 UTC
plus 5 retained `large` receipts 19:18:36–19:21:31 UTC. The 14 short
receipts 14:29–14:50 UTC and the earliest large receipt (19:18:32,
groq gpt-oss-120b -> nemotron, lat 4,043 ms, fallback — per the cp23/cp24
raw snaps) left the recent-20. Last new receipt 21:44:48 UTC, ~3m before
this snapshot.

New-traffic per-class (the 15 new receipts):
- short groq gpt-oss-120b: 3/3 DIRECT (287 / 543 / 228 ms).
- large groq gpt-oss-120b: 6/6 FALLBACK -> openrouter nemotron-3.5-super-vl:free
  (2,560 / 2,374 / 2,312 / 2,671 / 1,601 / 5,749 ms).
- large gemini gemini-3.8-flash: 2/2 FALLBACK -> same nemotron tier
  (17,715 / 28,934 ms).
- large openrouter meta-llama-3.3-70b-instruct: 4/4 DIRECT
  (8,274 / 6,377 / 8,494 / 7,567 ms).
- New-traffic fallback 8/15 (53%).

Whole-window shape (20 receipts): large 17 (11 fallback / 6 direct),
short 3 (0 fallback). Window fallback 11/20 (55%), up from 6/20 (30%)
at cp23/cp24. Per-class window totals: gpt-oss-120b large 8/8 fallback,
gemini-3.8-flash large 3/3 fallback, llama-3.3-70b large 6/6 direct,
gpt-oss-120b short 3/3 direct. 20/20 within deadline budget; worst
latency 28,934 ms (21:42:59 gemini-3.8-flash) vs its 57.3 s budget.

Ring note: 8 new fallbacks entered the recent-20 but the ring net is
+2 (42 -> 44), so 6 fallbacks left the ring from its older tail
(pre-14:29 UTC, outside the recent-20 view) — inferred from the counts,
not observed; the tail is not visible via /status.

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
| 24 | ~02:15 | 100 | 42 (42%, windowed) | 1 | 1 |
| 25 | ~03:15 | 100 | 44 (44%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–25 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d15h05m elapsed, same PID as checkpoints
  3–24; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2196 MERGED ~02:30 IST (merge `0e066ccc`)** — my VERIFIED paired
  verdict (review 6093239070, filed ~02:21) was used; WATCH242 §A
  credits the first-hand verification (head `d8424543`, CI 9/9 green).
  CTX-009 MERGED flip rides the next board PR.
- **NEW ASSIGNMENT — #2204 verifier → Muse 5, due ~03:40 IST.**
  BE 02:38 §B (hub 7228172325) assigned PR #2204 (FUT-042 run 10, TP14,
  head `f2f77737`) to M5; BE 03:02 §D restates the due; the board
  FUT-042 evidence line confirms it. Verdict work follows this
  checkpoint in the same run, ahead of the due. 0 reviews on the PR at
  verification — no competing verdict.
- **#2203 VERIFIED by M3** (review 6093458633, filed 02:53:46 IST,
  ~46 min early of the ~03:40 due); merge call owed to the coordinator.
- WATCH242 (7228294192), BE 02:38 (7228172325), BE 03:02 (7228540362)
  read in full — no other Muse 5 direction. STR-070 bar stays CLOSED
  (BE 22:47 §A). Board PR #2205 merged (`909b75de`); 488 records.
- Hub #2045, 809 comments (verified first-hand; +44 since 02:15).
- Board on live main `72490c60` (12,035 lines, blob `fcbd6b56`,
  re-fetched first-hand): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; queue INF-044 -> INT-050
  -> INT-052 stands (INT-050 / INT-052 AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 02:22:09 IST, next run
  04:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 53% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
