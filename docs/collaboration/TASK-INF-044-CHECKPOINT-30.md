# TASK-INF-044 — Checkpoint 30: twenty-ninth harvest (NEW TRAFFIC, 2 receipts; FIRST ATTRIBUTABLE ERROR; ring fallback 42 -> 41, error 0 -> 1) + #2242 VERIFIED

Date: 2026-11-28 ~08:15 IST. Worker: Muse 5.
Task: Inference adaptive-routing live audit — one week of INF-022 routing receipts, per-class fallback rate + deadline compliance (P1).
Branch: `muse5/task-inf-044-routing-audit` (head `f27aa44a`, checkpoint 29).
Main at this run: `9321b0d1` (board INF-044 IN_PROGRESS / muse_5, verified first-hand).

## 1. Twenty-ninth live harvest — NEW TRAFFIC, 2 new receipts; FIRST ATTRIBUTABLE ERROR

Snapshot: 2026-11-28 02:46:21 UTC (~08:16 IST), read-only curl of
FRIDAY-Server :8001 /status via bridge run_shell (server 3), under the
WATCH189 §3 settled grant. No writes, no restarts, no deploys.

Note on the first snap call: its receipt print loop crashed with
`TypeError` (exit 1) on the new error receipt — its
`provider_served` / `model_served` fields are null, and the print
expression concatenates them. Counts + 19 receipts were captured
before the crash; a None-safe re-read ~02:48 UTC (exit 0) recovered
the full 20 + the error receipt's JSON. Counts and receipts identical
across both reads — no traffic between them. No data lost; the crash
was in my print formatting, not the gateway or the bridge.

Ring counts (ring still at the 100 cap; windowed eviction in effect):
- total 100, success **99**, error **1**, fallback_used **41**,
  fallback_direct **1** — fallback_used moved 42 -> 41, error moved
  0 -> 1, success 100 -> 99.

The recent-20 window turned over 2 of 20: 2 NEW receipts 02:33:55–
02:34:18 UTC, after ~1h18m quiet (last cp29 receipt 01:15:40 UTC).
18 receipts carried from cp29 (00:26:56–01:15:40 UTC); the 2 oldest
(00:26:54, 00:26:55 UTC) evicted.

New-traffic per-class (the 2 new receipts):
- large gemini gemini-3.8-flash: 1/1 FALLBACK -> openrouter
  nemotron-3.5-super-vl:free (23,094 ms, tok 7213, budget 60.0 s).
- large openrouter meta-llama/llama-3.3-70b-instruct: 1/1 ERROR —
  direct attempt, stage `unified_direct`, capability `reasoning`,
  latency 36,908.6 ms, budget 36.9036 s, tok 7213:
  `TimeoutError: Request deadline exceeded for provider 'openrouter'
  after 15.0s`. `provider_served` / `model_served` null.
- New-traffic fallback 1/2 (50%); new-traffic error 1/2.

Both new receipts carry prompt_tokens_est 7213 — the same token
count, 23 seconds apart: plausibly the same prompt routed twice (one
fell back, one errored). Observation only; /status cannot confirm
they share a request id.

Whole-window shape (20 receipts): large 13 (11 fallback / 1 direct /
1 error), short 7 (1 fallback / 6 direct). Window fallback 12/20
(60%), up from 11/20 (55%) at cp29. Window errors 1/20. 19/20 within
deadline budget; worst latency 36,908.6 ms (the error receipt, ~5 ms
over its 36.9036 s budget — the provider's own 15.0 s deadline is
what tripped, per the error string).

Ring note: 1 new fallback entered the recent-20 but the ring net is
-1 (42 -> 41), so 2 fallbacks left the ring from its older tail
(pre-00:50 UTC, outside the recent-20 view) — inferred from the
counts, not observed; the tail is not visible via /status. Ring
fallback_direct is still 1, but NO fallback_direct receipt is in the
recent-20: cannot tell whether the cp27 fbd receipt persists in the
ring tail or a new fbd receipt entered at positions 21–100 — not
observable via /status.

**Error attribution — the SECOND error in the audit, and the first
attributable one.** The first error receipt (cp12) aged out of the
ring at cp28 NEVER attributed — that gap closed by eviction, not
evidence, as stated at cp28. This second error is fully specified
above: large, openrouter llama-3.3-70b-instruct, direct, TimeoutError
after 15.0 s. It is also the first openrouter-REQUESTED receipt in
the audit (prior requested providers were groq / gemini / nvidia),
and the first error on a llama-requested receipt (cp28 saw llama
2/2 direct). Llama-3.3-70b-instruct requested has now been seen 3
times: 2 direct (cp28), 1 error (this run).

Nvidia-requested short class: no new receipt this harvest; still 7
distinct receipts observed across the audit, ALL fallback ->
nemotron-3.5-super-vl:free — the class has never once been served
direct.

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

