# TASK-INF-044 — Checkpoint 31: thirtieth harvest (NEW TRAFFIC, 8 receipts; cp30 error RETRIED DIRECT; ring fallback 41 -> 40) + no M5 verdict assigned

Date: 2026-11-28 ~09:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `08ab6c26`, checkpoint 30).
Main at this run: `dc1ed6f0` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Thirtieth live harvest — NEW TRAFFIC, 8 new receipts; the cp30 error RETRIED DIRECT

Snapshot: 2026-11-28 03:48:03 UTC (~09:18 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Note on the first snap call: it failed with a `SyntaxError` (exit 1)
before printing anything — my None-safe edit put a `def` statement
after a semicolon in the one-liner, which Python forbids. Fixed to a
lambda and re-ran; the re-run exited 0 with the full 20 receipts.
No data lost; the gateway check ran clean on both attempts.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success **99**, error **1**, fallback_used **40**,
  fallback_direct **1** — fallback_used moved 41 -> 40, error still 1,
  success still 99.

The recent-20 window turned over 8 of 20: 8 NEW receipts 03:34:55–
03:36:55 UTC, after ~1h quiet (last cp30 receipt 02:34:18 UTC).
12 receipts carried from cp30 (00:53:10–02:34:18 UTC).

New-traffic per-class (the 8 new receipts):
- large gemini gemini-3.8-flash: 1/1 FALLBACK -> openrouter
  nemotron-3.5-super-vl:free (23,096 ms, tok 7213, budget 60.0 s).
- large openrouter meta-llama/llama-3.3-70b-instruct: 1/1 DIRECT
  (11,654 ms, tok 7213, budget 36.9 s) — the SAME prompt that errored
  at cp30 (02:34:18, TimeoutError after 15.0 s) now served direct.
  First observed retry outcome for an error receipt in the audit.
- short groq gpt-oss-120b: 5/5 DIRECT (2,267 / 2,296 / 566 / 482 /
  503 ms; tok 2752 / 4235 / 2561 / 2508 / 1969).
- short nvidia nemotron-3-super-120b-a12b: 1/1 FALLBACK -> openrouter
  nemotron-3.5-super-vl:free (30,937 ms, tok 260, budget 60.0 s) —
  8th distinct nvidia-requested receipt in the audit, ALL fallback.
- New-traffic fallback 2/8 (25%).

Whole-window shape (20 receipts): large 12 (10 fallback / 1 direct /
1 error), short 8 (1 fallback / 7 direct). Window fallback 11/20
(55%), down from 12/20 (60%) at cp30. Window errors 1/20 (the cp30
error receipt still in the window). 19/20 within deadline budget;
worst latency 36,908.6 ms (the error receipt, ~5 ms over its
36.9036 s budget).

The tok=7213 prompt now has FOUR receipts across ~1h: 02:33:55
gemini fallback, 02:34:18 llama ERROR, 03:34:55 gemini fallback,
03:35:19 llama DIRECT — same token count, outcomes
fallback / error / fallback / direct. Observation only; /status
cannot confirm they share a request id.

Ring note: 2 new fallbacks entered the recent-20 but the ring net is
-1 (41 -> 40), so 3 fallbacks left the ring from its older tail
(pre-00:53 UTC, outside the recent-20 view) — inferred from the
counts, not observed; the tail is not visible via /status. Ring
fallback_direct is still 1, but NO fallback_direct receipt is in the
recent-20: cannot tell whether the cp27 fbd receipt persists in the
ring tail or a new fbd receipt entered at positions 21–100 — not
observable via /status.

Llama-3.3-70b-instruct requested has now been seen 4 times: 3 direct
(2 at cp28, 1 here) and 1 error (cp30, now retried direct).

Nvidia-requested short class: 8 distinct receipts observed across
the audit, ALL fallback -> nemotron-3.5-super-vl:free — the class
has never once been served direct.

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
| 30 | ~08:15 | 100 | 41 (41%, windowed) | 1 | 1 |
| 31 | ~09:15 | 100 | 40 (40%, windowed) | 1 | 1 |

Rows 3–11 are cumulative (ring still growing); rows 12–31 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d21h04m58s elapsed, same PID as checkpoints
  3–30; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell: first snap call exit 1 (my SyntaxError — see §1);
  gateway check exit 0 on both attempts; None-safe re-run exit 0.
  Bridge FRIDAY-Cloud-Engineering-Bridge v1.30.0.
- **No paired verdict assigned to Muse 5 this run.** Verdict column
  (BE 08:50 §C + WATCH252 §C + BE 09:10 §C, all read in full):
  #2249 -> M3, #2252 -> M12, #2254 -> M18, #2255 -> M17, #2257 ->
  M6, #2258 -> TP13, #2253 -> M10 (due ~09:50 IST), #2260 -> TP11
  (due ~10:00), #2261 -> TP12 (due ~10:10); #2150 -> M17
  overdue-restated, waits on TP2's repair. Column at the 10-cap;
  verification-first until it drains.
- **#2241 / #2244 MERGED** (WATCH252 §A): INF-049 -> `fb288a35`
  (M12 VERIFIED), FRG-035 checkpoint 1 -> `dc1ed6f0` (M6 VERIFIED).
  Work PRs merged today: 155. Production-verified count stands at 4.
  **#2242 merge rides WATCH253** (VERIFIED + CI green, BE 09:10 §E).
  Board PR #2250 head `e024f4bb`, CI running; merge rides WATCH253.
- **No other new Muse 5 assignment.** BE 08:50 (7232927618),
  WATCH252 (7233202719), BE 09:10 (7233271297) read in full — no M5
  direction. STR-070 bar stays CLOSED (BE 22:47 §A). FRIDAY public
  route RECOVERED (M11 08:13 post: duckdns /health 200 after 9+
  hours down; TP1 corroborated) — the re-probe item is closed.
  S2 copy DOWN + disk watch items carried; server moves stay
  owner-frozen; no M5 action.
- Hub #2045, 1,073 comments (verified first-hand; +45 since 08:15).
- Board on live main `dc1ed6f0` (12,518 lines, blob `b1657b5d` —
  UNCHANGED from cp30's main `9321b0d1`; main moved on the two
  merges only): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; queue INF-044 ->
  INT-050 -> INT-052 stands (INT-050 / INT-052 AVAILABLE, owner
  muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 08:26:09 IST, next run
  10:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 56% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
