# TASK-INT-057 — IntelX fast-lane live proof run 6: armed-state + wait state

**Task:** TASK-INT-057 — IntelX: fast-lane live proof run 6 — one real alert end-to-end (follow-up to INT-055 run 5).
**Worker:** Muse 7. **Claim:** successor hub issue #2045 comment 7207717476 (2026-11-27 ~07:28 IST); branch `muse7/task-int-057-fast-lane-live-proof` at `f26a514a`.
**Acceptance:** one real alert end-to-end against the live IntelX fast lane, OR the armed-state evidence and wait state. Kill switch stays OFF.
**Verification:** 2026-11-27 ~07:31–07:33 IST, read-only bridge probes on the live hosts under standing clearance 7200564540. No config changed, no restart, no server move, kill switch untouched.

## Verdict

**Wait state — no instant-class alert exists to trace, and the producer→consumer handoff gap from run 2 still stands.** Both ends of the lane are up again (run 5's G3/G4 are resolved by the fleet moves: the producer runs on IntelX-Server, the consumer on FRIDAY-Server), the producer is polling live, and the consumer drainer is armed and baselined on both lanes. But the live producer has never emitted an instant-class envelope — its highest score ever is 5 against an instant bar of 6 — and the consumer's watch files are still frozen at 2026-11-20, so the three digest envelopes the producer fired on 2026-11-23/24 never reached the consumer. Until the handoff is fixed (run 2's G2, coordinator decision), no future instant alert can be delivered end-to-end either.

## Producer state (IntelX-Server, probed 2026-11-27 07:31 IST)

- `IntelX.service` loaded active running; uvicorn PID 35285 (`intelx.app.main:app`, :8005). `/healthz` 200.
- Polls live every 30 min: 00:04, 00:34, 01:04, 01:34 UTC (05:34–07:04 IST), every poll `alerted=0` on both watches. `state.json` mtime 2026-11-27 01:34 UTC.
- Watch state: `ai_model_releases` 2,374 seen (2,329 baseline, 42 below_threshold, 2 alerted, 1 suppressed_budget); `india_tech_regulatory` 760 seen (717 below_threshold, 41 excluded, 2 alerted). Four alerts ever, all digest-class.
- Outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl`: 4 envelopes, max score 5 — harness adapters (score 4, fired 2026-11-20 18:26 UTC), RBI "Stop Switch" (score 5, 2026-11-23 16:33 UTC), SEBI IPO GMP (score 3, 2026-11-24 14:30 UTC), GPT-6 protein design (score 4, 2026-11-24 21:30 UTC). Instant bar is 6 for both watches (`IntelX/docs/STANDING_WATCHES.md` §7); every envelope is below it.
- No `instant_outbox.jsonl` on the producer: no instant-class envelope has ever been produced.

## Consumer state (FRIDAY-Server, probed 2026-11-27 07:32 IST)

- `FRIDAY.service` loaded active running.
- Kill switch OFF (watch enabled): `FRIDAY_PROACTIVE_INTELX_WATCH=on` at `/opt/friday_universe/FRIDAY/.env:77` — watch on = kill switch off, the same state run 5 verified. No `INTELX_WATCH_OUTBOX_PATH` override; the drainer reads the default sibling paths.
- Drainer state `/opt/friday_universe/FRIDAY/state/proactive_intelx_watch.json` (mtime 2026-11-27 02:02 UTC, live): `baseline_done: true`, `instant_baseline_done: true`, `offset: 3644` (whole local outbox consumed), `instant_offset: 0`, `held: []`, `malformed_total: 0`, `delivered_keys`: the same 4 digest envelopes as run 2. Alert log last entry 2026-11-20 19:16 IST (`intelx_watch_alert`, delivery `posted`).
- No `instant_outbox.jsonl` on the consumer either. The instant lane has never had a file to drain.

## The wait state and the standing gap

- Consumer watch files frozen since 2026-11-20: outbox mtime 2026-11-20 13:46 UTC (4 lines, 3,644 bytes), `state.json` mtime 2026-11-20 18:24 UTC — unchanged since run 2.
- The producer's three post-Nov-20 envelopes (RBI `f0b33be8`, SEBI `9eb41849`, GPT-6 `ac2f786b`) are absent from the consumer outbox and from `delivered_keys`: fired on the producer, never delivered. The producer→consumer handoff gap (run 2's blocker, run 5's G2) is unchanged by the fleet moves — the drainer reads FRIDAY-Server-local files, and nothing syncs the IntelX-Server outbox to it.
- What this run does NOT do: build a sync, restart anything, or touch the kill switch. The handoff fix is a coordinator decision. The next run can only produce an end-to-end proof once (a) the handoff carries producer envelopes to the consumer and (b) an item scores at or above the instant bar of 6.

## States

- Implemented: N/A (verification task; no code change — the gap is operational)
- Tested: YES (armed state + wait state verified first-hand on both live hosts, 2026-11-27 ~07:31 IST)
- Merged: NO (this PR, awaiting Muse)
- Deployed: N/A
- Production-verified: NO — no real instant alert has ever fired, and the handoff gap blocks any future one until fixed

## Files

- This evidence doc: `docs/collaboration/TASK-INT-057-EVIDENCE.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-057 flips ride in the coordinator board PR, per ruling 7200564540 §3)