Rows 3–11 are cumulative (ring still growing); rows 12–30 are windowed
(ring at the 100 cap, eviction in effect). The audit needs a full week of
receipts per acceptance; the ring holds only the last 100, so the
per-hour snapshots remain the record.

## 3. Gateway, hub / board / job state this run

- Gateway process confirmed alive and unchanged: PID 58827, started
  2026-11-26 06:43:04 UTC, 1d20h03m16s elapsed, same PID as checkpoints
  3–29; `Inference.service` active, NRestarts=0; :8001 LISTEN. No
  restart, no ring wipe.
- Bridge run_shell: first snap call exit 1 (my print formatting vs the
  error receipt's null served fields — see §1); gateway check exit 0;
  None-safe re-read exit 0. Bridge FRIDAY-Cloud-Engineering-Bridge
  v1.30.0.
- **#2242 paired verdict — VERIFIED, filed this run (review + PR
  comment, due ~08:40 IST).** Assignment: WATCH250 §B (hub
  7232165652) + BE 08:00 §B/§C (hub 7232438956) + WATCH251 §C (hub
  7232592508) — #2242 → M5. (BE 07:35 had named M2; WATCH250
  re-assigned to M5; M2 correctly filed nothing — BE 08:00 §C.)
  Verified first-hand: head `6af7e6f6` (branch `muse9/task-vyr-098`),
  base `55a11a60`, open, 2 files +487/-0, evidence only, no board
  hunk; blob SHAs match the PR files list; content read first-hand
  (evidence 14,423 B, pool 7,199 B); CI 9 checks (7 success / 2
  skipped, 0 failures); 0 reviews before filing; claim comment
  7231690319 verified; board VYR-098 CLAIMED / muse_9 / pr 2242 on
  live main; pool 8 candidates views descending 5015/2573/691/335/
  310/303/73/70, excluded_ids 117 unique, filed ids disjoint;
  VYR-097 PR #2232 MERGED `220622c8`, VYR-096 PR #2218 MERGED
  `1553f8dd`. Caveats in the review: mergeable None/unknown; live
  discovery not re-executed; 117-id union verified for count +
  disjointness, not recomputed from all 17 prior pools.
- **#2243 / #2237 / #2240 / #2233 / #2235 MERGED** (WATCH251 §A):
  MEM-036 -> `32ccdcc6`, FRG-027 -> `f0affee0`, STR-106 ->
  `b9e3cf77`, FUT-043 -> `25aacc52`, CTX-015 -> `9321b0d1`. Work PRs
  merged today: 153. Production-verified count stands at 4.
  Board PR #2250 open (branch `coordinator/watch251-board`, head
  `ca0785f5`, CI running) — 20 flips incl. VYR-098 -> IN_REVIEW
  pr 2242. Verdict column: #2244 -> M6, #2245 -> M10 (due ~08:40);
  #2247 -> M8, #2150 -> M17 (due ~09:00); #2248 -> TP10, #2251 ->
  TP12 (due ~09:30).
- **No other new Muse 5 assignment.** WATCH251 rulings: TP1 FRD-064
  fix APPROVED (cap 200 -> 300 MB, no leak — born over cap); TP4
  aiosqlite install APPROVED; TP3 VYR-077 board record DECIDED
  (record added in #2250); FUT-043 redeploy DECIDED; #2173 repair ->
  M4. BE 08:00 §D: hourly self-check posts superseded — event-only
  from here; M5 named among those still posting hourly this window.
  This status is event-only (checkpoint 30 + verdict filed).
  STR-070 bar stays CLOSED (BE 22:47 §A). S2 copy DOWN + disk watch
  items carried; FRIDAY public route re-probe on port 10000 still
  owed before the next DOWN claim; server moves stay owner-frozen;
  no M5 action.
- Hub #2045, 1,028 comments (verified first-hand; +48 since 07:15).
  WATCH250 (7232165652), BE 07:35 (7232141421), BE 08:00
  (7232438956), WATCH251 (7232592508) read in full — no other M5
  direction.
- Board on live main `9321b0d1` (12,518 lines, blob `b1657b5d`,
  re-fetched first-hand via git blob API — the contents API returns
  no content for a 1.5 MB file): INF-044 IN_PROGRESS / muse_5, branch
  muse5/task-inf-044-routing-audit, pr null; VYR-098 CLAIMED /
  muse_9 / pr 2242; queue INF-044 -> INT-050 -> INT-052 stands
  (INT-050 / INT-052 AVAILABLE, owner muse_5).
- Hourly self-check job: healthy (verified this run: enabled,
  consecutive failures 0, last run succeeded 07:22:39 IST, next run
  09:14:55 IST). Work-request remains disabled (mid-task) — no
  re-arm owed. Usage 56% of free weekly limit (verified fresh this
  run; resets Nov 28 21:38 IST); additional tokens 0% used.
