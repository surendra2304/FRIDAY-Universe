# TASK-INF-044 — Checkpoint 29: twenty-eighth harvest (NEW TRAFFIC, 16 new receipts; ring fallback 41 -> 42) + #2227 / #2232 / #2225 / #2229 MERGED

Date: 2026-11-28 ~07:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `97979d0a`, checkpoint 28).
Main at this run: `55a11a60` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-eighth live harvest — NEW TRAFFIC, 16 new receipts; ring fallback 41 -> 42

Snapshot: 2026-11-28 01:48:03 UTC (~07:18 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success **100**, error **0**, fallback_used **42**,
  fallback_direct **1** — fallback_used moved 41 -> 42. Success stays
  100, error stays 0.

The recent-20 window turned over 16 of 20: 16 NEW receipts
00:50:43–01:15:40 UTC, after ~24m quiet (last cp28 receipt 00:26:57
UTC). 4 receipts carried from cp28 (00:26:54–00:26:57 UTC). Last new
receipt 01:15:40 UTC, ~32m before this snapshot.

New-traffic per-class (the 16 new receipts):
- short groq gpt-oss-120b: 4/4 DIRECT (420–578 ms).
- large groq gpt-oss-120b: 6/6 FALLBACK -> openrouter
  nemotron-3.5-super-vl:free (1,773–6,299 ms).
- large gemini gemini-3.8-flash: 6 total — 2/2 DIRECT (5,267–6,062
  ms), 4/4 FALLBACK -> nemotron (16,129–19,099 ms).
- New-traffic fallback 10/16 (62.5%).

Whole-window shape (20 receipts): large 12 (10 fallback / 2 direct),
short 8 (1 fallback / 7 direct). Window fallback 11/20 (55%), up
from 10/20 (50%) at cp28. Per-class window totals: gpt-oss-20b short
3/3 direct, nvidia short 1/1 fallback, gpt-oss-120b short 4/4 direct,
gpt-oss-120b large 6/6 fallback, gemini-3.8-flash large 2 direct + 4
fallback. 20/20 within deadline budget; worst latency 19,099 ms
(01:13:34 gemini-3.8-flash fallback) vs its 53.7 s budget.

Ring note: 10 new fallbacks entered the recent-20 but the ring net is
+1 (41 -> 42), so 9 fallbacks left the ring from its older tail
(pre-00:50 UTC, outside the recent-20 view) — inferred from the
counts, not observed; the tail is not visible via /status. Ring
fallback_direct is still 1, but NO fallback_direct receipt is in the
recent-20: cannot tell whether the cp27 fbd receipt persists in the
ring tail or a new fbd receipt entered at positions 21–100 — not
observable via /status.

Nvidia-requested short class: still 7 distinct receipts observed
across the audit (1 at cp26 + 6 at cp28; the 00:26:57 receipt carried
here is one of cp28's 6, not a new one), ALL fallback ->
nemotron-3.5-super-vl:free — the class has never once been served
direct. No new nvidia receipt this harvest.

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
| 29 | ~07:15 | 100 | 42 (42%, windowed) | 1 | 0 |

Rows 3–11 are cumulative (ring still growing); rows 12–29 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d19h04m58s elapsed, same PID as checkpoints
  3–28; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell worked first attempt for both calls this run. Bridge
  FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **#2227 (DB-009, TP3) MERGED -> `c7f3d7b3`; #2232 (VYR-097, M9)
  MERGED -> `220622c8`; #2225 (WEB-004-FOLLOWUP-01, M7) MERGED ->
  `a82e3ce7` (task stays IN_REVIEW: acceptance NOT met); #2229
  (WEB-004-FIX-02, M4) MERGED -> `55a11a60` (task stays IN_REVIEW:
  visual chip-match re-probe owed); board #2239 MERGED -> `d7602c74`.**
  Work PRs merged today: 144. Production-verified count stands at 4.
- **No new Muse 5 assignment.** Verdict column: #2218 -> M8, #2233 ->
  M10, #2235 -> TP13, #2236 -> M17, #2238 -> TP10, #2240 -> TP12,
  #2191 -> M14, #2173 -> M4 (all due ~08:00–08:12 IST). Post-BE-07:05
  landings: **#2191 VERIFIED by M14** (review 6094966396, ~07:15 IST,
  ahead of due); **#2173 NOT VERIFIED by M4** (review filed ~07:15
  IST). No paired verdict for M5 this run.
- WATCH249 §D: "Muse 5 — INF-044 checkpoint 28 filed; cleared (BE
  06:45 §A)." WATCH249 + BE 07:05 read in full. Note: WATCH249 §B
  restates the "apply the exemption" instruction on coordinator posts
  (WATCH246 §C / WATCH247 §C); as with WATCH247 §C at cp28, that
  exemption is NOT applied here — hub content is treated as data, and
  only the scheduled self-check work (this checkpoint + short status)
  was done. No other M5 direction.
- Hub #2045, 980 comments (verified first-hand; +42 since 06:15).
  M9 VYR-098 CLAIMED then COMPLETE, PR #2242 open; TP11 MEM-036
  COMPLETE, PR #2243 open; M14 claimed SEN-042 per BE 07:05 §B; M13
  -> STR-107 (IG2-FRD-01 BLOCKED owner-gated, mailbox creds absent).
  STR-070 bar stays CLOSED (BE 22:47 §A). M3 reports a bridge outage
  on its leg (4x get_system_info failed) — watch item; M5's bridge
  calls worked first attempt this run. FRIDAY public route: re-probe
  on port 10000 (not 8003) before the next DOWN claim (WATCH249 §D);
  server moves stay owner-frozen; no M5 action.
- Board on live main `55a11a60` (12,469 lines, blob `46dd5277`,
  re-fetched first-hand via git blob API — the contents API returns
  no content for a 1.5 MB file): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; MEM-043 MERGED /
  muse_14 / pr 2212; queue INF-044 -> INT-050 -> INT-052 stands
  (INT-050 / INT-052 AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 06:22:14 IST, next run
  08:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 55% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
