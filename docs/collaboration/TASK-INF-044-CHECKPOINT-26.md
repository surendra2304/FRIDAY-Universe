# TASK-INF-044 — Checkpoint 26: twenty-fifth harvest (NEW TRAFFIC; ring fallback 44 -> 42, direct 1 -> 0) + #2212 verifier assigned to M5

Date: 2026-11-28 ~04:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `a0cd964d`, checkpoint 25).
Main at this run: `124a835c` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-fifth live harvest — NEW TRAFFIC; ring counts moved down

Snapshot: 2026-11-27 22:46:29 UTC (~04:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used **42**, fallback_direct **0** —
  fallback_used moved 44 -> 42 and fallback_direct 1 -> 0 (second
  ring-count change in a row; first was 42 -> 44 at checkpoint 25).

The recent-20 window turned over: 8 NEW receipts 22:41:50–22:43:29 UTC
plus 12 retained receipts 21:34:40–21:44:48 UTC. The 3 earliest receipts
of the cp25 batch (21:24:01 short gpt-oss 287 ms direct; large gpt-oss
2,560 ms fallback; large gemini 17,715 ms fallback) and all 5 retained
large receipts 19:18:36–19:21:31 UTC left the recent-20. Last new receipt
22:43:29 UTC, ~3m before this snapshot.

New-traffic per-class (the 8 new receipts):
- large gemini gemini-3.8-flash: 1/1 FALLBACK -> openrouter
  nemotron-3.5-super-vl:free (22,374 ms).
- large openrouter meta-llama-3.3-70b-instruct: 1/1 DIRECT (8,940 ms).
- short groq gpt-oss-120b: 5/5 DIRECT (2,519 / 2,589 / 678 / 236 / 596 ms).
- short nvidia nvidia/nemotron-3-super-120b-a12b: 1/1 FALLBACK ->
  openrouter nemotron-3.5-super-vl:free (19,134 ms) — NEW provider in the
  short class (first nvidia-requested receipt in the audit).
- New-traffic fallback 2/8 (25%).

Whole-window shape (20 receipts): large 12 (7 fallback / 5 direct),
short 8 (1 fallback / 7 direct). Window fallback 8/20 (40%), down from
11/20 (55%) at cp25. Per-class window totals: gpt-oss-120b large 5/5
fallback, gemini-3.8-flash large 2/2 fallback, llama-3.3-70b large 5/5
direct, gpt-oss-120b short 7/7 direct, nvidia nemotron-3-super short 1/1
fallback. 20/20 within deadline budget; worst latency 28,934 ms
(21:42:59 gemini-3.8-flash) vs its 57.3 s budget.

Ring note: 2 new fallbacks entered the recent-20 but the ring net is
-2 (44 -> 42), so 4 fallbacks left the ring from its older tail
(pre-14:29 UTC, outside the recent-20 view) — inferred from the counts,
not observed; the tail is not visible via /status. The single
fallback_direct receipt also left the ring (1 -> 0) from the same older
tail.

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
| 26 | ~04:15 | 100 | 42 (42%, windowed) | 0 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–26 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d16h03m elapsed, same PID as checkpoints
  3–25; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2204 MERGED -> `ac630ff6`** — my VERIFIED paired verdict (review
  6093717541, filed ~03:26 IST) was used; WATCH244 §A credits it.
  FUT-042 run 10 done; board flip rides the next board PR.
- **#2192 MERGED -> `901a1114`** (M2 VERIFIED review 6093840443,
  filed ~03:52 IST); TP6's PARTIAL does not stand as a merge-blocker
  (WATCH244 §B — the five figures occur 0 times in the filed doc).
  STR-101 MERGED flip rides WATCH245.
- **NEW ASSIGNMENT — #2212 verifier → Muse 5, due ~05:30 IST.**
  WATCH244 §D (hub 7229329225) assigned PR #2212 (MEM-043 run 9, M14,
  head `88acc685`) to M5; BE 04:05 §D (hub 7229449958) restates the due.
  Verdict work follows this checkpoint in the same run, ahead of the
  due. 0 reviews on the PR at verification — no competing verdict.
- **#2210 VERIFIED by M12** (review 6093954233, filed ~03:58 IST,
  ~44 min early of the ~04:42 due); merge call owed to the coordinator.
  **#2209 VERIFIED by M3** (review 6094011749, filed ~04:09 IST).
  **#2211 VERIFIED by M6** (review 6094023606, filed ~04:12 IST).
  Verdict column: #2206 → TP8, #2207 → M8, #2211 → M6 (done), #2212 →
  M5 (this run), #2214 → M7, all due ~04:42–05:30 IST.
- WATCH244 (7229329225), BE 03:42 (7229120299), BE 04:05 (7229449958)
  read in full — no other Muse 5 direction. STR-070 bar stays CLOSED
  (BE 22:47 §A). Board PR #2213 merged (`7238520d`); 489 records.
  S2 copy DOWN + disk 85% / 7.4G free carried to WATCH245 (BE 03:42
  §E) — server moves stay owner-frozen; no M5 action.
- Hub #2045, 850 comments (verified first-hand; +41 since 03:15).
- Board on live main `124a835c` (12,154 lines, blob `35b6b1ef`,
  re-fetched first-hand via git blob API — the contents API returns
  no content for a 1.5 MB file): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; MEM-043 still AVAILABLE /
  owner null on the board (stale — M14 hub claim + PR #2212 filed;
  IN_REVIEW flip rides WATCH245 per BE 04:05 §E); queue INF-044 ->
  INT-050 -> INT-052 stands (INT-050 / INT-052 AVAILABLE, owner
  muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 03:28:22 IST, next run
  05:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 54% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
