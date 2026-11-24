# TASK-INT-038 — IntelX fast-lane live proof run 2

**Task:** TASK-INT-038 — IntelX: fast-lane live proof run 2 — one real alert end-to-end after INT-019.
**Worker:** Muse 7. **Claim:** issue #1483 comment 7118464054, 2026-11-24 ~06:20 IST, on coordinator ruling in watch 7118198302 (~06:10 IST): CLAIM TASK-INT-038 NOW under the blocked-head rule (INT-020 stays blocked head).
**Claim PR:** #1601 merged by the owner (surendra2304) 2026-11-24 08:27:19 IST (merge b46c2648; parents afef47ba + 1442b967). The merge applied only the INT-038 board hunk (+4/-3, board file only) — verified first-hand on main 06a7f5e3: SEN-024 / STR-045 / WF-003 all still MERGED, their evidence docs present. The coordinator's stale-board hold (watches 7120211317, 7120398989) was overtaken by the owner merge; the three-way merge did not revert anything. My rebuild commit d911692f (INT-038 flip rebuilt on main afef47ba, board blob d6c505c6) was orphaned by that merge — disclosed, no content lost.
**Branch:** `muse7/task-int-038-fast-lane-proof-run-2`, base main `06a7f5e3` (this work PR).
**Verification:** 2026-11-24 ~06:22–06:29 IST (recon) and re-probed ~08:34 IST, all probes read-only; no config changed, no restart, no merge by me.

## Verdict (this run)

**Wait state, not a proof — and the wait is not just "no big news yet".** No instant-class alert has ever been produced, so there is nothing to trace end-to-end. The fast lane is armed at the consumer, the producer is polling live on S2, but the producer-to-consumer handoff on S1 is stale: S1's watch files stopped updating 2026-11-20, so even if S2 fires an instant alert now, the S1 drainer cannot see it. That gap is filed below as the INT-038 blocker; it needs coordinator direction (it overlaps INT-019's S2 move, owner muse_16). Re-probe 08:34 IST confirms the wait state is unchanged since the 06:29 IST recon.

## Armed-state evidence (consumer, Server 1)

- FRIDAY running: `FRIDAY.service` loaded active running; API process PID 3424508 at 08:34 IST (was PID 3348707 since 05:46 IST at the 06:29 recon — FRIDAY restarted in between; the restart did not change the armed state or the 401 gate below).
- Kill switch ON: `FRIDAY_PROACTIVE_INTELX_WATCH=on` in `/opt/friday_universe/FRIDAY/.env:77`. No `INTELX_WATCH_OUTBOX_PATH` override — the drainer reads the default sibling paths on S1.
- Drainer state `/opt/friday_universe/FRIDAY/state/proactive_intelx_watch.json` (re-read 08:34 IST): `baseline_done: true`, `instant_baseline_done: true`, `offset: 3644` (whole S1 outbox consumed), `instant_offset: 0`, `held: []`, `malformed_total: 0`. `delivered_keys`: the 4 digest envelopes, each exactly once. Last alert-log entry 2026-11-20 19:16 IST.
- No `instant_outbox.jsonl` on S1. The instant lane has never had a file to drain.

## Producer state (Server 2)

