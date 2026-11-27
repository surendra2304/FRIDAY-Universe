# TASK-INF-044 — Checkpoint 27: twenty-sixth harvest (NEW TRAFFIC; ring fallback_direct 0 -> 1) + #2212 MERGED

Date: 2026-11-28 ~05:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `6dacf164`, checkpoint 26).
Main at this run: `6a51af9f` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-sixth live harvest — NEW TRAFFIC; ring direct count moved up

Snapshot: 2026-11-27 23:49:18 UTC (~05:19 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success 99, error 1, fallback_used **42** (unchanged),
  fallback_direct **1** — fallback_direct moved 0 -> 1 (third
  ring-count change in a row: 42 -> 44 at checkpoint 25, 44 -> 42 and
  1 -> 0 at checkpoint 26).

The recent-20 window turned over: 2 NEW receipts 23:23:04–23:23:14 UTC
plus 18 retained receipts 21:34:59–22:43:29 UTC. The 2 earliest cp26
receipts left the recent-20 (21:34:40 large gpt-oss 2,374 ms fallback;
21:34:42 large llama 8,274 ms direct). Last new receipt 23:23:14 UTC,
~26m before this snapshot.

New-traffic per-class (the 2 new receipts):
- large gemini gemini-flash-latest: 1/1 FALLBACK-DIRECT -> openrouter
  qwen qwen-2.5-coder-32b-instruct (9,469 ms) — first fallback_direct
  receipt in the recent-20 since the early audit (last fbd=True
  receipt 01:01:30 UTC Nov 27; no fbd=True receipt in the cp22–cp26
  windows, verified from the saved snapshots); first
  qwen-2.5-coder-32b-instruct served fallback target in the audit.
- short groq gpt-oss-120b: 1/1 DIRECT (471 ms).
- New-traffic fallback 1/2 (50%).

Whole-window shape (20 receipts): large 11 (7 fallback / 4 direct),
short 9 (1 fallback / 8 direct). Window fallback 8/20 (40%),
unchanged from cp26. Per-class window totals: gpt-oss-120b large 4/4
fallback, gemini-3.8-flash large 2/2 fallback, gemini-flash-latest
large 1/1 fallback-direct, llama-3.3-70b large 4/4 direct,
gpt-oss-120b short 8/8 direct, nvidia nemotron-3-super short 1/1
fallback. 20/20 within deadline budget; worst latency 28,934 ms
(21:42:59 gemini-3.8-flash) vs its 57.3 s budget.

Ring note: 1 new fallback entered the recent-20 but the ring net is
0 (42 -> 42), so 1 fallback left the ring from its older tail
(pre-14:29 UTC, outside the recent-20 view) — inferred from the
counts, not observed; the tail is not visible via /status. The single
fallback_direct receipt entered the ring and none left (0 -> 1).

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
| 27 | ~05:15 | 100 | 42 (42%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–27 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d17h06m elapsed, same PID as checkpoints
  3–26; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2212 MERGED -> `3c91241c`** — my VERIFIED paired verdict (review
  6094085323, filed ~04:23 IST) was used; WATCH246 §A credits it.
  MEM-043 MERGED flip landed on the live board (main `6a51af9f`,
  blob `4601fcfa` = board PR #2223's blob).
- **#2219 MERGED -> `02ed2f98`** (M2 VERIFIED review 6094235343);
  REL-068 MERGED flip rides WATCH247 (board PR #2223 was built
  before the merge). **#2206 MERGED -> `bd102f2a`, #2207 MERGED ->
  `08c3a966`, #2214 MERGED -> `3d2a82f0`** (WATCH246 §A / BE 05:05
  §A). Work PRs merged today: 133.
- **No new Muse 5 assignment.** Verdict column: #2215 -> TP11,
  #2216 -> TP3, #2218 -> TP5 (due ~05:25 IST); #2220 -> M6 (due
  ~06:00 IST, WATCH246 §B + correction — BE 05:05's M8 assignment
  withdrawn). No paired verdict for M5 this run.
- WATCH245 (7229735145), WATCH245 correction (7229760779), BE 04:37
  (7229895961), BE 05:05 (7230217309), WATCH246 (7230224376),
  WATCH246 correction (7230255962) read in full — no other Muse 5
  direction. STR-070 bar stays CLOSED (BE 22:47 §A). S2 copy DOWN +
  disk 7.6G free / 85% — watch item, coordinator re-probes next run;
  server moves stay owner-frozen; no M5 action.
- Hub #2045, 895 comments (verified first-hand; +45 since 04:15).
- Board on live main `6a51af9f` (12,206 lines, blob `4601fcfa`,
  re-fetched first-hand via git blob API — the contents API returns
  no content for a 1.5 MB file): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; MEM-043 MERGED /
  muse_14 / pr 2212; queue INF-044 -> INT-050 -> INT-052 stands
  (INT-050 / INT-052 AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 04:24:21 IST, next run
  06:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 54% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
