# TASK-INT-017 — IntelX production proof: armed-state evidence + wait state

- **Task:** TASK-INT-017 — IntelX: TASK-INT-016 production proof. Observe one real
  fast-lane alert end-to-end (kill switch stays OFF); if none occurs naturally,
  file the armed-state evidence and the wait state.
- **Owner:** Muse 10. **Claim:** hub #1483 comment 7121359130 (2026-11-24 ~09:13 IST).
- **Branch:** `muse10/task-int-017-intelx-production-proof`, base main `ab5651a5`.
- **Prior branch:** `muse3/task-int-017-intelx-production-proof` @ `af96cec1` (claim
  commit only, no work — Muse 3 silent ~48h; re-slotted to Muse 10 by coordinator
  enforcement 2026-11-23 ~22:40 IST). Picked up from that branch's state; work
  continues here.
- **Outcome:** no real fast-lane alert occurred naturally. This doc files the
  armed-state evidence and the wait state — the acceptance's second branch.

## What was checked (read-only, via the FRIDAY bridge)

All reads 2026-11-24 ~09:15–09:25 IST. Bridge `get_system_info`: both Oracle
servers ONLINE. No live production credentials/config touched, nothing written
to either server.

### Producer — Server 2, `IntelX/data/watches/`

- Directory contains exactly two files: `outbox.jsonl` (1,823 B, 2 lines) and
  `state.json` (1,244,963 B). No `instant_outbox.jsonl` exists.
- `outbox.jsonl` line 1: `ai_model_releases`, "Introducing harness adapters…",
  `alert_class: "digest"`, score 4, fired 2026-11-20T18:26:48Z. Already
  delivered (see drainer log below).
- `outbox.jsonl` line 2: `india_tech_regulatory`, "RBI Proposes 'Stop Switch'
  To Block Digital Payment Frauds", `alert_class: "digest"`, score 5, fired
  2026-11-23T16:33:10Z (22:03 IST). Digest-class, not instant.
- **The fast lane has never fired:** no instant-class envelope has ever been
  written — `instant_outbox.jsonl` is absent on Server 2, and both envelopes
  in the main outbox are `digest`.

### Consumer — Server 1 drainer state, `FRIDAY/state/proactive_intelx_watch.json`

Read in full just now:

- `version: 1`, `baseline_done: true`, `offset: 3644`
- `instant_baseline_done: true`, **`instant_offset: 0`**
- `delivered_keys`: 4 — all digest-class
  (`india_tech_regulatory:55fa9a3b9e05db08`,
  `ai_model_releases:8f6af8c44a4a1bfb`,
  `ai_model_releases:056cf0b58a3dbace`,
  `ai_model_releases:701a571706ec6c00`)
- `held: []`, `malformed_total: 0`
- `alert_log`: 7 entries, last 2026-11-20T19:16:14+05:30 (harness adapters,
  posted). No entry since Nov 20.
- **The fast lane has never delivered:** `instant_offset` is 0 and the instant
  baseline is done — zero instant-class deliveries, ever.

### Watches are alive

The newest envelope fired 2026-11-23 22:03 IST, so the Server 2 watch engine
is polling and producing. Corroborated by Muse 1 (TASK-INT-036, hub #1483
comment 7121113840, ~08:52 IST today): 6 watch polls since 07:38 IST, all
`alerted=0`, no new qualifying events; fast lane armed, never fired.

### Kill switch

No IntelX fast-lane kill switch exists in the codebase (searched `kill_switch`,
`KILL_SWITCH`, `fast_lane` across the repo — only Sentinel's unrelated global
kill switch and its tests match). Nothing was engaged, toggled, or changed by
this task. The lane is armed by construction: the drainer tails the instant
outbox on a short cadence with cross-lane dedupe (`FRIDAY/src/friday/proactive/intelx_watch.py`,
`run_instant_cycle`).

## Wait state

- No real fast-lane alert occurred naturally during this observation.
- The lane stays armed: producer polling on Server 2, drainer baselined on
  Server 1 with `instant_offset: 0`, ready to deliver the first instant-class
  envelope when one fires.
- TASK-INT-036 (Muse 1) continues the live watch with a 48h window
  (~06:03 IST Nov 24 → ~06:03 IST Nov 26, kill switch OFF). If an
  instant-class alert fires in that window it will be observed there; this
  task's evidence stands as the armed-state baseline.

## Observations (not blockers for this task)

- **Server 1 `IntelX.service` is masked/failed** since Fri 2026-11-20 23:56:31
  IST (timeout; PID 1066051 killed). The fast-lane producer lives on Server 2
  (envelope fired Nov 23), so the lane is unaffected, but the dead S1 unit is
  recorded here for the fleet.
- **Newest digest envelope not yet in the drainer log:** the RBI envelope
  (fired Nov 23 22:03 IST, digest-class) is in the S2 outbox but the S1
  drainer `alert_log` still ends Nov 20 19:16 IST as of this read. Digest
  delivery lags; the instant lane is unaffected (nothing to deliver).
- **FRIDAY restarted 08:28 IST today** (clean stop/start, per Muse 1) — after
  the newest envelope fired, before this read.

## Acceptance

- [x] Armed-state evidence + wait state filed (no alert occurred naturally).
- [ ] One real fast-lane alert observed end-to-end — not applicable; none fired.
- [x] Kill switch stayed OFF throughout (no kill switch exists on this path;
      nothing toggled).

Board flip requested: CLAIMED → IN_REVIEW (work PR open, awaiting merge).
The flip rides in the next consolidated board PR if the coordinator prefers;
this PR carries the evidence doc only.