- IntelX running: `IntelX.service` loaded active running; uvicorn PID 622490 (`intelx.app.main:app`, :8005) since 01:05 IST. `/healthz` 200 at 08:34 IST. `/health` returns `degraded` (capabilities unknown, NO_LIVE_PROBE — the known degraded-by-design report).
- Polls live in-process every 30 min: 03:37, 04:07, 04:37, 05:07, 05:37, 06:07 IST, and `state.json` mtime 2026-11-24 08:08 IST at the re-probe (polls continuing). All `alerted=0` on both watches at the 06:29 recon.
- Watch state (S2, 06:29 recon): `ai_model_releases` 2,361 seen (2,329 baseline, 30 below_threshold, 1 alerted, 1 suppressed_budget); `india_tech_regulatory` 389 seen (364 below_threshold, 24 excluded, 1 alerted). Exactly 2 alerted ever — both digest-class, both in S2's outbox.
- S2 outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl` (re-read 08:34 IST): 2 lines, last modified 2026-11-23 22:03 IST — (1) harness adapters, score 4, fired 2026-11-20 18:26 UTC; (2) RBI "Stop Switch" payments-fraud proposal, score 5, fired 2026-11-23 16:33 UTC. Both below the instant bar (6). No `instant_outbox.jsonl` on S2 — no instant-class envelope has ever been produced.

## The blocker: S1 watch files stale since 2026-11-20

- S1 outbox `/opt/friday_universe/IntelX/data/watches/outbox.jsonl` (re-read 08:34 IST): 4 lines, 3,644 bytes, last modified **2026-11-20 19:16 IST** — unchanged for ~4 days. S1 `state.json` mtime **2026-11-20 23:54 IST**.
- S1 and S2 poll independently with separate seen-stores (S1 counts differ: ai_model_releases 2,311 baseline / 40 below / 3 alerted; india_tech_regulatory 532 below / 48 excluded / 1 alerted). S1's poller has not run since Nov 20: no IntelX process on S1, no IntelX timers, no watch cron on S1, no S2→S1 sync found.
- Consequence, verified live: the RBI digest envelope fired on S2 on 2026-11-23 22:03 IST never reached S1 — it is absent from the S1 outbox and from the drainer's `delivered_keys` / `alert_log`. A digest alert fired and was never delivered. The same break applies to any future instant alert: the S1 drainer reads S1-local files only.
- What this task does NOT do: restart S1 polling, build a sync, or touch the kill switch — that is a coordinator decision (INT-019, owner muse_16, covers the S2 move; the delivery handoff is its open edge). INT-019 is MERGED (board PR #1613, main 518bad42) but its S2 legs are still blocked (bridge approval 7113152293 + timer-install clearance owed) — the handoff gap stands. No config changed this run.

## Run 1 / run 2 note

Muse 1 claimed TASK-INT-036 (fast-lane live proof, run 1) at ~06:03 IST today (claim PR #1595). Cross-lane dedupe is shared (`delivered_keys` in the one drainer state file), so a single instant alert can only ever be delivered once whichever run traces it. This run files the armed-state + wait-state evidence; if a qualifying instant event fires, the run that traces it end-to-end owns the proof.

## INT-020 blocked head, re-verified this run

- **Gate 1 — FRIDAY web-chat 401, UNCHANGED.** `POST https://friday-universe.duckdns.org/friday/api/chat` → HTTP 401 at 08:34:48 IST, body byte-identical (`{"error":"HTTP_401","message":"A valid FRIDAY control API key is required.",...}`), after the FRIDAY restart (PID 3424508). Agrees with Muse 8's VAL-009 re-probe (PR #1569, merged into main afef47ba 08:27 IST): dispatch STILL 401 after FRD-038 merged. Owned by Muse 11 (FRD-038); deploy is Muse 5's TASK-FRD-042 leg (claimed ~08:20 IST, hub 7120488172) — not yet effective on the live path.
- **Gate 2 — IntelX synthesis, cleared** per Muse 9's INF-028 verified re-probe (corroborated first-hand in earlier runs; not re-probed this run).

## States

- Implemented: N/A (verification task; no code change — the gap is operational, not a code defect)
- Tested: YES (armed state + wait state verified first-hand on both servers, recon 06:29 IST + re-probe 08:34 IST)
- Merged: claim YES (PR #1601, merge b46c2648); work PR this PR, awaiting Muse
- Deployed: N/A
- Production-verified: NO — no real instant alert has ever fired, and the S1 handoff gap blocks any future one until fixed

## Files

- This evidence doc: `docs/collaboration/TASK-INT-038-FAST-LANE-PROOF-RUN-2.md`
- Board record: `docs/collaboration/WORK_BOARD.yaml` (TASK-INT-038 AVAILABLE → CLAIMED in PR #1601; CLAIMED → IN_REVIEW in this PR)
- Probe outputs (working state): `~/workspace/goals/muse-7-onboarding-for-friday-universe/hidden_files/int038_*.txt`
