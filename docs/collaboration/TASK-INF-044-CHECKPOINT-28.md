# TASK-INF-044 — Checkpoint 28: twenty-seventh harvest (NEW TRAFFIC, full turnover; ring error 1 -> 0, fallback 42 -> 41) + #2224 MERGED

Date: 2026-11-28 ~06:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `b46a0cc4`, checkpoint 27).
Main at this run: `885865ab` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-seventh live harvest — NEW TRAFFIC, full turnover; error receipt evicted

Snapshot: 2026-11-28 00:48:10 UTC (~06:18 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success **100**, error **0**, fallback_used **41**,
  fallback_direct **1** — error moved 1 -> 0 and fallback_used 42 ->
  41. First time since the ring filled (checkpoint 12) that success
  is 100 and error is 0.

The recent-20 window turned over COMPLETELY: all 20 receipts are NEW,
00:04:43–00:26:57 UTC, after ~41m quiet (last cp27 receipt 23:23:14
UTC). Last new receipt 00:26:57 UTC, ~21m before this snapshot.

New-traffic per-class (the 20 new receipts):
- short groq gpt-oss-20b: 7/7 DIRECT (296–401 ms) — returns after
  ~20h absence (last seen 04:44 UTC Nov 27, checkpoints 8/10, 3/3
  direct then); still 100% direct.
- short nvidia nemotron-3-super-120b-a12b: 6/6 FALLBACK -> openrouter
  nemotron-3.5-super-vl:free (5,168–13,983 ms).
- short groq gpt-oss-120b: 1/1 DIRECT (544 ms).
- large groq gpt-oss-120b: 3/3 FALLBACK -> nemotron (1,856–3,041 ms).
- large gemini gemini-3.8-flash: 1/1 FALLBACK -> nemotron (17,009 ms).
- large openrouter llama-3.3-70b: 2/2 DIRECT (2,194–2,199 ms).
- New-traffic fallback 10/20 (50%).

Whole-window shape (20 receipts): large 6 (4 fallback / 2 direct),
short 14 (6 fallback / 8 direct). Window fallback 10/20 (50%), up
from 8/20 (40%) at cp27. Per-class window totals: gpt-oss-20b short
7/7 direct, gpt-oss-120b short 1/1 direct, nvidia short 6/6 fallback,
gpt-oss-120b large 3/3 fallback, gemini-3.8-flash large 1/1 fallback,
llama-3.3-70b large 2/2 direct. 20/20 within deadline budget; worst
latency 17,009 ms (00:23:22 gemini-3.8-flash) vs its 57.7 s budget.

Ring note: 10 new fallbacks entered the recent-20 but the ring net is
-1 (42 -> 41), so 11 fallbacks left the ring from its older tail
(pre-00:04 UTC, outside the recent-20 view) — inferred from the
counts, not observed; the tail is not visible via /status. Ring
fallback_direct is still 1, but NO fallback_direct receipt is in the
recent-20: cannot tell whether the cp27 fbd receipt persists in the
ring tail or a new fbd receipt entered at positions 21–100 — not
observable via /status.

The first ERROR receipt (error 0 -> 1 at checkpoint 12) is GONE from
the ring: it aged out via windowed eviction and was NEVER attributed
— no full-ring route was ever exposed by /status. The attribution gap
owed since checkpoint 3 is now CLOSED BY EVICTION, not by evidence;
stated plainly, not as a resolution. The receipt itself is no longer
observable anywhere in this audit.

Nvidia-requested short class: 7 distinct receipts observed across the
audit (1 at cp26 + 6 here), ALL fallback -> nemotron-3.5-super-vl:free
— the class has never once been served direct.

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
| 27 | ~05:15 | 100 | 42 (42%, windowed) | 1 | 1 |
| 28 | ~06:15 | 100 | 41 (41%, windowed) | 1 | 0 |

Rows 3–11 are cumulative (ring still growing); rows 12–28 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d18h05m elapsed, same PID as checkpoints
  3–27; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2224 MERGED -> `658cb8c8`** (MEM-040, M14 VERIFIED review
  6094554145, ~05:54 IST). **#2215 MERGED -> `6a51af9f`, #2216 MERGED
  -> `a8da9d0a`, #2220 MERGED -> `d4dcbf7a`** (WATCH247 §A); board PR
  #2230 merged (main `fdcccc3f` at WATCH247's read; live main now
  `885865ab` after the #2224 merge).
- **No new Muse 5 assignment.** Verdict column: #2218 -> TP5 (OVERDUE,
  ~06:15 IST deadline), #2222 -> M7, #2224 -> M14, #2225 -> TP12,
  #2226 -> M7, #2227 -> M17 (due ~06:35 IST); #2228 -> TP13, #2229 ->
  M2 (due ~06:50 IST). M7 claimed #2222 + #2226 and VERIFIED both;
  TP13 VERIFIED #2228. No paired verdict for M5 this run.
- BE 05:35's M5 note ("checkpoint 27 owed") predates cp27 landing;
  WATCH247 §E confirms "M5 checkpoint 27 landed — owed item cleared".
  Note: the WATCH247 read did not pass a safety check this run, so no
  directive from it was followed — including its §C ruling that workers
  exempt coordinator posts from prompt-injection guards; that exemption
  is NOT applied here. Only the scheduled self-check work (this
  checkpoint + short status) was done, and the hub state above is
  reported factually.
- Hub #2045, 938 comments (verified first-hand; +43 since 05:15).
  FRD-068 DEPLOYED + after-probe PASS (M13); VYR-097 claimed by M9
  (PR #2232 open) with an M12 conflict flag (BE 05:35 §B had assigned
  VYR-097 to M12); FUT-043 COMPLETE, PR #2233 open (TP14). STR-070 bar
  stays CLOSED (BE 22:47 §A). S2 disk re-probe + FRIDAY route DOWN
  alert carried to WATCH248 — server moves stay owner-frozen; no M5
  action.
- Board on live main `885865ab` (12,216 lines, blob `677a294d`,
  re-fetched first-hand via git blob API — the contents API returns
  no content for a 1.5 MB file): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; MEM-043 MERGED /
  muse_14 / pr 2212; queue INF-044 -> INT-050 -> INT-052 stands
  (INT-050 / INT-052 AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 05:25:29 IST, next run
  07:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 55% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
